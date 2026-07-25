"""Score normalizer for Phase 7.

This module implements `ScoreNormalizer`, a small component that applies a
configured `NormalizationStrategy` to collections of `FusionRecord` objects.
It delegates all normalization calculations to the provided strategy and
focuses on: collecting source scores, invoking the strategy independently
for KPI and LOG scores, writing normalized values back into new
`FusionRecord` instances, validating inputs, and exporting immutable
normalization diagnostics.

The class is deliberately small and uses helper methods for single
responsibilities. It never mutates caller-provided collections and returns
immutable tuples of `FusionRecord`.
"""
from __future__ import annotations

from types import MappingProxyType
from typing import List, Mapping, Tuple
import logging

from phase7.config.fusion_config import FusionConfig
from phase7.models.fusion_record import FusionRecord
from phase7.normalization.normalization_strategy import (
    NormalizationStrategy,
    NormalizationValidationError as StrategyValidationError,
)

logger = logging.getLogger("project.phase7.normalization")


# Exceptions -------------------------------------------------------------


class ScoreNormalizerError(RuntimeError):
    """Base exception for ScoreNormalizer failures."""


class ScoreNormalizationValidationError(ScoreNormalizerError):
    """Raised when input records violate validation rules."""


class ScoreNormalizationConfigurationError(ScoreNormalizerError):
    """Raised when ScoreNormalizer is misconfigured."""


# ScoreNormalizer --------------------------------------------------------


class ScoreNormalizer:
    """Applies a `NormalizationStrategy` to `FusionRecord` collections.

    Initialization parameters
    - `config`: the `FusionConfig` (used for future extension points)
    - `normalization_strategy`: an instance implementing `NormalizationStrategy`

    Public API
    - `normalize_records(records)` : normalize KPI and LOG scores independently
    - `normalize_record(record)` : normalize a single record using the strategy
    - `export_diagnostics()` : return immutable diagnostics mapping
    - `get_strategy()` : return the configured strategy instance
    - `clear()` : clear diagnostics
    """

    def __init__(self, config: FusionConfig, normalization_strategy: NormalizationStrategy) -> None:
        if config is None:
            raise ScoreNormalizationConfigurationError("config is required")
        # Accept duck-typed strategies (must provide normalize, get_name, get_metadata)
        if normalization_strategy is None:
            raise ScoreNormalizationConfigurationError("normalization_strategy must be provided and implement NormalizationStrategy")

        required_attrs = ("normalize", "get_name", "get_metadata")
        missing = [a for a in required_attrs if not hasattr(normalization_strategy, a) or not callable(getattr(normalization_strategy, a))]
        if missing:
            raise ScoreNormalizationConfigurationError("normalization_strategy must be provided and implement NormalizationStrategy")

        self._config = config
        self._strategy = normalization_strategy
        self._logger = logger
        # diagnostics stored as MappingProxyType for immutability
        self._diagnostics: Mapping[str, object] = MappingProxyType({})

        self._logger.info("Selected normalization strategy: %s", self._strategy.get_name())

    # Public API ---------------------------------------------------------
    def get_strategy(self) -> NormalizationStrategy:
        """Return the configured NormalizationStrategy instance."""
        return self._strategy

    def normalize_records(self, records: Tuple[FusionRecord, ...]) -> Tuple[FusionRecord, ...]:
        """Normalize KPI and LOG scores across the provided records.

        Parameters
        - records: an immutable tuple of `FusionRecord` objects.

        Returns
        - tuple of new `FusionRecord` objects with normalized scores populated
          where appropriate. Order is preserved. Caller collections are not
          mutated.
        """
        self._validate_records(records)

        # Work on a mutable copy for staged updates, but do not modify caller data
        updated: List[FusionRecord] = list(records)

        # KPI normalization (delegated)
        kpi_indices, kpi_scores = self._collect_kpi_scores(updated)
        kpi_count = len(kpi_scores)
        updated = self._apply_normalization(updated, kpi_indices, kpi_scores, "kpi_score_normalized", "KPI")

        # LOG normalization (delegated)
        log_indices, log_scores = self._collect_log_scores(updated)
        log_count = len(log_scores)
        updated = self._apply_normalization(updated, log_indices, log_scores, "log_score_normalized", "LOG")

        # Build diagnostics reflecting the latest strategy metadata
        self._build_diagnostics(record_count=len(records), kpi_count=kpi_count, log_count=log_count)

        # Return an immutable tuple preserving input order
        return tuple(updated)

    def normalize_record(self, record: FusionRecord) -> FusionRecord:
        """Normalize a single `FusionRecord` and return a new record.

        The method validates the input record and applies the configured
        strategy separately to KPI and LOG if they are available. This is a
        convenience wrapper around `normalize_records` for single-record use.
        """
        if record is None or not isinstance(record, FusionRecord):
            raise ScoreNormalizationValidationError("record must be a FusionRecord")
        # delegate to normalize_records to keep behavior consistent
        out = self.normalize_records((record,))
        return out[0]

    def export_diagnostics(self) -> Mapping[str, object]:
        """Return an immutable diagnostics mapping describing the last run."""
        return self._diagnostics

    def clear(self) -> None:
        """Clear stored diagnostics."""
        self._diagnostics = MappingProxyType({})

    # Private helpers ---------------------------------------------------
    def _validate_records(self, records: Tuple[FusionRecord, ...]) -> None:
        if records is None:
            raise ScoreNormalizationValidationError("records must not be None")
        if not isinstance(records, tuple):
            raise ScoreNormalizationValidationError("records must be provided as an immutable tuple")
        if len(records) == 0:
            raise ScoreNormalizationValidationError("records must not be empty")
        for idx, r in enumerate(records):
            self._validate_record(r, idx)

    def _validate_record(self, r: FusionRecord, idx: int) -> None:
        if not isinstance(r, FusionRecord):
            raise ScoreNormalizationValidationError(f"item at index {idx} is not a FusionRecord")
        # basic field presence checks
        if getattr(r, "window_ts", None) is None or getattr(r, "window_end_ts", None) is None:
            raise ScoreNormalizationValidationError(f"record at index {idx} missing required timestamps")

    def _update_record(self, record: FusionRecord, **fields) -> FusionRecord:
        """Return a new FusionRecord with updated fields using dataclass replace.

        Encapsulates record reconstruction to centralize future changes.
        """
        return record.replace(**fields)

    def _collect_kpi_scores(self, records: List[FusionRecord]) -> Tuple[List[int], List[float]]:
        indices: List[int] = []
        values: List[float] = []
        for i, r in enumerate(records):
            if getattr(r, "kpi_available", False) and getattr(r, "kpi_score", None) is not None:
                indices.append(i)
                values.append(float(r.kpi_score))
        return indices, values

    def _collect_log_scores(self, records: List[FusionRecord]) -> Tuple[List[int], List[float]]:
        indices: List[int] = []
        values: List[float] = []
        for i, r in enumerate(records):
            if getattr(r, "log_available", False) and getattr(r, "log_score", None) is not None:
                indices.append(i)
                values.append(float(r.log_score))
        return indices, values

    def _apply_normalization(
        self,
        records: List[FusionRecord],
        score_indices: List[int],
        score_values: List[float],
        field_name: str,
        source_name: str,
    ) -> List[FusionRecord]:
        """Apply normalization using the configured strategy to the given scores.

        Parameters
        - records: mutable list of FusionRecord to update
        - score_indices: indices in `records` corresponding to values
        - score_values: raw numeric values to normalize
        - field_name: name of the normalized field to set on records
        - source_name: human-readable source name for logging

        Returns the updated records list.
        """
        count = len(score_values)
        if count == 0:
            self._logger.info("No %s scores to normalize", source_name)
            return records

        try:
            normalized = self._strategy.normalize(tuple(score_values))
        except StrategyValidationError as exc:
            self._logger.error("%s normalization failed: %s", source_name, exc)
            raise ScoreNormalizationValidationError(f"{source_name} normalization failed") from exc

        # apply normalized values back into records using _update_record
        for idx, norm_val in zip(score_indices, normalized):
            records[idx] = self._update_record(records[idx], **{field_name: float(norm_val)})

        self._logger.info("%s normalized for %d record(s)", source_name, count)
        return records

    def _build_diagnostics(self, *, record_count: int, kpi_count: int, log_count: int) -> None:
        # Strategy metadata is expected to be a read-only mapping from the strategy
        strat_meta = self._strategy.get_metadata() or {}
        # Build deterministic diagnostics mapping
        diag_src = {
            "strategy_name": self._strategy.get_name(),
            "record_count": int(record_count),
            "kpi_records_normalized": int(kpi_count),
            "log_records_normalized": int(log_count),
            "strategy_metadata": dict(strat_meta),
        }
        ordered = {k: diag_src[k] for k in sorted(diag_src.keys())}
        self._diagnostics = MappingProxyType(ordered)
        # Log summary statistics
        self._logger.info(
            "Normalization summary: strategy=%s records=%d kpi=%d log=%d",
            self._strategy.get_name(),
            record_count,
            kpi_count,
            log_count,
        )


__all__ = [
    "ScoreNormalizer",
    "ScoreNormalizerError",
    "ScoreNormalizationValidationError",
    "ScoreNormalizationConfigurationError",
]
