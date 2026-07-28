"""DeepLog Evaluator for Phase 8 Milestone 2.

This evaluator now uses the published Phase 6 predictions and the HDFS
ground-truth labels joined on the authoritative HDFS BlockId (`block_id`).

Evaluation workflow (summary):

- Resolve the DeepLog ground-truth CSV using this order:
    1. If the dataset manifest provides a path to the DeepLog ground-truth
         file, use that location.
    2. Otherwise fall back to the project's default HDFS location
         `data/logs/HDFS_v1/preprocessed/anomaly_label.csv`.
    3. If neither location is available, raise `DeepLogEvaluatorError`.

- Read Phase 6 published predictions from the stabilized run
    `artifacts/phase6/latest/predictions.csv` (required columns: `block_id`,
    `is_anomaly`).

- Read the resolved `anomaly_label.csv` (required columns: `BlockId`,
    `Label`) and normalize labels to booleans.

- Join predictions and labels on `block_id` (string equality). Validate
    the join and compute metrics only on matched rows. Log a short join
    summary and raise `DeepLogEvaluatorError` if zero rows match.

This replaces the legacy `ground_truth.seq` / `predictions.seq` positional
comparison logic and keeps the public API and JSON summary schema unchanged
for backward compatibility with the Phase 8 orchestrator.

Duplicate handling note:
- Duplicate `block_id` values in either the Phase 6 `predictions.csv` or
    the ground-truth `anomaly_label.csv` are treated as data-quality issues.
    The evaluator logs a warning for each duplicate and retains the *first*
    occurrence while ignoring subsequent duplicates. This behavior is
    intentional to preserve stable, deterministic evaluation results.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Tuple
import logging
import csv
from pathlib import Path

from phase8.core.artifact_store import ArtifactStore, ArtifactStoreError
from phase8.core.experiment_manager import ExperimentManager, ExperimentNotFoundError
from phase8.core.dataset_manager import DatasetManager, DatasetNotFoundError
from .exceptions import DeepLogEvaluatorError

logger = logging.getLogger("phase8.evaluators.deeplog")


@dataclass(frozen=True)
class DeepLogMetrics:
    precision: float
    recall: float
    f1: float


@dataclass(frozen=True)
class DeepLogResult:
    experiment_id: str
    dataset_id: str
    metrics: DeepLogMetrics
    summary_path: str


# Module-level filename/constants
PHASE6_RUN = "phase6/latest"
PHASE6_PREDICTIONS = "predictions.csv"
DEFAULT_HDFS_LABELS = Path(__file__).resolve().parents[2] / "data" / "logs" / "HDFS_v1" / "preprocessed" / "anomaly_label.csv"
SUMMARY_PATH = "evaluation/deeplog_summary.json"


class DeepLogEvaluator:

    def __init__(self, experiment_manager: ExperimentManager, dataset_manager: DatasetManager, artifact_store: ArtifactStore) -> None:
        self._exp = experiment_manager
        self._ds = dataset_manager
        self._store = artifact_store

    def _resolve_ground_truth_path(self, dataset_manifest) -> str | None:
        """Resolve the path to the DeepLog ground-truth CSV.

        Resolution order:
        1. If the dataset manifest provides a path, use it.
        2. Otherwise use the project's default HDFS path.
        Returns an absolute or workspace-relative path string, or None.
        """
        if dataset_manifest and getattr(dataset_manifest, "source", None):
            try:
                src = dataset_manifest.source
                # common manifest keys that could point to the ground-truth CSV
                for k in ("deeplog_ground_truth", "deep_log_ground_truth", "ground_truth", "anomaly_label", "anomaly_labels", "labels_path", "anomaly_label_path", "ground_truth_path"):
                    if k in src and isinstance(src[k], str) and src[k].strip():
                        return src[k].strip()
                # scan values for plausible CSV path
                for v in src.values():
                    if isinstance(v, str) and (v.endswith(".csv") and ("anomaly" in v or "label" in v or "ground" in v)):
                        return v
            except Exception:
                # ignore manifest parsing errors and fall back
                pass

        # fallback to default HDFS path if it exists
        if DEFAULT_HDFS_LABELS.exists():
            return str(DEFAULT_HDFS_LABELS)
        return None

    def _read_predictions_phase6(self) -> Dict[str, bool]:
        """Read Phase 6 published predictions and return mapping block_id -> is_anomaly(bool).

        Raises DeepLogEvaluatorError on missing file, missing required columns, or parse errors.
        """
        try:
            data = self._store.read_artifact(PHASE6_RUN, PHASE6_PREDICTIONS)
        except Exception as exc:
            logger.exception("Failed to read Phase 6 predictions from %s/%s", PHASE6_RUN, PHASE6_PREDICTIONS)
            raise DeepLogEvaluatorError(f"failed to read Phase 6 predictions: {exc}") from exc

        text = data.decode("utf-8")
        fh = text.splitlines()
        reader = csv.DictReader(fh)
        # check columns (case-insensitive)
        fieldnames = [fn for fn in (reader.fieldnames or [])]
        norm = {fn.lower().replace(" ", "").replace("-", ""): fn for fn in fieldnames}
        if not fieldnames:
            raise DeepLogEvaluatorError(f"Phase 6 predictions {PHASE6_PREDICTIONS} is empty or missing header")

        # required columns: block_id, is_anomaly
        block_key = None
        is_anom_key = None
        for k, orig in norm.items():
            if k in {"blockid", "block_id", "block"} and block_key is None:
                block_key = orig
            if k in {"isanomaly", "is_anomaly", "is_anom", "isanom"} and is_anom_key is None:
                is_anom_key = orig

        if block_key is None or is_anom_key is None:
            raise DeepLogEvaluatorError(f"Phase 6 predictions missing required columns. Required: 'block_id', 'is_anomaly' (found: {fieldnames})")

        mapping: Dict[str, bool] = {}
        for row in reader:
            try:
                bk = (row.get(block_key) or "").strip()
                if bk == "":
                    logger.debug("Skipping prediction row with empty block_id")
                    continue
                # Detect duplicate block_id: keep first occurrence, warn on duplicates
                if bk in mapping:
                    logger.warning("Duplicate block_id '%s' found in Phase 6 predictions; keeping first occurrence and ignoring this row", bk)
                    continue
                raw = row.get(is_anom_key)
                val = self._parse_bool_like(raw)
                mapping[bk] = val
            except DeepLogEvaluatorError:
                raise
            except Exception as exc:
                logger.exception("Failed to parse Phase 6 prediction row: %s", exc)
                raise DeepLogEvaluatorError(f"failed to parse Phase 6 predictions: {exc}") from exc

        return mapping

    def _read_ground_truth(self, path_or_manifest_location: str | None, dataset_id: str) -> Dict[str, bool]:
        """Read ground-truth CSV and return mapping BlockId -> bool(label).

        The `path_or_manifest_location` may be:
        - a path string (absolute or repo-relative)
        - None (in which case we will raise)

        First try to read via the ArtifactStore using dataset_id as root (useful when
        manifests point to dataset-local artifact paths). If that fails, try the
        filesystem path directly.
        """
        if not path_or_manifest_location:
            raise DeepLogEvaluatorError("no ground-truth location resolved for dataset")

        # Attempt to read via ArtifactStore first (dataset-scoped)
        text = None
        try:
            try:
                data = self._store.read_artifact(dataset_id, path_or_manifest_location)
                text = data.decode("utf-8")
            except Exception:
                # try reading as filesystem path
                p = Path(path_or_manifest_location)
                if not p.is_absolute():
                    # interpret relative paths relative to repo root
                    repo_root = Path(__file__).resolve().parents[2]
                    p = repo_root / p
                if not p.exists():
                    raise DeepLogEvaluatorError(f"ground-truth file not found at {path_or_manifest_location}")
                text = p.read_text(encoding="utf-8")
        except DeepLogEvaluatorError:
            raise
        except Exception as exc:
            logger.exception("Failed to read ground-truth from %s: %s", path_or_manifest_location, exc)
            raise DeepLogEvaluatorError(f"failed to read ground-truth: {exc}") from exc

        fh = text.splitlines()
        reader = csv.DictReader(fh)
        fieldnames = [fn for fn in (reader.fieldnames or [])]
        norm = {fn.lower().replace(" ", "").replace("-", ""): fn for fn in fieldnames}

        if not fieldnames:
            raise DeepLogEvaluatorError(f"ground-truth file {path_or_manifest_location} is empty or missing header")

        # required columns: BlockId, Label (case-insensitive)
        block_key = None
        label_key = None
        for k, orig in norm.items():
            if k in {"blockid", "block_id", "block"} and block_key is None:
                block_key = orig
            if k in {"label", "groundtruth", "ground_truth", "anomalylabel", "anomaly_label", "y", "target"} and label_key is None:
                label_key = orig

        if block_key is None or label_key is None:
            raise DeepLogEvaluatorError(f"ground-truth file missing required columns. Required: 'BlockId', 'Label' (found: {fieldnames})")

        mapping: Dict[str, bool] = {}
        for row in reader:
            try:
                bk = (row.get(block_key) or "").strip()
                if bk == "":
                    logger.debug("Skipping ground-truth row with empty BlockId")
                    continue
                # Detect duplicate BlockId: keep first occurrence, warn on duplicates
                if bk in mapping:
                    logger.warning("Duplicate BlockId '%s' found in ground-truth; keeping first occurrence and ignoring this row", bk)
                    continue
                raw = row.get(label_key)
                val = self._normalize_label(raw)
                mapping[bk] = val
            except DeepLogEvaluatorError:
                raise
            except Exception as exc:
                logger.exception("Failed to parse ground-truth row: %s", exc)
                raise DeepLogEvaluatorError(f"failed to parse ground-truth: {exc}") from exc

        return mapping

    def _normalize_label(self, raw) -> bool:
        """Normalize various label representations into bool.

        Accepts: 'Normal', 'normal', '0', 0, False, 'False' -> False
                 'Anomaly', 'anomaly', '1', 1, True, 'True' -> True
        Raises DeepLogEvaluatorError on unknown values.
        """
        if raw is None:
            raise DeepLogEvaluatorError("encountered empty label value in ground-truth")
        if isinstance(raw, bool):
            return raw
        s = str(raw).strip()
        if s == "":
            raise DeepLogEvaluatorError("encountered empty label value in ground-truth")
        low = s.lower()
        if low in {"normal", "0", "false", "f", "no", "n"}:
            return False
        if low in {"anomaly", "1", "true", "t", "yes", "y"}:
            return True
        raise DeepLogEvaluatorError(f"unknown ground-truth label value: '{s}'")

    def _parse_bool_like(self, raw) -> bool:
        """Parse published prediction boolean-like values into bool.

        Accepts '1','0','true','false', numeric 1/0, and boolean values.
        """
        if raw is None:
            raise DeepLogEvaluatorError("missing is_anomaly value in predictions")
        if isinstance(raw, bool):
            return raw
        s = str(raw).strip()
        low = s.lower()
        if low in {"1", "true", "t", "yes", "y"}:
            return True
        if low in {"0", "false", "f", "no", "n"}:
            return False
        raise DeepLogEvaluatorError(f"unknown boolean-like prediction value: '{s}'")

    def _compute_metrics_and_confusion(self, y_true: List[bool], y_pred: List[bool]) -> Tuple[DeepLogMetrics, Dict[str, int]]:
        if len(y_true) != len(y_pred):
            logger.error("Length mismatch: true=%d pred=%d", len(y_true), len(y_pred))
            raise DeepLogEvaluatorError("ground truth and predictions length mismatch")
        tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
        tn = sum(1 for t, p in zip(y_true, y_pred) if (not t) and (not p))
        fp = sum(1 for t, p in zip(y_true, y_pred) if (not t) and p)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t and (not p))
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0.0
        metrics = DeepLogMetrics(precision=precision, recall=recall, f1=f1)
        confusion = {"tp": tp, "tn": tn, "fp": fp, "fn": fn, "accuracy": accuracy}
        return metrics, confusion

    def evaluate(self, experiment_id: str, dataset_id: str) -> DeepLogResult:
        # validate experiment exists
        try:
            _meta = self._exp.get_metadata(experiment_id)
        except ExperimentNotFoundError as exc:
            logger.error("Experiment %s not found", experiment_id)
            raise DeepLogEvaluatorError("experiment not found") from exc

        # attempt to read dataset manifest, but allow evaluation to fail with
        # a descriptive error if ground-truth cannot be resolved
        try:
            dataset_manifest = self._ds.get_manifest(dataset_id)
        except DatasetNotFoundError:
            dataset_manifest = None
            logger.info("Dataset manifest for %s not found; attempting default ground-truth lookup", dataset_id)

        try:
            # resolve ground-truth location
            gt_location = self._resolve_ground_truth_path(dataset_manifest)
            if not gt_location:
                raise DeepLogEvaluatorError("could not resolve ground-truth location: dataset manifest missing and default HDFS path not found")

            # read inputs
            preds_map = self._read_predictions_phase6()
            gt_map = self._read_ground_truth(gt_location, dataset_id)

            total_preds = len(preds_map)
            total_gt = len(gt_map)

            # join on block_id
            pred_keys = set(preds_map.keys())
            gt_keys = set(gt_map.keys())
            matched_keys = sorted(k for k in pred_keys & gt_keys)
            matched = len(matched_keys)
            unmatched_preds = len(pred_keys - gt_keys)
            unmatched_gt = len(gt_keys - pred_keys)

            logger.info("DeepLog join summary: total_preds=%d total_gt=%d matched=%d unmatched_preds=%d unmatched_gt=%d", total_preds, total_gt, matched, unmatched_preds, unmatched_gt)

            if matched == 0:
                logger.error("No matching prediction-label pairs found for dataset %s", dataset_id)
                raise DeepLogEvaluatorError("no matching prediction-label pairs found")

            y_true = [gt_map[k] for k in matched_keys]
            y_pred = [preds_map[k] for k in matched_keys]

            metrics, confusion = self._compute_metrics_and_confusion(y_true, y_pred)

            # Preserve existing summary schema: precision, recall, f1
            summary = {
                "experiment_id": experiment_id,
                "dataset_id": dataset_id,
                "precision": metrics.precision,
                "recall": metrics.recall,
                "f1": metrics.f1,
            }

            # Write summary JSON (unchanged filename/schema)
            self._store.write_json(experiment_id, SUMMARY_PATH, summary)

            # Log extended metrics and confusion matrix for diagnostics
            logger.info("DeepLog metrics for %s/%s - accuracy=%.4f precision=%.4f recall=%.4f f1=%.4f", dataset_id, experiment_id, confusion["accuracy"], metrics.precision, metrics.recall, metrics.f1)
            logger.info("Confusion matrix: tp=%d fp=%d fn=%d tn=%d", confusion["tp"], confusion["fp"], confusion["fn"], confusion["tn"])

            return DeepLogResult(experiment_id=experiment_id, dataset_id=dataset_id, metrics=metrics, summary_path=SUMMARY_PATH)
        except (ArtifactStoreError, ValueError, DeepLogEvaluatorError) as exc:
            logger.exception("DeepLog evaluation failed for %s/%s", experiment_id, dataset_id)
            # Preserve original error details while maintaining exception chaining
            raise DeepLogEvaluatorError(f"evaluation failed: {exc}") from exc
