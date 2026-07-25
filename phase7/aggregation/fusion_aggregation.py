"""Aggregation utilities for Phase 7 Fusion Engine.

This module implements `FusionAggregation`, a focused component that
aggregates already-aligned `FusionRecord` objects into immutable
`AggregatedFusionRecord` objects suitable for downstream normalization.

Responsibilities:
- validate aligned groups
- aggregate KPI and Log scores independently and deterministically
- preserve temporal metadata and logical identifiers
- preserve provenance information
- emit immutable aggregated results

This component does NOT perform normalization, weighting, fusion,
classification, thresholding, or decision making.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Iterable, List, Mapping, Optional, Sequence, Tuple, Callable
import logging

from phase7.models.fusion_record import FusionRecord, SourceType
from phase7.config.fusion_config import FusionConfig

logger = logging.getLogger("project.phase7.aggregation")


class FusionAggregationError(RuntimeError):
    """Base exception for aggregation-related failures."""


class AggregationValidationError(FusionAggregationError):
    """Raised when input aligned groups violate aggregation expectations."""


class AggregationConfigurationError(FusionAggregationError):
    """Raised when the aggregation component is misconfigured."""


@dataclass(frozen=True, slots=True)
class AggregatedFusionRecord:
    """Immutable aggregation result for a single alignment window.

    Fields are intentionally minimal and focused on later normalization
    stages. All fields are deterministic and preserve provenance.
    """

    window_ts: datetime
    window_end_ts: datetime
    entity_id: Optional[str]

    aggregated_kpi_score: Optional[float]
    aggregated_log_score: Optional[float]

    source_record_ids_kpi: Tuple[str, ...] = field(default_factory=tuple)
    source_record_ids_log: Tuple[str, ...] = field(default_factory=tuple)

    raw_kpi_scores: Tuple[float, ...] = field(default_factory=tuple)
    raw_log_scores: Tuple[float, ...] = field(default_factory=tuple)

    source_metadata: Mapping[str, Mapping] | None = None
    group_size: int = 0


class FusionAggregation:
    """Aggregate aligned `FusionRecord` groups into `AggregatedFusionRecord`.

    Public API:
    - `aggregate(aligned_groups)` : alias for `aggregate_groups`
    - `aggregate_groups(aligned_groups)` : aggregate multiple groups
    - `aggregate_group(group)` : aggregate a single group
    - `get_aggregated_records()` : return stored aggregated results
    - `clear()` : clear stored aggregated results
    """

    def __init__(self, config: FusionConfig) -> None:
        if config is None:
            raise AggregationConfigurationError("config is required")
        self.config = config
        self._logger = logger
        self._aggregated: List[AggregatedFusionRecord] = []

    # Public API ---------------------------------------------------------
    def aggregate(self, aligned_groups: Iterable[Tuple[FusionRecord, ...]]) -> Tuple[AggregatedFusionRecord, ...]:
        """Aggregate aligned groups and return immutable tuple of results.

        This is a convenience alias that forwards to `aggregate_groups()`.
        """
        return self.aggregate_groups(aligned_groups)

    def aggregate_groups(self, aligned_groups: Iterable[Tuple[FusionRecord, ...]]) -> Tuple[AggregatedFusionRecord, ...]:
        """Aggregate multiple aligned groups.

        Parameters
        - aligned_groups: iterable of immutable tuples produced by
          `FusionAlignment`.

        Returns an immutable tuple of `AggregatedFusionRecord`.
        """
        groups = tuple(aligned_groups)
        if len(groups) == 0:
            self._logger.info("No groups provided to aggregate; returning empty tuple")
            self._aggregated = []
            return tuple()

        self._logger.info("Starting aggregation of %d group(s)", len(groups))
        self._validate_groups(groups)

        # Deterministic ordering for groups: sort by group's earliest window_ts
        def _group_key(g: Tuple[FusionRecord, ...]) -> tuple:
            return (min(r.window_ts for r in g), min((r.source_record_id or "") for r in g))

        ordered_groups = tuple(sorted(groups, key=_group_key))

        results: List[AggregatedFusionRecord] = []
        for g in ordered_groups:
            result = self.aggregate_group(g)
            results.append(result)

        self._aggregated = list(results)
        self._logger.info("Aggregation complete: %d aggregated record(s)", len(self._aggregated))
        return tuple(self._aggregated)

    def aggregate_group(self, group: Tuple[FusionRecord, ...]) -> AggregatedFusionRecord:
        """Aggregate a single aligned group into an `AggregatedFusionRecord`.

        The input `group` is not modified.
        """
        self._validate_group(group)

        # preserve temporal span and logical id
        window_ts = min(r.window_ts for r in group)
        window_end_ts = max(r.window_end_ts for r in group)

        # entity_id must be consistent across the group (or None)
        entity_ids = {r.entity_id for r in group}
        entity_id = None
        if len(entity_ids - {None}) > 1:
            raise AggregationValidationError("Inconsistent entity_id values in group")
        if len(entity_ids) == 1:
            entity_id = next(iter(entity_ids))
        else:
            # pick the non-None if present
            for v in entity_ids:
                if v is not None:
                    entity_id = v
                    break

        # extract and aggregate scores deterministically
        kpi_scores, kpi_ids, kpi_metadata = self._extract_scores(group, SourceType.KPI)
        log_scores, log_ids, log_metadata = self._extract_scores(group, SourceType.LOG)

        # encapsulated aggregation strategy
        strategy = self._select_aggregation_strategy()
        aggregated_kpi = self._apply_aggregation_strategy(strategy, kpi_scores)
        aggregated_log = self._apply_aggregation_strategy(strategy, log_scores)

        # Build a deterministic mapping of source metadata if present
        combined_meta = None
        if kpi_metadata or log_metadata:
            meta: dict = {}
            # deterministic insertion order: preserve kpi then log tuple order
            for i, md in enumerate(kpi_metadata or ()):  # preserve tuple order
                if isinstance(md, Mapping):
                    meta_key = f"kpi:{i}"
                    meta[meta_key] = dict(md)
            for i, md in enumerate(log_metadata or ()):  # preserve tuple order
                if isinstance(md, Mapping):
                    meta_key = f"log:{i}"
                    meta[meta_key] = dict(md)
            if meta:
                # Create immutable, deterministic MappingProxyType for outer and inner mappings
                outer: dict = {}
                for k in sorted(meta.keys()):
                    v = meta[k]
                    if isinstance(v, Mapping):
                        # inner mapping: deterministic ordering of items
                        inner = dict(sorted(v.items()))
                        outer[k] = MappingProxyType(inner)
                    else:
                        outer[k] = MappingProxyType(dict())
                combined_meta = MappingProxyType(outer)

        result = AggregatedFusionRecord(
            window_ts=window_ts,
            window_end_ts=window_end_ts,
            entity_id=entity_id,
            aggregated_kpi_score=aggregated_kpi,
            aggregated_log_score=aggregated_log,
            source_record_ids_kpi=tuple(kpi_ids),
            source_record_ids_log=tuple(log_ids),
            raw_kpi_scores=tuple(kpi_scores),
            raw_log_scores=tuple(log_scores),
            source_metadata=combined_meta,
            group_size=len(group),
        )

        self._logger.debug(
            "Aggregated group window=%s..%s entity=%s kpi_count=%d log_count=%d",
            result.window_ts.isoformat(),
            result.window_end_ts.isoformat(),
            result.entity_id,
            len(kpi_scores),
            len(log_scores),
        )

        return result

    def get_aggregated_records(self) -> Tuple[AggregatedFusionRecord, ...]:
        """Return aggregated records created by the last `aggregate()`.

        The returned value is an immutable tuple of immutable dataclasses.
        """
        return tuple(self._aggregated)

    def clear(self) -> None:
        """Clear internally stored aggregated results."""
        self._aggregated.clear()

    # Private helpers ---------------------------------------------------
    def _validate_groups(self, groups: Sequence[Tuple[FusionRecord, ...]]) -> None:
        """Validate container-level constraints for aligned groups."""
        if groups is None:
            raise AggregationValidationError("Aligned groups must not be None")
        if len(groups) == 0:
            # explicit: empty collection is allowed and will be handled by caller
            return
        for g in groups:
            self._validate_group(g)

    def _validate_group(self, group: Tuple[FusionRecord, ...]) -> None:
        """Validate a single aligned group.

        Checks for:
        - non-empty group
        - all items are FusionRecord
        - consistent timestamps (window_end > window_ts for each record)
        """
        if not isinstance(group, tuple):
            raise AggregationValidationError("Each aligned group must be an immutable tuple")
        if len(group) == 0:
            raise AggregationValidationError("Aligned group must not be empty")
        for r in group:
            if not isinstance(r, FusionRecord):
                raise AggregationValidationError("Aligned group contains non-FusionRecord items")
            if r.window_ts is None or r.window_end_ts is None:
                raise AggregationValidationError("Record contains invalid timestamps")
            if r.window_end_ts <= r.window_ts:
                raise AggregationValidationError("Record has non-positive window duration")

    def _extract_scores(self, group: Tuple[FusionRecord, ...], source_type: SourceType) -> Tuple[List[float], List[str], Tuple[Mapping, ...]]:
        """Extract scores, source ids and metadata for the given source type.

        Returns (scores, source_ids, metadata_tuple) where scores is a list of
        floats (deterministically ordered), source_ids is a list of non-None
        strings (in the same order), and metadata_tuple is a tuple of mapping
        or empty tuple.
        """
        scores: List[float] = []
        ids: List[str] = []
        metas: List[Mapping] = []

        # deterministic ordering: sort by window_ts then source_record_id
        ordered = sorted(group, key=lambda r: (r.window_ts, r.source_record_id or ""))
        if source_type == SourceType.KPI:
            for r in ordered:
                if r.kpi_score is not None:
                    scores.append(float(r.kpi_score))
                    if r.source_record_id is not None:
                        ids.append(r.source_record_id)
                    metas.append(r.source_metadata or {})
        elif source_type == SourceType.LOG:
            for r in ordered:
                if r.log_score is not None:
                    scores.append(float(r.log_score))
                    if r.source_record_id is not None:
                        ids.append(r.source_record_id)
                    metas.append(r.source_metadata or {})

        return scores, ids, tuple(metas)

    # Aggregation strategy encapsulation --------------------------------
    def _select_aggregation_strategy(self) -> Callable[[List[float]], Optional[float]]:
        """Return the aggregation strategy to use.

        Currently returns arithmetic mean strategy. This method centralizes
        strategy selection so future strategies can be introduced without
        changing the aggregation workflow.
        """
        return self._mean_strategy

    def _apply_aggregation_strategy(self, strategy: Callable[[List[float]], Optional[float]], values: List[float]) -> Optional[float]:
        """Apply the provided aggregation strategy to `values`.

        Strategy functions must accept a `List[float]` and return an
        Optional[float].
        """
        return strategy(values)

    def _mean_strategy(self, values: List[float]) -> Optional[float]:
        """Deterministic arithmetic mean strategy.

        Returns `None` for empty input.
        """
        if not values:
            return None
        s = 0.0
        for v in values:
            s += float(v)
        return s / float(len(values))


__all__ = [
    "FusionAggregation",
    "AggregatedFusionRecord",
    "FusionAggregationError",
    "AggregationValidationError",
    "AggregationConfigurationError",
]
