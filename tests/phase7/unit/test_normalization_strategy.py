import math
from types import MappingProxyType
from typing import Tuple

import pytest

from phase7.normalization.normalization_strategy import (
    IdentityNormalization,
    MinMaxNormalization,
    NormalizationConfigurationError,
    NormalizationValidationError,
    NormalizationStrategyError,
    ZScoreNormalization,
)


# Fixtures -----------------------------------------------------------------

@pytest.fixture
def default_minmax() -> MinMaxNormalization:
    return MinMaxNormalization()


@pytest.fixture
def custom_minmax() -> MinMaxNormalization:
    return MinMaxNormalization(epsilon=1e-6)


@pytest.fixture
def identity() -> IdentityNormalization:
    return IdentityNormalization()


@pytest.fixture
def zscore() -> ZScoreNormalization:
    return ZScoreNormalization()


# Helper builders ----------------------------------------------------------

def tup(*vals) -> Tuple[float, ...]:
    return tuple(vals)


# Construction & metadata -------------------------------------------------

def test_minmax_default_epsilon_and_metadata(default_minmax):
    meta = default_minmax.get_metadata()
    assert isinstance(meta, MappingProxyType)
    # contains strategy and epsilon keys and deterministic ordering
    assert list(meta.keys()) == sorted(list(meta.keys()))
    assert meta["strategy"] == "min_max"
    assert math.isclose(float(meta["epsilon"]), 1e-8)


def test_minmax_custom_epsilon_and_invalid():
    m = MinMaxNormalization(epsilon=1e-4)
    assert math.isclose(float(m.get_metadata()["epsilon"]), 1e-4)
    with pytest.raises(NormalizationConfigurationError):
        MinMaxNormalization(epsilon=0.0)
    with pytest.raises(NormalizationConfigurationError):
        MinMaxNormalization(epsilon=-1.0)


# Validation branches -----------------------------------------------------

@pytest.mark.parametrize("bad", [None, (), [1.0], ("a",), (1, None)])
def test_validate_bad_inputs_raise(bad, default_minmax):
    with pytest.raises(NormalizationValidationError):
        default_minmax.normalize(bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_validate_nan_and_infinite(bad, default_minmax):
    with pytest.raises(NormalizationValidationError):
        default_minmax.normalize((bad,))


def test_validate_non_numeric_element(default_minmax):
    with pytest.raises(NormalizationValidationError):
        default_minmax.normalize((object(),))


# Min-max behavior -------------------------------------------------------

@pytest.mark.parametrize(
    "vals,expected",
    [
        (tup(5.0,), tup(0.5,)),  # single value -> identical behavior: minimum==maximum -> outside [0,1] -> 0.5
    ],
)
def test_single_value_behavior(vals, expected):
    m = MinMaxNormalization()
    out = m.normalize(vals)
    # For single value 5.0, identical outside [0,1] -> 0.5
    assert out == expected


def test_multiple_values_ascending_and_descending(default_minmax):
    asc = (0.0, 0.5, 1.0)
    desc = (1.0, 0.5, 0.0)
    out1 = default_minmax.normalize(asc)
    out2 = default_minmax.normalize(desc)
    # Normalizing asc should yield values in [0,1] and deterministic
    assert all(0.0 <= v <= 1.0 for v in out1)
    # Descending should produce symmetric normalized values but same set
    assert tuple(sorted(out1)) == tuple(sorted(out2))


@pytest.mark.parametrize(
    "vals",
    [
        tup(-1.0, 0.0, 1.0),
        tup(1e9, 1e9 + 1.0, 1e9 + 2.0),
        tup(1e-9, 2e-9, 3e-9),
        tup(2.5, 2.5, 2.5),
    ],
)
def test_various_numeric_inputs(vals, custom_minmax):
    out = custom_minmax.normalize(vals)
    assert isinstance(out, tuple)
    assert all(isinstance(x, float) for x in out)
    assert all(0.0 <= x <= 1.0 for x in out)


# Identical values handling -----------------------------------------------

def test_identical_values_within_unit_interval_preserved():
    m = MinMaxNormalization()
    vals = tup(0.2, 0.2, 0.2)
    out = m.normalize(vals)
    # identical and inside [0,1] => preserved
    assert out == vals


def test_identical_values_outside_unit_interval_normalized_to_half():
    m = MinMaxNormalization()
    vals = tup(5.0, 5.0, 5.0)
    out = m.normalize(vals)
    assert out == tup(0.5, 0.5, 0.5)


@pytest.mark.parametrize("vals", [tup(0.0, 0.0), tup(1.0, 1.0), tup(-3.0, -3.0)])
def test_all_zeros_ones_negative_identical(vals):
    m = MinMaxNormalization()
    out = m.normalize(vals)
    if all(0.0 <= v <= 1.0 for v in vals):
        assert out == vals
    else:
        assert out == tuple(0.5 for _ in vals)


# Epsilon & division safety ----------------------------------------------

def test_epsilon_prevents_divide_by_zero():
    # craft values with very small range
    m = MinMaxNormalization(epsilon=1e-12)
    vals = tup(1.0, 1.0 + 1e-14)
    out = m.normalize(vals)
    assert all(0.0 <= x <= 1.0 for x in out)


def test_epsilon_reflected_in_metadata():
    m = MinMaxNormalization(epsilon=1e-6)
    # metadata from construction
    meta = m.get_metadata()
    assert math.isclose(float(meta["epsilon"]), 1e-6)
    # after normalize, metadata updated
    _ = m.normalize(tup(2.0, 4.0))
    meta2 = m.get_metadata()
    assert meta2["input_count"] == 2
    assert math.isfinite(float(meta2["minimum"]))
    assert math.isfinite(float(meta2["maximum"]))


# Clamping ---------------------------------------------------------------

def test_clamping_bounds(default_minmax):
    m = MinMaxNormalization()
    vals = tup(-100.0, 0.0, 100.0)
    out = m.normalize(vals)
    assert all(0.0 <= x <= 1.0 for x in out)


# Immutability -----------------------------------------------------------

def test_caller_tuple_unchanged_and_return_immutable_and_metadata_immutable():
    m = MinMaxNormalization()
    vals = tup(10.0, 20.0)
    vals_copy = tuple(vals)
    out = m.normalize(vals)
    assert vals == vals_copy
    with pytest.raises(TypeError):
        out[0] = 1.0  # type: ignore[misc]
    meta = m.get_metadata()
    assert isinstance(meta, MappingProxyType)
    with pytest.raises(TypeError):
        meta["minimum"] = 0.0


# Determinism ------------------------------------------------------------

def test_repeated_calls_are_deterministic():
    m = MinMaxNormalization()
    vals = tup(3.0, 6.0, 9.0)
    out1 = m.normalize(vals)
    meta1 = m.get_metadata()
    out2 = m.normalize(vals)
    meta2 = m.get_metadata()
    assert out1 == out2
    assert meta1 == meta2


# Helper methods coverage ------------------------------------------------

def test_validate_values_helper(identity):
    # _validate_values should raise for empty and return converted tuple otherwise
    with pytest.raises(NormalizationValidationError):
        identity._validate_values(())
    res = identity._validate_values(tup(1, 2, 3))
    assert isinstance(res, tuple)
    assert all(isinstance(x, float) for x in res)


def test_clamp_internal():
    m = MinMaxNormalization()
    assert m._clamp(-1.0) == 0.0
    assert m._clamp(2.0) == 1.0
    assert m._clamp(0.5) == 0.5


# Identity strategy ------------------------------------------------------

def test_identity_returns_floats_and_updates_metadata(identity):
    vals = tup(1, 2, 3)
    out = identity.normalize(vals)
    assert out == (1.0, 2.0, 3.0)
    meta = identity.get_metadata()
    assert meta["strategy"] == "identity"
    assert meta["input_count"] == 3
    assert isinstance(meta, MappingProxyType)


def test_identity_validation_reused(identity):
    with pytest.raises(NormalizationValidationError):
        identity.normalize(None)  # type: ignore[arg-type]


# Z-score strategy -------------------------------------------------------

def test_zscore_not_implemented_and_metadata(zscore):
    assert zscore.get_name() == "z_score"
    meta = zscore.get_metadata()
    assert meta["strategy"] == "z_score"
    with pytest.raises(NotImplementedError):
        zscore.normalize(tup(1.0, 2.0))


# Exceptions typing ------------------------------------------------------

def test_exceptions_types():
    assert issubclass(NormalizationValidationError, NormalizationStrategyError)
    assert issubclass(NormalizationConfigurationError, NormalizationStrategyError)


# Type safety ------------------------------------------------------------

def test_returned_types_are_floats():
    m = MinMaxNormalization()
    vals = tup(2, 4)
    out = m.normalize(vals)
    assert all(isinstance(x, float) for x in out)


# End of file
