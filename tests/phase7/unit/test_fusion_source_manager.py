import json
from types import MappingProxyType
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from phase7.source_manager.fusion_source_manager import (
    FusionSourceManager,
    FusionSourceManagerError,
    SourceConfigurationError,
    SourceLoadError,
    SourceValidationError,
)
from phase7.config.fusion_config import FusionConfig


def _write_csv(path: Path, records: list[dict[str, Any]], columns: list[str] | None = None) -> None:
    df = pd.DataFrame(records)
    if columns is not None:
        # ensure column order and presence
        df = df.reindex(columns=columns)
    df.to_csv(path, index=False)


def test_construction_and_logger(minimal_phase7_config) -> None:
    mgr = FusionSourceManager(minimal_phase7_config)
    assert mgr.list_sources() == []

    custom_logger = None
    mgr2 = FusionSourceManager(minimal_phase7_config, logger_=custom_logger)
    assert mgr2 is not None


def test_construction_invalid_config_raises() -> None:
    with pytest.raises(SourceConfigurationError):
        FusionSourceManager(None)  # type: ignore[arg-type]


def test_initialize_valid_configuration(tmp_path: Path) -> None:
    # prepare a small KPI CSV
    csv = tmp_path / "kpi.csv"
    _write_csv(csv, [{"id": "a", "score": 0.1}], columns=["id", "score"])

    overrides = {"extensions": {"sources": {"kpi1": {"type": "KPI", "path": str(csv), "required_columns": ["id", "score"]}}}}
    cfg = FusionConfig.load(overrides=overrides)
    mgr = FusionSourceManager(cfg)
    mgr.initialize()
    assert mgr.list_sources() == ["kpi1"]


def test_initialize_missing_section_raises(minimal_phase7_config) -> None:
    mgr = FusionSourceManager(minimal_phase7_config)
    with pytest.raises(SourceConfigurationError):
        mgr.initialize(section_name="nope")


def test_initialize_invalid_section_type(monkeypatch, minimal_phase7_config) -> None:
    mgr = FusionSourceManager(minimal_phase7_config)
    monkeypatch.setattr(FusionConfig, "get_section", lambda self, name: [1, 2, 3])
    with pytest.raises(SourceConfigurationError):
        mgr.initialize()


def test_initialize_missing_sources_mapping(monkeypatch, minimal_phase7_config) -> None:
    mgr = FusionSourceManager(minimal_phase7_config)
    monkeypatch.setattr(FusionConfig, "get_section", lambda self, name: {})
    with pytest.raises(SourceConfigurationError):
        mgr.initialize()


def test_initialize_invalid_sources_mapping(monkeypatch, minimal_phase7_config) -> None:
    mgr = FusionSourceManager(minimal_phase7_config)
    monkeypatch.setattr(FusionConfig, "get_section", lambda self, name: {"sources": "nope"})
    with pytest.raises(SourceConfigurationError):
        mgr.initialize()


@pytest.mark.parametrize("bad", [None, {}, {"required_columns": "bad"}])
def test_initialize_missing_type_or_path_or_invalid_required_columns(bad, tmp_path: Path) -> None:
    csv = tmp_path / "k.csv"
    csv.write_text("id,score\n1,0.1\n")
    src = {"type": "KPI", "path": str(csv)}
    if bad is None:
        src = {"path": str(csv)}
    elif bad == {}:
        src = {"type": "KPI"}
    elif bad == {"required_columns": "bad"}:
        src = {"type": "KPI", "path": str(csv), "required_columns": "bad"}

    overrides = {"extensions": {"sources": {"s1": src}}}
    cfg = FusionConfig.load(overrides=overrides)
    mgr = FusionSourceManager(cfg)
    if bad is None or bad == {}:
        with pytest.raises(SourceConfigurationError):
            mgr.initialize()
    else:
        with pytest.raises(SourceConfigurationError):
            mgr.initialize()


def test_unsupported_source_type_triggers_on_load(tmp_path: Path) -> None:
    csv = tmp_path / "x.csv"
    _write_csv(csv, [{"a": 1}])
    overrides = {"extensions": {"sources": {"s": {"type": "UNKNOWN", "path": str(csv)}}}}
    cfg = FusionConfig.load(overrides=overrides)
    mgr = FusionSourceManager(cfg)
    mgr.initialize()
    with pytest.raises(SourceConfigurationError):
        mgr.load_sources()


def test_load_sources_and_accessors(tmp_path: Path, caplog) -> None:
    caplog.set_level("INFO", logger="project.phase7.source_manager")
    # prepare KPI and LOG CSVs
    kpi = tmp_path / "k.csv"
    log = tmp_path / "l.csv"
    _write_csv(kpi, [{"id": "a", "score": 0.1}], columns=["id", "score"])
    _write_csv(log, [{"evt": "x", "severity": 1}], columns=["evt", "severity"])

    overrides = {
        "extensions": {
            "sources": {
                "kpi1": {"type": "KPI", "path": str(kpi), "required_columns": ["id"]},
                "log1": {"type": "LOG", "path": str(log), "required_columns": ["evt"]},
            }
        }
    }
    cfg = FusionConfig.load(overrides=overrides)
    mgr = FusionSourceManager(cfg)
    mgr.initialize()
    mgr.load_sources()

    # accessors
    assert mgr.has_source("kpi1")
    assert set(mgr.list_sources()) == {"kpi1", "log1"}

    df_k = mgr.get_source("kpi1")
    assert isinstance(df_k, pd.DataFrame)
    all_map = mgr.get_all_sources()
    assert isinstance(all_map, MappingProxyType)

    meta = mgr.get_source_metadata("kpi1")
    assert isinstance(meta, MappingProxyType)

    # logging assertions
    assert any("Configured 2 source(s)" in rec.message for rec in caplog.records)
    assert any("Loaded source 'kpi1'" in rec.message for rec in caplog.records)


def test_loading_empty_dataset_raises(tmp_path: Path) -> None:
    empty = tmp_path / "empty.csv"
    empty.write_text("id,score\n")
    overrides = {"extensions": {"sources": {"s": {"type": "KPI", "path": str(empty), "required_columns": ["id"]}}}}
    cfg = FusionConfig.load(overrides=overrides)
    mgr = FusionSourceManager(cfg)
    mgr.initialize()
    with pytest.raises(SourceValidationError):
        mgr.load_sources()


def test_nonexistent_file_raises(tmp_path: Path) -> None:
    p = tmp_path / "nope.csv"
    overrides = {"extensions": {"sources": {"s": {"type": "LOG", "path": str(p)}}}}
    cfg = FusionConfig.load(overrides=overrides)
    mgr = FusionSourceManager(cfg)
    mgr.initialize()
    with pytest.raises(SourceLoadError):
        mgr.load_sources()


def test_csv_parsing_failure(monkeypatch, tmp_path: Path) -> None:
    csv = tmp_path / "bad.csv"
    csv.write_text("not,csv,content")
    overrides = {"extensions": {"sources": {"s": {"type": "KPI", "path": str(csv)}}}}
    cfg = FusionConfig.load(overrides=overrides)
    mgr = FusionSourceManager(cfg)
    mgr.initialize()

    def _raise(path):
        raise pd.errors.ParserError("bad parse")

    monkeypatch.setattr(pd, "read_csv", lambda p: (_ for _ in ()).throw(pd.errors.ParserError("bad parse")))
    with pytest.raises(SourceLoadError):
        mgr.load_sources()


def test_invalid_dataframe_return(monkeypatch, tmp_path: Path) -> None:
    csv = tmp_path / "f.csv"
    csv.write_text("a,b\n1,2\n")
    overrides = {"extensions": {"sources": {"s": {"type": "KPI", "path": str(csv)}}}}
    cfg = FusionConfig.load(overrides=overrides)
    mgr = FusionSourceManager(cfg)
    mgr.initialize()

    monkeypatch.setattr(pd, "read_csv", lambda p: "not-a-df")
    with pytest.raises(SourceValidationError):
        mgr.load_sources()


def test_missing_required_columns(tmp_path: Path) -> None:
    csv = tmp_path / "m.csv"
    _write_csv(csv, [{"x": 1}], columns=["x"])
    overrides = {"extensions": {"sources": {"s": {"type": "KPI", "path": str(csv), "required_columns": ["y"]}}}}
    cfg = FusionConfig.load(overrides=overrides)
    mgr = FusionSourceManager(cfg)
    mgr.initialize()
    with pytest.raises(SourceValidationError):
        mgr.load_sources()


def test_get_source_errors_and_clear(tmp_path: Path) -> None:
    csv = tmp_path / "k.csv"
    _write_csv(csv, [{"id": "a"}], columns=["id"])
    overrides = {"extensions": {"sources": {"k": {"type": "KPI", "path": str(csv)}}}}
    cfg = FusionConfig.load(overrides=overrides)
    mgr = FusionSourceManager(cfg)
    mgr.initialize()
    with pytest.raises(SourceLoadError):
        mgr.get_source("k")

    mgr.load_sources()
    df1 = mgr.get_source("k")
    df1.loc[0, "id"] = "changed"
    df2 = mgr.get_source("k")
    assert df2.loc[0, "id"] == "a"

    all_map = mgr.get_all_sources()
    with pytest.raises(TypeError):
        all_map["k"] = pd.DataFrame()

    mgr.clear()
    with pytest.raises(SourceLoadError):
        mgr.get_source("k")


def test_metadata_immutable_and_recursive(tmp_path: Path) -> None:
    csv = tmp_path / "k.csv"
    _write_csv(csv, [{"id": "a"}], columns=["id"])
    overrides = {"extensions": {"sources": {"k": {"type": "KPI", "path": str(csv), "required_columns": [], "extra": {"nested": {"list": [1, 2], "set": [3]}}}}}}
    cfg = FusionConfig.load(overrides=overrides)
    mgr = FusionSourceManager(cfg)
    mgr.initialize()
    mgr.load_sources()

    meta = mgr.get_source_metadata("k")
    assert isinstance(meta, MappingProxyType)
    with pytest.raises(TypeError):
        meta["new"] = 1  # type: ignore

    # nested structures frozen (list -> tuple, set -> frozenset subclass)
    nested = meta.get("extra")
    assert isinstance(nested, MappingProxyType)
    inner = nested["nested"]
    assert isinstance(inner["list"], tuple)
    assert isinstance(inner["set"], tuple) or hasattr(inner["set"], "add") is False


def test_edge_cases_empty_required_columns_and_unicode_names(tmp_path: Path) -> None:
    csv = tmp_path / "u.csv"
    _write_csv(csv, [{"x": 1}], columns=["x"])
    name = "ユニコード"
    overrides = {"extensions": {"sources": {name: {"type": "KPI", "path": str(csv), "required_columns": []}}}}
    cfg = FusionConfig.load(overrides=overrides)
    mgr = FusionSourceManager(cfg)
    mgr.initialize()
    mgr.load_sources()
    assert mgr.has_source(name)


def test_repeated_initialize_and_load_and_clear(tmp_path: Path) -> None:
    csv = tmp_path / "r.csv"
    _write_csv(csv, [{"a": 1}], columns=["a"])
    overrides = {"extensions": {"sources": {"s1": {"type": "KPI", "path": str(csv)}, "s2": {"type": "LOG", "path": str(csv)}}}}
    cfg = FusionConfig.load(overrides=overrides)
    mgr = FusionSourceManager(cfg)
    mgr.initialize()
    mgr.initialize()  # repeated
    mgr.load_sources()
    mgr.load_sources()  # repeated
    mgr.clear()
    mgr.clear()


def test_regression_kpi_log_load_consistency(tmp_path: Path) -> None:
    csv = tmp_path / "d.csv"
    _write_csv(csv, [{"a": 1}], columns=["a"])
    overrides_k = {"extensions": {"sources": {"k": {"type": "KPI", "path": str(csv)}}}}
    overrides_l = {"extensions": {"sources": {"l": {"type": "LOG", "path": str(csv)}}}}
    cfg_k = FusionConfig.load(overrides=overrides_k)
    cfg_l = FusionConfig.load(overrides=overrides_l)
    mgr_k = FusionSourceManager(cfg_k)
    mgr_l = FusionSourceManager(cfg_l)
    mgr_k.initialize()
    mgr_l.initialize()
    mgr_k.load_sources()
    mgr_l.load_sources()
    assert list(mgr_k.get_all_sources().keys()) == ["k"]
    assert list(mgr_l.get_all_sources().keys()) == ["l"]
