"""Assertion helpers for Phase 7 tests.

These helpers are intentionally implementation-agnostic so they can be reused
across unit, integration, and regression suites.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from math import isclose
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd
import pandas.testing as pdt


def assert_float_equal(
    actual: float,
    expected: float,
    *,
    rel_tol: float = 1e-9,
    abs_tol: float = 1e-9,
) -> None:
    """Assert that two floating-point values are close enough."""

    if not isclose(actual, expected, rel_tol=rel_tol, abs_tol=abs_tol):
        raise AssertionError(
            f"Float mismatch: actual={actual!r}, expected={expected!r}, "
            f"rel_tol={rel_tol}, abs_tol={abs_tol}"
        )


def assert_fusion_record_equal(
    actual: Any,
    expected: Any,
    *,
    float_fields: Iterable[str] | None = None,
    excluded_fields: Iterable[str] | None = None,
    rel_tol: float = 1e-9,
    abs_tol: float = 1e-9,
) -> None:
    """Assert equality for FusionRecord-like objects or mappings."""

    actual_map = _to_mapping(actual)
    expected_map = _to_mapping(expected)
    excluded = set(excluded_fields or ())
    float_field_names = set(float_fields or ())

    actual_keys = set(actual_map) - excluded
    expected_keys = set(expected_map) - excluded
    if actual_keys != expected_keys:
        raise AssertionError(
            f"FusionRecord keys differ: actual={sorted(actual_keys)}, expected={sorted(expected_keys)}"
        )

    for key in sorted(actual_keys):
        actual_value = actual_map[key]
        expected_value = expected_map[key]
        if key in float_field_names:
            assert_float_equal(float(actual_value), float(expected_value), rel_tol=rel_tol, abs_tol=abs_tol)
            continue
        if actual_value != expected_value:
            raise AssertionError(
                f"FusionRecord field mismatch for '{key}': actual={actual_value!r}, expected={expected_value!r}"
            )


def assert_dataframe_equal(
    actual: pd.DataFrame,
    expected: pd.DataFrame,
    *,
    sort_by: Sequence[str] | None = None,
    check_like: bool = False,
    rtol: float = 1e-9,
    atol: float = 1e-9,
) -> None:
    """Assert equality between two DataFrames with optional stable sorting."""

    actual_frame = actual.copy()
    expected_frame = expected.copy()

    if sort_by:
        actual_frame = actual_frame.sort_values(list(sort_by)).reset_index(drop=True)
        expected_frame = expected_frame.sort_values(list(sort_by)).reset_index(drop=True)

    pdt.assert_frame_equal(
        actual_frame,
        expected_frame,
        check_like=check_like,
        rtol=rtol,
        atol=atol,
    )


def assert_artifact_exists(path: str | Path) -> Path:
    """Assert that an artifact exists and return its resolved path."""

    artifact_path = Path(path)
    if not artifact_path.exists():
        raise AssertionError(f"Expected artifact to exist: {artifact_path}")
    return artifact_path


def assert_manifest_valid(
    manifest: Mapping[str, Any],
    *,
    required_top_level_fields: Sequence[str] | None = None,
    required_artifact_fields: Sequence[str] | None = None,
) -> None:
    """Assert that a manifest dictionary contains the required contract fields."""

    top_level_fields = list(required_top_level_fields or [
        "manifest_version",
        "generated_on",
        "experiment_id",
        "artifacts",
    ])
    for field_name in top_level_fields:
        if field_name not in manifest:
            raise AssertionError(f"Manifest missing required field: {field_name}")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise AssertionError("Manifest field 'artifacts' must be a mapping")

    for artifact_field in list(required_artifact_fields or ["predictions"]):
        if artifact_field not in artifacts:
            raise AssertionError(
                f"Manifest artifacts missing required entry: {artifact_field}"
            )


def _to_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    raise TypeError(f"Unsupported FusionRecord comparison type: {type(value).__name__}")


__all__ = [
    "assert_artifact_exists",
    "assert_dataframe_equal",
    "assert_float_equal",
    "assert_fusion_record_equal",
    "assert_manifest_valid",
]