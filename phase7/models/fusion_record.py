"""Canonical immutable FusionRecord data model for Phase 7.

This module implements the frozen `FusionRecord` dataclass described by the
Phase 7 Architecture and Design documents. It provides strict validation on
construction, deterministic (stable) serialization to dictionary/JSON, helper
constructors for source-level records, and convenience methods used across the
pipeline.

Do NOT change the architecture or introduce external dependencies. The class
is intentionally self-contained and depends only on the Python standard
library and the frozen `fusion_config` for configuration values when needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Mapping, Optional
from collections.abc import Mapping as _MappingABC
from types import MappingProxyType
from copy import deepcopy
import math
import json


class _ImmutableFrozenSet(frozenset):
    """frozenset subclass which provides mutation methods that raise TypeError.

    This allows code that expects a `.add` attribute to raise `TypeError`
    (instead of `AttributeError`) when attempted to mutate, matching tests'
    expectations about immutability semantics.
    """
    def add(self, *args, **kwargs):  # pragma: no cover - trivial wrapper
        raise TypeError("cannot modify immutable set")

    def remove(self, *args, **kwargs):  # pragma: no cover - trivial wrapper
        raise TypeError("cannot modify immutable set")


def _deep_freeze(value: Any) -> Any:
    """Recursively convert mutable containers into immutable equivalents.

    - dict/mapping -> MappingProxyType with frozen values
    - list -> tuple
    - set -> frozenset
    - tuple -> tuple with frozen values

    Primitive immutables are returned unchanged.
    """
    if isinstance(value, _MappingABC):
        # preserve key types as-is but freeze values
        frozen = {k: _deep_freeze(v) for k, v in value.items()}
        return MappingProxyType(frozen)
    if isinstance(value, list):
        return tuple(_deep_freeze(v) for v in value)
    if isinstance(value, set):
        return _ImmutableFrozenSet(_deep_freeze(v) for v in value)
    if isinstance(value, tuple):
        return tuple(_deep_freeze(v) for v in value)
    return value


def _deep_thaw(value: Any) -> Any:
    """Recursively convert frozen immutable structures into JSON-serializable types.

    - MappingProxyType or Mapping -> dict (with thawed values)
    - tuple -> list
    - frozenset/set -> list (deterministic ordering via JSON-key)
    - list -> list (thawed elements)
    - primitives returned unchanged
    """
    # Mapping (including MappingProxyType)
    if isinstance(value, _MappingABC):
        return {k: _deep_thaw(v) for k, v in value.items()}
    # tuple/list
    if isinstance(value, tuple) or isinstance(value, list):
        return [_deep_thaw(v) for v in value]
    # frozenset/set -> deterministic list
    if isinstance(value, frozenset) or isinstance(value, set):
        thawed = [_deep_thaw(v) for v in value]
        try:
            # sort by JSON representation for deterministic ordering
            thawed.sort(key=lambda e: json.dumps(e, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        except Exception:
            # fallback to default order if sorting fails
            pass
        return thawed
    # primitives
    return value


class FusionRecordValidationError(ValueError):
    """Raised when a constructed FusionRecord violates the canonical contract."""


class SourceType(str, Enum):
    KPI = "KPI"
    LOG = "LOG"


@dataclass(frozen=True, slots=True)
class FusionRecord:
    """Immutable canonical FusionRecord used across Phase 7 pipeline.

    Fields reflect the frozen design document (window-level canonical unit).
    All datetime fields are timezone-aware and normalized to UTC.
    """

    # Window boundaries (timezone-aware UTC datetimes)
    window_ts: datetime
    window_end_ts: datetime

    # Optional entity and source identifiers
    entity_id: Optional[str] = None
    source_type: Optional[SourceType] = None
    source_record_id: Optional[str] = None

    # Raw (pre-normalization) scores from sources
    kpi_score: Optional[float] = None
    log_score: Optional[float] = None

    # Normalized scores (populated during normalization stage)
    kpi_score_normalized: Optional[float] = None
    log_score_normalized: Optional[float] = None

    # Availability flags and missing-data metadata
    kpi_available: bool = False
    log_available: bool = False
    missing_reason: Optional[str] = None

    # Configured or effective weights
    kpi_weight: Optional[float] = None
    log_weight: Optional[float] = None

    # Contribution values computed by fusion strategy
    kpi_contribution: Optional[float] = None
    log_contribution: Optional[float] = None

    # Fused outputs and decision metadata
    fused_score: Optional[float] = None
    final_label: Optional[int] = None
    decision_reason: Optional[str] = None
    decision_metadata: Mapping[str, Any] = field(default_factory=dict)

    # Source-level metadata (lineage, provenance, record counts, etc.)
    source_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Validate mapping types for metadata before any mutation
        if not isinstance(self.decision_metadata, _MappingABC):
            raise FusionRecordValidationError("decision_metadata must be a mapping")
        if not isinstance(self.source_metadata, _MappingABC):
            raise FusionRecordValidationError("source_metadata must be a mapping")

        # Normalize timezone-aware datetimes to UTC
        if self.window_ts.tzinfo is None or self.window_ts.tzinfo.utcoffset(self.window_ts) is None:
            raise FusionRecordValidationError("window_ts must be timezone-aware (UTC)")
        if self.window_end_ts.tzinfo is None or self.window_end_ts.tzinfo.utcoffset(self.window_end_ts) is None:
            raise FusionRecordValidationError("window_end_ts must be timezone-aware (UTC)")

        # Normalize to UTC
        object.__setattr__(self, "window_ts", self.window_ts.astimezone(timezone.utc))
        object.__setattr__(self, "window_end_ts", self.window_end_ts.astimezone(timezone.utc))

        if self.window_end_ts <= self.window_ts:
            raise FusionRecordValidationError("window_end_ts must be strictly after window_ts")

        # Validate string identifiers
        if self.entity_id is not None:
            if not isinstance(self.entity_id, str) or not self.entity_id.strip():
                raise FusionRecordValidationError("entity_id must be a non-empty string when provided")
            object.__setattr__(self, "entity_id", self.entity_id.strip())
        if self.source_record_id is not None:
            if not isinstance(self.source_record_id, str) or not self.source_record_id.strip():
                raise FusionRecordValidationError("source_record_id must be a non-empty string when provided")
            object.__setattr__(self, "source_record_id", self.source_record_id.strip())

        # Availability consistency: if a source is marked available it must have a score
        # final_label, if present, must be 0 or 1
        if self.final_label is not None and self.final_label not in {0, 1}:
            raise FusionRecordValidationError("final_label must be 0, 1, or None")

        # Validate numeric fields for finiteness early so numeric issues are
        # reported before availability/consistency checks that depend on them.
        _validate_finite_numeric("kpi_score", self.kpi_score)
        _validate_finite_numeric("log_score", self.log_score)
        _validate_finite_numeric("kpi_score_normalized", self.kpi_score_normalized)
        _validate_finite_numeric("log_score_normalized", self.log_score_normalized)
        _validate_finite_numeric("kpi_weight", self.kpi_weight)
        _validate_finite_numeric("log_weight", self.log_weight)
        _validate_finite_numeric("kpi_contribution", self.kpi_contribution)
        _validate_finite_numeric("log_contribution", self.log_contribution)
        _validate_finite_numeric("fused_score", self.fused_score)

        # Availability consistency: if a source is marked available it must have a score
        if self.kpi_available and self.kpi_score is None:
            raise FusionRecordValidationError("kpi_available is True but kpi_score is missing")
        if self.log_available and self.log_score is None:
            raise FusionRecordValidationError("log_available is True but log_score is missing")

        # If a score is present, the corresponding availability flag should be True
        if self.kpi_score is not None and not self.kpi_available:
            raise FusionRecordValidationError("kpi_score provided while kpi_available is False")
        if self.log_score is not None and not self.log_available:
            raise FusionRecordValidationError("log_score provided while log_available is False")

        # Replace metadata with recursively frozen immutable equivalents
        object.__setattr__(self, "decision_metadata", _deep_freeze(dict(self.decision_metadata)))
        object.__setattr__(self, "source_metadata", _deep_freeze(dict(self.source_metadata)))

    # Construction helpers -------------------------------------------------
    @classmethod
    def _ensure_utc(cls, dt: datetime) -> datetime:
        if dt.tzinfo is None:
            raise FusionRecordValidationError("provided datetime must be timezone-aware (UTC)")
        return dt.astimezone(timezone.utc)

    @classmethod
    def from_kpi_source(
        cls,
        window_ts: datetime,
        window_end_ts: datetime,
        source_record_id: Optional[str],
        kpi_score: float,
        *,
        entity_id: Optional[str] = None,
        source_metadata: Mapping[str, Any] | None = None,
    ) -> "FusionRecord":
        """Construct a source-level FusionRecord representing a KPI row mapped to a window."""

        return cls(
            window_ts=cls._ensure_utc(window_ts),
            window_end_ts=cls._ensure_utc(window_end_ts),
            entity_id=entity_id,
            source_type=SourceType.KPI,
            source_record_id=source_record_id,
            kpi_score=float(kpi_score),
            kpi_available=True,
            source_metadata=dict(source_metadata or {}),
        )

    @classmethod
    def from_log_source(
        cls,
        window_ts: datetime,
        window_end_ts: datetime,
        source_record_id: Optional[str],
        log_score: float,
        *,
        entity_id: Optional[str] = None,
        source_metadata: Mapping[str, Any] | None = None,
    ) -> "FusionRecord":
        """Construct a source-level FusionRecord representing a Log row mapped to a window."""

        return cls(
            window_ts=cls._ensure_utc(window_ts),
            window_end_ts=cls._ensure_utc(window_end_ts),
            entity_id=entity_id,
            source_type=SourceType.LOG,
            source_record_id=source_record_id,
            log_score=float(log_score),
            log_available=True,
            source_metadata=dict(source_metadata or {}),
        )

    # Serialization / deserialization -------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dictionary representation with deterministic ordering."""

        def _dt_to_iso(dt: datetime) -> str:
            # Use RFC3339-like formatting with Z for UTC
            return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

        payload: Dict[str, Any] = {
            "window_ts": _dt_to_iso(self.window_ts),
            "window_end_ts": _dt_to_iso(self.window_end_ts),
            "entity_id": self.entity_id,
            "source_type": self.source_type.value if self.source_type is not None else None,
            "source_record_id": self.source_record_id,
            "kpi_score": self.kpi_score,
            "log_score": self.log_score,
            "kpi_score_normalized": self.kpi_score_normalized,
            "log_score_normalized": self.log_score_normalized,
            "kpi_available": self.kpi_available,
            "log_available": self.log_available,
            "missing_reason": self.missing_reason,
            "kpi_weight": self.kpi_weight,
            "log_weight": self.log_weight,
            "kpi_contribution": self.kpi_contribution,
            "log_contribution": self.log_contribution,
            "fused_score": self.fused_score,
            "final_label": self.final_label,
            "decision_reason": self.decision_reason,
            "decision_metadata": _deep_thaw(self.decision_metadata),
            "source_metadata": _deep_thaw(self.source_metadata),
        }
        # Deterministic ordering for external consumers: sort keys when serializing
        return payload

    def to_json(self) -> str:
        """Return a deterministic JSON string representation of the record."""

        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def _parse_iso_datetime(cls, value: str) -> datetime:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(value)
        except Exception as exc:  # pragma: no cover - defensive
            raise FusionRecordValidationError(f"Invalid ISO datetime: {value}") from exc
        if dt.tzinfo is None:
            # interpret naive as UTC to remain explicit in the pipeline
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FusionRecord":
        """Create a FusionRecord from a mapping parsed from JSON/YAML.

        This method performs validation of required types and converts
        ISO-formatted datetimes into timezone-aware UTC datetimes.
        """
        if not isinstance(data, _MappingABC):
            raise FusionRecordValidationError("from_dict requires a mapping input")

        # required keys
        for key in ("window_ts", "window_end_ts"):
            if key not in data:
                raise FusionRecordValidationError(f"Missing required key in input mapping: {key}")

        window_ts = cls._parse_iso_datetime(str(data["window_ts"]))
        window_end_ts = cls._parse_iso_datetime(str(data["window_end_ts"]))

        source_type_val = data.get("source_type")
        source_type = None
        if source_type_val is not None:
            try:
                source_type = SourceType(source_type_val)
            except ValueError as exc:
                raise FusionRecordValidationError(f"Invalid source_type: {source_type_val}") from exc

        return cls(
            window_ts=window_ts,
            window_end_ts=window_end_ts,
            entity_id=data.get("entity_id"),
            source_type=source_type,
            source_record_id=data.get("source_record_id"),
            kpi_score=_opt_float(data.get("kpi_score")),
            log_score=_opt_float(data.get("log_score")),
            kpi_score_normalized=_opt_float(data.get("kpi_score_normalized")),
            log_score_normalized=_opt_float(data.get("log_score_normalized")),
            kpi_available=bool(data.get("kpi_available", False)),
            log_available=bool(data.get("log_available", False)),
            missing_reason=data.get("missing_reason"),
            kpi_weight=_opt_float(data.get("kpi_weight")),
            log_weight=_opt_float(data.get("log_weight")),
            kpi_contribution=_opt_float(data.get("kpi_contribution")),
            log_contribution=_opt_float(data.get("log_contribution")),
            fused_score=_opt_float(data.get("fused_score")),
            final_label=_opt_int(data.get("final_label")),
            decision_reason=data.get("decision_reason"),
            decision_metadata=data.get("decision_metadata") or {},
            source_metadata=data.get("source_metadata") or {},
        )

    @classmethod
    def from_json(cls, payload: str) -> "FusionRecord":
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise FusionRecordValidationError("Invalid JSON payload") from exc
        return cls.from_dict(data)

    # Convenience utilities -----------------------------------------------
    def to_readable_dict(self) -> Dict[str, Any]:
        """Return a human-friendly dictionary suitable for logs and debugging.

        The result is a snapshot mapping intended for readability: metadata
        fields that are empty are presented as `None` for brevity. The returned
        structure is a plain `dict` (not a live view into the frozen record).
        """

        d = dict(self.to_dict())
        # shorten metadata for readability
        if d["decision_metadata"] == {}:
            d["decision_metadata"] = None
        if d["source_metadata"] == {}:
            d["source_metadata"] = None
        return d

    def replace(self, **overrides: Any) -> "FusionRecord":
        """Return a new `FusionRecord` with the given field overrides (immutable)."""

        # Use dataclasses.replace to preserve frozen semantics
        return replace(self, **overrides)

    def __hash__(self) -> int:  # deterministic hash based on stable JSON
        return hash(self.to_json())

    def __eq__(self, other: Any) -> bool:
        """Deterministic equality based on canonical JSON representation.

        Using the stable `to_json()` ensures semantically-equivalent records
        (with potentially different internal frozen container types) compare
        equal in a way that's robust to serialization round-trips.
        """
        if not isinstance(other, FusionRecord):
            return NotImplemented
        return self.to_json() == other.to_json()


def _opt_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError) as exc:
        raise FusionRecordValidationError(f"Expected numeric value, got: {value}") from exc
    _validate_finite_numeric("value", f)
    return f


def _opt_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise FusionRecordValidationError(f"Expected integer value, got: {value}") from exc


def _validate_finite_numeric(name: str, value: Any) -> None:
    """Validate that a numeric-like value is finite (not NaN or infinite).

    Parameters
    - name: field name for descriptive error messages
    - value: numeric value to validate (expected float-able)

    Raises FusionRecordValidationError on invalid values.
    """
    if value is None:
        return
    try:
        f = float(value)
    except (TypeError, ValueError) as exc:
        raise FusionRecordValidationError(f"FusionRecord field '{name}' must be numeric") from exc
    if not math.isfinite(f):
        raise FusionRecordValidationError(f"FusionRecord field '{name}' must be a finite number (not NaN or infinity): {value}")


__all__ = ["FusionRecord", "SourceType", "FusionRecordValidationError"]
