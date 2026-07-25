"""Ingestion bridge converting loaded source datasets into `FusionRecord`s.

This module implements `FusionIngestion`, a focused component that converts
per-row source data (KPI, Log) provided by `FusionSourceManager` into the
canonical, immutable `FusionRecord` objects used by downstream Phase 7
components.

The class performs lightweight validation and mapping only; it does NOT
perform windowing, alignment, aggregation, normalization, fusion, or any
decision logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Iterable, List, Mapping, Optional, Tuple
import logging
import math

import pandas as pd  # type: ignore

from phase7.config.fusion_config import FusionConfig
from phase7.source_manager.fusion_source_manager import FusionSourceManager
from phase7.models.fusion_record import FusionRecord, SourceType

logger = logging.getLogger("project.phase7.ingestion")


class FusionIngestionError(RuntimeError):
    """Base exception for ingestion-related failures."""


class IngestionValidationError(FusionIngestionError):
    """Raised when source data fails validation (missing/invalid fields)."""


class IngestionConfigurationError(FusionIngestionError):
    """Raised when the ingestion component is misconfigured."""


@dataclass
class FusionIngestion:
    """Convert loaded source DataFrames into canonical `FusionRecord`s.

    Parameters
    - source_manager: FusionSourceManager instance with loaded sources
    - config: FusionConfig for default parameters (window size fallback)
    - logger_: optional logger
    """

    source_manager: FusionSourceManager
    config: FusionConfig
    logger_: Optional[logging.Logger] = None

    def __post_init__(self) -> None:
        if self.source_manager is None or self.config is None:
            raise IngestionConfigurationError("source_manager and config are required")
        self._logger = self.logger_ or logger
        self._records: List[FusionRecord] = []

    # Public API ---------------------------------------------------------
    def ingest(self) -> None:
        """Ingest all currently configured and loaded sources from the manager.

        This iterates over `source_manager.list_sources()` and ingests each
        available source. Errors from individual sources are raised and logged.
        """
        self._logger.info("Starting ingestion of %d configured source(s)", len(self.source_manager.list_sources()))
        self._records.clear()
        for name in self.source_manager.list_sources():
            try:
                self.ingest_source(name)
            except IngestionValidationError:
                raise
            except Exception as exc:
                self._logger.exception("Failed to ingest source '%s': %s", name, exc)
                raise

    def ingest_source(self, source_name: str) -> None:
        """Ingest a single source by name.

        Parameters
        - source_name: configured source name

        Raises
        - KeyError: if source unknown
        - IngestionValidationError: on validation failures
        """
        if not self.source_manager.has_source(source_name):
            raise KeyError(f"Unknown source: {source_name}")
        df = self.source_manager.get_source(source_name)
        meta = self.source_manager.get_source_metadata(source_name)
        src_type = str(meta.get("type", "")).upper()
        self._logger.info("Ingesting source '%s' (type=%s) with %d rows", source_name, src_type, len(df))

        if src_type == "KPI":
            recs = self.ingest_kpi(df, source_name, meta)
        elif src_type == "LOG":
            recs = self.ingest_log(df, source_name, meta)
        else:
            raise IngestionValidationError(f"Unsupported source type for ingestion: {src_type}")

        self._records.extend(recs)
        self._logger.info("Ingested %d records from source '%s'", len(recs), source_name)

    def ingest_kpi(self, df: pd.DataFrame, source_name: str, meta: Mapping[str, Any]) -> list[FusionRecord]:
        """Convert a KPI DataFrame into a list of `FusionRecord` objects.

        The method locates common column names for timestamp, record id, entity
        id and score. If `window_end_ts` is not present, a window end is
        inferred using `config.fusion.window_size`.
        """
        return self._ingest_dataframe(
            df=df,
            meta=meta,
            source_name=source_name,
            score_candidates=[meta.get("score_column"), "anomaly_score", "score", "value"],
            factory=FusionRecord.from_kpi_source,
            score_kw="kpi_score",
            error_label="KPI",
        )

    def ingest_log(self, df: pd.DataFrame, source_name: str, meta: Mapping[str, Any]) -> list[FusionRecord]:
        """Convert a Log DataFrame into a list of `FusionRecord` objects.

        Similar to `ingest_kpi` but maps the log score fields and identifiers.
        """
        return self._ingest_dataframe(
            df=df,
            meta=meta,
            source_name=source_name,
            score_candidates=[meta.get("score_column"), "anomaly_score", "score", "prediction_confidence"],
            factory=FusionRecord.from_log_source,
            score_kw="log_score",
            error_label="Log",
        )

    def _ingest_dataframe(
        self,
        df: pd.DataFrame,
        meta: Mapping[str, Any],
        source_name: str,
        *,
        score_candidates: Iterable[Optional[str]],
        factory: Any,
        score_kw: str,
        error_label: str,
    ) -> list[FusionRecord]:
        """Generalized ingestion for KPI/Log dataframes.

        Parameters mirror the public ingestors; `factory` is a callable that
        constructs a `FusionRecord` and `score_kw` is the keyword name expected
        by that factory for the numeric score (e.g. 'kpi_score' or 'log_score').
        """
        ts_col = _choose_column(df, [meta.get("timestamp_column"), "window_ts", "timestamp", "time", "ts"])  # type: ignore[arg-type]
        id_col = _choose_column(df, [meta.get("id_column"), "KPI ID", "id", "source_record_id"])  # type: ignore[arg-type]
        end_col = _choose_column(df, [meta.get("end_timestamp_column"), "window_end_ts", "window_end", "end_ts"])  # type: ignore[arg-type]
        score_col = _choose_column(df, score_candidates)

        if ts_col is None:
            raise IngestionValidationError(f"{error_label} source '{source_name}' missing timestamp column")
        if id_col is None:
            raise IngestionValidationError(f"{error_label} source '{source_name}' missing source record id column")

        records: List[FusionRecord] = []
        window_size = self.config.fusion_settings.window_size

        for idx, row in df.iterrows():
            raw_ts = row[ts_col]
            try:
                ts = _parse_timestamp(raw_ts)
            except Exception as exc:
                raise IngestionValidationError(f"Invalid timestamp at row {idx} in source '{source_name}': {raw_ts}") from exc

            if end_col is not None and pd.notna(row[end_col]):
                try:
                    end_ts = _parse_timestamp(row[end_col])
                except Exception as exc:
                    raise IngestionValidationError(f"Invalid end timestamp at row {idx} in source '{source_name}': {row[end_col]}") from exc
            else:
                end_ts = ts + window_size

            source_id = _coerce_str(row[id_col])
            if source_id is None:
                raise IngestionValidationError(f"Missing source record id at row {idx} in source '{source_name}'")

            sc = None
            if score_col is not None and pd.notna(row[score_col]):
                try:
                    sc = float(row[score_col])
                except Exception:
                    raise IngestionValidationError(f"Invalid {error_label} score at row {idx} in source '{source_name}': {row[score_col]}")
                if not math.isfinite(sc):
                    raise IngestionValidationError(f"{error_label} score must be finite at row {idx} in source '{source_name}': {sc}")

            kwargs = {
                "window_ts": ts,
                "window_end_ts": end_ts,
                "source_record_id": source_id,
                score_kw: sc,
                "entity_id": _coerce_str(row.get("entity_id")) if "entity_id" in df.columns else None,
                "source_metadata": meta,
            }

            rec = factory(**kwargs)
            records.append(rec)
        return records

    def get_records(self) -> Tuple[FusionRecord, ...]:
        """Return an immutable tuple of ingested `FusionRecord`s."""
        return tuple(self._records)

    def clear(self) -> None:
        """Clear ingested records held in memory."""
        self._records.clear()


# Helper utilities ---------------------------------------------------------
def _choose_column(df: pd.DataFrame, candidates: Iterable[Optional[str]]) -> Optional[str]:
    for c in candidates:
        if c is None:
            continue
        cname = str(c)
        if cname in df.columns:
            return cname
    return None


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            # assume naive timestamps are UTC
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    raise ValueError("Unsupported timestamp value")


def _coerce_str(value: Any) -> Optional[str]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    s = str(value).strip()
    return s if s else None


__all__ = [
    "FusionIngestion",
    "FusionIngestionError",
    "IngestionValidationError",
    "IngestionConfigurationError",
]
