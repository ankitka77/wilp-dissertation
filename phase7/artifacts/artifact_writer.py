"""Artifact writer for Phase 7.

This module provides `ArtifactWriter`, a small component that serializes
already-processed `FusionRecord` objects into the architecture-defined
artifacts (CSV reports, JSON summaries, plots, and a manifest).

The writer performs input validation, directory preparation, deterministic
serialization, and emits immutable generation statistics.
"""
from __future__ import annotations

from types import MappingProxyType
# dataclasses.asdict intentionally not used here
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Tuple
import csv
import json
import logging
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from phase7.models.fusion_record import FusionRecord
from phase7.config.fusion_config import FusionConfig

logger = logging.getLogger("project.phase7.artifacts")


class ArtifactWriterError(RuntimeError):
    """Base error for artifact writer failures."""


class ArtifactValidationError(ArtifactWriterError):
    """Raised when inputs fail validation."""


class ArtifactWriteError(ArtifactWriterError):
    """Raised when writing artifacts fails."""


class ArtifactWriter:
    """Serialize Phase 7 `FusionRecord` results into files and plots.

    Typical usage:
        aw = ArtifactWriter()
        aw.write(records, experiment_id="experiment_001", ...)
        stats = aw.export_statistics()
    """

    def __init__(self, config: FusionConfig) -> None:
        # Accept the frozen FusionConfig and derive artifact root and settings from it
        if not isinstance(config, FusionConfig):
            raise ArtifactValidationError("ArtifactWriter requires a FusionConfig instance")
        self._config = config
        # root where experiments are stored (keep experiments subdir for compatibility)
        self._output_root = Path(self._config.artifacts.root_dir) / "experiments"
        self._statistics: Mapping[str, object] = MappingProxyType({})

    # Public API ---------------------------------------------------------
    def write(
        self,
        records: Tuple[FusionRecord, ...],
        experiment_id: str,
        *,
        kpi_detector_id: str | None = None,
        log_detector_id: str | None = None,
        config_snapshot: Mapping[str, object] | None = None,
    ) -> None:
        """Write all artifacts for the given `records` and `experiment_id`.

        Parameters
        - `records`: immutable tuple of `FusionRecord` objects already
            processed by the decision engine.
        - `experiment_id`: unique identifier for this experiment run.
        - optional detector ids and config snapshot for manifest.
        """
        start = time.time()
        self._validate_records(records)

        base_dir = self._prepare_output_directories(experiment_id)
        generated: List[Path] = []

        try:
            # CSV reports
            csv_dir = base_dir / "reports"
            fusion_inputs = csv_dir / "fusion_inputs.csv"
            aligned_windows = csv_dir / "aligned_windows.csv"
            normalized_scores = csv_dir / "normalized_scores.csv"
            fused_predictions = csv_dir / "fused_predictions.csv"

            self._write_csv(fusion_inputs, records, "fusion_inputs")
            generated.append(fusion_inputs)
            self._write_csv(normalized_scores, records, "normalized_scores")
            generated.append(normalized_scores)
            # aligned windows report (architecture-defined)
            self._write_csv(aligned_windows, records, "aligned_windows")
            generated.append(aligned_windows)
            self._write_csv(fused_predictions, records, "fused_predictions")
            generated.append(fused_predictions)

            # JSON outputs
            json_dir = base_dir / "reports"
            fusion_summary = json_dir / "fusion_summary.json"
            source_coverage = json_dir / "source_coverage.json"

            summary_obj = self._build_fusion_summary(records, config_snapshot)
            self._write_json(fusion_summary, summary_obj)
            generated.append(fusion_summary)

            coverage_obj = self._build_source_coverage(records)
            self._write_json(source_coverage, coverage_obj)
            generated.append(source_coverage)

            # Plots
            plots_dir = base_dir / "plots"
            hist = plots_dir / "fused_score_histogram.png"
            ts = plots_dir / "fused_score_timeseries.png"
            self._write_plots(records, hist, ts)
            generated.extend([hist, ts])

            # Manifest
            manifest_dir = base_dir / "manifests"
            manifest = manifest_dir / "phase7_manifest.json"
            manifest_obj = self._build_manifest(
                experiment_id=experiment_id,
                kpi_detector_id=kpi_detector_id,
                log_detector_id=log_detector_id,
                config_snapshot=config_snapshot,
                generated_files=[str(p.relative_to(self._config.artifacts.root_dir)) for p in generated],
                records=records,
            )
            self._write_json(manifest, manifest_obj)
            generated.append(manifest)

        except Exception as exc:
            logger.error("Artifact generation failed: %s", exc)
            raise ArtifactWriteError("Failed to generate artifacts") from exc
        finally:
            duration = time.time() - start
            # csv: fusion_inputs, normalized_scores, aligned_windows, fused_predictions -> 4
            # json_reports: fusion_summary, source_coverage -> 2
            self._build_statistics(
                records_written=len(records),
                csv_files_written=4,
                json_files_written=2,
                plots_generated=2,
                manifest_generated=1,
                output_directory=str(base_dir),
                generated_files=[str(p) for p in generated],
                write_duration_seconds=float(duration),
            )

    def write_csv(self, path: Path, records: Tuple[FusionRecord, ...], report: str) -> None:
        """Write a single CSV report (helper exposed for unit testing)."""
        self._validate_records(records)
        self._prepare_parent(path)
        self._write_csv(path, records, report)

    def write_json(self, path: Path, obj: Mapping[str, object]) -> None:
        """Write a single JSON file (helper)."""
        self._prepare_parent(path)
        self._write_json(path, obj)

    def write_plots(self, hist_path: Path, ts_path: Path, records: Tuple[FusionRecord, ...]) -> None:
        """Write plots to the provided paths."""
        self._validate_records(records)
        self._prepare_parent(hist_path)
        self._prepare_parent(ts_path)
        self._write_plots(records, hist_path, ts_path)

    def write_manifest(self, path: Path, manifest_obj: Mapping[str, object]) -> None:
        """Write manifest file."""
        self._prepare_parent(path)
        self._write_json(path, manifest_obj)

    def export_statistics(self) -> Mapping[str, object]:
        """Return immutable generation statistics."""
        return self._statistics

    def clear(self) -> None:
        """Clear stored statistics."""
        self._statistics = MappingProxyType({})

    # Private helpers ---------------------------------------------------
    def _validate_records(self, records: Tuple[FusionRecord, ...]) -> None:
        if records is None:
            raise ArtifactValidationError("records must not be None")
        if not isinstance(records, tuple):
            raise ArtifactValidationError("records must be provided as an immutable tuple")
        if len(records) == 0:
            raise ArtifactValidationError("records must not be empty")
        for idx, r in enumerate(records):
            self._validate_record(r, idx)

    def _validate_record(self, r: FusionRecord, idx: int) -> None:
        if not isinstance(r, FusionRecord):
            raise ArtifactValidationError(f"item at index {idx} is not a FusionRecord")

    def _prepare_output_directories(self, experiment_id: str) -> Path:
        base = self._output_root / experiment_id
        try:
            reports = base / "reports"
            plots = base / "plots"
            manifests = base / "manifests"
            reports.mkdir(parents=True, exist_ok=True)
            plots.mkdir(parents=True, exist_ok=True)
            manifests.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.error("Failed to create output directories: %s", exc)
            raise ArtifactWriteError("Failed to create output directories") from exc
        logger.info("Created artifact directories under %s", str(base))
        return base

    def _prepare_parent(self, path: Path) -> None:
        parent = path.parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            raise ArtifactWriteError(f"Failed to create directory: {parent}") from exc

    def _generate_rows(self, records: Tuple[FusionRecord, ...], report: str) -> Iterable[Dict[str, object]]:
        # deterministic ordering by window_ts then source_record_id
        def sort_key(r: FusionRecord):
            d = r.to_dict()
            return (d["window_ts"], d.get("source_record_id") or "")

        for r in sorted(records, key=sort_key):
            d = r.to_dict()
            if report == "fusion_inputs":
                yield {
                    "window_ts": d["window_ts"],
                    "window_end_ts": d["window_end_ts"],
                    "entity_id": d["entity_id"],
                    "kpi_score": d["kpi_score"],
                    "log_score": d["log_score"],
                    "kpi_available": d["kpi_available"],
                    "log_available": d["log_available"],
                    "missing_reason": d["missing_reason"],
                }
            elif report == "normalized_scores":
                yield {
                    "window_ts": d["window_ts"],
                    "entity_id": d["entity_id"],
                    "kpi_score": d["kpi_score"],
                    "log_score": d["log_score"],
                    "kpi_score_normalized": d["kpi_score_normalized"],
                    "log_score_normalized": d["log_score_normalized"],
                }
            elif report == "fused_predictions":
                yield {
                    "window_ts": d["window_ts"],
                    "window_end_ts": d["window_end_ts"],
                    "entity_id": d["entity_id"],
                    "kpi_score": d["kpi_score"],
                    "log_score": d["log_score"],
                    "kpi_score_normalized": d["kpi_score_normalized"],
                    "log_score_normalized": d["log_score_normalized"],
                    "kpi_available": d["kpi_available"],
                    "log_available": d["log_available"],
                    "kpi_weight": d.get("kpi_weight"),
                    "log_weight": d.get("log_weight"),
                    "kpi_contribution": d.get("kpi_contribution"),
                    "log_contribution": d.get("log_contribution"),
                    "fused_score": d.get("fused_score"),
                    "final_label": d.get("final_label"),
                    "decision_reason": d.get("decision_reason"),
                }
            elif report == "aligned_windows":
                # Use the canonical FusionRecord serialization and include alignment metadata
                yield {
                    "window_ts": d["window_ts"],
                    "window_end_ts": d["window_end_ts"],
                    "entity_id": d["entity_id"],
                    "source_type": d.get("source_type"),
                    "source_record_id": d.get("source_record_id"),
                    "kpi_available": d.get("kpi_available"),
                    "log_available": d.get("log_available"),
                    "kpi_score": d.get("kpi_score"),
                    "log_score": d.get("log_score"),
                    "kpi_score_normalized": d.get("kpi_score_normalized"),
                    "log_score_normalized": d.get("log_score_normalized"),
                    "fused_score": d.get("fused_score"),
                    "final_label": d.get("final_label"),
                }
            else:
                raise ArtifactWriteError(f"Unknown report type: {report}")

    def _write_csv(self, path: Path, records: Tuple[FusionRecord, ...], report: str) -> None:
        rows = list(self._generate_rows(records, report))
        try:
            self._prepare_parent(path)
            with path.open("w", newline="", encoding="utf-8") as fh:
                if rows:
                    fieldnames = list(rows[0].keys())
                else:
                    # fallback deterministic headers per report
                    if report == "fusion_inputs":
                        fieldnames = ["window_ts", "window_end_ts", "entity_id", "kpi_score", "log_score", "kpi_available", "log_available", "missing_reason"]
                    elif report == "normalized_scores":
                        fieldnames = ["window_ts", "entity_id", "kpi_score", "log_score", "kpi_score_normalized", "log_score_normalized"]
                    elif report == "aligned_windows":
                        fieldnames = ["window_ts", "window_end_ts", "entity_id", "source_type", "source_record_id", "kpi_available", "log_available", "kpi_score", "log_score", "kpi_score_normalized", "log_score_normalized", "fused_score", "final_label"]
                    else:
                        fieldnames = ["window_ts", "window_end_ts", "entity_id", "kpi_score", "log_score", "kpi_score_normalized", "log_score_normalized", "kpi_available", "log_available", "kpi_weight", "log_weight", "kpi_contribution", "log_contribution", "fused_score", "final_label", "decision_reason"]
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)
        except Exception as exc:
            logger.error("CSV write failed for %s: %s", path, exc)
            raise ArtifactWriteError("Failed to write CSV") from exc

    def _write_json(self, path: Path, obj: Mapping[str, object]) -> None:
        try:
            self._prepare_parent(path)
            with path.open("w", encoding="utf-8") as fh:
                json.dump(obj, fh, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        except Exception as exc:
            logger.error("JSON write failed for %s: %s", path, exc)
            raise ArtifactWriteError("Failed to write JSON") from exc

    def _write_plots(self, records: Tuple[FusionRecord, ...], hist_path: Path, ts_path: Path) -> None:
        # collect fused_score values and timeseries
        rows = [r.to_dict() for r in records]
        # deterministic ordering
        rows.sort(key=lambda d: (d["window_ts"], d.get("source_record_id") or ""))
        scores = [d.get("fused_score") for d in rows if d.get("fused_score") is not None]
        times = [d.get("window_ts") for d in rows if d.get("fused_score") is not None]

        try:
            # histogram
            plt.figure(figsize=(6, 4))
            plt.hist([float(s) for s in scores] if scores else [], bins=50)
            plt.title("Fused score distribution")
            plt.xlabel("fused_score")
            plt.ylabel("count")
            plt.tight_layout()
            plt.savefig(hist_path, dpi=150)
            plt.close()

            # timeseries
            plt.figure(figsize=(8, 3))
            if times and scores:
                # convert ISO timestamps to datetime for plotting
                parsed = [datetime.fromisoformat(t.replace("Z", "+00:00")) for t in times]
                plt.plot(parsed, [float(s) for s in scores], marker=".")
                plt.gcf().autofmt_xdate()
            plt.title("Fused score timeseries")
            plt.xlabel("window_ts")
            plt.ylabel("fused_score")
            plt.tight_layout()
            plt.savefig(ts_path, dpi=150)
            plt.close()
        except Exception as exc:
            logger.error("Plot generation failed: %s", exc)
            raise ArtifactWriteError("Failed to generate plots") from exc

    def _build_fusion_summary(self, records: Tuple[FusionRecord, ...], config_snapshot: Mapping[str, object] | None) -> Dict[str, object]:
        counts = self._build_source_coverage(records)
        total = len(records)
        anomalies = sum(1 for r in records if getattr(r, "final_label", None) == 1)
        normal = sum(1 for r in records if getattr(r, "final_label", None) == 0)
        summary = {
            "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
            "record_counts": {"total": int(total), "anomalies": int(anomalies), "normal": int(normal)},
            "coverage": counts,
            "configuration": config_snapshot or {},
        }
        return summary

    def _build_source_coverage(self, records: Tuple[FusionRecord, ...]) -> Dict[str, int]:
        kpi_avail = 0
        log_avail = 0
        both = 0
        kpi_only = 0
        log_only = 0
        missing_both = 0
        for r in records:
            ka = bool(getattr(r, "kpi_available", False))
            la = bool(getattr(r, "log_available", False))
            if ka:
                kpi_avail += 1
            if la:
                log_avail += 1
            if ka and la:
                both += 1
            elif ka and not la:
                kpi_only += 1
            elif la and not ka:
                log_only += 1
            else:
                missing_both += 1
        return {
            "kpi_available": int(kpi_avail),
            "log_available": int(log_avail),
            "both_available": int(both),
            "kpi_only": int(kpi_only),
            "log_only": int(log_only),
            "missing_both": int(missing_both),
        }

    def _build_manifest(
        self,
        *,
        experiment_id: str,
        kpi_detector_id: str | None,
        log_detector_id: str | None,
        config_snapshot: Mapping[str, object] | None,
        generated_files: List[str],
        records: Tuple[FusionRecord, ...],
    ) -> Dict[str, object]:
        # input artifact locations (best-effort) - point to detector experiment folders when provided
        input_artifacts: List[str] = []
        root = Path(self._config.artifacts.root_dir)
        if kpi_detector_id:
            input_artifacts.append(str((root / "experiments" / kpi_detector_id).as_posix()))
        if log_detector_id:
            input_artifacts.append(str((root / "experiments" / log_detector_id).as_posix()))

        coverage = self._build_source_coverage(records)

        manifest = {
            "manifest_version": 1,
            "generation_timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "experiment_id": experiment_id,
            "kpi_detector_experiment_id": kpi_detector_id,
            "log_detector_experiment_id": log_detector_id,
            "input_artifact_locations": input_artifacts,
            "output_artifact_locations": generated_files,
            "artifact_root": str(self._config.artifacts.root_dir),
            "fusion_strategy": self._config.fusion.strategy.value,
            "kpi_weight": float(self._config.fusion.kpi_weight),
            "log_weight": float(self._config.fusion.log_weight),
            "threshold": float(self._config.fusion.threshold),
            "window_size": self._config.fusion.window_size.total_seconds(),
            "normalization_strategy": self._config.fusion.normalization_strategy.value,
            "coverage": coverage,
            "summary": {},
        }
        if config_snapshot:
            manifest["configuration_snapshot"] = config_snapshot
        return manifest

    # _read_config_value removed: manifest values are read from FusionConfig

    def _build_statistics(self, *, records_written: int, csv_files_written: int, json_files_written: int, plots_generated: int, manifest_generated: int, output_directory: str, generated_files: List[str], write_duration_seconds: float) -> None:
        stats = {
            "records_written": int(records_written),
            "csv_files_written": int(csv_files_written),
            "json_files_written": int(json_files_written),
            "plots_generated": int(plots_generated),
            "manifest_generated": int(manifest_generated),
            "output_directory": output_directory,
            "generated_files": list(generated_files),
            "write_duration_seconds": float(write_duration_seconds),
        }
        # preserve insertion order as defined above
        self._statistics = MappingProxyType(stats)


__all__ = ["ArtifactWriter", "ArtifactWriterError", "ArtifactValidationError", "ArtifactWriteError"]
