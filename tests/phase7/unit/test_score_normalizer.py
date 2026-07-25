from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import List, Tuple

import pytest

from phase7.config.fusion_config import FusionConfig
from phase7.models.fusion_record import FusionRecord
from phase7.normalization.normalization_strategy import (
    NormalizationValidationError as StrategyValidationError,
)
from phase7.normalization.score_normalizer import (
    ScoreNormalizer,
    ScoreNormalizerError,
    ScoreNormalizationValidationError,
    ScoreNormalizationConfigurationError,
)


# Helpers -----------------------------------------------------------------

def now() -> datetime:
    return datetime.now(timezone.utc)


def kpi_record(ts: datetime, val: float, *, src_id: str | None = None, entity: str | None = None) -> FusionRecord:
    return FusionRecord.from_kpi_source(window_ts=ts, window_end_ts=ts + timedelta(seconds=1), source_record_id=src_id, kpi_score=val, entity_id=entity)


def log_record(ts: datetime, val: float, *, src_id: str | None = None, entity: str | None = None) -> FusionRecord:
    return FusionRecord.from_log_source(window_ts=ts, window_end_ts=ts + timedelta(seconds=1), source_record_id=src_id, log_score=val, entity_id=entity)


# Fake strategy for delegation and control -------------------------------

class FakeStrategy:
    def __init__(self, *, to_return: Tuple[float, ...] | None = None, raise_exc: Exception | None = None, meta: dict | None = None):
        self.calls: List[Tuple[float, ...]] = []
        self.to_return = to_return
        self.raise_exc = raise_exc
        self._meta = meta or {"strategy": "fake"}

    def normalize(self, values: Tuple[float, ...]) -> Tuple[float, ...]:
        self.calls.append(tuple(values))
        if self.raise_exc is not None:
            raise self.raise_exc
        if self.to_return is not None:
            return tuple(self.to_return)
        # default: echo floats
        return tuple(float(v) for v in values)

    def get_name(self) -> str:
        return "fake"

    def get_metadata(self):
        return MappingProxyType(dict(self._meta))


# Fixtures -----------------------------------------------------------------

@pytest.fixture
def config() -> FusionConfig:
    return FusionConfig()


@pytest.fixture
def simple_strategy():
    return FakeStrategy()


@pytest.fixture
def echo_strategy():
    return FakeStrategy()  # echoes inputs


# Constructor tests ------------------------------------------------------

def test_constructor_valid_and_get_strategy_and_clear(config, simple_strategy):
    sn = ScoreNormalizer(config, simple_strategy)
    assert sn.get_strategy() is simple_strategy
    # diagnostics initially empty mapping proxy
    diag = sn.export_diagnostics()
    assert isinstance(diag, MappingProxyType)
    sn.clear()
    assert isinstance(sn.export_diagnostics(), MappingProxyType)


def test_constructor_invalid_inputs_raise(config):
    with pytest.raises(ScoreNormalizationConfigurationError):
        ScoreNormalizer(None, FakeStrategy())  # type: ignore[arg-type]
    with pytest.raises(ScoreNormalizationConfigurationError):
        ScoreNormalizer(config, None)  # type: ignore[arg-type]
    with pytest.raises(ScoreNormalizationConfigurationError):
        ScoreNormalizer(config, object())  # invalid strategy object


# normalize_records validations ------------------------------------------

def test_normalize_records_none_and_empty_and_non_tuple(config, simple_strategy):
    sn = ScoreNormalizer(config, simple_strategy)
    with pytest.raises(ScoreNormalizationValidationError):
        sn.normalize_records(None)  # type: ignore[arg-type]
    with pytest.raises(ScoreNormalizationValidationError):
        sn.normalize_records(())
    with pytest.raises(ScoreNormalizationValidationError):
        sn.normalize_records([1, 2, 3])  # type: ignore[arg-type]


def test_validate_record_missing_timestamps(config, simple_strategy):
    sn = ScoreNormalizer(config, simple_strategy)
    r = kpi_record(now(), 1.0)
    # corrupt record to remove timestamps
    object.__setattr__(r, "window_ts", None)
    with pytest.raises(ScoreNormalizationValidationError):
        sn.normalize_records((r,))


def test_invalid_record_type_in_tuple(config, simple_strategy):
    sn = ScoreNormalizer(config, simple_strategy)
    with pytest.raises(ScoreNormalizationValidationError):
        sn.normalize_records((object(),))


# Normalization delegation & behavior -----------------------------------

def test_kpi_and_log_delegation_and_order_preserved(config):
    strategy = FakeStrategy()
    sn = ScoreNormalizer(config, strategy)
    t = now()
    r1 = kpi_record(t, 1.0, src_id="a")
    r2 = log_record(t + timedelta(seconds=1), 2.0, src_id="b")
    r3 = kpi_record(t + timedelta(seconds=2), 3.0, src_id="c")

    out = sn.normalize_records((r1, r2, r3))
    # strategy should have been called twice (KPI and LOG)
    assert len(strategy.calls) == 2
    # order preserved
    assert tuple(type(x) for x in out) == (type(r1), type(r2), type(r3))
    # returned tuple is immutable
    with pytest.raises(TypeError):
        out[0] = None  # type: ignore[misc]


def test_only_kpi_or_only_log_and_no_scores(config):
    strategy = FakeStrategy()
    sn = ScoreNormalizer(config, strategy)
    t = now()
    k = kpi_record(t, 5.0)
    l = log_record(t + timedelta(seconds=1), 6.0)

    # only KPI
    out1 = sn.normalize_records((k,))
    assert len(strategy.calls) == 1
    # only LOG
    out2 = sn.normalize_records((l,))
    assert len(strategy.calls) == 2

    # no scores -> strategy not called
    r = kpi_record(t + timedelta(seconds=2), 7.0)
    # make it unavailable by toggling flags -> must not normalize
    object.__setattr__(r, "kpi_available", False)
    object.__setattr__(r, "kpi_score", None)
    out3 = sn.normalize_records((r,))
    # strategy calls unchanged
    assert len(strategy.calls) == 2


def test_normalized_values_written_correctly_and_are_floats(config):
    # use strategy that echoes inputs multiplied
    class MulStrategy(FakeStrategy):
        def normalize(self, values):
            super().normalize(values)
            return tuple(float(v) * 2.0 for v in values)

    strat = MulStrategy()
    sn = ScoreNormalizer(config, strat)
    t = now()
    r1 = kpi_record(t, 1.5)
    r2 = log_record(t + timedelta(seconds=1), -2.0)
    out = sn.normalize_records((r1, r2))
    # check normalized fields
    assert out[0].kpi_score_normalized == pytest.approx(3.0)
    assert out[1].log_score_normalized == pytest.approx(-4.0)
    assert isinstance(out[0].kpi_score_normalized, float)
    assert isinstance(out[1].log_score_normalized, float)


# _collect helpers and _update_record -----------------------------------

def test_collect_helpers_and_update_record(config):
    strat = FakeStrategy()
    sn = ScoreNormalizer(config, strat)
    t = now()
    a = kpi_record(t, 1.0)
    b = kpi_record(t + timedelta(seconds=1), 2.0)
    indices, vals = sn._collect_kpi_scores([a, b])
    assert indices == [0, 1]
    assert vals == [1.0, 2.0]
    # update record
    new = sn._update_record(a, kpi_score_normalized=9.9)
    assert new.kpi_score_normalized == pytest.approx(9.9)
    assert a.kpi_score_normalized is None


# _apply_normalization exception translation and logging ---------------

def test_apply_normalization_translates_strategy_exceptions_and_logs(caplog, config):
    strat = FakeStrategy(raise_exc=StrategyValidationError("bad"))
    sn = ScoreNormalizer(config, strat)
    t = now()
    r = kpi_record(t, 1.0)
    caplog.set_level("INFO")
    with pytest.raises(ScoreNormalizationValidationError):
        sn.normalize_records((r,))
    # ensure error logged
    assert any("KPI normalization failed" in rec.message or "LOG normalization failed" in rec.message for rec in caplog.records)


# Diagnostics ------------------------------------------------------------

def test_diagnostics_content_and_immutability(config):
    strat = FakeStrategy()
    sn = ScoreNormalizer(config, strat)
    t = now()
    r1 = kpi_record(t, 1.0)
    r2 = log_record(t + timedelta(seconds=1), 2.0)
    _ = sn.normalize_records((r1, r2))
    d = sn.export_diagnostics()
    assert isinstance(d, MappingProxyType)
    keys = set(d.keys())
    assert {"strategy_name", "record_count", "kpi_records_normalized", "log_records_normalized", "strategy_metadata"}.issubset(keys)
    # metadata preserved
    assert isinstance(d["strategy_metadata"], dict)
    # updating diagnostics should require clear
    sn.clear()
    assert sn.export_diagnostics() == MappingProxyType({})


# Determinism -----------------------------------------------------------

def test_repeated_runs_deterministic(config):
    strat = FakeStrategy()
    sn = ScoreNormalizer(config, strat)
    t = now()
    r1 = kpi_record(t, 1.0)
    r2 = log_record(t + timedelta(seconds=1), 2.0)
    out1 = sn.normalize_records((r1, r2))
    diag1 = sn.export_diagnostics()
    out2 = sn.normalize_records((r1, r2))
    diag2 = sn.export_diagnostics()
    assert out1 == out2
    assert diag1 == diag2


# Exception hierarchy ---------------------------------------------------

def test_exception_hierarchy():
    assert issubclass(ScoreNormalizationValidationError, ScoreNormalizerError)
    assert issubclass(ScoreNormalizationConfigurationError, ScoreNormalizerError)


# Type safety ------------------------------------------------------------

def test_returned_types_and_mapping_types(config):
    strat = FakeStrategy()
    sn = ScoreNormalizer(config, strat)
    t = now()
    r = kpi_record(t, 1.0)
    out = sn.normalize_records((r,))
    assert isinstance(out, tuple)
    assert isinstance(out[0], FusionRecord)
    assert isinstance(sn.export_diagnostics(), MappingProxyType)


# Edge validations ------------------------------------------------------

def test_normalize_record_wrapper(config):
    strat = FakeStrategy()
    sn = ScoreNormalizer(config, strat)
    r = kpi_record(now(), 2.0)
    out = sn.normalize_record(r)
    assert isinstance(out, FusionRecord)

    with pytest.raises(ScoreNormalizationValidationError):
        sn.normalize_record(None)  # type: ignore[arg-type]


# End of file
