"""Evaluation skeleton for anomaly detection outputs."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn import metrics


@dataclass
class EvaluationService:
    """Computes standard binary classification metrics."""

    def classification_report(self, y_true: pd.Series, y_pred: pd.Series) -> dict[str, float]:
        """Return core metrics used by the project roadmap."""
        return {
            "accuracy": float(metrics.accuracy_score(y_true, y_pred)),
            "precision": float(metrics.precision_score(y_true, y_pred, zero_division=0)),
            "recall": float(metrics.recall_score(y_true, y_pred, zero_division=0)),
            "f1": float(metrics.f1_score(y_true, y_pred, zero_division=0)),
        }

    def roc_auc(self, y_true: pd.Series, y_scores: pd.Series) -> float:
        """Compute ROC-AUC for probabilistic anomaly scores."""
        unique_labels = np.unique(y_true)
        if unique_labels.shape[0] < 2:
            raise ValueError("ROC-AUC requires at least two classes in y_true.")
        return float(metrics.roc_auc_score(y_true, y_scores))
