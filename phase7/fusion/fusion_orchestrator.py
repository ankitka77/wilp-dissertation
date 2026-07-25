"""Orchestrator for Phase 7 Fusion pipeline.

This module provides `FusionOrchestrator`, a small coordinator that runs
the Phase 7 pipeline in the frozen order and exposes a compact,
deterministic public API for execution and statistics export.

The orchestrator strictly composes existing Phase 7 components and does
not implement business logic itself. Exceptions are translated to
`FusionOrchestratorError` to provide a stable public surface.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType
from typing import Mapping, Optional, Tuple
import logging
import time

from phase7.config.fusion_config import FusionConfig
from phase7.source_manager.fusion_source_manager import FusionSourceManager
from phase7.ingestion.fusion_ingestion import FusionIngestion
from phase7.alignment.fusion_alignment import FusionAlignment
from phase7.aggregation.fusion_aggregation import FusionAggregation
from phase7.aggregation.fusion_aggregation import AggregatedFusionRecord
from phase7.normalization.score_normalizer import ScoreNormalizer
from phase7.fusion.fusion_decision_engine import FusionDecisionEngine
from phase7.artifacts.artifact_writer import ArtifactWriter
from phase7.models.fusion_record import FusionRecord

logger = logging.getLogger("project.phase7.orchestrator")


class FusionOrchestratorError(RuntimeError):
    """Base exception for orchestrator failures."""


class FusionOrchestrator:
    """Coordinate Phase 7 pipeline stages and expose execution summary.

    Public API
    - `run(experiment_id=..., kpi_detector_experiment_id=..., log_detector_experiment_id=...)` : execute pipeline
    - `export_statistics()` : return cumulative immutable orchestrator statistics
    - `clear()` : reset internal statistics
    """

    def __init__(self, config: FusionConfig, *, normalization_strategy: object | None = None, logger_: Optional[logging.Logger] = None) -> None:
        if config is None:
            raise FusionOrchestratorError("FusionConfig is required")
        if not isinstance(config, FusionConfig):
            raise FusionOrchestratorError("config must be a FusionConfig instance")
        self._config = config
        self._logger = logger_ or logger
        # Normalization strategy must be provided by the caller (dependency injection)
        self._normalization_strategy = normalization_strategy

        # cumulative stats
        self._stats = {
            "pipeline_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "last_execution_duration": None,
            "last_experiment_id": None,
            "records_processed": 0,
            "records_written": 0,
            "generated_artifacts": 0,
            "output_directory": None,
        }

    # Public API ---------------------------------------------------------
    def run(
        self,
        *,
        experiment_id: str,
        kpi_detector_experiment_id: Optional[str] = None,
        log_detector_experiment_id: Optional[str] = None,
    ) -> Mapping[str, object]:
        """Execute the pipeline for the given `experiment_id`.

        Returns an immutable summary mapping with deterministic keys.
        """
        start_wall = time.time()
        start_ts = datetime.now(timezone.utc).isoformat()
        self._logger.info("Pipeline run starting: experiment_id=%s", experiment_id)

        # High-level orchestration: delegate to helpers
        try:
            # initialize components
            self._initialize_components()

            # execute stages
            src_mgr = self._execute_source_manager()
            records, aligned = self._execute_ingestion_and_alignment(src_mgr)
            aggregated = self._execute_aggregation(aligned)
            normalized, normalizer = self._execute_normalization(aggregated)
            fused, decision_engine = self._execute_decision_engine(normalized)

            # Artifact generation: follow ArtifactWriter contract (it may reject empty inputs)
            aw_stats = self._execute_artifact_generation(
                fused, experiment_id, kpi_detector_experiment_id, log_detector_experiment_id
            )

            end_wall = time.time()
            duration = float(end_wall - start_wall)
            end_ts = datetime.now(timezone.utc).isoformat()

            # Build summary statistics combining available diagnostics
            summary_statistics = {
                "fusion": decision_engine.export_statistics(),
                "normalization": normalizer.export_diagnostics(),
                "artifact_generation": aw_stats or {},
            }

            # Update cumulative orchestrator stats
            self._update_statistics(
                success=True,
                duration=duration,
                experiment_id=experiment_id,
                records_processed=len(records),
                records_written=int((aw_stats or {}).get("records_written", 0)),
                generated_artifacts=int(len((aw_stats or {}).get("generated_files", []))),
                output_directory=(aw_stats or {}).get("output_directory"),
            )

            summary = self._build_execution_summary(
                experiment_id=experiment_id,
                start_ts=start_ts,
                end_ts=end_ts,
                duration=duration,
                records_processed=len(records),
                records_written=int((aw_stats or {}).get("records_written", 0)),
                generated_artifacts=int(len((aw_stats or {}).get("generated_files", []))),
                output_directory=(aw_stats or {}).get("output_directory"),
                summary_statistics=summary_statistics,
            )

            return MappingProxyType(summary)

        except Exception as exc:
            self._logger.exception("Pipeline execution failed: %s", exc)
            self._update_statistics(success=False, duration=None, experiment_id=experiment_id)
            raise FusionOrchestratorError("Pipeline execution failed") from exc

    def export_statistics(self) -> Mapping[str, object]:
        """Return cumulative orchestrator statistics as an immutable mapping."""
        # Ensure deterministic ordering
        ordered_keys = [
            "pipeline_runs",
            "successful_runs",
            "failed_runs",
            "last_execution_duration",
            "last_experiment_id",
            "records_processed",
            "records_written",
            "generated_artifacts",
            "output_directory",
        ]
        ordered = {k: self._stats.get(k) for k in ordered_keys}
        return MappingProxyType(ordered)

    # Helper methods --------------------------------------------------
    def _initialize_components(self) -> None:
        self._logger.info("Orchestrator initialization starting")
        # No-op: components are instantiated per-stage to preserve purity
        self._logger.info("Orchestrator initialization complete")

    def _execute_source_manager(self) -> FusionSourceManager:
        self._logger.info("Stage: source_manager start")
        src_mgr = FusionSourceManager(self._config)
        src_mgr.initialize()
        src_mgr.load_sources()
        self._logger.info("Stage: source_manager complete; configured sources=%d", len(src_mgr.list_sources()))
        return src_mgr

    def _execute_ingestion_and_alignment(self, src_mgr: FusionSourceManager):
        self._logger.info("Stage: ingestion start")
        ingestion = FusionIngestion(src_mgr, self._config)
        ingestion.ingest()
        records = ingestion.get_records()
        self._logger.info("Stage: ingestion complete; records=%d", len(records))

        self._logger.info("Stage: alignment start")
        alignment = FusionAlignment(self._config)
        alignment.align(records)
        aligned = alignment.get_aligned_records()
        self._logger.info("Stage: alignment complete; windows=%d", len(aligned))
        return records, aligned

    def _execute_aggregation(self, aligned):
        self._logger.info("Stage: aggregation start")
        aggregation = FusionAggregation(self._config)
        aggregated = aggregation.aggregate_groups(aligned)
        self._logger.info("Stage: aggregation complete; aggregated=%d", len(aggregated))
        return aggregated

    # NOTE: Normalization strategy selection is the responsibility of the
    # caller or the normalization subsystem. The orchestrator accepts a
    # `normalization_strategy` via constructor injection and does not perform
    # any dynamic discovery or selection.

    def _execute_normalization(self, aggregated):
        self._logger.info("Stage: normalization start")
        if self._normalization_strategy is None:
            raise FusionOrchestratorError("Normalization strategy not provided to orchestrator")
        normalizer = ScoreNormalizer(self._config, self._normalization_strategy)
        # If there are no aggregated records, skip calling normalize_records
        if not aggregated:
            self._logger.info("Stage: normalization skipped; no aggregated records")
            return tuple(), normalizer

        # Convert AggregatedFusionRecord -> FusionRecord as ScoreNormalizer expects FusionRecord
        converted: list[object] = []
        for idx, a in enumerate(aggregated):
            if isinstance(a, AggregatedFusionRecord):
                # Preserve timestamps, entity_id, aggregated scores and provenance
                fm = FusionRecord(
                    window_ts=a.window_ts,
                    window_end_ts=a.window_end_ts,
                    entity_id=a.entity_id,
                    kpi_score=a.aggregated_kpi_score,
                    log_score=a.aggregated_log_score,
                    kpi_available=(a.aggregated_kpi_score is not None),
                    log_available=(a.aggregated_log_score is not None),
                    source_metadata={
                        "aggregated": {
                            "raw_kpi_scores": list(a.raw_kpi_scores),
                            "raw_log_scores": list(a.raw_log_scores),
                            "source_record_ids_kpi": list(a.source_record_ids_kpi),
                            "source_record_ids_log": list(a.source_record_ids_log),
                            "group_size": int(a.group_size),
                            "source_metadata": dict(a.source_metadata) if a.source_metadata is not None else {},
                        }
                    },
                )
                converted.append(fm)
            elif isinstance(a, FusionRecord):
                converted.append(a)
            else:
                raise FusionOrchestratorError(f"Unexpected aggregated record type at index {idx}: {type(a)}")

        # Delegate validation/behavior to ScoreNormalizer; do not swallow exceptions
        normalized = normalizer.normalize_records(tuple(converted))
        self._logger.info("Stage: normalization complete; records=%d", len(normalized))
        return normalized, normalizer

    def _execute_decision_engine(self, normalized):
        self._logger.info("Stage: decision_engine start")
        engine = FusionDecisionEngine(self._config)
        if not normalized:
            self._logger.info("Stage: decision_engine skipped; no normalized records")
            return tuple(), engine
        fused = engine.fuse_records(normalized)
        self._logger.info("Stage: decision_engine complete; fused=%d", len(fused))
        return fused, engine

    def _execute_artifact_generation(self, fused, experiment_id, kpi_detector_experiment_id, log_detector_experiment_id):
        self._logger.info("Stage: artifact_generation start")
        # Always invoke ArtifactWriter and allow it to validate inputs.
        # If ArtifactWriter rejects empty collections, that is a pipeline failure.
        aw = ArtifactWriter(self._config)
        config_snapshot = self._config.export_snapshot()
        aw.write(
            fused,
            experiment_id,
            kpi_detector_id=kpi_detector_experiment_id,
            log_detector_id=log_detector_experiment_id,
            config_snapshot=config_snapshot,
        )
        stats = aw.export_statistics()
        self._logger.info("Stage: artifact_generation complete; files=%d", len(stats.get("generated_files", [])))
        return stats

    def _build_execution_summary(
        self,
        *,
        experiment_id: str,
        start_ts: str,
        end_ts: str,
        duration: float,
        records_processed: int,
        records_written: int,
        generated_artifacts: int,
        output_directory: Optional[str],
        summary_statistics: Mapping[str, object],
    ) -> dict:
        return {
            "experiment_id": experiment_id,
            "execution_status": "success",
            "pipeline_start_time": start_ts,
            "pipeline_end_time": end_ts,
            "execution_duration_seconds": float(duration) if duration is not None else None,
            "records_processed": int(records_processed),
            "records_written": int(records_written),
            "generated_artifacts": int(generated_artifacts),
            "output_directory": output_directory,
            "summary_statistics": summary_statistics,
        }

    def _update_statistics(self, *, success: bool, duration: Optional[float], experiment_id: Optional[str], records_processed: int = 0, records_written: int = 0, generated_artifacts: int = 0, output_directory: Optional[str] = None) -> None:
        self._stats["pipeline_runs"] += 1
        if success:
            self._stats["successful_runs"] += 1
        else:
            self._stats["failed_runs"] += 1
        if duration is not None:
            self._stats["last_execution_duration"] = float(duration)
        if experiment_id is not None:
            self._stats["last_experiment_id"] = experiment_id
        self._stats["records_processed"] = int(records_processed)
        self._stats["records_written"] = int(records_written)
        self._stats["generated_artifacts"] = int(generated_artifacts)
        self._stats["output_directory"] = output_directory

    def clear(self) -> None:
        """Reset cumulative orchestrator statistics to initial state."""
        self._stats = {
            "pipeline_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "last_execution_duration": None,
            "last_experiment_id": None,
            "records_processed": 0,
            "records_written": 0,
            "generated_artifacts": 0,
            "output_directory": None,
        }


__all__ = ["FusionOrchestrator", "FusionOrchestratorError"]
