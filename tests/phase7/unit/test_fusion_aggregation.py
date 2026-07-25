import dataclasses
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Any, Iterable, List, Tuple

import pytest

from phase7.aggregation.fusion_aggregation import (
    AggregatedFusionRecord,
    AggregationConfigurationError,
    AggregationValidationError,
    FusionAggregation,
)
from phase7.config.fusion_config import FusionConfig
from phase7.models.fusion_record import FusionRecord


# --- Fixtures & helpers -------------------------------------------------

@pytest.fixture
def config() -> FusionConfig:
    return FusionConfig()


def make_kpi(ts: datetime, end: datetime, value: float, *, source_id: str | None = None, entity_id: str | None = None, metadata: dict | None = None) -> FusionRecord:
    return FusionRecord.from_kpi_source(window_ts=ts, window_end_ts=end, source_record_id=source_id, kpi_score=value, entity_id=entity_id, source_metadata=metadata)


def make_log(ts: datetime, end: datetime, value: float, *, source_id: str | None = None, entity_id: str | None = None, metadata: dict | None = None) -> FusionRecord:
    return FusionRecord.from_log_source(window_ts=ts, window_end_ts=end, source_record_id=source_id, log_score=value, entity_id=entity_id, source_metadata=metadata)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# --- Construction & basics ----------------------------------------------

def test_construction_requires_config_and_initial_state_empty(caplog):
    with pytest.raises(AggregationConfigurationError):
        FusionAggregation(None)  # type: ignore[arg-type]

    agg = FusionAggregation(FusionConfig())
    assert isinstance(agg.get_aggregated_records(), tuple)
    assert agg.get_aggregated_records() == ()


# --- aggregate() / aggregate_groups() -----------------------------------

def test_aggregate_empty_iterable_returns_empty_tuple_and_logs(caplog, config):
    agg = FusionAggregation(config)
    caplog.clear()
    caplog.set_level("INFO")
    result = agg.aggregate(())
    assert result == ()
    assert "No groups provided to aggregate" in "\n".join(m.message for m in caplog.records)
    assert agg.get_aggregated_records() == ()


def test_aggregate_groups_and_aggregate_replaces_state_and_is_deterministic(config):
    agg = FusionAggregation(config)
    t0 = now_utc()
    r1 = make_kpi(t0, t0 + timedelta(seconds=10), 1.0, source_id="A", entity_id="e1")
    r2 = make_kpi(t0 + timedelta(seconds=5), t0 + timedelta(seconds=15), 3.0, source_id="B", entity_id="e1")

    group1 = (r1,)
    group2 = (r2,)

    # pass in reversed order to ensure deterministic ordering by earliest window
    out = agg.aggregate_groups([group2, group1])
    assert isinstance(out, tuple)
    assert len(out) == 2

    # deterministic ordering: group1 has earlier window -> should appear first
    assert out[0].window_ts <= out[1].window_ts

    # calling aggregate again replaces internal state
    out2 = agg.aggregate_groups([group1])
    assert tuple(out2) == tuple(agg.get_aggregated_records())
    assert len(agg.get_aggregated_records()) == 1

    # caller input unchanged
    assert isinstance([group2, group1][0], tuple)


def test_aggregate_groups_returns_immutable_tuple(config):
    agg = FusionAggregation(config)
    t0 = now_utc()
    r = make_kpi(t0, t0 + timedelta(seconds=1), 2.0, source_id="id")
    out = agg.aggregate_groups([(r,)])
    assert isinstance(out, tuple)
    with pytest.raises(TypeError):
        out[0] = 1  # tuples are immutable


# --- aggregate_group() behaviors ---------------------------------------

def test_aggregate_group_kpi_only_and_metadata_and_source_ids_and_raw_scores(config):
    agg = FusionAggregation(config)
    t0 = now_utc()

    md = {"a": 1}
    r = make_kpi(t0, t0 + timedelta(seconds=5), 4.5, source_id="s1", entity_id="unicode-✓", metadata=md)
    out = agg.aggregate_group((r,))

    assert isinstance(out, AggregatedFusionRecord)
    assert out.window_ts == r.window_ts
    assert out.window_end_ts == r.window_end_ts
    assert out.entity_id == "unicode-✓"
    assert out.aggregated_kpi_score == pytest.approx(4.5)
    assert out.aggregated_log_score is None
    assert out.group_size == 1
    assert out.source_record_ids_kpi == ("s1",)
    assert out.raw_kpi_scores == (4.5,)
    # metadata should be MappingProxyType and immutable
    assert out.source_metadata is None or isinstance(out.source_metadata, MappingProxyType)
    if isinstance(out.source_metadata, MappingProxyType):
        with pytest.raises(TypeError):
            out.source_metadata["kpi:0"] = {}


def test_aggregate_group_log_only_and_multiple_records_aggregation(config):
    agg = FusionAggregation(config)
    t0 = now_utc()
    r1 = make_log(t0, t0 + timedelta(seconds=1), -1.0, source_id="L1")
    r2 = make_log(t0 + timedelta(seconds=2), t0 + timedelta(seconds=3), 1.0, source_id="L2")

    out = agg.aggregate_group((r1, r2))
    # aggregated log is mean
    assert out.aggregated_log_score == pytest.approx(0.0)
    assert out.aggregated_kpi_score is None
    assert out.raw_log_scores == (-1.0, 1.0)
    assert out.source_record_ids_log == ("L1", "L2")


def test_aggregate_group_mixed_kpi_and_log_and_multiple_kpis(config):
    agg = FusionAggregation(config)
    t0 = now_utc()
    k1 = make_kpi(t0, t0 + timedelta(seconds=1), 2.0, source_id="K1", entity_id="e")
    l1 = make_log(t0 + timedelta(seconds=1), t0 + timedelta(seconds=2), 4.0, source_id="L1", entity_id="e")
    k2 = make_kpi(t0 + timedelta(seconds=2), t0 + timedelta(seconds=3), 6.0, source_id="K2", entity_id="e")

    out = agg.aggregate_group((k2, k1, l1))
    # KPI aggregation mean of 2.0 and 6.0 -> 4.0
    assert out.aggregated_kpi_score == pytest.approx(4.0)
    # LOG aggregated is 4.0
    assert out.aggregated_log_score == pytest.approx(4.0)
    # raw scores are ordered by window_ts
    assert out.raw_kpi_scores == (2.0, 6.0)
    assert out.raw_log_scores == (4.0,)
    assert out.group_size == 3


# --- get_aggregated_records & clear -----------------------------------

def test_get_aggregated_records_immutable_and_reflects_latest(config):
    agg = FusionAggregation(config)
    t0 = now_utc()
    r = make_kpi(t0, t0 + timedelta(seconds=1), 9.0, source_id="X")
    agg.aggregate_groups(((r,),))
    recs = agg.get_aggregated_records()
    assert isinstance(recs, tuple)
    assert recs == agg.get_aggregated_records()
    with pytest.raises(TypeError):
        recs[0] = None

    agg.clear()
    assert agg.get_aggregated_records() == ()
    # repeated clear is safe
    agg.clear()
    assert agg.get_aggregated_records() == ()


# --- validation branches -----------------------------------------------

def test_validate_groups_none_raises(config):
    agg = FusionAggregation(config)
    with pytest.raises(AggregationValidationError):
        agg._validate_groups(None)  # type: ignore[arg-type]


def test_validate_group_non_tuple_and_empty_and_non_fusion_record(config):
    agg = FusionAggregation(config)
    t0 = now_utc()
    r = make_kpi(t0, t0 + timedelta(seconds=1), 1.0)

    with pytest.raises(AggregationValidationError):
        agg._validate_group([r])  # non-tuple
    with pytest.raises(AggregationValidationError):
        agg._validate_group(())  # empty
    with pytest.raises(AggregationValidationError):
        agg._validate_group((object(),))  # non-FusionRecord


def test_validate_group_missing_timestamps_and_invalid_duration_and_inconsistent_entity(config):
    agg = FusionAggregation(config)
    t0 = now_utc()
    r = make_kpi(t0, t0 + timedelta(seconds=1), 1.0, entity_id="a")

    # Temporarily mutate the frozen dataclass to simulate missing timestamps
    object.__setattr__(r, "window_ts", None)
    with pytest.raises(AggregationValidationError):
        agg._validate_group((r,))

    # create a new record and make invalid duration
    r2 = make_kpi(t0, t0 + timedelta(seconds=1), 2.0, entity_id="a")
    object.__setattr__(r2, "window_end_ts", r2.window_ts)  # non-positive duration
    with pytest.raises(AggregationValidationError):
        agg._validate_group((r2,))

    # inconsistent entity ids across group
    r3 = make_kpi(t0 + timedelta(seconds=2), t0 + timedelta(seconds=3), 3.0, entity_id="x")
    r4 = make_kpi(t0 + timedelta(seconds=4), t0 + timedelta(seconds=5), 4.0, entity_id="y")
    with pytest.raises(AggregationValidationError):
        agg.aggregate_group((r3, r4))


# --- score extraction determinism & edge cases -------------------------

def test_score_extraction_ordering_and_duplicates_and_floating_point(config):
    agg = FusionAggregation(config)
    t0 = now_utc()
    # Provide out-of-order records and duplicate source ids/scores
    k_a = make_kpi(t0 + timedelta(seconds=5), t0 + timedelta(seconds=6), 1.5, source_id="S1")
    k_b = make_kpi(t0 + timedelta(seconds=1), t0 + timedelta(seconds=2), 2.5, source_id="S2")
    k_c = make_kpi(t0 + timedelta(seconds=3), t0 + timedelta(seconds=4), 2.5, source_id="S1")

    out = agg.aggregate_group((k_a, k_b, k_c))
    # raw scores ordered by window_ts: k_b, k_c, k_a
    assert out.raw_kpi_scores == (2.5, 2.5, 1.5)
    # mean is deterministic
    assert out.aggregated_kpi_score == pytest.approx((2.5 + 2.5 + 1.5) / 3)
    # source ids preserved in same order
    assert out.source_record_ids_kpi == ("S2", "S1", "S1")


# --- aggregation strategy functions -----------------------------------

def test_aggregation_strategy_mean_empty_one_many(config):
    agg = FusionAggregation(config)
    mean_fn = agg._select_aggregation_strategy()
    assert mean_fn is not None
    # empty
    assert agg._apply_aggregation_strategy(mean_fn, []) is None
    # one
    assert agg._apply_aggregation_strategy(mean_fn, [3.0]) == pytest.approx(3.0)
    # many
    vals = [1.0, 2.0, 3.0, 4.0]
    assert agg._apply_aggregation_strategy(mean_fn, vals) == pytest.approx(sum(vals) / len(vals))


# --- immutability checks -----------------------------------------------

def test_aggregated_record_frozen_and_collections_immutable(config):
    agg = FusionAggregation(config)
    t0 = now_utc()
    r = make_kpi(t0, t0 + timedelta(seconds=1), 7.0, source_id="immut")
    out = agg.aggregate_group((r,))
    # dataclass is frozen
    with pytest.raises(FrozenInstanceError):
        out.aggregated_kpi_score = 1.0  # type: ignore[assignment]

    # tuples are immutable
    with pytest.raises(TypeError):
        out.raw_kpi_scores[0] = 2.0  # type: ignore[misc]

    # source ids tuple immutable
    with pytest.raises(TypeError):
        out.source_record_ids_kpi[0] = "x"  # type: ignore[misc]


# --- logging expectations ----------------------------------------------

def test_logging_messages_for_aggregate_and_validation(caplog, config):
    agg = FusionAggregation(config)
    caplog.clear()
    caplog.set_level("INFO")
    t0 = now_utc()
    r = make_kpi(t0, t0 + timedelta(seconds=1), 5.0)
    agg.aggregate_groups(((r,),))
    msgs = "\n".join(m.message for m in caplog.records)
    assert "Starting aggregation" in msgs
    assert "Aggregation complete" in msgs

    # validation failure logged as an exception being raised (we capture INFO logs around it)
    with pytest.raises(AggregationValidationError):
        agg.aggregate_groups(((),))


# --- edge cases: unicode, timezone-aware timestamps -------------------

def test_unicode_and_timezone_and_zero_and_negative_values(config):
    agg = FusionAggregation(config)
    t0 = datetime(2020, 1, 1, 12, 0, tzinfo=timezone.utc)
    r1 = make_kpi(t0, t0 + timedelta(seconds=1), 0.0, source_id="σ")
    r2 = make_log(t0 + timedelta(seconds=1), t0 + timedelta(seconds=2), -5.5, source_id="日志")
    out = agg.aggregate_group((r1, r2))
    assert out.entity_id is None
    assert out.raw_kpi_scores == (0.0,)
    assert out.raw_log_scores == (-5.5,)


# --- regression: caller input unchanged --------------------------------

def test_caller_input_unchanged_after_aggregate_groups(config):
    agg = FusionAggregation(config)
    t0 = now_utc()
    r = make_kpi(t0, t0 + timedelta(seconds=1), 1.0)
    groups = [(r,)]
    groups_copy = list(groups)
    _ = agg.aggregate_groups(groups)
    assert groups == groups_copy


# End of file
