"""Temporal alignment utilities for Phase 7 Fusion Engine.

This module provides `FusionAlignment`, a focused component that performs
temporal alignment of immutable `FusionRecord` instances produced by the
`FusionIngestion` stage. It groups records into alignment windows according
to configuration provided by `FusionConfig` and returns immutable tuples of
aligned `FusionRecord` objects.

Responsibilities:
- sorting and optional validation of input records
- grouping records into temporal alignment windows
- matching KPI and Log records that belong to the same logical window
- emitting immutable aligned record collections

This module does NOT perform normalization, fusion, aggregation, or any
decision-making logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, List, Mapping, Optional, Tuple
import logging

from phase7.config.fusion_config import FusionConfig
from phase7.models.fusion_record import FusionRecord

logger = logging.getLogger("project.phase7.alignment")


class FusionAlignmentError(RuntimeError):
    """Base exception for alignment-related failures."""


class AlignmentValidationError(FusionAlignmentError):
    """Raised when input records violate alignment validation rules."""


class AlignmentConfigurationError(FusionAlignmentError):
    """Raised when the alignment component is misconfigured."""


@dataclass
class FusionAlignment:
    """Align `FusionRecord` objects into temporal windows.

    Parameters
    - config: `FusionConfig` providing alignment parameters. The alignment
      window and tolerance are read from the optional `alignment` section if
      present; otherwise `config.fusion.window_size` is used and tolerance is
      derived from it.

    Public methods
    - `align(records)` : perform alignment and store aligned groups
    - `align_records(records)` : pure function returning aligned groups
    - `align_window(records)` : align a pre-filtered window (helper)
    - `get_aligned_records()` : return stored aligned groups
    - `clear()` : clear stored groups
    """

    config: FusionConfig

    def __post_init__(self) -> None:
        if self.config is None:
            raise AlignmentConfigurationError("config is required")
        self._aligned: List[Tuple[FusionRecord, ...]] = []
        # centralize logger on the instance for consistent logging
        self._logger = logger
        self._window_size, self._tolerance = self._load_alignment_config()

    # Public API ---------------------------------------------------------
    def align(self, records: Iterable[FusionRecord]) -> None:
        """Align the provided records and store the resulting groups.

        This method validates and sorts input records, then groups them into
        alignment windows according to the configured window size and
        tolerance. Results are stored internally and are accessible via
        `get_aligned_records()`.
        """
        self._logger.info("Starting alignment")
        groups = self.align_records(records)
        self._aligned = list(groups)
        self._logger.info("Alignment complete: %d window(s) created", len(self._aligned))

    def align_records(self, records: Iterable[FusionRecord]) -> Tuple[Tuple[FusionRecord, ...], ...]:
        """Pure function: return aligned groups for the given records.

        Returns a tuple of groups where each group is an immutable tuple of
        `FusionRecord` objects. The input is not mutated.
        """
        recs = list(records)
        self._logger.debug("Received %d record(s) for alignment", len(recs))

        if not recs:
            return tuple()

        # Deterministic validation of record integrity (pure; does not mutate)
        self._validate_records(recs)

        # Operate on a sorted copy to guarantee deterministic grouping
        sorted_recs = self._sort_records(recs)

        # Additional validations that assume ordering
        self._validate_duplicates(sorted_recs)
        self._validate_overlaps(sorted_recs)

        # Group records into alignment windows by temporal proximity AND logical key
        groups: List[List[FusionRecord]] = []
        first = sorted_recs[0]
        current_group: List[FusionRecord] = [first]
        current_group_end = first.window_end_ts
        current_key = self._record_key(first)

        for r in sorted_recs[1:]:
            r_key = self._record_key(r)
            within_time = r.window_ts <= current_group_end + self._tolerance
            same_key = (r_key == current_key)
            # Only merge when both temporal proximity and logical key match
            if within_time and same_key:
                current_group.append(r)
                if r.window_end_ts > current_group_end:
                    current_group_end = r.window_end_ts
            else:
                groups.append(current_group)
                current_group = [r]
                current_group_end = r.window_end_ts
                current_key = r_key

        if current_group:
            groups.append(current_group)

        aligned: List[Tuple[FusionRecord, ...]] = []
        for g in groups:
            aligned_group = tuple(g)
            self._logger.info("Created alignment window with %d record(s)", len(aligned_group))
            aligned.append(aligned_group)

        return tuple(aligned)

    def align_window(self, records: Iterable[FusionRecord]) -> Tuple[FusionRecord, ...]:
        """Align a pre-filtered set of records that are expected to belong
        to the same logical window. This performs validation and returns an
        immutable tuple of the input records sorted by `window_ts`.
        """
        recs = sorted(list(records), key=lambda r: r.window_ts)
        # validation: ensure records indeed overlap or are within tolerance
        if not recs:
            return tuple()
        start = recs[0].window_ts
        end = max(r.window_end_ts for r in recs)
        for r in recs:
            if r.window_end_ts < start - self._tolerance or r.window_ts > end + self._tolerance:
                raise AlignmentValidationError("Record outside of provided window tolerance")
        return tuple(recs)

    def get_aligned_records(self) -> Tuple[Tuple[FusionRecord, ...], ...]:
        """Return the aligned record groups created by the last `align()`.

        The returned value is an immutable tuple of immutable tuples.
        """
        return tuple(self._aligned)

    def clear(self) -> None:
        """Clear internally stored aligned groups."""
        self._aligned.clear()

    # Private helpers ---------------------------------------------------
    def _load_alignment_config(self) -> Tuple[timedelta, timedelta]:
        """Load alignment window and tolerance from configuration.

        The optional top-level `alignment` section may provide `window_size`
        and `tolerance` as `timedelta` objects. If absent, `fusion.window_size`
        is used and tolerance defaults to half the window size.
        """
        # Use officially supported fusion window size; do not rely on an
        # undocumented `alignment` section. Tolerance defaults to half the
        # configured fusion window.
        window = self.config.fusion_settings.window_size
        tolerance = window / 2
        if not isinstance(window, timedelta) or not isinstance(tolerance, timedelta):
            raise AlignmentConfigurationError("alignment timing parameters must be timedelta instances")
        if tolerance < timedelta(0) or window <= timedelta(0):
            raise AlignmentConfigurationError("alignment timing parameters must be positive")
        return window, tolerance

    # Validation helpers -------------------------------------------------
    def _validate_records(self, recs: List[FusionRecord]) -> None:
        for r in recs:
            if r.window_ts is None or r.window_end_ts is None:
                raise AlignmentValidationError("Record contains invalid timestamps")
            if r.window_ts >= r.window_end_ts:
                raise AlignmentValidationError("Record has non-positive window duration")

    def _validate_order(self, recs: List[FusionRecord]) -> None:
        # Check monotonic ordering. This helper does NOT mutate `recs`.
        is_sorted = all(recs[i].window_ts <= recs[i + 1].window_ts for i in range(len(recs) - 1))
        if not is_sorted:
            self._logger.debug("Input records are not ordered by window_ts")

    def _validate_duplicates(self, recs: List[FusionRecord]) -> None:
        seen_ts = set()
        for r in recs:
            if r.window_ts in seen_ts:
                msg = f"Duplicate window_ts detected: {r.window_ts.isoformat()}"
                raise AlignmentValidationError(msg)
            seen_ts.add(r.window_ts)

    def _validate_overlaps(self, recs: List[FusionRecord]) -> None:
        for i in range(len(recs) - 1):
            if recs[i].window_end_ts > recs[i + 1].window_ts:
                msg = f"Overlapping windows detected between records at {recs[i].window_ts.isoformat()} and {recs[i+1].window_ts.isoformat()}"
                raise AlignmentValidationError(msg)

    def _record_key(self, r: FusionRecord) -> Optional[str]:
        # Primary logical key is entity_id; fallback to source_record_id.
        if r.entity_id:
            return r.entity_id
        return r.source_record_id

    def _sort_records(self, recs: List[FusionRecord]) -> List[FusionRecord]:
        # Return a new list sorted by window_ts without mutating the input.
        return sorted(list(recs), key=lambda r: r.window_ts)


__all__ = [
    "FusionAlignment",
    "FusionAlignmentError",
    "AlignmentValidationError",
    "AlignmentConfigurationError",
]
