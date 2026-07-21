"""Metrics utilities for Phase 6.

Provides `MetricsProvider` with pure methods computing top-k accuracy,
precision/recall, anomaly score conversions, and batch-level aggregates.
"""
from __future__ import annotations

from typing import Dict, Iterable, List
import logging
import math

logger = logging.getLogger("project")


class MetricsProvider:
    """Stateless provider of common evaluation metrics.

    All methods are pure and accept Python built-in types. They perform
    lightweight validation and log issues via the centralized logger.
    """

    @staticmethod
    def topk_accuracy(predictions: Iterable[Iterable[int]], targets: Iterable[int], k: int) -> float:
        """Compute top-K accuracy: fraction of targets present in the top-K predictions.

        Parameters
        ----------
        predictions:
            Iterable of iterables containing predicted ids (ordered by score).
        targets:
            Iterable of true target ids (one per prediction).
        k:
            Number of top predictions to consider.

        Returns
        -------
        float
            Top-K accuracy in [0.0, 1.0].
        """
        if k <= 0:
            raise ValueError("k must be > 0")

        preds = list(predictions)
        tars = list(targets)
        if len(preds) != len(tars):
            raise ValueError("predictions and targets must have the same length")

        hits = 0
        for p, t in zip(preds, tars):
            topk = list(p)[:k]
            if t in topk:
                hits += 1
        return hits / len(tars) if tars else 0.0

    @staticmethod
    def topk_recall_precision(predictions: Iterable[Iterable[int]], targets: Iterable[int], k: int) -> Dict[str, float]:
        """Compute precision, recall, and F1 for top-K predictions.

        Interpretation:
        - True positives (TP): number of examples where the true target is in
          the top-K list.
        - Recall = TP / N (N = number of examples) which equals top-K accuracy.
        - Precision = TP / (N * k) since each example contributes k predicted
          items.

        Returns a dict with keys: `precision`, `recall`, `f1`.
        """
        if k <= 0:
            raise ValueError("k must be > 0")

        preds = list(predictions)
        tars = list(targets)
        if len(preds) != len(tars):
            raise ValueError("predictions and targets must have the same length")

        n = len(tars)
        if n == 0:
            return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

        tp = 0
        for p, t in zip(preds, tars):
            if t in list(p)[:k]:
                tp += 1

        recall = tp / n
        precision = tp / (n * k)
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        return {"precision": precision, "recall": recall, "f1": f1}

    @staticmethod
    def anomaly_score_from_probs(predicted_probs: Iterable[float]) -> float:
        """Convert a list of predicted probabilities into an anomaly score.

        The anomaly score is defined as 1.0 - max(predicted_probs), producing a
        value in [0.0, 1.0] where higher values indicate higher anomaly.
        """
        probs = list(predicted_probs)
        if not probs:
            logger.warning("Empty predicted_probs passed to anomaly_score_from_probs; returning 0.0")
            return 0.0
        # Normalize to [0,1] defensively
        try:
            norm = MetricsProvider._normalize_probs(probs)
        except Exception:
            logger.exception("Failed to normalize probabilities")
            norm = [float(p) for p in probs]
        mx = max(norm)
        # Clamp to [0,1]
        mx = max(0.0, min(1.0, mx))
        return 1.0 - mx

    @staticmethod
    def batch_metrics(predicted_topk: Iterable[Iterable[int]], predicted_probs: Iterable[Iterable[float]], targets: Iterable[int], k: int) -> Dict[str, float]:
        """Compute a collection of metrics for a batch.

        Returns a mapping containing at least: `topk_accuracy`, `precision`,
        `recall`, `f1`, `avg_anomaly_score`.
        """
        preds = list(predicted_topk)
        probs = list(predicted_probs)
        tars = list(targets)
        if not (len(preds) == len(probs) == len(tars)):
            raise ValueError("predicted_topk, predicted_probs, and targets must have the same length")
        if k <= 0:
            raise ValueError("k must be > 0")

        topk_acc = MetricsProvider.topk_accuracy(preds, tars, k)
        pr = MetricsProvider.topk_recall_precision(preds, tars, k)

        # Anomaly scores per example
        scores: List[float] = []
        for prob_list in probs:
            try:
                score = MetricsProvider.anomaly_score_from_probs(prob_list)
            except Exception:
                logger.exception("Failed to compute anomaly score for an example; using 0.0")
                score = 0.0
            scores.append(score)

        avg_anomaly = float(sum(scores) / len(scores)) if scores else 0.0

        out = {"topk_accuracy": float(topk_acc), "precision": float(pr["precision"]), "recall": float(pr["recall"]), "f1": float(pr["f1"]), "avg_anomaly_score": avg_anomaly}
        return out

    @staticmethod
    def _normalize_probs(probs: List[float]) -> List[float]:
        """Normalize a list of non-negative numbers to sum to 1.0.

        If all values are zero or normalization fails, returns the original
        list cast to floats.
        """
        arr = [float(p) for p in probs]
        total = sum(x for x in arr if x >= 0.0)
        if total <= 0.0 or math.isclose(total, 0.0):
            return arr
        return [x / total for x in arr]


__all__ = ["MetricsProvider"]
