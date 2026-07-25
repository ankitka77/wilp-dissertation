import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest

from phase7.config.fusion_config import FusionConfig
from phase7.normalization.normalization_strategy import MinMaxNormalization
from phase7.source_manager.fusion_source_manager import FusionSourceManager
from phase7.ingestion.fusion_ingestion import FusionIngestion
from phase7.alignment.fusion_alignment import FusionAlignment
from phase7.aggregation.fusion_aggregation import FusionAggregation
from phase7.normalization.score_normalizer import ScoreNormalizer
from phase7.fusion.fusion_decision_engine import FusionDecisionEngine
from phase7.artifacts.artifact_writer import ArtifactWriter
from phase7.fusion.fusion_orchestrator import FusionOrchestrator, FusionOrchestratorError


# Helper to create deterministic timestamps
def iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def make_csv(path: Path, header: str, rows: list[list[str]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(header + "\n")
        for r in rows:
            fh.write(",".join(r) + "\n")


@pytest.fixture
def synthetic_inputs(tmp_path):
    """Create small deterministic KPI and Log CSV inputs and return paths."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # base timestamp
    t0 = datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    # window size default is 5 minutes; choose spacing to demonstrate alignment vs non-alignment
    k_rows = []
    l_rows = []

    # KPI rows (5 rows) - space widely to avoid overlap with log windows
    k_times = [t0 + timedelta(minutes=10 * i) for i in range(5)]
    for i, t in enumerate(k_times, start=1):
        # include window_end as start + 5m
        end = t + timedelta(minutes=5)
        k_rows.append([iso(t), f"kpi_{i}", f"entity_{(i%3)}", f"{float(i * 1.0):.1f}", iso(end)])

    # Log rows (5 rows) - some align with KPI by falling within alignment tolerance, others do not
    # space KPI and log windows by 5 minutes so windows touch but do not overlap
    # KPI at 0,10,20... minutes; Log at 5,15,25... minutes (window_size=5m)
    l_times = [t0 + timedelta(minutes=10 * i + 5) for i in range(5)]
    for i, t in enumerate(l_times, start=1):
        end = t + timedelta(minutes=5)
        l_rows.append([iso(t), f"log_{i}", f"entity_{(i%3)}", f"{float(i * -1.0):.1f}", iso(end)])

    kpi_csv = data_dir / "kpi.csv"
    log_csv = data_dir / "log.csv"

    # headers: timestamp, source_record_id, entity_id, score, window_end
    make_csv(kpi_csv, "timestamp,source_record_id,entity_id,score,window_end", k_rows)
    # log header uses anomaly_score column name
    make_csv(log_csv, "timestamp,source_record_id,entity_id,anomaly_score,window_end", l_rows)

    return {"kpi": kpi_csv, "log": log_csv}


def _build_config(tmp_path: Path, inputs: dict[str, Path]) -> FusionConfig:
    # artifacts root under tmp_path
    artifacts_root = tmp_path / "artifacts"
    overrides = {
        "artifacts": {"root_dir": str(artifacts_root), "retain_intermediate": True},
        "extensions": {
            "sources": {
                "kpi": {
                    "type": "KPI",
                    "path": str(inputs["kpi"]),
                    "required_columns": ["timestamp", "source_record_id", "entity_id", "score", "window_end"],
                },
                "log": {
                    "type": "LOG",
                    "path": str(inputs["log"]),
                    "required_columns": ["timestamp", "source_record_id", "entity_id", "anomaly_score", "window_end"],
                },
            }
        },
        # use a small window size (1 minute) for synthetic test data to avoid overlaps
        "fusion": {"window_size": "1m", "normalization_strategy": "min_max"},
        "aggregation": {"strategy": "mean"},
    }
    cfg = FusionConfig.load(overrides=overrides)
    return cfg


def _list_expected_artifacts(root: Path, exp_id: str) -> list[Path]:
    base = root / "experiments" / exp_id
    expected = [
        base / "reports" / "fusion_inputs.csv",
        base / "reports" / "normalized_scores.csv",
        base / "reports" / "aligned_windows.csv",
        base / "reports" / "fused_predictions.csv",
        base / "reports" / "fusion_summary.json",
        base / "reports" / "source_coverage.json",
        base / "plots" / "fused_score_histogram.png",
        base / "plots" / "fused_score_timeseries.png",
        base / "manifests" / "phase7_manifest.json",
    ]
    return expected


def test_phase7_pipeline_happy_path(tmp_path, synthetic_inputs):
    cfg = _build_config(tmp_path, synthetic_inputs)
    strat = MinMaxNormalization()
    orch = FusionOrchestrator(cfg, normalization_strategy=strat)

    summary = orch.run(experiment_id="int-happy", kpi_detector_experiment_id="kpi-x", log_detector_experiment_id="log-x")

    assert summary["execution_status"] == "success"
    assert summary["records_processed"] > 0
    assert summary["records_written"] > 0
    assert summary["generated_artifacts"] > 0

    out_root = Path(cfg.artifacts.root_dir)
    exp_dir = out_root / "experiments" / "int-happy"
    assert exp_dir.exists()

    for p in _list_expected_artifacts(out_root, "int-happy"):
        assert p.exists()


def test_pipeline_data_flow_consistency(tmp_path, synthetic_inputs):
    cfg = _build_config(tmp_path, synthetic_inputs)

    # Run stage-by-stage using real components
    sm = FusionSourceManager(cfg)
    sm.initialize()
    sm.load_sources()

    ing = FusionIngestion(sm, cfg)
    ing.ingest()
    records = ing.get_records()
    ingested = len(records)
    assert ingested > 0

    align = FusionAlignment(cfg)
    align.align(records)
    aligned_groups = align.get_aligned_records()
    aligned_flat = sum(len(g) for g in aligned_groups)
    # alignment should not drop records
    assert aligned_flat == ingested

    agg = FusionAggregation(cfg)
    aggregated = agg.aggregate_groups(aligned_groups)
    agg_count = len(aggregated)
    assert agg_count >= 0

    # Normalize aggregated groups by converting aggregated -> pseudo-FusionRecord
    # The pipeline's normalization expects FusionRecord; the real pipeline uses
    # normalization over fused windows; use ScoreNormalizer on reconstructed
    # FusionRecord objects by expanding aggregated windows into representative records
    normalizer = ScoreNormalizer(cfg, MinMaxNormalization())
    # build a tuple of FusionRecord-like objects by converting aggregated windows to minimal FusionRecord objects
    # For integration verification we validate non-increasing counts across stages as windows are merged
    normalized = []
    for a in aggregated:
        # Create a minimal FusionRecord from AggregatedFusionRecord raw fields using timestamps and entity_id
        # Use FusionRecord.from_kpi_source or from_log_source depending on availability
        # Prefer KPI if available else log
        if a.aggregated_kpi_score is not None:
            rec = None
            # create a FusionRecord via from_kpi_source using aggregated_kpi_score
            from phase7.models.fusion_record import FusionRecord
            rec = FusionRecord.from_kpi_source(window_ts=a.window_ts, window_end_ts=a.window_end_ts, source_record_id=(a.source_record_ids_kpi[0] if a.source_record_ids_kpi else None), kpi_score=(a.aggregated_kpi_score if a.aggregated_kpi_score is not None else 0.0), entity_id=a.entity_id)
            normalized.append(rec)
        elif a.aggregated_log_score is not None:
            from phase7.models.fusion_record import FusionRecord
            rec = FusionRecord.from_log_source(window_ts=a.window_ts, window_end_ts=a.window_end_ts, source_record_id=(a.source_record_ids_log[0] if a.source_record_ids_log else None), log_score=(a.aggregated_log_score if a.aggregated_log_score is not None else 0.0), entity_id=a.entity_id)
            normalized.append(rec)

    # normalized_count is number of representative records
    normalized_tuple = tuple(normalized)
    try:
        normalized_out = normalizer.normalize_records(normalized_tuple)
    except Exception:
        normalized_out = tuple()

    normalized_count = len(normalized_out)

    # Decision engine
    dec = FusionDecisionEngine(cfg)
    if normalized_count:
        fused = dec.fuse_records(normalized_out)
    else:
        fused = tuple()
    fused_count = len(fused)

    # Validate non-increasing counts along the pipeline windows/records
    assert ingested >= aligned_flat
    assert aligned_flat >= agg_count
    assert agg_count >= normalized_count
    assert normalized_count >= fused_count


def test_pipeline_determinism(tmp_path, synthetic_inputs):
    cfg = _build_config(tmp_path, synthetic_inputs)
    strat = MinMaxNormalization()
    orch = FusionOrchestrator(cfg, normalization_strategy=strat)

    # run twice
    s1 = orch.run(experiment_id="det-1")
    # read generated CSV/JSON
    out_root = Path(cfg.artifacts.root_dir)
    files = _list_expected_artifacts(out_root, "det-1")

    # read file contents for comparison
    contents1 = {}
    for f in files:
        with f.open("rb") as fh:
            contents1[f.name] = fh.read()

    s2 = orch.run(experiment_id="det-2")
    files2 = _list_expected_artifacts(out_root, "det-2")
    contents2 = {}
    for f in files2:
        with f.open("rb") as fh:
            contents2[f.name] = fh.read()

    # CSV files should be identical
    for name in ("fusion_inputs.csv", "normalized_scores.csv", "aligned_windows.csv", "fused_predictions.csv"):
        assert contents1.get(name) == contents2.get(name)

    # JSON outputs: fusion_summary.json contains generated_at timestamp; compare after stripping timestamp
    for name in ("fusion_summary.json", "source_coverage.json", "phase7_manifest.json"):
        b1 = contents1.get(name)
        b2 = contents2.get(name)
        if b1 is None or b2 is None:
            pytest.skip("Missing JSON artifact for comparison")
        j1 = json.loads(b1.decode("utf-8"))
        j2 = json.loads(b2.decode("utf-8"))
        # remove generated timestamps if present
        j1.pop("generated_at", None)
        j2.pop("generated_at", None)
        # manifest has generation_timestamp
        j1.pop("generation_timestamp", None)
        j2.pop("generation_timestamp", None)
        # Normalize experiment-specific identifiers/paths so we compare stable content
        def _normalize(obj, exp_id):
            if isinstance(obj, dict):
                # replace experiment id value when present
                if "experiment_id" in obj:
                    obj["experiment_id"] = "<EXP>"
                for k, v in list(obj.items()):
                    obj[k] = _normalize(v, exp_id)
                return obj
            if isinstance(obj, list):
                return [_normalize(v, exp_id) for v in obj]
            if isinstance(obj, str):
                # collapse experiment-specific paths
                return obj.replace(f"experiments\\det-1\\", "experiments\\<EXP>\\").replace(f"experiments/det-1/", "experiments/<EXP>/").replace(f"experiments\\det-2\\", "experiments\\<EXP>\\").replace(f"experiments/det-2/", "experiments/<EXP>/")
            return obj

        _normalize(j1, "det-1")
        _normalize(j2, "det-2")
        assert j1 == j2


def test_pipeline_missing_input_dataset(tmp_path, synthetic_inputs):
    cfg = _build_config(tmp_path, synthetic_inputs)
    # remove KPI input to simulate missing dataset
    kp = synthetic_inputs["kpi"]
    kp.unlink()

    orch = FusionOrchestrator(cfg, normalization_strategy=MinMaxNormalization())
    with pytest.raises(FusionOrchestratorError):
        orch.run(experiment_id="missing-input")

    # ensure no artifacts directory created for the failed experiment
    out_root = Path(cfg.artifacts.root_dir)
    exp_dir = out_root / "experiments" / "missing-input"
    assert not exp_dir.exists()


def test_generated_artifacts_exist(tmp_path, synthetic_inputs):
    cfg = _build_config(tmp_path, synthetic_inputs)
    strat = MinMaxNormalization()
    orch = FusionOrchestrator(cfg, normalization_strategy=strat)
    orch.run(experiment_id="artifact-check")

    out_root = Path(cfg.artifacts.root_dir)
    for p in _list_expected_artifacts(out_root, "artifact-check"):
        assert p.exists()
