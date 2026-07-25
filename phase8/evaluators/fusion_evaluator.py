"""Fusion Evaluator for Phase 8 Milestone 3.

Combines KPI and DeepLog evaluator outputs into a fused prediction and
computes fusion-level metrics. Uses only existing infrastructure:
`ExperimentManager`, `DatasetManager`, `ArtifactStore`, `KPIEvaluator`,
and `DeepLogEvaluator`.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List
import logging

from phase8.core.artifact_store import ArtifactStore, ArtifactStoreError
from phase8.core.experiment_manager import ExperimentManager, ExperimentNotFoundError
from phase8.core.dataset_manager import DatasetManager, DatasetNotFoundError
from phase8.evaluators.kpi_evaluator import KPIEvaluator
from phase8.evaluators.deep_log_evaluator import DeepLogEvaluator
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
KPI_PREDICTIONS = "predictions.csv"
DEEPLOG_PREDICTIONS = "predictions.seq"
FUSION_PREDICTIONS = "evaluation/fusion_predictions.txt"
FUSION_SUMMARY = "evaluation/fusion_summary.json"


def _parse_csv_predictions(data: bytes) -> List[int]:
    text = data.decode("utf-8").strip()
    if text == "":
        return []
    return [int(line.strip().split(",")[0]) for line in text.splitlines()]


def _parse_seq_predictions(data: bytes) -> List[int]:
    text = data.decode("utf-8").strip()
    if text == "":
        return []
    vals = []
    for line in text.splitlines():
        vals.extend(int(x) for x in line.strip().split())
    return vals


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


class FusionEvaluator:
    """Combine KPI and DeepLog predictions into a fused evaluation.

    API: evaluate(experiment_id, kpi_dataset_id, deeplog_dataset_id, strategy=FusionStrategy.AND)
    """

    def __init__(self, experiment_manager: ExperimentManager, dataset_manager: DatasetManager, artifact_store: ArtifactStore) -> None:
        self._exp = experiment_manager
        self._ds = dataset_manager
        self._store = artifact_store
        # compose evaluators but FusionEvaluator will re-read predictions itself
        self._kpi = KPIEvaluator(self._exp, self._ds, self._store)
        self._dl = DeepLogEvaluator(self._exp, self._ds, self._store)

    def evaluate(self, experiment_id: str, kpi_dataset_id: str, deeplog_dataset_id: str, strategy: FusionStrategy = FusionStrategy.AND) -> FusionResult:
        # validate experiment
        try:
            _m = self._exp.get_metadata(experiment_id)
        except ExperimentNotFoundError as exc:
            logger.error("Experiment %s not found", experiment_id)
            raise EvaluatorError("experiment not found") from exc

        # run underlying evaluators to ensure their artifacts/metrics are present
        try:
            self._kpi.evaluate(experiment_id, kpi_dataset_id)
            self._dl.evaluate(experiment_id, deeplog_dataset_id)
        except Exception as exc:
            logger.exception("Underlying evaluator failed")
            raise

        # read predictions
        try:
            kpi_pred_bytes = self._store.read_artifact(kpi_dataset_id, KPI_PREDICTIONS)
            dl_pred_bytes = self._store.read_artifact(deeplog_dataset_id, DEEPLOG_PREDICTIONS)
        except ArtifactStoreError as exc:
            logger.exception("Failed to read predictions for fusion")
            raise EvaluatorError("failed to read predictions") from exc

        kpi_preds = _parse_csv_predictions(kpi_pred_bytes)
        dl_preds = _parse_seq_predictions(dl_pred_bytes)

        # length alignment
        if len(kpi_preds) != len(dl_preds):
            logger.error("Prediction length mismatch kpi=%d dl=%d", len(kpi_preds), len(dl_preds))
            raise EvaluatorError("prediction length mismatch")

        # fusion
        if strategy == FusionStrategy.AND:
            fused = [int(a == 1 and b == 1) for a, b in zip(kpi_preds, dl_preds)]
        else:  # OR
            fused = [int(a == 1 or b == 1) for a, b in zip(kpi_preds, dl_preds)]

        # write fused predictions
        try:
            data = "\n".join(str(x) for x in fused).encode("utf-8")
            self._store.write_artifact(experiment_id, FUSION_PREDICTIONS, data)
        except ArtifactStoreError as exc:
            logger.exception("Failed to write fusion predictions")
            raise EvaluatorError("failed to write fusion predictions") from exc

        # compute fusion metrics against KPI dataset ground truth (assume same GT)
        try:
            gt_bytes = self._store.read_artifact(kpi_dataset_id, "ground_truth.csv")
            y_true = _parse_csv_predictions(gt_bytes)
            metrics = _compute_metrics(y_true, fused)
        except ArtifactStoreError as exc:
            logger.exception("Failed to read ground truth for fusion")
            raise EvaluatorError("failed to read ground truth") from exc

        # write summary
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
        except ArtifactStoreError as exc:
            logger.exception("Failed to write fusion summary")
            raise EvaluatorError("failed to write fusion summary") from exc

        return FusionResult(experiment_id=experiment_id, kpi_dataset_id=kpi_dataset_id, deeplog_dataset_id=deeplog_dataset_id, metrics=metrics, predictions_path=FUSION_PREDICTIONS, summary_path=FUSION_SUMMARY)
