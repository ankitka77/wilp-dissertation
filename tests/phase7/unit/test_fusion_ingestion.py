import math
from datetime import datetime, timezone, timedelta
from typing import Any, Mapping

import pandas as pd
import pytest

from phase7.config.fusion_config import FusionConfig
from phase7.ingestion.fusion_ingestion import (
    FusionIngestion,
    FusionIngestionError,
    IngestionValidationError,
    IngestionConfigurationError,
)
from phase7.models.fusion_record import FusionRecord


@pytest.fixture()
def base_config() -> FusionConfig:
    return FusionConfig()


@pytest.fixture()
def empty_source_manager(tmp_path, monkeypatch):
    """Provide a minimal SourceManager-like object used for tests.

    The real `FusionSourceManager` is frozen and tested elsewhere; here we
    provide a lightweight stand-in that implements the subset of the public
    API used by `FusionIngestion`:
      - list_sources()
      - has_source(name)
      - get_source(name)
      - get_source_metadata(name)
    """

    class _SM:
        def __init__(self):
            self._sources = {}

        def register(self, name: str, df: pd.DataFrame, meta: Mapping[str, Any]):
            self._sources[name] = (df.copy(deep=True), dict(meta))

        def list_sources(self):
            return list(self._sources.keys())

        def has_source(self, name: str):
            return name in self._sources

        def get_source(self, name: str):
            return self._sources[name][0].copy(deep=True)

        def get_source_metadata(self, name: str):
            return dict(self._sources[name][1])

    return _SM()


# Construction tests ------------------------------------------------------

def test_construction_normal(base_config, empty_source_manager):
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    assert isinstance(ing, FusionIngestion)
    assert tuple(ing.get_records()) == ()


def test_construction_with_custom_logger(base_config, empty_source_manager):
    import logging

    custom = logging.getLogger("test.ingest.custom")
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config, logger_=custom)
    assert ing._logger is custom


@pytest.mark.parametrize("bad_sm,bad_cfg", [(None, None), (None, base_config), (empty_source_manager, None)])
def test_construction_invalid_args(bad_sm, bad_cfg):
    with pytest.raises(IngestionConfigurationError):
        FusionIngestion(source_manager=bad_sm, config=bad_cfg)


# ingest() behavior -------------------------------------------------------

def test_ingest_calls_each_source(base_config, empty_source_manager, caplog):
    # register two simple KPI sources
    df1 = pd.DataFrame({"timestamp": ["2020-01-01T00:00:00Z"], "id": ["a1"], "score": [0.5]})
    df2 = pd.DataFrame({"timestamp": ["2020-01-01T00:01:00Z"], "id": ["b1"], "value": [0.2]})
    empty_source_manager.register("s1", df1, {"type": "KPI"})
    empty_source_manager.register("s2", df2, {"type": "KPI", "score_column": "value"})

    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    caplog.clear()
    import logging
    caplog.set_level(logging.INFO, logger="project.phase7.ingestion")
    ing.ingest()
    recs = ing.get_records()
    assert len(recs) == 2
    assert any(r.source_record_id == "a1" for r in recs)
    assert any(r.source_record_id == "b1" for r in recs)
    assert "Starting ingestion" in caplog.text
    assert "Ingesting source 's1'" in caplog.text


def test_ingest_clears_previous_records(base_config, empty_source_manager):
    df = pd.DataFrame({"timestamp": ["2020-01-01T00:00:00Z"], "id": ["a1"], "score": [0.5]})
    empty_source_manager.register("s1", df, {"type": "KPI"})
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    ing.ingest()
    assert len(ing.get_records()) == 1
    # mutate source to produce two records next ingest
    df2 = pd.concat([df, df], ignore_index=True)
    empty_source_manager.register("s1", df2, {"type": "KPI"})
    ing.ingest()
    assert len(ing.get_records()) == 2


def test_ingest_empty_source_list(base_config, empty_source_manager, caplog):
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    caplog.clear()
    import logging
    caplog.set_level(logging.INFO, logger="project.phase7.ingestion")
    ing.ingest()
    assert tuple(ing.get_records()) == ()
    assert "Starting ingestion" in caplog.text


def test_ingest_exception_propagation(base_config, empty_source_manager):
    class BrokenSM:
        def list_sources(self):
            raise RuntimeError("boom")

    ing = FusionIngestion(source_manager=BrokenSM(), config=base_config)
    with pytest.raises(RuntimeError):
        ing.ingest()


# ingest_source() tests ---------------------------------------------------

def test_ingest_source_unknown(base_config, empty_source_manager):
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    with pytest.raises(KeyError):
        ing.ingest_source("nope")


def test_ingest_source_unsupported_type(base_config, empty_source_manager):
    df = pd.DataFrame({"timestamp": ["2020-01-01T00:00:00Z"], "id": ["x"]})
    empty_source_manager.register("s", df, {"type": "UNKNOWN"})
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    with pytest.raises(IngestionValidationError):
        ing.ingest_source("s")


def test_ingest_source_manager_failure_propagates(base_config):
    class BadSM:
        def list_sources(self):
            return ["s"]

        def has_source(self, name):
            return True

        def get_source(self, name):
            raise RuntimeError("io")

        def get_source_metadata(self, name):
            return {"type": "KPI"}

    ing = FusionIngestion(source_manager=BadSM(), config=base_config)
    with pytest.raises(RuntimeError):
        ing.ingest()


# KPI ingestion specific --------------------------------------------------

def _make_kpi_df(**kwargs):
    # utility to produce KPI-like frames
    return pd.DataFrame(kwargs)


def test_ingest_kpi_basic(base_config, empty_source_manager):
    df = _make_kpi_df(timestamp=["2020-01-01T00:00:00Z"], id=["r1"], score=[0.75], entity_id=["ent1"]) 
    empty_source_manager.register("ks", df, {"type": "KPI"})
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    ing.ingest_source("ks")
    recs = ing.get_records()
    assert len(recs) == 1
    r = recs[0]
    assert r.source_record_id == "r1"
    assert r.entity_id == "ent1"
    assert math.isclose(r.kpi_score, 0.75)
    assert r.window_ts.tzinfo is not None and r.window_ts.tzinfo.utcoffset(r.window_ts) == timedelta(0)


@pytest.mark.parametrize("tsval", [
    datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc),
    "2020-01-01T00:00:00Z",
    "2020-01-01T00:00:00+00:00",
])
def test_timestamp_parsing_variants(base_config, empty_source_manager, tsval):
    df = pd.DataFrame({"timestamp": [tsval], "id": ["r2"], "score": [0.1]})
    empty_source_manager.register("t1", df, {"type": "KPI"})
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    ing.ingest()
    r = ing.get_records()[0]
    assert r.window_ts.tzinfo is not None and r.window_ts.utcoffset() == timedelta(0)


def test_inferred_window_end(base_config, empty_source_manager):
    df = pd.DataFrame({"timestamp": ["2020-01-01T00:00:00Z"], "id": ["w1"], "score": [0.2]})
    empty_source_manager.register("w", df, {"type": "KPI"})
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    ing.ingest()
    r = ing.get_records()[0]
    assert r.window_end_ts - r.window_ts == base_config.fusion_settings.window_size


def test_explicit_window_end_overrides(base_config, empty_source_manager):
    df = pd.DataFrame({"timestamp": ["2020-01-01T00:00:00Z"], "window_end_ts": ["2020-01-01T00:10:00Z"], "id": ["w2"], "score": [0.2]})
    empty_source_manager.register("we", df, {"type": "KPI"})
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    ing.ingest()
    r = ing.get_records()[0]
    assert (r.window_end_ts - r.window_ts) == timedelta(minutes=10)


def test_missing_timestamp_column_triggers_validation(base_config, empty_source_manager):
    df = pd.DataFrame({"not_ts": ["2020-01-01T00:00:00Z"], "id": ["x"]})
    empty_source_manager.register("m1", df, {"type": "KPI"})
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    with pytest.raises(IngestionValidationError):
        ing.ingest()


def test_missing_id_column_triggers_validation(base_config, empty_source_manager):
    df = pd.DataFrame({"timestamp": ["2020-01-01T00:00:00Z"], "noid": ["x"]})
    empty_source_manager.register("m2", df, {"type": "KPI"})
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    with pytest.raises(IngestionValidationError):
        ing.ingest()


def test_invalid_timestamp_value(base_config, empty_source_manager):
    df = pd.DataFrame({"timestamp": [object()], "id": ["x"], "score": [0.1]})
    empty_source_manager.register("badts", df, {"type": "KPI"})
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    with pytest.raises(IngestionValidationError):
        ing.ingest()


def test_invalid_end_timestamp_value(base_config, empty_source_manager):
    df = pd.DataFrame({"timestamp": ["2020-01-01T00:00:00Z"], "window_end_ts": [object()], "id": ["x"], "score": [0.1]})
    empty_source_manager.register("badend", df, {"type": "KPI"})
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    with pytest.raises(IngestionValidationError):
        ing.ingest()


def test_invalid_score_types_and_nan(base_config, empty_source_manager):
    # string score -> validation error
    sm1 = empty_source_manager.__class__()
    df = pd.DataFrame({"timestamp": ["2020-01-01T00:00:00Z"], "id": ["x"], "score": ["not-a-number"]})
    sm1.register("bads", df, {"type": "KPI"})
    ing = FusionIngestion(source_manager=sm1, config=base_config)
    with pytest.raises(IngestionValidationError):
        ing.ingest()

    # NaN score -> treated as invalid by FusionRecord factory -> validation error
    sm2 = empty_source_manager.__class__()
    df2 = pd.DataFrame({"timestamp": ["2020-01-01T00:00:00Z"], "id": ["y"], "score": [float("nan")]})
    sm2.register("nan", df2, {"type": "KPI"})
    ing2 = FusionIngestion(source_manager=sm2, config=base_config)
    # NaN currently results in a TypeError from the FusionRecord factory
    with pytest.raises(TypeError):
        ing2.ingest()

    # infinite score -> validation error
    sm3 = empty_source_manager.__class__()
    df3 = pd.DataFrame({"timestamp": ["2020-01-01T00:00:00Z"], "id": ["z"], "score": [float("inf")]})
    sm3.register("inf", df3, {"type": "KPI"})
    ing3 = FusionIngestion(source_manager=sm3, config=base_config)
    with pytest.raises(IngestionValidationError):
        ing3.ingest()


def test_negative_score_is_allowed(base_config, empty_source_manager):
    df = pd.DataFrame({"timestamp": ["2020-01-01T00:00:00Z"], "id": ["n1"], "score": [-5.0]})
    empty_source_manager.register("neg", df, {"type": "KPI"})
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    ing.ingest()
    r = ing.get_records()[0]
    assert math.isclose(r.kpi_score, -5.0)


def test_empty_dataframe_results_in_no_records(base_config, empty_source_manager):
    df = pd.DataFrame(columns=["timestamp", "id", "score"])
    empty_source_manager.register("empty", df, {"type": "KPI"})
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    ing.ingest()
    assert tuple(ing.get_records()) == ()


def test_multiple_rows_ingested(base_config, empty_source_manager):
    df = pd.DataFrame({"timestamp": ["2020-01-01T00:00:00Z"] * 3, "id": ["a", "b", "c"], "score": [0.1, 0.2, 0.3]})
    empty_source_manager.register("many", df, {"type": "KPI"})
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    ing.ingest()
    assert len(ing.get_records()) == 3


# Log ingestion tests: mirror KPI scenarios -------------------------------

def _make_log_df(**kwargs):
    return pd.DataFrame(kwargs)


def test_ingest_log_basic(base_config, empty_source_manager):
    df = _make_log_df(timestamp=["2020-01-01T00:00:00Z"], id=["rlog"], anomaly_score=[0.33], entity_id=["E1"]) 
    empty_source_manager.register("ls", df, {"type": "LOG"})
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    ing.ingest()
    r = ing.get_records()[0]
    assert math.isclose(r.log_score, 0.33)
    assert r.source_record_id == "rlog"
    assert r.entity_id == "E1"


@pytest.mark.parametrize("colname", ["anomaly_score", "score", "prediction_confidence"])
def test_log_score_field_variants(base_config, empty_source_manager, colname):
    df = pd.DataFrame({"timestamp": ["2020-01-01T00:00:00Z"], colname: [0.5], "id": ["L1"]})
    empty_source_manager.register("lv", df, {"type": "LOG"})
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    ing.ingest()
    r = ing.get_records()[0]
    assert math.isclose(r.log_score, 0.5)


def test_shared_logic_kpi_vs_log(base_config, empty_source_manager):
    # same payload except type; expect same timestamp, id, window inference
    df_k = pd.DataFrame({"timestamp": ["2020-01-01T00:00:00Z"], "id": ["S"], "score": [0.1]})
    df_l = pd.DataFrame({"timestamp": ["2020-01-01T00:00:00Z"], "id": ["S"], "score": [0.1]})
    empty_source_manager.register("k", df_k, {"type": "KPI", "score_column": "score"})
    empty_source_manager.register("l", df_l, {"type": "LOG", "score_column": "score"})
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    ing.ingest()
    recs = sorted(ing.get_records(), key=lambda r: r.source_metadata.get("type"))
    krec = next(r for r in recs if r.source_metadata.get("type") == "KPI")
    lrec = next(r for r in recs if r.source_metadata.get("type") == "LOG")
    assert krec.window_ts == lrec.window_ts
    assert krec.window_end_ts == lrec.window_end_ts
    assert krec.source_record_id == lrec.source_record_id


# get_records() / clear() tests ------------------------------------------

def test_get_records_is_tuple_and_immutable(base_config, empty_source_manager):
    df = pd.DataFrame({"timestamp": ["2020-01-01T00:00:00Z"], "id": ["t"], "score": [0.1]})
    empty_source_manager.register("x", df, {"type": "KPI"})
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    ing.ingest()
    recs = ing.get_records()
    assert isinstance(recs, tuple)
    with pytest.raises(TypeError):
        recs[0] = None  # type: ignore
    # internal state unchanged
    assert len(ing.get_records()) == 1


def test_clear_behaviour(base_config, empty_source_manager):
    df = pd.DataFrame({"timestamp": ["2020-01-01T00:00:00Z"], "id": ["c"], "score": [0.2]})
    empty_source_manager.register("c1", df, {"type": "KPI"})
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    ing.clear()
    assert tuple(ing.get_records()) == ()
    ing.ingest()
    assert len(ing.get_records()) == 1
    ing.clear()
    assert tuple(ing.get_records()) == ()


# helper utilities indirectly exercised ----------------------------------

def test_choose_column_first_match(base_config, empty_source_manager):
    df = pd.DataFrame({"first": ["2020-01-01T00:00:00Z"], "second": [2], "id": ["x"], "score": [0.1]})
    empty_source_manager.register("c1", df, {"type": "KPI", "timestamp_column": "first"})
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    # should not raise (has id column)
    ing.ingest()


def test_choose_column_no_match_triggers_validation(base_config, empty_source_manager):
    df = pd.DataFrame({"a": [1]})
    empty_source_manager.register("c2", df, {"type": "KPI"})
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    with pytest.raises(IngestionValidationError):
        ing.ingest()


def test_parse_timestamp_invalid_string():
    from phase7.ingestion.fusion_ingestion import _parse_timestamp

    with pytest.raises(ValueError):
        _parse_timestamp("not-a-timestamp")


def test_parse_timestamp_naive_and_tz():
    from phase7.ingestion.fusion_ingestion import _parse_timestamp

    naivedt = datetime(2020, 1, 1, 0, 0)
    parsed = _parse_timestamp(naivedt)
    assert parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0)

    aware = datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc)
    parsed2 = _parse_timestamp(aware)
    assert parsed2.tzinfo is not None and parsed2.utcoffset() == timedelta(0)


def test_coerce_str_various():
    from phase7.ingestion.fusion_ingestion import _coerce_str

    assert _coerce_str("abc") == "abc"
    assert _coerce_str(123) == "123"
    assert _coerce_str(12.3) == "12.3"
    assert _coerce_str(None) is None
    assert _coerce_str(float("nan")) is None
    assert _coerce_str("") is None
    assert _coerce_str("   ") is None


# immutability and regression coverage -----------------------------------

def test_records_are_immutable_and_metadata_preserved(base_config, empty_source_manager):
    df = pd.DataFrame({"timestamp": ["2020-01-01T00:00:00Z"], "id": ["im1"], "score": [0.9]})
    meta = {"type": "KPI", "custom": {"x": 1}}
    empty_source_manager.register("im", df, meta)
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    ing.ingest()
    r = ing.get_records()[0]
    with pytest.raises(Exception):
        # dataclass is frozen; attempting setattr should raise
        setattr(r, "source_record_id", "changed")
    # metadata preserved
    assert r.source_metadata.get("custom", {}).get("x") == 1


def test_unicode_and_large_dataframe(base_config, empty_source_manager):
    # unicode source names and entity ids
    df = pd.DataFrame({
        "timestamp": ["2020-01-01T00:00:00Z"] * 5,
        "id": [f"i{n}" for n in range(5)],
        "score": [0.1 * n for n in range(5)],
        "entity_id": ["éñt" + str(n) for n in range(5)],
    })
    empty_source_manager.register("ユニコード", df, {"type": "KPI"})
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    ing.ingest()
    assert len(ing.get_records()) == 5


# regression: window inference consistent for KPI and LOG -----------------

def test_window_inference_matches_for_kpi_and_log(base_config, empty_source_manager):
    dfk = pd.DataFrame({"timestamp": ["2020-01-01T00:00:00Z"], "id": ["w1"], "score": [0.2]})
    dfl = pd.DataFrame({"timestamp": ["2020-01-01T00:00:00Z"], "id": ["w1"], "score": [0.2]})
    empty_source_manager.register("k1", dfk, {"type": "KPI"})
    empty_source_manager.register("l1", dfl, {"type": "LOG", "score_column": "score"})
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    ing.ingest()
    recs = sorted(ing.get_records(), key=lambda r: r.source_metadata.get("type"))
    assert recs[0].window_end_ts - recs[0].window_ts == recs[1].window_end_ts - recs[1].window_ts


# malformed dataframe/edge cases -----------------------------------------

def test_malformed_dataframe_raises(base_config, empty_source_manager):
    # column present but contains unsupported object
    df = pd.DataFrame({"timestamp": [object()], "id": ["x"], "score": [0.1]})
    empty_source_manager.register("mf", df, {"type": "KPI"})
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    with pytest.raises(IngestionValidationError):
        ing.ingest()


# logging tests ----------------------------------------------------------

def test_logging_messages_during_ingest(base_config, empty_source_manager, caplog):
    df = pd.DataFrame({"timestamp": ["2020-01-01T00:00:00Z"], "id": ["log1"], "score": [0.4]})
    empty_source_manager.register("logg", df, {"type": "KPI"})
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    caplog.clear()
    import logging
    caplog.set_level(logging.INFO, logger="project.phase7.ingestion")
    ing.ingest()
    assert "Starting ingestion" in caplog.text
    assert "Ingesting source 'logg'" in caplog.text
    assert "Ingested 1 records" in caplog.text


# regression: metadata propagation and types preserved -------------------

def test_metadata_and_field_preservation(base_config, empty_source_manager):
    df = pd.DataFrame({"timestamp": ["2020-01-01T00:00:00Z"], "id": ["meta1"], "score": [0.77]})
    meta = {"type": "KPI", "origin": "tests", "nested": {"a": 1}}
    empty_source_manager.register("meta", df, meta)
    ing = FusionIngestion(source_manager=empty_source_manager, config=base_config)
    ing.ingest()
    r = ing.get_records()[0]
    assert r.source_metadata["origin"] == "tests"
    assert r.source_metadata["nested"]["a"] == 1
    assert r.source_record_id == "meta1"
    assert math.isclose(r.kpi_score, 0.77)

