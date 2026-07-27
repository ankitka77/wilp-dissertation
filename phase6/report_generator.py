"""Report generation utilities for Phase 6.

The `ReportGenerator` writes training metrics, predictions, and a final
manifest to the experiment directories described by `ExperimentInfo`.
All filesystem writes are atomic where appropriate to avoid partial files.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, List
import csv
import json
import logging
from enum import Enum

from phase6.types import ExperimentInfo, DecisionResult, TrainingResult, ManifestInfo
from phase6.config import Config
from phase6.persistence import PersistenceManager
import subprocess

logger = logging.getLogger("project")


class ReportGenerationError(RuntimeError):
    """Raised when a report cannot be generated or written to disk."""


class ReportGenerator:
    """Generate and persist experiment reports and manifests.

    Parameters
    ----------
    experiment_info:
        `ExperimentInfo` describing canonical experiment paths.
    logger:
        Optional logger; defaults to the centralized project logger.
    config:
        `Config` instance used for any configuration-dependent behavior.
    """

    def __init__(self, experiment_info: ExperimentInfo, logger: logging.Logger | None = None, config: Config | None = None) -> None:
        if not isinstance(experiment_info, ExperimentInfo):
            raise ReportGenerationError("experiment_info must be an ExperimentInfo instance")

        self._experiment_info = experiment_info
        self._logger = logger or logging.getLogger("project")
        self._config = config or Config()

        # Ensure target directories exist
        Path(self._experiment_info.reports_path).mkdir(parents=True, exist_ok=True)
        Path(self._experiment_info.manifests_path).mkdir(parents=True, exist_ok=True)

    def write_training_metrics(self, training_result: TrainingResult) -> str:
        """Write training metrics JSON to the reports directory and return path.

        The file name is `training_metrics.json` under the experiment's
        reports path.
        """
        if not isinstance(training_result, TrainingResult):
            raise ReportGenerationError("training_result must be a TrainingResult instance")

        out_path = Path(self._experiment_info.reports_path) / "training_metrics.json"
        try:
            payload = asdict(training_result)
            payload = self._prepare_for_json(payload)
            self._atomic_write_json(out_path, payload)
        except Exception as exc:
            self._logger.exception("Failed to write training metrics: %s", exc)
            raise ReportGenerationError(f"Failed to write training metrics: {exc}") from exc
        return str(out_path)

    def write_predictions(self, decision_result: DecisionResult) -> str:
        """Serialize `DecisionResult.decisions` to CSV and return file path.

        The CSV is written to `predictions.csv` under the experiment's
        reports directory.
        """
        if not isinstance(decision_result, DecisionResult):
            raise ReportGenerationError("decision_result must be a DecisionResult instance")

        out_path = Path(self._experiment_info.reports_path) / "predictions.csv"
        try:
            rows, fieldnames = self._normalize_predictions_for_csv(decision_result.decisions)

            # Write CSV atomically using a temporary file in the same dir
            tmp = out_path.with_suffix(out_path.suffix + ".tmp")
            with tmp.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                for r in rows:
                    writer.writerow(r)
            tmp.replace(out_path)
        except Exception as exc:
            self._logger.exception("Failed to write predictions CSV: %s", exc)
            raise ReportGenerationError(f"Failed to write predictions CSV: {exc}") from exc
        return str(out_path)

    def write_manifest(self, manifest_info: ManifestInfo) -> str:
        """Write the final phase manifest JSON and return the manifest path.

        The filename used is `phase6_manifest.json` under the manifests path.
        """
        if not isinstance(manifest_info, ManifestInfo):
            raise ReportGenerationError("manifest_info must be a ManifestInfo instance")

        out_path = Path(self._experiment_info.manifests_path) / "phase6_manifest.json"
        try:
            payload = asdict(manifest_info)

            # ---- Checkpoint verification and augmentation ----
            try:
                # Use PersistenceManager to discover actual checkpoint files
                pm = PersistenceManager(self._experiment_info.path, self._config, self._logger)
                known_ckpts = pm.list_checkpoints()

                ts = payload.get("training_summary", {}) or {}

                # Helper to convert PersistenceInfo -> serializable dict
                def _pi_to_dict(pi):
                    return {
                        "path": str(pi.path),
                        "metadata_path": str(pi.metadata_path),
                        "checksum": str(pi.checksum),
                        "created_on": str(pi.created_on),
                        "checkpoint_type": pi.checkpoint_type.name if hasattr(pi, "checkpoint_type") else str(pi),
                    }

                # Ensure best_checkpoint references an existing file; if not,
                # attempt to find one from known checkpoints with type BEST.
                best = ts.get("best_checkpoint")
                if best:
                    try:
                        best_path = Path(best.get("path")) if isinstance(best.get("path"), str) else None
                        if best_path is None or not best_path.exists():
                            # Find BEST from known_ckpts
                            for k in known_ckpts:
                                if getattr(k.checkpoint_type, "name", "") == "BEST":
                                    ts["best_checkpoint"] = _pi_to_dict(k)
                                    break
                    except Exception:
                        # Ignore and leave as-is
                        self._logger.debug("Failed to verify best_checkpoint in manifest")
                else:
                    # No best recorded; look for one and populate it
                    for k in known_ckpts:
                        if getattr(k.checkpoint_type, "name", "") == "BEST":
                            ts["best_checkpoint"] = _pi_to_dict(k)
                            break

                # Populate final_checkpoint if a FINAL checkpoint exists but was
                # not recorded by Trainer. Do not override if already present.
                final = ts.get("final_checkpoint")
                if not final:
                    for k in known_ckpts:
                        if getattr(k.checkpoint_type, "name", "") == "FINAL":
                            ts["final_checkpoint"] = _pi_to_dict(k)
                            break

                payload["training_summary"] = ts
            except Exception:
                # Best-effort: do not fail manifest writing if persistence checks fail
                self._logger.exception("Failed to verify checkpoints for manifest")

            # ---- Git metadata enrichment (best-effort) ----
            try:
                repo_root = Path(__file__).resolve().parents[1]
                git_meta: Dict[str, Any] = {}
                # Ensure this is a git repo
                p = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=str(repo_root), capture_output=True, text=True)
                if p.returncode == 0 and p.stdout.strip() == "true":
                    # commit
                    p1 = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo_root), capture_output=True, text=True)
                    if p1.returncode == 0:
                        git_meta["commit"] = p1.stdout.strip()
                    # branch
                    p2 = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(repo_root), capture_output=True, text=True)
                    if p2.returncode == 0:
                        git_meta["branch"] = p2.stdout.strip()
                    # tag (if any)
                    p3 = subprocess.run(["git", "describe", "--tags", "--exact-match", "HEAD"], cwd=str(repo_root), capture_output=True, text=True)
                    if p3.returncode == 0:
                        git_meta["tag"] = p3.stdout.strip()
                else:
                    git_meta = {}
                payload["git"] = git_meta
            except Exception:
                # Do not fail manifest generation for git metadata issues
                self._logger.debug("Failed to populate git metadata for manifest")

            self._atomic_write_json(out_path, payload)
        except Exception as exc:
            self._logger.exception("Failed to write manifest: %s", exc)
            raise ReportGenerationError(f"Failed to write manifest: {exc}") from exc
        return str(out_path)

    def write_experiment_summary(self, summary: Dict[str, Any]) -> str:
        """Write a summary JSON into the reports directory and return path.

        The filename used is `experiment_summary.json`.
        """
        out_path = Path(self._experiment_info.reports_path) / "experiment_summary.json"
        try:
            self._atomic_write_json(out_path, summary)
        except Exception as exc:
            self._logger.exception("Failed to write experiment summary: %s", exc)
            raise ReportGenerationError(f"Failed to write experiment summary: {exc}") from exc
        return str(out_path)

    # ---- Private helpers ----
    def _normalize_predictions_for_csv(self, decisions: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[str]]:
        """Flatten decisions into CSV rows and return (rows, fieldnames).

        Each decision is expected to contain at minimum: `index`,
        `is_anomaly`, `reason`, and `confidence` (a dict with
        `confidence_score` and `method`). Additional fields such as `id`
        are preserved when present.
        """
        rows: List[Dict[str, Any]] = []
        # Metadata whitelist to include as separate CSV columns when present.
        METADATA_FIELDS = ["sequence_id", "block_id", "source", "dataset", "session_id", "timestamp"]

        # Include standardized `timestamp` and `anomaly_score` columns when
        # present in decisions. Preserve existing `confidence_score` and
        # `confidence_method` columns for backward compatibility. Metadata
        # columns come first for easier downstream processing.
        fieldnames = list(METADATA_FIELDS) + ["index", "id", "is_anomaly", "anomaly_score", "reason", "confidence_score", "confidence_method"]

        for d in decisions:
            row: Dict[str, Any] = {}
            row["index"] = d.get("index")
            row["id"] = d.get("id", "")
            # Copy metadata whitelist into CSV columns when present. Leave
            # blank when absent for backward compatibility.
            for m in METADATA_FIELDS:
                row[m] = d.get(m, "")

            row["is_anomaly"] = bool(d.get("is_anomaly", False))
            # anomaly_score provided explicitly by DecisionEngine (or
            # originally by the inference engine); include as a top-level
            # column to standardize across phases.
            row["anomaly_score"] = d.get("anomaly_score", "")
            row["reason"] = d.get("reason", "")

            conf = d.get("confidence", {}) or {}
            # Confidence may be a dict-like or dataclass that was serialized
            if isinstance(conf, dict):
                row["confidence_score"] = conf.get("confidence_score", "")
                row["confidence_method"] = conf.get("method", conf.get("confidence_method", ""))
            else:
                # Fallback to string representation
                row["confidence_score"] = ""
                row["confidence_method"] = str(conf)

            # Preserve other potential keys as JSON strings (e.g. topk, probs)
            extras = {}
            for key in ("topk", "probs"):
                if key in d:
                    extras[key] = d.get(key)
            if extras:
                row["extras"] = json.dumps(extras, ensure_ascii=False)
                if "extras" not in fieldnames:
                    fieldnames.append("extras")

            rows.append(row)

        return rows, fieldnames

    def _atomic_write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        """Write `payload` as JSON to `path` atomically.

        A temporary file with suffix `.tmp` is created in the same directory
        and replaced on success.
        """
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            # Ensure payload is JSON-safe (convert Enums, dataclasses, tuples, etc.)
            safe_payload = self._prepare_for_json(payload)
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(safe_payload, fh, indent=2, ensure_ascii=False)
            tmp.replace(path)
        finally:
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                # Best-effort cleanup; do not raise
                pass

    def _prepare_for_json(self, obj: Any) -> Any:
        """Recursively convert objects that JSON can't handle (Enums, etc.)

        Converts Enum instances to their `.value`, and walks lists/dicts
        recursively. Leaves primitives unchanged.
        """
        # Enums: prefer `.value`, otherwise fall back to `.name`.
        if isinstance(obj, Enum):
            try:
                return obj.value
            except Exception:
                return obj.name

        # Dataclasses: convert to dict then prepare recursively
        if is_dataclass(obj):
            return self._prepare_for_json(asdict(obj))

        # Mapping types
        if isinstance(obj, dict):
            return {k: self._prepare_for_json(v) for k, v in obj.items()}

        # Sequences: lists and tuples
        if isinstance(obj, list):
            return [self._prepare_for_json(v) for v in obj]
        if isinstance(obj, tuple):
            return [self._prepare_for_json(v) for v in obj]

        # Fallback: primitive types (str, int, float, bool, None) or objects
        # that json can handle directly.
        return obj


__all__ = ["ReportGenerator", "ReportGenerationError"]
