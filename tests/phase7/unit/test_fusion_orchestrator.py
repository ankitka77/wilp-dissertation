import logging
from types import MappingProxyType
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from phase7.config.fusion_config import FusionConfig
from phase7.fusion.fusion_orchestrator import FusionOrchestrator, FusionOrchestratorError
from phase7.aggregation.fusion_aggregation import AggregatedFusionRecord
from phase7.models.fusion_record import FusionRecord


@pytest.fixture
def config() -> FusionConfig:
    return FusionConfig()


@pytest.fixture
def sample_records():
    return (object(), object(), object())


@pytest.fixture
def sample_aligned():
    return ((object(),), (object(),))


@pytest.fixture
def sample_aggregated():
    # minimal valid AggregatedFusionRecord preserving required fields
    w_start = datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc)
    w_end = datetime(2020, 1, 1, 0, 1, tzinfo=timezone.utc)
    afr = AggregatedFusionRecord(
        window_ts=w_start,
        window_end_ts=w_end,
        entity_id="entity-1",
        aggregated_kpi_score=0.75,
        aggregated_log_score=0.25,
        source_record_ids_kpi=("k1",),
        source_record_ids_log=("l1",),
        raw_kpi_scores=(0.7, 0.8),
        raw_log_scores=(0.2,),
        source_metadata={"example": {"meta": 1}},
        group_size=3,
    )
    return (afr,)


@pytest.fixture
def sample_normalized():
    return (object(),)


@pytest.fixture
def sample_fused():
    return (object(),)


@pytest.fixture
def sample_aw_stats(tmp_path):
    return {
        "records_written": 3,
        "generated_files": ["a", "b"],
        "output_directory": str(tmp_path / "out"),
    }


def _patch_components(monkeypatch, *, records, aligned, aggregated, normalized, fused, aw_stats, normalization_strategy, call_recorder=None):
    mod = "phase7.fusion.fusion_orchestrator"

    mock_src = MagicMock(name="FusionSourceManagerInstance")
    def _src_init():
        if call_recorder is not None:
            call_recorder.append("initialize")
    mock_src.initialize.side_effect = _src_init
    def _src_load():
        if call_recorder is not None:
            call_recorder.append("load_sources")
    mock_src.load_sources.side_effect = _src_load
    mock_src.list_sources.return_value = ["s1"]
    monkeypatch.setattr(mod + ".FusionSourceManager", lambda cfg: mock_src)

    mock_ing = MagicMock(name="FusionIngestionInstance")
    def _ingest():
        if call_recorder is not None:
            call_recorder.append("ingest")
    mock_ing.ingest.side_effect = _ingest
    mock_ing.get_records.return_value = tuple(records)
    monkeypatch.setattr(mod + ".FusionIngestion", lambda sm, cfg: mock_ing)

    mock_align = MagicMock(name="FusionAlignmentInstance")
    def _align(v):
        if call_recorder is not None:
            call_recorder.append("align")
    mock_align.align.side_effect = _align
    mock_align.get_aligned_records.return_value = tuple(aligned)
    monkeypatch.setattr(mod + ".FusionAlignment", lambda cfg: mock_align)

    mock_agg = MagicMock(name="FusionAggregationInstance")
    def _aggregate(v):
        if call_recorder is not None:
            call_recorder.append("aggregate_groups")
        return tuple(aggregated)
    mock_agg.aggregate_groups.side_effect = _aggregate
    monkeypatch.setattr(mod + ".FusionAggregation", lambda cfg: mock_agg)

    mock_norm = MagicMock(name="ScoreNormalizerInstance")
    def _normalize(v):
        if call_recorder is not None:
            call_recorder.append("normalize_records")
        return tuple(normalized)
    mock_norm.normalize_records.side_effect = _normalize
    mock_norm.export_diagnostics.return_value = {"strategy": "mocked"}

    def _sn_factory(cfg, strat):
        assert strat is normalization_strategy
        return mock_norm

    monkeypatch.setattr(mod + ".ScoreNormalizer", _sn_factory)

    mock_dec = MagicMock(name="FusionDecisionEngineInstance")
    def _fuse(v):
        if call_recorder is not None:
            call_recorder.append("fuse_records")
        return tuple(fused)
    mock_dec.fuse_records.side_effect = _fuse
    mock_dec.export_statistics.return_value = {"fusion_strategy": "mocked", "records_processed": len(fused)}
    monkeypatch.setattr(mod + ".FusionDecisionEngine", lambda cfg: mock_dec)

    mock_aw = MagicMock(name="ArtifactWriterInstance")
    def _write(*a, **kw):
        if call_recorder is not None:
            call_recorder.append("write")
    mock_aw.write.side_effect = _write
    mock_aw.export_statistics.return_value = dict(aw_stats or {})
    monkeypatch.setattr(mod + ".ArtifactWriter", lambda cfg: mock_aw)

    return {
        "src": mock_src,
        "ing": mock_ing,
        "align": mock_align,
        "agg": mock_agg,
        "norm": mock_norm,
        "dec": mock_dec,
        "aw": mock_aw,
    }


def test_constructor_valid_and_invalid(config):
    orchestrator = FusionOrchestrator(config, normalization_strategy=object())
    assert isinstance(orchestrator, FusionOrchestrator)

    with pytest.raises(FusionOrchestratorError):
        FusionOrchestrator(None)  # type: ignore[arg-type]

    with pytest.raises(FusionOrchestratorError):
        FusionOrchestrator("bad-config")  # type: ignore[arg-type]


def test_constructor_logger_and_strategy_injection(config):
    custom_logger = logging.getLogger("test.orch")
    strat = object()
    orch = FusionOrchestrator(config, normalization_strategy=strat, logger_=custom_logger)
    s = orch.export_statistics()
    assert s["pipeline_runs"] == 0
    assert s["successful_runs"] == 0
    assert s["failed_runs"] == 0


def test_exact_stage_order_and_argument_passing(monkeypatch, config, sample_records, sample_aligned, sample_aggregated, sample_normalized, sample_fused, sample_aw_stats):
    order = []
    strat = object()
    mocks = _patch_components(
        monkeypatch,
        records=sample_records,
        aligned=sample_aligned,
        aggregated=sample_aggregated,
        normalized=sample_normalized,
        fused=sample_fused,
        aw_stats=sample_aw_stats,
        normalization_strategy=strat,
        call_recorder=order,
    )

    orch = FusionOrchestrator(config, normalization_strategy=strat)
    summary = orch.run(experiment_id="order-test", kpi_detector_experiment_id="kpi-x", log_detector_experiment_id="log-x")

    assert order == [
        "initialize",
        "load_sources",
        "ingest",
        "align",
        "aggregate_groups",
        "normalize_records",
        "fuse_records",
        "write",
    ]

    mocks["ing"].get_records.assert_called_once_with()
    mocks["align"].align.assert_called_once_with(tuple(sample_records))
    mocks["agg"].aggregate_groups.assert_called_once_with(tuple(sample_aligned))
    # Normalizer should be called once and receive FusionRecord instances converted
    mocks["norm"].normalize_records.assert_called_once()
    called_args = mocks["norm"].normalize_records.call_args[0]
    assert len(called_args) == 1
    arg_tuple = called_args[0]
    assert isinstance(arg_tuple, tuple)
    # Verify conversion preserved key fields
    for fr, agg in zip(arg_tuple, sample_aggregated):
        assert isinstance(fr, FusionRecord)
        assert fr.window_ts == agg.window_ts
        assert fr.window_end_ts == agg.window_end_ts
        assert fr.entity_id == agg.entity_id
        assert fr.kpi_score == agg.aggregated_kpi_score
        assert fr.log_score == agg.aggregated_log_score
    mocks["dec"].fuse_records.assert_called_once_with(tuple(sample_normalized))
    mocks["aw"].write.assert_called_once()
    called_args, called_kwargs = mocks["aw"].write.call_args
    assert called_args[0] == tuple(sample_fused)
    assert called_args[1] == "order-test"
    assert called_kwargs.get("kpi_detector_id") == "kpi-x" or called_kwargs.get("kpi_detector_id") == "kpi-x"

    assert isinstance(summary, MappingProxyType)
    assert summary["experiment_id"] == "order-test"


def test_run_success_path_and_full_statistics(monkeypatch, config, sample_records, sample_aligned, sample_aggregated, sample_normalized, sample_fused, sample_aw_stats):
    strat = object()
    mocks = _patch_components(
        monkeypatch,
        records=sample_records,
        aligned=sample_aligned,
        aggregated=sample_aggregated,
        normalized=sample_normalized,
        fused=sample_fused,
        aw_stats=sample_aw_stats,
        normalization_strategy=strat,
    )

    orch = FusionOrchestrator(config, normalization_strategy=strat)
    summary = orch.run(experiment_id="full-stats", kpi_detector_experiment_id="kpi-a", log_detector_experiment_id="log-a")

    for key in ("experiment_id", "execution_status", "pipeline_start_time", "pipeline_end_time", "execution_duration_seconds", "records_processed", "records_written", "generated_artifacts", "output_directory", "summary_statistics"):
        assert key in summary

    stats = orch.export_statistics()
    assert stats["pipeline_runs"] == 1
    assert stats["successful_runs"] == 1
    assert stats["failed_runs"] == 0
    assert stats["last_experiment_id"] == "full-stats"
    assert isinstance(stats["last_execution_duration"], float)
    assert stats["records_processed"] == len(sample_records)
    assert stats["records_written"] == sample_aw_stats["records_written"]
    assert stats["generated_artifacts"] == len(sample_aw_stats["generated_files"])
    assert stats["output_directory"] == sample_aw_stats["output_directory"]

    with pytest.raises(TypeError):
        stats["pipeline_runs"] = 2  # type: ignore[misc]


def test_empty_aggregation_skips_normalization_and_decision(monkeypatch, config, sample_records, sample_aligned, sample_aggregated, sample_normalized, sample_aw_stats):
    strat = object()
    mocks = _patch_components(
        monkeypatch,
        records=sample_records,
        aligned=sample_aligned,
        aggregated=(),
        normalized=(),
        fused=(),
        aw_stats=sample_aw_stats,
        normalization_strategy=strat,
    )

    orch = FusionOrchestrator(config, normalization_strategy=strat)
    summary = orch.run(experiment_id="empty-agg")

    mocks["norm"].normalize_records.assert_not_called()
    mocks["dec"].fuse_records.assert_not_called()
    mocks["aw"].write.assert_called_once()


def test_exception_chaining_preserved(monkeypatch, config):
    def bad_ing_factory(sm, cfg):
        m = MagicMock()
        m.ingest.side_effect = ValueError("boom")
        m.get_records.return_value = ()
        return m

    monkeypatch.setattr("phase7.fusion.fusion_orchestrator.FusionIngestion", bad_ing_factory)
    monkeypatch.setattr("phase7.fusion.fusion_orchestrator.FusionSourceManager", lambda cfg: MagicMock(initialize=lambda: None, load_sources=lambda: None, list_sources=lambda: []))

    orch = FusionOrchestrator(config, normalization_strategy=object())
    with pytest.raises(FusionOrchestratorError) as ei:
        orch.run(experiment_id="chain")

    assert isinstance(ei.value.__cause__, ValueError)
    assert str(ei.value.__cause__) == "boom"


def test_logging_messages(monkeypatch, config, sample_records, sample_aligned, sample_aggregated, sample_normalized, sample_fused, sample_aw_stats, caplog):
    caplog.set_level(logging.INFO)
    strat = object()
    _patch_components(
        monkeypatch,
        records=sample_records,
        aligned=sample_aligned,
        aggregated=sample_aggregated,
        normalized=sample_normalized,
        fused=sample_fused,
        aw_stats=sample_aw_stats,
        normalization_strategy=strat,
    )

    orch = FusionOrchestrator(config, normalization_strategy=strat)
    orch.run(experiment_id="log-test")

    text = caplog.text
    assert "Pipeline run starting" in text
    assert "Stage: source_manager start" in text
    assert "Stage: ingestion start" in text
    assert "Stage: alignment start" in text
    assert "Stage: aggregation start" in text
    assert "Stage: normalization start" in text
    assert "Stage: decision_engine start" in text
    assert "Stage: artifact_generation start" in text
    assert "Pipeline run starting" in text


def test_clear_idempotent(monkeypatch, config, sample_records, sample_aligned, sample_aggregated, sample_normalized, sample_fused, sample_aw_stats):
    strat = object()
    _patch_components(
        monkeypatch,
        records=sample_records,
        aligned=sample_aligned,
        aggregated=sample_aggregated,
        normalized=sample_normalized,
        fused=sample_fused,
        aw_stats=sample_aw_stats,
        normalization_strategy=strat,
    )

    orch = FusionOrchestrator(config, normalization_strategy=strat)
    orch.run(experiment_id="clear-1")
    orch.clear()
    s = orch.export_statistics()
    assert s["pipeline_runs"] == 0
    assert s["successful_runs"] == 0
    assert s["failed_runs"] == 0
    assert s["last_execution_duration"] is None
    assert s["last_experiment_id"] is None
    assert s["records_processed"] == 0
    assert s["records_written"] == 0
    assert s["generated_artifacts"] == 0
    assert s["output_directory"] is None
    # idempotent
    orch.clear()
    s2 = orch.export_statistics()
    assert s2 == s


def test_repeated_runs_deterministic_except_time(monkeypatch, config, sample_records, sample_aligned, sample_aggregated, sample_normalized, sample_fused, sample_aw_stats):
    strat = object()
    _patch_components(
        monkeypatch,
        records=sample_records,
        aligned=sample_aligned,
        aggregated=sample_aggregated,
        normalized=sample_normalized,
        fused=sample_fused,
        aw_stats=sample_aw_stats,
        normalization_strategy=strat,
    )

    orch = FusionOrchestrator(config, normalization_strategy=strat)
    s1 = orch.run(experiment_id="repeat")
    s2 = orch.run(experiment_id="repeat")

    # keys that are allowed to differ
    allowed_diff = {"pipeline_start_time", "pipeline_end_time", "execution_duration_seconds"}
    assert set(s1.keys()) == set(s2.keys())
    for k in s1.keys():
        if k in allowed_diff:
            continue
        assert s1[k] == s2[k]


def test_summary_mappingproxy_immutable(monkeypatch, config, sample_records, sample_aligned, sample_aggregated, sample_normalized, sample_fused, sample_aw_stats):
    strat = object()
    _patch_components(
        monkeypatch,
        records=sample_records,
        aligned=sample_aligned,
        aggregated=sample_aggregated,
        normalized=sample_normalized,
        fused=sample_fused,
        aw_stats=sample_aw_stats,
        normalization_strategy=strat,
    )

    orch = FusionOrchestrator(config, normalization_strategy=strat)
    summary = orch.run(experiment_id="immut")
    with pytest.raises(TypeError):
        summary["records_processed"] = 0  # type: ignore[misc]


def test_missing_normalization_strategy(monkeypatch, config, sample_records, sample_aligned, sample_aggregated, sample_normalized, sample_fused, sample_aw_stats):
    # Patch downstream so pipeline reaches normalization check
    _patch_components(
        monkeypatch,
        records=sample_records,
        aligned=sample_aligned,
        aggregated=sample_aggregated,
        normalized=sample_normalized,
        fused=sample_fused,
        aw_stats=sample_aw_stats,
        normalization_strategy=object(),
    )

    orch = FusionOrchestrator(config)  # no normalization_strategy
    with pytest.raises(FusionOrchestratorError) as ei:
        orch.run(experiment_id="no-norm")
    # underlying cause should indicate missing normalization strategy
    assert isinstance(ei.value.__cause__, FusionOrchestratorError)
    assert "Normalization strategy not provided" in str(ei.value.__cause__)
    stats = orch.export_statistics()
    assert stats["pipeline_runs"] == 1
    assert stats["failed_runs"] == 1


@pytest.mark.parametrize("stage", ["alignment", "aggregation", "normalization", "decision", "artifact"])
def test_parameterized_stage_failures(monkeypatch, config, sample_records, sample_aligned, sample_aggregated, sample_normalized, sample_fused, sample_aw_stats, stage):
    strat = object()
    mocks = _patch_components(
        monkeypatch,
        records=sample_records,
        aligned=sample_aligned,
        aggregated=sample_aggregated,
        normalized=sample_normalized,
        fused=sample_fused,
        aw_stats=sample_aw_stats,
        normalization_strategy=strat,
    )

    exc = RuntimeError(f"{stage}-fail")
    if stage == "alignment":
        mocks["align"].align.side_effect = exc
    elif stage == "aggregation":
        mocks["agg"].aggregate_groups.side_effect = exc
    elif stage == "normalization":
        mocks["norm"].normalize_records.side_effect = exc
    elif stage == "decision":
        mocks["dec"].fuse_records.side_effect = exc
    elif stage == "artifact":
        mocks["aw"].write.side_effect = exc

    orch = FusionOrchestrator(config, normalization_strategy=strat)
    with pytest.raises(FusionOrchestratorError) as ei:
        orch.run(experiment_id=f"fail-{stage}")
    assert isinstance(ei.value.__cause__, RuntimeError)
    stats = orch.export_statistics()
    assert stats["pipeline_runs"] == 1
    assert stats["failed_runs"] == 1


def test_export_statistics_immutable(monkeypatch, config, sample_records, sample_aligned, sample_aggregated, sample_normalized, sample_fused, sample_aw_stats):
    strat = object()
    _patch_components(
        monkeypatch,
        records=sample_records,
        aligned=sample_aligned,
        aggregated=sample_aggregated,
        normalized=sample_normalized,
        fused=sample_fused,
        aw_stats=sample_aw_stats,
        normalization_strategy=strat,
    )

    orch = FusionOrchestrator(config, normalization_strategy=strat)
    orch.run(experiment_id="stats-immut")
    stats = orch.export_statistics()
    assert isinstance(stats, MappingProxyType)
    with pytest.raises(TypeError):
        stats["pipeline_runs"] = 0  # type: ignore[misc]


def test_summary_exact_keys_and_artifact_write_args(monkeypatch, config, sample_records, sample_aligned, sample_aggregated, sample_normalized, sample_fused, sample_aw_stats):
    strat = object()
    mocks = _patch_components(
        monkeypatch,
        records=sample_records,
        aligned=sample_aligned,
        aggregated=sample_aggregated,
        normalized=sample_normalized,
        fused=sample_fused,
        aw_stats=sample_aw_stats,
        normalization_strategy=strat,
    )

    orch = FusionOrchestrator(config, normalization_strategy=strat)
    summary = orch.run(experiment_id="keys-test", kpi_detector_experiment_id="k1", log_detector_experiment_id="l1")

    expected_keys = {
        "experiment_id",
        "execution_status",
        "pipeline_start_time",
        "pipeline_end_time",
        "execution_duration_seconds",
        "records_processed",
        "records_written",
        "generated_artifacts",
        "output_directory",
        "summary_statistics",
    }
    assert set(summary.keys()) == expected_keys

    # ArtifactWriter.write received expected args/kwargs
    called_args, called_kwargs = mocks["aw"].write.call_args
    assert called_args[0] == tuple(sample_fused)
    assert called_args[1] == "keys-test"
    assert called_kwargs.get("kpi_detector_id") == "k1"
    assert called_kwargs.get("log_detector_id") == "l1"
    assert "config_snapshot" in called_kwargs

    # verify every downstream stage called exactly once
    mocks["src"].initialize.assert_called_once()
    mocks["src"].load_sources.assert_called_once()
    mocks["ing"].ingest.assert_called_once()
    mocks["ing"].get_records.assert_called_once()
    mocks["align"].align.assert_called_once()
    mocks["align"].get_aligned_records.assert_called_once()
    mocks["agg"].aggregate_groups.assert_called_once()
    mocks["norm"].normalize_records.assert_called_once()
    mocks["dec"].fuse_records.assert_called_once()
    mocks["aw"].write.assert_called_once()
