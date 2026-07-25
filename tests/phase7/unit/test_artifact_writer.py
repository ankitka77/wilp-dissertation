import json
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType

import pytest
import logging

from phase7.config.fusion_config import FusionConfig
from phase7.artifacts.artifact_writer import (
    ArtifactWriter,
    ArtifactValidationError,
    ArtifactWriteError,
)
from phase7.models.fusion_record import FusionRecord

# Replace datetime.utcnow used by artifact_writer with a timezone-aware equivalent
import phase7.artifacts.artifact_writer as _aw_mod
class _DummyDateTime:
    # deterministic fixed timestamp for tests
    _FIXED = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    @staticmethod
    def utcnow():
        # emulate datetime.utcnow() but return timezone-aware UTC datetime
        return _DummyDateTime._FIXED

    @staticmethod
    def now(tz=None):
        # emulate datetime.now(tz=...)
        if tz is None:
            # return naive datetime similar to real datetime.now(None)
            return _DummyDateTime._FIXED.replace(tzinfo=None)
        # respect the tz argument and return tz-aware datetime
        return _DummyDateTime._FIXED.astimezone(tz)

    @staticmethod
    def fromisoformat(value: str):
        # delegate parsing to the real datetime.fromisoformat to emulate
        # full stdlib behavior while returning a timezone-aware UTC datetime
        try:
            # use the real datetime imported at module scope
            dt = datetime.fromisoformat(value)
        except Exception:
            # propagate parsing errors to mimic stdlib behavior
            raise
        if dt.tzinfo is None:
            # interpret naive as UTC for compatibility with production
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

_aw_mod.datetime = _DummyDateTime


@pytest.fixture
def fusion_config(tmp_path: Path) -> FusionConfig:
    # point artifact root to tmp_path for isolation
    return FusionConfig.load(overrides={"artifacts": {"root_dir": str(tmp_path)}})


@pytest.fixture
def sample_config_snapshot() -> dict:
    return {"note": "snapshot", "version": 1}


def make_window(offset_minutes: int = 0) -> tuple[datetime, datetime]:
    start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(minutes=offset_minutes)
    end = start + timedelta(minutes=5)
    return start, end


@pytest.fixture
def single_kpi_record() -> FusionRecord:
    s, e = make_window(0)
    return FusionRecord.from_kpi_source(s, e, source_record_id="k1", kpi_score=0.42, entity_id="ent-A")


@pytest.fixture
def single_log_record() -> FusionRecord:
    s, e = make_window(1)
    return FusionRecord.from_log_source(s, e, source_record_id="l1", log_score=0.33, entity_id="ent-A")


@pytest.fixture
def combined_records(single_kpi_record: FusionRecord, single_log_record: FusionRecord) -> tuple[FusionRecord, ...]:
    # create two records with deterministic ordering (window_ts then source_record_id)
    # ensure different window_ts for deterministic ordering
    return (single_kpi_record, single_log_record)


@pytest.fixture
def writer(fusion_config: FusionConfig) -> ArtifactWriter:
    return ArtifactWriter(fusion_config)


class TestConstruction:
    def test_valid_construction_and_statistics_init(self, fusion_config: FusionConfig):
        aw = ArtifactWriter(fusion_config)
        stats = aw.export_statistics()
        assert isinstance(stats, MappingProxyType)
        assert dict(stats) == {}
        aw.clear()
        assert dict(aw.export_statistics()) == {}

    def test_invalid_constructor_args(self):
        with pytest.raises(ArtifactValidationError):
            ArtifactWriter(None)  # type: ignore[arg-type]


class TestValidation:
    def test_records_none(self, writer: ArtifactWriter):
        with pytest.raises(ArtifactValidationError):
            writer.write(None, "exp-1")  # type: ignore[arg-type]

    def test_records_not_tuple(self, writer: ArtifactWriter, combined_records):
        with pytest.raises(ArtifactValidationError):
            writer.write(list(combined_records), "exp-1")  # type: ignore[arg-type]

    def test_empty_tuple(self, writer: ArtifactWriter):
        with pytest.raises(ArtifactValidationError):
            writer.write(tuple(), "exp-1")

    def test_tuple_with_nonfusionrecord(self, writer: ArtifactWriter, single_kpi_record):
        with pytest.raises(ArtifactValidationError):
            writer.write((single_kpi_record, object()), "exp-1")  # type: ignore[arg-type]


class TestDirectoryCreation:
    def test_directories_created(self, writer: ArtifactWriter, combined_records: tuple[FusionRecord, ...], caplog):
        caplog.clear()
        caplog.set_level(logging.INFO, logger="project.phase7.artifacts")
        writer.write(combined_records, "exp-dirs")
        root = Path(writer._config.artifacts.root_dir) / "experiments" / "exp-dirs"
        assert (root / "reports").is_dir()
        assert (root / "plots").is_dir()
        assert (root / "manifests").is_dir()
        assert any("Created artifact directories" in m.message for m in caplog.records)

    def test_directory_creation_failure(self, writer: ArtifactWriter, combined_records: tuple[FusionRecord, ...], monkeypatch):
        # simulate failure in _prepare_output_directories
        monkeypatch.setattr(writer, "_prepare_output_directories", lambda _id: (_ for _ in ()).throw(OSError("disk full")))
        # _prepare_output_directories is called before write()'s try-block; OSError propagates
        with pytest.raises(OSError):
            writer.write(combined_records, "exp-fail")


class TestCSVWriting:
    def test_all_csvs_generated_and_content(self, writer: ArtifactWriter, combined_records: tuple[FusionRecord, ...], tmp_path: Path):
        writer.write(combined_records, "exp-csv", config_snapshot={})
        root = Path(writer._config.artifacts.root_dir) / "experiments" / "exp-csv" / "reports"
        files = ["fusion_inputs.csv", "aligned_windows.csv", "normalized_scores.csv", "fused_predictions.csv"]
        for fn in files:
            p = root / fn
            assert p.exists()
            txt = p.read_text(encoding="utf-8")
            assert "window_ts" in txt

    def test_deterministic_csv_ordering(self, writer: ArtifactWriter, combined_records: tuple[FusionRecord, ...]):
        # write twice and compare bytes
        writer.write(combined_records, "exp-det")
        root = Path(writer._config.artifacts.root_dir) / "experiments" / "exp-det" / "reports"
        a = (root / "fusion_inputs.csv").read_bytes()
        # rewrite
        writer.write(combined_records, "exp-det")
        b = (root / "fusion_inputs.csv").read_bytes()
        assert a == b

    def test_header_only_csv(self, writer: ArtifactWriter, fusion_config: FusionConfig):
        # create a writer and call _write_csv directly with empty records tuple to get header-only output
        aw = ArtifactWriter(fusion_config)
        aw._prepare_parent(Path(fusion_config.artifacts.root_dir) / "reports")
        # call internal method to produce header-only CSV for fusion_inputs
        aw._write_csv(Path(fusion_config.artifacts.root_dir) / "reports" / "fusion_inputs_empty.csv", tuple(), "fusion_inputs")
        p = Path(fusion_config.artifacts.root_dir) / "reports" / "fusion_inputs_empty.csv"
        assert p.exists()
        content = p.read_text(encoding="utf-8")
        assert content.splitlines()[0].startswith("window_ts")


class TestJSONOutputs:
    def test_json_outputs_and_manifest(self, writer: ArtifactWriter, combined_records: tuple[FusionRecord, ...], sample_config_snapshot: dict):
        writer.write(combined_records, "exp-json", kpi_detector_id="k-d", log_detector_id="l-d", config_snapshot=sample_config_snapshot)
        root = Path(writer._config.artifacts.root_dir) / "experiments" / "exp-json" / "reports"
        summary = json.loads((root / "fusion_summary.json").read_text(encoding="utf-8"))
        coverage = json.loads((root / "source_coverage.json").read_text(encoding="utf-8"))
        assert "record_counts" in summary
        assert summary["configuration"] == sample_config_snapshot
        assert isinstance(coverage, dict)

        manifest = json.loads((Path(writer._config.artifacts.root_dir) / "experiments" / "exp-json" / "manifests" / "phase7_manifest.json").read_text(encoding="utf-8"))
        # required manifest keys
        keys = ["manifest_version", "generation_timestamp", "experiment_id", "fusion_strategy", "kpi_weight", "log_weight", "threshold", "window_size", "normalization_strategy", "coverage", "output_artifact_locations"]
        for k in keys:
            assert k in manifest
        assert manifest["experiment_id"] == "exp-json"


class TestPlots:
    def test_plots_created_and_nonzero(self, writer: ArtifactWriter, combined_records: tuple[FusionRecord, ...]):
        writer.write(combined_records, "exp-plot")
        root = Path(writer._config.artifacts.root_dir) / "experiments" / "exp-plot" / "plots"
        hist = root / "fused_score_histogram.png"
        ts = root / "fused_score_timeseries.png"
        assert hist.exists() and hist.stat().st_size > 0
        assert ts.exists() and ts.stat().st_size > 0

    def test_plot_generation_failure(self, writer: ArtifactWriter, combined_records: tuple[FusionRecord, ...], monkeypatch):
        # force plt.savefig to raise
        import matplotlib.pyplot as plt

        def fail_save(*args, **kwargs):
            raise OSError("cannot save")

        monkeypatch.setattr(plt, "savefig", fail_save)
        with pytest.raises(ArtifactWriteError):
            writer.write(combined_records, "exp-plot-fail")


class TestStatisticsAndImmutability:
    def test_statistics_populated_and_immutable(self, writer: ArtifactWriter, combined_records: tuple[FusionRecord, ...]):
        writer.write(combined_records, "exp-stats")
        stats = writer.export_statistics()
        assert isinstance(stats, MappingProxyType)
        assert stats["records_written"] == len(combined_records)
        with pytest.raises(TypeError):
            stats["records_written"] = 0  # type: ignore[misc]
        # clearing resets
        writer.clear()
        assert dict(writer.export_statistics()) == {}


class TestErrorHandling:
    def test_csv_write_failure(self, writer: ArtifactWriter, combined_records: tuple[FusionRecord, ...], monkeypatch):
        # make _write_csv raise
        monkeypatch.setattr(writer, "_write_csv", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("io")))
        with pytest.raises(ArtifactWriteError):
            writer.write(combined_records, "exp-csv-fail")

    def test_json_write_failure(self, writer: ArtifactWriter, combined_records: tuple[FusionRecord, ...], monkeypatch):
        # let CSV succeed but JSON fail
        original_write_json = writer._write_json

        def fail_once(path, obj):
            if path.name.endswith("fusion_summary.json"):
                raise OSError("json fail")
            return original_write_json(path, obj)

        monkeypatch.setattr(writer, "_write_json", fail_once)
        with pytest.raises(ArtifactWriteError):
            writer.write(combined_records, "exp-json-fail")


class TestDeterminism:
    def test_two_writes_identical_outputs_except_timestamps(self, writer: ArtifactWriter, combined_records: tuple[FusionRecord, ...]):
        exp = "exp-determinism"
        writer.write(combined_records, exp)
        base = Path(writer._config.artifacts.root_dir) / "experiments" / exp / "reports"
        a_csv = (base / "fusion_inputs.csv").read_bytes()
        a_json = json.loads((base / "fusion_summary.json").read_text(encoding="utf-8"))

        # rewrite after slight delay
        writer.write(combined_records, exp)
        b_csv = (base / "fusion_inputs.csv").read_bytes()
        b_json = json.loads((base / "fusion_summary.json").read_text(encoding="utf-8"))

        assert a_csv == b_csv
        # summary timestamps may differ, compare other parts
        a_json_ts = a_json.pop("generated_at", None)
        b_json_ts = b_json.pop("generated_at", None)
        assert a_json == b_json


class TestEdgeCases:
    @pytest.mark.parametrize("kpi,log", [(True, False), (False, True), (False, False)])
    def test_various_availability(self, writer: ArtifactWriter, kpi: bool, log: bool):
        s, e = make_window(10)
        # construct records directly to exercise edge conditions
        rec = FusionRecord(window_ts=s, window_end_ts=e)
        # if kpi: replace with kpi source
        if kpi:
            rec = FusionRecord.from_kpi_source(s, e, "rk", 1.0, entity_id="E")
        if log and not kpi:
            rec = FusionRecord.from_log_source(s, e, "rl", 0.5, entity_id="E")
        writer.write((rec,), "exp-edge")
        base = Path(writer._config.artifacts.root_dir) / "experiments" / "exp-edge" / "reports"
        assert (base / "fusion_inputs.csv").exists()


def test_private_helpers_direct_invocation(fusion_config: FusionConfig):
    # cover some private helpers via a fresh writer instance
    aw = ArtifactWriter(fusion_config)
    s, e = make_window(20)
    r = FusionRecord(window_ts=s, window_end_ts=e)
    # prepare dirs
    aw._prepare_parent(Path(fusion_config.artifacts.root_dir) / "reports")
    # generate rows for aligned_windows
    rows = list(aw._generate_rows((r,), "aligned_windows"))
    assert isinstance(rows, list)
    # build coverage and summary
    cov = aw._build_source_coverage((r,))
    assert isinstance(cov, dict)
    summ = aw._build_fusion_summary((r,), config_snapshot=None)
    assert summ["record_counts"]["total"] == 1
