import json
import math
from datetime import datetime, timezone, timedelta

import pytest

from phase7.models import fusion_record as frmod
from phase7.models.fusion_record import (
    FusionRecord,
    SourceType,
    FusionRecordValidationError,
)
from tests.phase7.helpers.fixture_builders import build_fusion_record


# -------------------------
# Construction / basic API
# -------------------------


def test_minimum_valid_fusion_record_construction() -> None:
    now = datetime.now(timezone.utc)
    rec = FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5))
    assert rec.window_ts.tzinfo is not None
    assert rec.window_end_ts.tzinfo is not None
    assert rec.kpi_available is False
    assert rec.log_available is False
    assert rec.decision_metadata == {}
    assert rec.source_metadata == {}


def test_fully_populated_fusion_record() -> None:
    now = datetime.now(timezone.utc)
    meta = {"lineage": {"run": "exp-1"}, "tags": ["a", "b"], "vals": {1, 2}}
    rec = FusionRecord(
        window_ts=now,
        window_end_ts=now + timedelta(minutes=5),
        entity_id=" entity-1 ",
        source_type=SourceType.KPI,
        source_record_id=" rec-1 ",
        kpi_score=0.8,
        log_score=0.1,
        kpi_score_normalized=0.9,
        log_score_normalized=0.2,
        kpi_available=True,
        log_available=True,
        missing_reason=None,
        kpi_weight=0.5,
        log_weight=0.5,
        kpi_contribution=0.45,
        log_contribution=0.05,
        fused_score=0.5,
        final_label=1,
        decision_reason="threshold",
        decision_metadata=meta,
        source_metadata=meta,
    )
    # trimmed identifiers
    assert rec.entity_id == "entity-1"
    assert rec.source_record_id == "rec-1"
    # metadata stored immutably (checked in immutability section)
    assert rec.decision_metadata is not None
    assert rec.source_metadata is not None


def test_kpi_and_log_constructors_helpers() -> None:
    now = datetime.now(timezone.utc)
    k = FusionRecord.from_kpi_source(now, now + timedelta(minutes=5), "k1", 0.7, entity_id="e1")
    assert k.source_type is SourceType.KPI
    assert k.kpi_available is True
    assert k.kpi_score == pytest.approx(0.7)

    l = FusionRecord.from_log_source(now, now + timedelta(minutes=5), "l1", 0.3, entity_id="e2")
    assert l.source_type is SourceType.LOG
    assert l.log_available is True
    assert l.log_score == pytest.approx(0.3)


def test_replace_returns_new_object() -> None:
    now = datetime.now(timezone.utc)
    a = FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5))
    b = a.replace(final_label=1)
    assert a is not b
    assert a.final_label is None
    assert b.final_label == 1


def test_from_dict_and_from_json_and_roundtrip() -> None:
    now = datetime.now(timezone.utc)
    payload = {
        "window_ts": now.isoformat().replace("+00:00", "Z"),
        "window_end_ts": (now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
        "entity_id": "E",
        "kpi_score": 0.4,
        "kpi_available": True,
        "decision_metadata": {"x": 1},
    }
    rec = FusionRecord.from_dict(payload)
    assert isinstance(rec, FusionRecord)
    js = rec.to_json()
    rec2 = FusionRecord.from_json(js)
    assert rec == rec2
    assert rec.to_json() == rec2.to_json()


# -------------------------
# Validation tests
# -------------------------


def test_timezone_aware_validation_and_utc_normalization() -> None:
    # create tz-aware non-UTC datetime and ensure normalize to UTC
    tz2 = timezone(timedelta(hours=2))
    window_ts = datetime(2026, 7, 21, 12, 0, tzinfo=tz2)
    window_end = window_ts + timedelta(minutes=5)
    rec = FusionRecord(window_ts=window_ts, window_end_ts=window_end)
    assert rec.window_ts.tzinfo == timezone.utc
    # original hour 12 at +02:00 becomes 10:00Z
    assert rec.window_ts.hour == 10


def test_window_ordering_must_be_strict() -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(FusionRecordValidationError, match="window_end_ts must be strictly after window_ts"):
        FusionRecord(window_ts=now, window_end_ts=now)


def test_availability_and_missing_scores_consistency() -> None:
    now = datetime.now(timezone.utc)
    # available flag true, score missing -> error
    with pytest.raises(FusionRecordValidationError, match="kpi_available is True but kpi_score is missing"):
        FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5), kpi_available=True)

    with pytest.raises(FusionRecordValidationError, match="log_available is True but log_score is missing"):
        FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5), log_available=True)

    # score present but availability false -> error
    with pytest.raises(FusionRecordValidationError, match="kpi_score provided while kpi_available is False"):
        FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5), kpi_score=0.5)

    with pytest.raises(FusionRecordValidationError, match="log_score provided while log_available is False"):
        FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5), log_score=0.5)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_invalid_numeric_fields_raise(bad) -> None:
    now = datetime.now(timezone.utc)
    # Trying any numeric field with NaN/inf should raise
    with pytest.raises(FusionRecordValidationError, match="must be a finite number"):
        FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5), kpi_score=bad)
    with pytest.raises(FusionRecordValidationError, match="must be a finite number"):
        FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5), kpi_weight=bad)
    with pytest.raises(FusionRecordValidationError, match="must be a finite number"):
        FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5), fused_score=bad)


def test_invalid_final_label() -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(FusionRecordValidationError, match="final_label must be 0, 1, or None"):
        FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5), final_label=2)


def test_invalid_source_type_in_from_dict() -> None:
    now = datetime.now(timezone.utc)
    d = {
        "window_ts": now.isoformat().replace("+00:00", "Z"),
        "window_end_ts": (now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
        "source_type": "BAD",
    }
    with pytest.raises(FusionRecordValidationError, match="Invalid source_type"):
        FusionRecord.from_dict(d)


def test_invalid_metadata_type() -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(FusionRecordValidationError, match="decision_metadata must be a mapping"):
        FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5), decision_metadata=123)
    with pytest.raises(FusionRecordValidationError, match="source_metadata must be a mapping"):
        FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5), source_metadata=123)


def test_invalid_entity_and_source_ids() -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(FusionRecordValidationError, match="entity_id must be a non-empty string"):
        FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5), entity_id="   ")
    with pytest.raises(FusionRecordValidationError, match="source_record_id must be a non-empty string"):
        FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5), source_record_id="  ")


def test_invalid_json_in_from_json_wrapped() -> None:
    with pytest.raises(FusionRecordValidationError, match="Invalid JSON payload"):
        FusionRecord.from_json("{invalid: json}")


def test_from_dict_input_validation_missing_keys() -> None:
    with pytest.raises(FusionRecordValidationError, match="from_dict requires a mapping input"):
        FusionRecord.from_dict(["not", "a", "map"])
    with pytest.raises(FusionRecordValidationError, match="Missing required key in input mapping: window_ts"):
        FusionRecord.from_dict({"window_end_ts": "2026-01-01T00:00:00Z"})


# -------------------------
# Immutability
# -------------------------


def test_dataclass_is_frozen() -> None:
    now = datetime.now(timezone.utc)
    rec = FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5))
    with pytest.raises((AttributeError, TypeError)):
        # dataclass frozen — cannot assign attributes
        rec.kpi_score = 0.5  # type: ignore


def test_metadata_top_level_immutable_and_nested_immutability() -> None:
    now = datetime.now(timezone.utc)
    nested = {"a": {"b": [1, 2, {"c": {3, 4}}]}, "s": {1, 2, 3}, "t": (4, 5)}
    rec = FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5), decision_metadata=nested, source_metadata=nested)

    # top-level mapping is immutable
    with pytest.raises(TypeError):
        rec.decision_metadata["new"] = 1  # type: ignore

    # nested dict becomes MappingProxyType and is immutable
    inner = rec.decision_metadata["a"]
    assert isinstance(inner, dict) or hasattr(inner, "items")
    # attempting to modify nested mapping should raise
    with pytest.raises(TypeError):
        inner["b"] = "x"  # type: ignore

    # nested list becomes tuple
    assert isinstance(rec.decision_metadata["a"]["b"], tuple)

    # nested set becomes frozenset
    assert isinstance(rec.decision_metadata["a"]["b"][2]["c"], frozenset)

    # tuple preserved as tuple inside frozen mapping
    assert isinstance(rec.decision_metadata["t"], tuple)


def test_replace_preserves_immutability_of_original() -> None:
    now = datetime.now(timezone.utc)
    nested = {"a": [1, 2]}
    base = FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5), decision_metadata=nested)
    new = base.replace(entity_id="x")
    assert base.entity_id is None
    assert new.entity_id == "x"
    # original metadata remains immutable
    with pytest.raises(TypeError):
        base.decision_metadata["a"] = 3  # type: ignore


# -------------------------
# Serialization
# -------------------------


def test_to_dict_and_recursive_metadata_serialization() -> None:
    now = datetime.now(timezone.utc)
    nested = {"x": {"y": [1, 2, {"z": {9, 8}}]}, "u": ()}
    rec = FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5), decision_metadata=nested, source_metadata=nested)
    d = rec.to_dict()
    # decision_metadata and source_metadata are JSON-serializable plain structures
    assert isinstance(d["decision_metadata"], dict)
    assert isinstance(d["decision_metadata"]["x"]["y"], list)
    assert isinstance(d["decision_metadata"]["x"]["y"][2]["z"], list)
    # empty tuple becomes empty list in serialization
    assert d["decision_metadata"]["u"] == []

    # deterministic JSON (same input order yields same JSON)
    j1 = rec.to_json()
    j2 = rec.to_json()
    assert j1 == j2

    # round-trip via JSON
    rec2 = FusionRecord.from_json(rec.to_json())
    assert rec2 == rec


def test_recursive_thaw_ordering_deterministic_for_sets() -> None:
    now = datetime.now(timezone.utc)
    # include a set so thaw sorts by JSON key for deterministic output
    nested = {"s": {3, 1, 2}}
    rec = FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5), decision_metadata=nested)
    d = rec.to_dict()
    assert d["decision_metadata"]["s"] == [1, 2, 3]


# -------------------------
# Hashing and equality
# -------------------------


def test_equality_hash_and_usage_in_collections() -> None:
    now = datetime.now(timezone.utc)
    a = FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5))
    b = FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5))
    assert a == b
    assert hash(a) == hash(b)
    s = {a, b}
    assert len(s) == 1
    d = {a: "value"}
    assert d[b] == "value"


# -------------------------
# Helper functions and edge cases
# -------------------------


def test_opt_float_and_opt_int_valid_and_invalid() -> None:
    assert frmod._opt_float(1) == pytest.approx(1.0)
    assert frmod._opt_float(1.5) == pytest.approx(1.5)
    assert frmod._opt_int(2) == 2
    assert frmod._opt_int("3") == 3
    with pytest.raises(FusionRecordValidationError):
        frmod._opt_float("not-a-number")
    with pytest.raises(FusionRecordValidationError):
        frmod._opt_int("not-int")


def test_validate_finite_numeric_edge_cases() -> None:
    with pytest.raises(FusionRecordValidationError):
        frmod._validate_finite_numeric("test", math.nan)
    with pytest.raises(FusionRecordValidationError):
        frmod._validate_finite_numeric("test", math.inf)
    with pytest.raises(FusionRecordValidationError):
        frmod._validate_finite_numeric("test", -math.inf)
    # large finite values ok
    frmod._validate_finite_numeric("test", 1e308)


def test_internal_datetime_parsing_and_malformed() -> None:
    # valid with trailing Z
    dt = FusionRecord._parse_iso_datetime("2026-07-21T12:00:00Z")
    assert dt.tzinfo == timezone.utc
    # malformed input raises
    with pytest.raises(FusionRecordValidationError):
        FusionRecord._parse_iso_datetime("not-a-date")


def test_deep_freeze_and_thaw_roundtrip_and_edge_cases() -> None:
    nested = {"a": [1, {"b": {2, 1}}, ()], "empty_list": [], "empty_set": set(), "empty_map": {}}
    frozen = frmod._deep_freeze(nested)
    # frozen should not be directly JSON-serializable, but thawed is
    thawed = frmod._deep_thaw(frozen)
    assert isinstance(thawed, dict)
    assert thawed["a"][1]["b"] == [1, 2] or set(thawed["a"][1]["b"]) == {1, 2}
    # empty structures round-trip
    assert thawed["empty_list"] == []
    assert thawed["empty_set"] == []
    assert thawed["empty_map"] == {}


def test_edge_cases_optional_fields_and_unicode_and_none_values() -> None:
    now = datetime.now(timezone.utc)
    nested = {"unicode": "μñ", "none": None, "empty_tuple": (), "empty_list": []}
    rec = FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5), decision_metadata=nested)
    d = rec.to_dict()
    assert d["decision_metadata"]["unicode"] == "μñ"
    assert d["decision_metadata"]["none"] is None
    assert d["decision_metadata"]["empty_tuple"] == []
    assert d["decision_metadata"]["empty_list"] == []


def test_empty_and_deeply_nested_metadata() -> None:
    now = datetime.now(timezone.utc)
    deep = {"a": {"b": {"c": {"d": {"e": [1, 2, {"f": {3, 4}}]}}}}}
    rec = FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5), decision_metadata=deep)
    # ensure serialization completes
    j = rec.to_json()
    assert isinstance(j, str)
    rec2 = FusionRecord.from_json(j)
    assert rec == rec2


# Regression tests for previously fixed issues
def test_regression_utc_normalization() -> None:
    tz2 = timezone(timedelta(hours=3))
    ts = datetime(2026, 7, 21, 15, 0, tzinfo=tz2)
    rec = FusionRecord(window_ts=ts, window_end_ts=ts + timedelta(minutes=5))
    assert rec.window_ts.tzinfo == timezone.utc
    assert rec.window_ts.hour == 12


def test_regression_deep_immutability_prevent_nested_mutation() -> None:
    now = datetime.now(timezone.utc)
    nested = {"a": {"b": [1, 2, {"c": {9}}]}}
    rec = FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5), decision_metadata=nested)
    # nested mapping is frozen; attempts to modify should raise TypeError
    with pytest.raises(TypeError):
        rec.decision_metadata["a"]["b"][2]["c"].add(10)  # type: ignore


def test_regression_recursive_metadata_serialization_det_order() -> None:
    now = datetime.now(timezone.utc)
    nested = {"s": {2, 1, 3}, "m": {"k1": 1, "k2": 2}}
    r1 = FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5), decision_metadata=nested)
    r2 = FusionRecord(window_ts=now, window_end_ts=now + timedelta(minutes=5), decision_metadata=nested)
    assert r1.to_json() == r2.to_json()
