"""KPI Evaluator for Phase 8 Milestone 2.

Computes simple binary classification metrics (precision, recall, f1)
for KPI predictions and writes metric artifacts using the ArtifactStore.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Mapping
import logging
from pathlib import Path

from phase8.core.artifact_store import ArtifactStore, ArtifactStoreError
from phase8.core.experiment_manager import ExperimentManager, ExperimentNotFoundError
from phase8.core.dataset_manager import DatasetManager, DatasetNotFoundError
from .exceptions import KPIEvaluatorError

logger = logging.getLogger("phase8.evaluators.kpi")

# Module-level filename constants
GROUND_TRUTH_FILENAME = "ground_truth.csv"
PREDICTIONS_FILENAME = "predictions.csv"
SUMMARY_PATH = "evaluation/kpi_summary.json"

@dataclass(frozen=True)
class KPIMetrics:
    precision: float
    recall: float
    f1: float


@dataclass(frozen=True)
class KPIResult:
    experiment_id: str
    dataset_id: str
    metrics: KPIMetrics
    summary_path: str


class KPIEvaluator:
    """Evaluator for KPI binary predictions.

    The evaluator expects the dataset to contain two artifacts under the
    dataset id root: `ground_truth.csv` and `predictions.csv`. Each file is
    a CSV with one column per line (no header) containing `0` or `1`.
    """

    def __init__(self, experiment_manager: ExperimentManager, dataset_manager: DatasetManager, artifact_store: ArtifactStore) -> None:
        self._exp = experiment_manager
        self._ds = dataset_manager
        self._store = artifact_store

    def _read_series(self, dataset_id: str, relative: str) -> List[int]:
        data = self._store.read_artifact(dataset_id, relative)
        # deterministic parsing
        text = data.decode("utf-8").strip()
        if text == "":
            return []
        return [int(line.strip().split(",")[0]) for line in text.splitlines()]

    def _compute_metrics(self, y_true: List[int], y_pred: List[int]) -> KPIMetrics:
        if len(y_true) != len(y_pred):
            logger.error("Length mismatch: true=%d pred=%d", len(y_true), len(y_pred))
            raise KPIEvaluatorError("ground truth and predictions length mismatch")
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        return KPIMetrics(precision=precision, recall=recall, f1=f1)

    def evaluate(self, experiment_id: str, dataset_id: str) -> KPIResult:
        """Run evaluation for `experiment_id` using dataset `dataset_id`.

        The result is written as JSON to `evaluation/kpi_summary.json` under the
        experiment artifact root and the `KPIResult` is returned.
        """
        # validate experiment exists and retrieve metadata
        try:
            _meta = self._exp.get_metadata(experiment_id)
        except ExperimentNotFoundError as exc:
            logger.error("Experiment %s not found", experiment_id)
            raise KPIEvaluatorError("experiment not found") from exc

        # validate dataset exists
        try:
            self._ds.get_manifest(dataset_id)
        except DatasetNotFoundError as exc:
            logger.error("Dataset %s not found", dataset_id)
            raise KPIEvaluatorError("dataset not found") from exc

        # read, compute and persist
        try:
            y_true = self._read_series(dataset_id, GROUND_TRUTH_FILENAME)
            y_pred = self._read_series(dataset_id, PREDICTIONS_FILENAME)
            metrics = self._compute_metrics(y_true, y_pred)

            summary = {
                "experiment_id": experiment_id,
                "dataset_id": dataset_id,
                "precision": metrics.precision,
                "recall": metrics.recall,
                "f1": metrics.f1,
            }
            self._store.write_json(experiment_id, SUMMARY_PATH, summary)
            logger.info("KPI evaluation complete for %s/%s", experiment_id, dataset_id)
            return KPIResult(experiment_id=experiment_id, dataset_id=dataset_id, metrics=metrics, summary_path=SUMMARY_PATH)
        except (ArtifactStoreError, ValueError, KPIEvaluatorError) as exc:
            # ArtifactStoreError -> IO problems; ValueError -> parse issues
            logger.exception("KPI evaluation failed for %s/%s", experiment_id, dataset_id)
            raise KPIEvaluatorError("evaluation failed") from exc
