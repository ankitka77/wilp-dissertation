"""DeepLog Evaluator for Phase 8 Milestone 2.

Simplified sequence-level evaluator that compares predicted anomaly labels
per event against ground truth. Produces basic precision/recall/f1 metrics
and writes artifacts via the ArtifactStore.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List
import logging

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


# Module-level filename constants
GROUND_TRUTH_FILENAME = "ground_truth.seq"
PREDICTIONS_FILENAME = "predictions.seq"
SUMMARY_PATH = "evaluation/deeplog_summary.json"


class DeepLogEvaluator:

    def __init__(self, experiment_manager: ExperimentManager, dataset_manager: DatasetManager, artifact_store: ArtifactStore) -> None:
        self._exp = experiment_manager
        self._ds = dataset_manager
        self._store = artifact_store

    def _read_seq(self, dataset_id: str, relative: str) -> List[int]:
        data = self._store.read_artifact(dataset_id, relative)
        text = data.decode("utf-8").strip()
        if text == "":
            return []
        # each line is a space-separated sequence of 0/1 tokens
        vals = []
        for line in text.splitlines():
            vals.extend(int(x) for x in line.strip().split())
        return vals

    def _compute_metrics(self, y_true: List[int], y_pred: List[int]) -> DeepLogMetrics:
        if len(y_true) != len(y_pred):
            logger.error("Sequence length mismatch true=%d pred=%d", len(y_true), len(y_pred))
            raise DeepLogEvaluatorError("sequence length mismatch")
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        return DeepLogMetrics(precision=precision, recall=recall, f1=f1)

    def evaluate(self, experiment_id: str, dataset_id: str) -> DeepLogResult:
        # validate experiment exists
        try:
            _meta = self._exp.get_metadata(experiment_id)
        except ExperimentNotFoundError as exc:
            logger.error("Experiment %s not found", experiment_id)
            raise DeepLogEvaluatorError("experiment not found") from exc

        # validate dataset exists
        try:
            self._ds.get_manifest(dataset_id)
        except DatasetNotFoundError as exc:
            logger.error("Dataset %s not found", dataset_id)
            raise DeepLogEvaluatorError("dataset not found") from exc

        try:
            y_true = self._read_seq(dataset_id, GROUND_TRUTH_FILENAME)
            y_pred = self._read_seq(dataset_id, PREDICTIONS_FILENAME)
            metrics = self._compute_metrics(y_true, y_pred)
            summary = {
                "experiment_id": experiment_id,
                "dataset_id": dataset_id,
                "precision": metrics.precision,
                "recall": metrics.recall,
                "f1": metrics.f1,
            }
            self._store.write_json(experiment_id, SUMMARY_PATH, summary)
            logger.info("DeepLog evaluation complete for %s/%s", experiment_id, dataset_id)
            return DeepLogResult(experiment_id=experiment_id, dataset_id=dataset_id, metrics=metrics, summary_path=SUMMARY_PATH)
        except (ArtifactStoreError, ValueError, DeepLogEvaluatorError) as exc:
            logger.exception("DeepLog evaluation failed for %s/%s", experiment_id, dataset_id)
            raise DeepLogEvaluatorError("evaluation failed") from exc
