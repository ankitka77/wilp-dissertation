"""Dedicated evaluator for anomaly detection models."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn import metrics


class Evaluator:
    """Compute standard evaluation metrics for binary anomaly detection tasks."""

    def evaluate(self, y_true: Any, y_pred: Any, y_scores: Any | None = None) -> dict[str, Any]:
        """Compute accuracy, precision, recall, F1, ROC-AUC, confusion matrix and classification report."""
        true_array = np.asarray(y_true)
        pred_array = np.asarray(y_pred)

        metrics_dict: dict[str, Any] = {
            "accuracy": float(metrics.accuracy_score(true_array, pred_array)),
            "precision": float(metrics.precision_score(true_array, pred_array, zero_division=0)),
            "recall": float(metrics.recall_score(true_array, pred_array, zero_division=0)),
            "f1": float(metrics.f1_score(true_array, pred_array, zero_division=0)),
            "confusion_matrix": metrics.confusion_matrix(true_array, pred_array).tolist(),
            "classification_report": metrics.classification_report(true_array, pred_array, zero_division=0, output_dict=True),
        }

        if y_scores is not None:
            score_array = np.asarray(y_scores)
            if len(np.unique(true_array)) >= 2:
                metrics_dict["roc_auc"] = float(metrics.roc_auc_score(true_array, score_array))
            else:
                metrics_dict["roc_auc"] = float("nan")
        else:
            metrics_dict["roc_auc"] = float("nan")

        return metrics_dict
