"""Fusion Evaluator for Phase 8 Milestone 3.

Evaluator that measures correctness of Phase 7's published fusion output.

Important: this evaluator is a pure consumer of the Phase 7 published
`fused_predictions.csv` artifact and DOES NOT recreate fusion logic
(normalization, weighting, thresholding, or score aggregation).

It reads the Phase 7 fused predictions, resolves ground-truth via the
`DatasetManager` (with a fallback to the standard HDFS anomaly_label.csv),
joins on the stable identifier published by Phase 7, validates the join,
and computes evaluation metrics.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Dict
import logging
import csv
from pathlib import Path

from phase8.core.artifact_store import ArtifactStore, ArtifactStoreError
from phase8.core.experiment_manager import ExperimentManager, ExperimentNotFoundError
from phase8.core.dataset_manager import DatasetManager, DatasetNotFoundError
from .exceptions import EvaluatorError

logger = logging.getLogger("phase8.evaluators.fusion")


class FusionStrategy(Enum):
    AND = "and"
    OR = "or"


@dataclass(frozen=True)
class FusionMetrics:
    precision: float
    recall: float
    f1: float


@dataclass(frozen=True)
class FusionResult:
    experiment_id: str
    kpi_dataset_id: str
    deeplog_dataset_id: str
    metrics: FusionMetrics
    predictions_path: str
    summary_path: str


# filenames
PHASE7_RUN = "phase7/latest"
PHASE7_PREDICTIONS = "fused_predictions.csv"
FUSION_SUMMARY = "evaluation/fusion_summary.json"
DEFAULT_HDFS_LABELS = Path(__file__).resolve().parents[2] / "data" / "logs" / "HDFS_v1" / "preprocessed" / "anomaly_label.csv"


def _compute_metrics(y_true: List[int], y_pred: List[int]) -> FusionMetrics:
    if len(y_true) != len(y_pred):
        raise EvaluatorError("length mismatch")
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    return FusionMetrics(precision=precision, recall=recall, f1=f1)


def _parse_bool_like(raw) -> int:
    if raw is None:
        raise EvaluatorError("missing prediction value")
    if isinstance(raw, bool):
        return 1 if raw else 0
    s = str(raw).strip()
    low = s.lower()
    if low in {"1", "true", "t", "yes", "y"}:
        return 1
    if low in {"0", "false", "f", "no", "n"}:
        return 0
    raise EvaluatorError(f"unknown boolean-like value: '{s}'")


class FusionEvaluator:
    """Combine KPI and DeepLog predictions into a fused evaluation.

    API: evaluate(experiment_id, kpi_dataset_id, deeplog_dataset_id, strategy=FusionStrategy.AND)
    """

    def __init__(self, experiment_manager: ExperimentManager, dataset_manager: DatasetManager, artifact_store: ArtifactStore) -> None:
        self._exp = experiment_manager
        self._ds = dataset_manager
        self._store = artifact_store
        # FusionEvaluator is a pure evaluator: it consumes Phase 7 published
        # fused predictions and does not recreate fusion logic.

    def evaluate(self, experiment_id: str, kpi_dataset_id: str, deeplog_dataset_id: str, strategy: FusionStrategy = FusionStrategy.AND) -> FusionResult:
        # validate experiment
        try:
            _m = self._exp.get_metadata(experiment_id)
        except ExperimentNotFoundError as exc:
            logger.error("Experiment %s not found", experiment_id)
            raise EvaluatorError("experiment not found") from exc
        # NOTE: `strategy` parameter is retained for API compatibility but
        # ignored because Phase 7 already produced the final fused decision.

        # Read Phase 7 published fused predictions
        try:
            data = self._store.read_artifact(PHASE7_RUN, PHASE7_PREDICTIONS)
        except Exception as exc:
            logger.exception("Failed to read Phase 7 fused predictions from %s/%s", PHASE7_RUN, PHASE7_PREDICTIONS)
            raise EvaluatorError(f"failed to read Phase 7 fused predictions: {exc}") from exc

        # parse CSV and validate required Phase 7 schema (strict)
        try:
            text = data.decode("utf-8")
        except Exception as exc:
            raise EvaluatorError(f"failed decoding fused_predictions.csv: {exc}") from exc

        fh = text.splitlines()
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        if not fieldnames:
            raise EvaluatorError(f"Phase 7 fused_predictions file {PHASE7_PREDICTIONS} is empty or missing header")

        # Strict schema: require exact column names 'entity_id' and 'final_label'
        required_cols = {"entity_id", "final_label"}
        found_cols = set(fieldnames)
        if not required_cols.issubset(found_cols):
            raise EvaluatorError(f"Phase 7 fused_predictions must contain columns: {sorted(required_cols)}; found: {fieldnames}")

        id_key = "entity_id"
        decision_key = "final_label"

        # Read rows into mapping identifier -> decision (int 0/1), detect duplicates
        preds_map: Dict[str, int] = {}
        duplicate_ids: List[str] = []
        total_rows = 0
        blank_entity_count = 0
        for row in reader:
            total_rows += 1
            try:
                ident = (row.get(id_key) or "").strip()
                if ident == "":
                    blank_entity_count += 1
                    #logger.warning("Skipping fused_predictions row with blank 'entity_id' (row %d)", total_rows)
                    continue
                if ident in preds_map:
                    logger.warning("Duplicate identifier '%s' found in fused_predictions; keeping first occurrence and ignoring this row", ident)
                    duplicate_ids.append(ident)
                    continue
                raw = row.get(decision_key)
                val = _parse_bool_like(raw)
                preds_map[ident] = val
            except EvaluatorError:
                raise
            except Exception as exc:
                logger.exception("Failed to parse fused_predictions row: %s", exc)
                raise EvaluatorError(f"failed to parse fused_predictions: {exc}") from exc

        logger.info("Loaded %d fused prediction rows (evaluable=%d, blank_entity_rows=%d, duplicates=%d)", total_rows, len(preds_map), blank_entity_count, len(duplicate_ids))

        # Resolve ground truth for the fusion evaluation.
        # Preferred order:
        # 1) fusion-specific location published with Phase 7 artifacts (manifest or published_info)
        # 2) project's standard HDFS anomaly_label.csv
        # 3) KPI dataset manifest (backward-compat fallback)
        try:
            gt_location = None

            # 1) Try Phase 7 manifest for an explicit ground-truth pointer
            try:
                phase7_manifest = self._store.read_json(PHASE7_RUN, "phase7_manifest.json")
            except Exception:
                phase7_manifest = None

            if phase7_manifest:
                # check common manifest keys that could contain a ground-truth path
                for key in ("ground_truth", "ground_truth_path", "anomaly_label", "labels_path"):
                    v = phase7_manifest.get(key)
                    if isinstance(v, str) and v.strip():
                        gt_location = v.strip()
                        logger.info("Using fusion-specific ground-truth from Phase 7 manifest: %s", key)
                        break
                # also check configuration snapshot if present
                if not gt_location:
                    cfg = phase7_manifest.get("configuration_snapshot") or {}
                    for key in ("ground_truth", "ground_truth_path", "anomaly_label", "labels_path"):
                        v = cfg.get(key)
                        if isinstance(v, str) and v.strip():
                            gt_location = v.strip()
                            logger.info("Using fusion-specific ground-truth from Phase 7 configuration_snapshot: %s", key)
                            break

            # Also allow a lightweight published_info.json to point at ground-truth
            if not gt_location:
                try:
                    pubinfo = self._store.read_json(PHASE7_RUN, "published_info.json")
                except Exception:
                    pubinfo = None
                if pubinfo and isinstance(pubinfo.get("ground_truth"), str) and pubinfo.get("ground_truth").strip():
                    gt_location = pubinfo.get("ground_truth").strip()
                    logger.info("Using fusion-specific ground-truth from Phase 7 published_info.json")

            # 2) If still unresolved, prefer the standard HDFS labels file
            if not gt_location and DEFAULT_HDFS_LABELS.exists():
                gt_location = str(DEFAULT_HDFS_LABELS)
                logger.info("Using default HDFS ground-truth at %s", gt_location)

            # 3) Fallback: consult KPI dataset manifest for legacy compatibility
            if not gt_location:
                try:
                    dataset_manifest = self._ds.get_manifest(kpi_dataset_id)
                except DatasetNotFoundError:
                    dataset_manifest = None
                    logger.info("KPI dataset manifest for %s not found; cannot use as fallback", kpi_dataset_id)

                if dataset_manifest and getattr(dataset_manifest, "source", None):
                    src = dataset_manifest.source
                    for k in ("deeplog_ground_truth", "deep_log_ground_truth", "ground_truth", "anomaly_label", "anomaly_labels", "labels_path", "anomaly_label_path", "ground_truth_path"):
                        if k in src and isinstance(src[k], str) and src[k].strip():
                            gt_location = src[k].strip()
                            logger.info("Using ground-truth from KPI dataset manifest key: %s", k)
                            break
                    if not gt_location:
                        for v in src.values():
                            if isinstance(v, str) and (v.endswith(".csv") and ("anomaly" in v or "label" in v or "ground" in v)):
                                gt_location = v
                                logger.info("Using ground-truth from KPI dataset manifest (heuristic match)")
                                break

            if not gt_location:
                raise EvaluatorError("could not resolve ground-truth location: no Phase 7 fusion-specific pointer, default HDFS missing, and KPI dataset manifest absent")

            # Read ground-truth CSV (try dataset-scoped artifact read first, then filesystem)
            try:
                # attempt to read as an artifact under the Phase7 run first, then as dataset-scoped artifact
                data_gt = None
                try:
                    data_gt = self._store.read_artifact(PHASE7_RUN, gt_location)
                except Exception:
                    # try as dataset-scoped artifact using kpi dataset id
                    try:
                        data_gt = self._store.read_artifact(kpi_dataset_id, gt_location)
                    except Exception:
                        data_gt = None

                if data_gt is not None:
                    text_gt = data_gt.decode("utf-8")
                else:
                    p = Path(gt_location)
                    if not p.is_absolute():
                        repo_root = Path(__file__).resolve().parents[2]
                        p = repo_root / p
                    if not p.exists():
                        raise EvaluatorError(f"ground-truth file not found at {gt_location}")
                    text_gt = p.read_text(encoding="utf-8")
            except EvaluatorError:
                raise
            except Exception as exc:
                logger.exception("Failed to read ground-truth file at %s", gt_location)
                raise EvaluatorError(f"failed to read ground-truth: {exc}") from exc

            # Parse GT CSV
            fh2 = text_gt.splitlines()
            reader2 = csv.DictReader(fh2)
            gt_fieldnames = [fn for fn in (reader2.fieldnames or [])]
            if not gt_fieldnames:
                raise EvaluatorError(f"ground-truth file {gt_location} is empty or missing header")
            norm2 = {fn.lower().replace(" ", "").replace("-", ""): fn for fn in gt_fieldnames}
            # find BlockId and Label
            block_key = None
            label_key = None
            for k, orig in norm2.items():
                if k in {"blockid", "block_id", "block"} and block_key is None:
                    block_key = orig
                if k in {"label", "groundtruth", "ground_truth", "anomalylabel", "anomaly_label", "y", "target"} and label_key is None:
                    label_key = orig
            if block_key is None or label_key is None:
                raise EvaluatorError(f"ground-truth file missing required columns. Required: 'BlockId', 'Label' (found: {gt_fieldnames})")

            gt_map: Dict[str, int] = {}
            dup_gt: List[str] = []
            total_gt_rows = 0
            for row in reader2:
                total_gt_rows += 1
                bid = (row.get(block_key) or "").strip()
                if bid == "":
                    logger.debug("Skipping ground-truth row with empty BlockId")
                    continue
                if bid in gt_map:
                    logger.warning("Duplicate BlockId '%s' found in ground-truth; keeping first occurrence and ignoring this row", bid)
                    dup_gt.append(bid)
                    continue
                raw = row.get(label_key)
                # normalize label: Anomaly -> 1, Normal -> 0
                s = str(raw).strip()
                low = s.lower()
                if low in {"anomaly", "1", "true", "t", "yes", "y"}:
                    gt_map[bid] = 1
                elif low in {"normal", "0", "false", "f", "no", "n"}:
                    gt_map[bid] = 0
                else:
                    raise EvaluatorError(f"unknown ground-truth label value: '{s}'")

            logger.info("Loaded %d ground-truth rows (unique=%d, duplicates=%d)", total_gt_rows, len(gt_map), len(dup_gt))

        except EvaluatorError:
            raise
        except Exception as exc:
            logger.exception("Failed to resolve/read ground-truth for fusion evaluation")
            raise EvaluatorError(f"evaluation failed: {exc}") from exc

        # Join and validate
        try:
            pred_keys = set(preds_map.keys())
            gt_keys = set(gt_map.keys())
            matched_keys = sorted(k for k in pred_keys & gt_keys)
            matched = len(matched_keys)
            unmatched_preds = len(pred_keys - gt_keys)
            unmatched_gt = len(gt_keys - pred_keys)

            logger.info("Fusion join summary: total_preds=%d total_gt=%d matched=%d unmatched_preds=%d unmatched_gt=%d", len(pred_keys), len(gt_keys), matched, unmatched_preds, unmatched_gt)

            if matched == 0:
                logger.error("No matching fused prediction - ground-truth pairs found for dataset %s", kpi_dataset_id)
                raise EvaluatorError("no matching prediction-label pairs found")

            y_true = [gt_map[k] for k in matched_keys]
            y_pred = [preds_map[k] for k in matched_keys]

            # compute metrics (reuse int lists)
            y_true_int = [int(x) for x in y_true]
            y_pred_int = [int(x) for x in y_pred]
            metrics = _compute_metrics(y_true_int, y_pred_int)

            # compute confusion for logging
            tp = sum(1 for t, p in zip(y_true_int, y_pred_int) if t == 1 and p == 1)
            tn = sum(1 for t, p in zip(y_true_int, y_pred_int) if t == 0 and p == 0)
            fp = sum(1 for t, p in zip(y_true_int, y_pred_int) if t == 0 and p == 1)
            fn = sum(1 for t, p in zip(y_true_int, y_pred_int) if t == 1 and p == 0)
            accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0.0

            logger.info("Fusion metrics: accuracy=%.4f precision=%.4f recall=%.4f f1=%.4f", accuracy, metrics.precision, metrics.recall, metrics.f1)
            logger.info("Confusion matrix: tp=%d fp=%d fn=%d tn=%d", tp, fp, fn, tn)

            # write summary (preserve schema)
            try:
                summary = {
                    "experiment_id": experiment_id,
                    "kpi_dataset_id": kpi_dataset_id,
                    "deeplog_dataset_id": deeplog_dataset_id,
                    "precision": metrics.precision,
                    "recall": metrics.recall,
                    "f1": metrics.f1,
                }
                self._store.write_json(experiment_id, FUSION_SUMMARY, summary)
            except Exception as exc:
                logger.exception("Failed to write fusion summary")
                raise EvaluatorError(f"failed to write fusion summary: {exc}") from exc

            # predictions_path: point to the Phase 7 published artifact for user reference
            predictions_path = f"{PHASE7_RUN}/{PHASE7_PREDICTIONS}"
            return FusionResult(experiment_id=experiment_id, kpi_dataset_id=kpi_dataset_id, deeplog_dataset_id=deeplog_dataset_id, metrics=metrics, predictions_path=predictions_path, summary_path=FUSION_SUMMARY)
        except EvaluatorError:
            raise
        except Exception as exc:
            logger.exception("Fusion evaluation failed for %s/%s", experiment_id, kpi_dataset_id)
            raise EvaluatorError(f"evaluation failed: {exc}") from exc
