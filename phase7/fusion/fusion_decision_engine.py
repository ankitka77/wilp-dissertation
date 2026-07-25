"""Fusion decision engine for Phase 7.

This module provides `FusionDecisionEngine`, a small component that
combines normalized KPI and LOG scores from `FusionRecord` objects into a
final fused score and binary decision label according to the configured
fusion strategy in `FusionConfig`.

Responsibilities
- Consume already-normalized `FusionRecord` tuples
- Compute `fused_score` and `final_label` per record
- Return new immutable `FusionRecord` instances preserving input order
- Expose immutable execution statistics

The implementation is intentionally limited to decision logic and does not
perform ingestion, alignment, aggregation, or normalization.
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Mapping, Tuple
import logging
import math

from phase7.config.fusion_config import FusionConfig, FusionStrategyName
from phase7.models.fusion_record import FusionRecord, FusionRecordValidationError

logger = logging.getLogger("project.phase7.fusion")


# Exceptions -------------------------------------------------------------


class FusionDecisionError(RuntimeError):
    """Base exception for fusion decision failures."""


class FusionDecisionValidationError(FusionDecisionError):
    """Raised when input records violate validation rules."""


class FusionDecisionConfigurationError(FusionDecisionError):
    """Raised when engine is misconfigured."""


# Engine -----------------------------------------------------------------


class FusionDecisionEngine:
    """Combine normalized KPI and LOG scores into a final fusion decision.

    Public API
    - `fuse_records(records) -> Tuple[FusionRecord, ...]`
    - `fuse_record(record) -> FusionRecord`
    - `export_statistics() -> Mapping[str, object]`
    - `clear()`
    """

    def __init__(self, config: FusionConfig) -> None:
        if config is None:
            raise FusionDecisionConfigurationError("config is required")
        self._config = config
        self._logger = logger
        # immutable statistics mapping
        self._statistics: Mapping[str, object] = MappingProxyType({})

        # Validate basic config consistency for supported strategies
        self._validate_config()

        # Prepare strategy-specific implementation (keeps compute logic isolated)
        self._strategy_impl = self._get_strategy_impl()

        self._logger.info("Selected fusion strategy: %s", self._config.fusion.strategy.value)

    # Public API ---------------------------------------------------------
    # Named labels instead of magic values
    NORMAL_LABEL: int = 0
    ANOMALY_LABEL: int = 1

    def fuse_records(self, records: Tuple[FusionRecord, ...]) -> Tuple[FusionRecord, ...]:
        """Fuse a tuple of already-normalized `FusionRecord` objects.

        Returns a new immutable tuple of `FusionRecord` objects with
        `fused_score`, `final_label`, contribution fields, and weights set
        where applicable. Order is preserved.
        """
        self._validate_records(records)

        processed = []
        fused_count = 0
        anomalies = 0
        normal_count = 0

        for r in records:
            try:
                final_score, kpi_contrib, log_contrib = self._strategy_impl(r)
            except FusionDecisionValidationError:
                # propagate validation to caller after logging
                self._logger.error("Record validation failed during fusion")
                raise

            if final_score is None:
                # leave record unset for fused fields
                new = self._update_record(r, kpi_weight=self._config.fusion.kpi_weight, log_weight=self._config.fusion.log_weight)
            else:
                fused_count += 1
                label = self._apply_threshold(final_score)
                if label == self.ANOMALY_LABEL:
                    anomalies += 1
                else:
                    normal_count += 1
                new = self._update_record(
                    r,
                    fused_score=float(final_score),
                    final_label=int(label),
                    kpi_contribution=(None if kpi_contrib is None else float(kpi_contrib)),
                    log_contribution=(None if log_contrib is None else float(log_contrib)),
                    kpi_weight=self._config.fusion.kpi_weight,
                    log_weight=self._config.fusion.log_weight,
                )

            processed.append(new)

        # Build immutable statistics
        self._build_statistics(
            records_processed=len(records),
            records_fused=fused_count,
            anomalies_detected=anomalies,
            normal_records=normal_count,
        )

        self._logger.info(
            "Fusion summary: processed=%d fused=%d anomalies=%d",
            len(records),
            fused_count,
            anomalies,
        )

        return tuple(processed)

    def fuse_record(self, record: FusionRecord) -> FusionRecord:
        """Fuse a single `FusionRecord` and return a new record."""
        if record is None or not isinstance(record, FusionRecord):
            raise FusionDecisionValidationError("record must be a FusionRecord")
        return self.fuse_records((record,))[0]

    def export_statistics(self) -> Mapping[str, object]:
        """Return immutable execution statistics for the last run."""
        return self._statistics

    def clear(self) -> None:
        """Clear stored statistics."""
        self._statistics = MappingProxyType({})

    # Private helpers ---------------------------------------------------
    def _validate_config(self) -> None:
        # Basic validation of weights and threshold
        s = self._config.fusion
        try:
            k = float(s.kpi_weight)
            l = float(s.log_weight)
            t = float(s.threshold)
        except (TypeError, ValueError) as exc:
            raise FusionDecisionConfigurationError("Invalid numeric values in fusion configuration") from exc

        if not math.isfinite(k) or not math.isfinite(l):
            raise FusionDecisionConfigurationError("Fusion weights must be finite numbers")
        if not math.isfinite(t):
            raise FusionDecisionConfigurationError("Fusion threshold must be a finite number")

        if s.strategy == FusionStrategyName.WEIGHTED_AVERAGE:
            # accept any non-negative weights; zero-sum will be handled at compute time
            if k < 0 or l < 0:
                raise FusionDecisionConfigurationError("Fusion weights must be non-negative")

    def _validate_records(self, records: Tuple[FusionRecord, ...]) -> None:
        if records is None:
            raise FusionDecisionValidationError("records must not be None")
        if not isinstance(records, tuple):
            raise FusionDecisionValidationError("records must be provided as an immutable tuple")
        if len(records) == 0:
            raise FusionDecisionValidationError("records must not be empty")
        for idx, r in enumerate(records):
            self._validate_record(r, idx)

    def _validate_record(self, r: FusionRecord, idx: int) -> None:
        if not isinstance(r, FusionRecord):
            raise FusionDecisionValidationError(f"item at index {idx} is not a FusionRecord")
        # If a source is marked available, it must have a normalized score
        if getattr(r, "kpi_available", False):
            val = getattr(r, "kpi_score_normalized", None)
            if val is None:
                raise FusionDecisionValidationError(f"record at index {idx} marked kpi_available but missing kpi_score_normalized")
            try:
                f = float(val)
            except (TypeError, ValueError):
                raise FusionDecisionValidationError(f"record at index {idx} has non-numeric kpi_score_normalized")
            if not math.isfinite(f):
                raise FusionDecisionValidationError(f"record at index {idx} has non-finite kpi_score_normalized")

        if getattr(r, "log_available", False):
            val = getattr(r, "log_score_normalized", None)
            if val is None:
                raise FusionDecisionValidationError(f"record at index {idx} marked log_available but missing log_score_normalized")
            try:
                f = float(val)
            except (TypeError, ValueError):
                raise FusionDecisionValidationError(f"record at index {idx} has non-numeric log_score_normalized")
            if not math.isfinite(f):
                raise FusionDecisionValidationError(f"record at index {idx} has non-finite log_score_normalized")

    def _compute_final_score(self, r: FusionRecord) -> Tuple[float | None, float | None, float | None]:
        """Compute final fused score and per-source contributions.

        Returns a tuple `(final_score, kpi_contribution, log_contribution)`.
        If neither source is available, `final_score` is `None`.
        """
        k_available = bool(getattr(r, "kpi_available", False))
        l_available = bool(getattr(r, "log_available", False))

        k_val = None
        l_val = None
        if k_available:
            k = getattr(r, "kpi_score_normalized", None)
            k_val = float(k)  # validated earlier
        if l_available:
            l = getattr(r, "log_score_normalized", None)
            l_val = float(l)

        # No available sources -> leave fused score unset
        if not k_available and not l_available:
            return None, None, None

        # Deprecated: calls now delegated to strategy-specific implementation.
        # Keep for backwards-compatibility by delegating to the selected impl.
        return self._get_strategy_impl()(r)

    def _apply_threshold(self, final_score: float) -> int:
        thr = float(self._config.fusion.threshold)
        return self.ANOMALY_LABEL if final_score >= thr else self.NORMAL_LABEL

    # Strategy dispatch / implementations --------------------------------
    def _get_strategy_impl(self):
        """Return a callable implementing the selected fusion strategy.

        The callable accepts a `FusionRecord` and returns a tuple
        `(final_score, kpi_contribution, log_contribution)`.
        """
        strat = self._config.fusion.strategy
        if strat == FusionStrategyName.WEIGHTED_AVERAGE:
            return self._weighted_average_impl
        # unknown strategies result in a configuration error when selected
        raise FusionDecisionConfigurationError(f"Unsupported fusion strategy: {strat}")

    def _weighted_average_impl(self, r: FusionRecord) -> Tuple[float | None, float | None, float | None]:
        """Weighted-average fusion implementation (isolated for future strategies)."""
        k_available = bool(getattr(r, "kpi_available", False))
        l_available = bool(getattr(r, "log_available", False))

        k_val = None
        l_val = None
        if k_available:
            k_val = float(getattr(r, "kpi_score_normalized"))
        if l_available:
            l_val = float(getattr(r, "log_score_normalized"))

        if not k_available and not l_available:
            return None, None, None

        kw = float(self._config.fusion.kpi_weight)
        lw = float(self._config.fusion.log_weight)

        if k_available and l_available:
            k_contrib = kw * k_val
            l_contrib = lw * l_val
            final = k_contrib + l_contrib
            return final, k_contrib, l_contrib

        if k_available:
            return k_val, k_val, None

        return l_val, None, l_val

    def _update_record(self, record: FusionRecord, **fields) -> FusionRecord:
        try:
            return record.replace(**fields)
        except FusionRecordValidationError:
            # propagate as decision validation error for caller clarity
            raise FusionDecisionValidationError("Failed to construct fused FusionRecord")

    def _build_statistics(self, *, records_processed: int, records_fused: int, anomalies_detected: int, normal_records: int) -> None:
        stats = {
            "fusion_strategy": self._config.fusion.strategy.value,
            "records_processed": int(records_processed),
            "records_fused": int(records_fused),
            "anomalies_detected": int(anomalies_detected),
            "normal_records": int(normal_records),
            "threshold": float(self._config.fusion.threshold),
            "weights": {"kpi_weight": float(self._config.fusion.kpi_weight), "log_weight": float(self._config.fusion.log_weight)},
        }
        # Preserve logical ordering defined by the architecture
        ordered_keys = [
            "fusion_strategy",
            "records_processed",
            "records_fused",
            "anomalies_detected",
            "normal_records",
            "threshold",
            "weights",
        ]
        ordered = {k: stats[k] for k in ordered_keys}
        self._statistics = MappingProxyType(ordered)


__all__ = ["FusionDecisionEngine", "FusionDecisionError", "FusionDecisionValidationError", "FusionDecisionConfigurationError"]
