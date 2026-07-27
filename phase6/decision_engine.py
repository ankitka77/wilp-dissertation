"""Decision engine for Phase 6.

Convert prediction outputs and anomaly scores into binary decisions with
metadata (reason and confidence). This module follows the Phase 6
implementation blueprint and relies on the centralized configuration and
types.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Iterable, List, Optional
import logging

from phase6.types import DecisionResult, PredictionConfidence, DecisionReason, JSONDict, PredictionResult as PR
from phase6.metrics import MetricsProvider
from phase6.config import Config

logger = logging.getLogger("project")

# Whitelist of metadata fields to preserve from predictions into decisions
METADATA_FIELDS = [
    "sequence_id",
    "block_id",
    "source",
    "dataset",
    "session_id",
    "timestamp",
]


class DecisionEngineError(RuntimeError):
    """Raised when decision making cannot be completed."""


class DecisionEngine:
    """Engine that converts `PredictionResult` into `DecisionResult`.

    Parameters
    ----------
    config:
        Phase 6 `Config` instance providing defaults such as `threshold`.
    logger:
        Optional logger; defaults to the centralized project logger.
    """

    def __init__(self, config: Config, logger: Optional[logging.Logger] = None) -> None:
        self._config = config
        self._logger = logger or logging.getLogger("project")

    def decide(self, prediction_result: PR, threshold: Optional[float] = None) -> DecisionResult:
        """Produce `DecisionResult` from `prediction_result` using `threshold`.

        Parameters
        ----------
        prediction_result:
            Instance of `PredictionResult` produced by the inference engine.
        threshold:
            Optional numeric threshold in [0,1] applied to anomaly scores
            to produce binary decisions. If omitted the value from
            `self._config.threshold` is used. If no threshold is available a
            DecisionEngineError is raised.

        Returns
        -------
        DecisionResult

        Raises
        ------
        DecisionEngineError
            If inputs are invalid or threshold is not available/invalid.
        """
        if not isinstance(prediction_result, PR):
            raise DecisionEngineError("prediction_result must be a PredictionResult")

        # Resolve threshold precedence
        thr = threshold if threshold is not None else getattr(self._config, "threshold", None)
        if thr is None:
            raise DecisionEngineError("No threshold provided and none configured")
        try:
            thr_val = float(thr)
        except Exception:
            raise DecisionEngineError("Threshold must be numeric")
        if not (0.0 <= thr_val <= 1.0):
            raise DecisionEngineError("Threshold must be in [0.0, 1.0]")

        decisions: List[JSONDict] = []

        for idx, pred in enumerate(prediction_result.predictions):
            try:
                anomaly_score = float(pred.get("anomaly_score", MetricsProvider.anomaly_score_from_probs(pred.get("probs", []))))
            except Exception:
                self._logger.exception("Failed to determine anomaly score for prediction %s", idx)
                raise DecisionEngineError("Invalid prediction entry: cannot compute anomaly score")

            is_anomaly, reason = self._apply_threshold(anomaly_score, thr_val)

            # Compute confidence
            conf = self._compute_prediction_confidence(pred.get("probs"), anomaly_score)

            decision_entry: JSONDict = {
                "index": idx,
                "is_anomaly": bool(is_anomaly),
                "reason": reason.value,
                "confidence": asdict(conf),
            }

            # Preserve anomaly_score explicitly to provide a standardized
            # score field downstream (Phase 7 expects `anomaly_score`). Do
            # not remove existing confidence information.
            decision_entry["anomaly_score"] = float(anomaly_score)

            # Propagate whitelisted metadata fields from the prediction
            # (if present) into the decision entry. Do not fabricate any
            # missing metadata.
            if isinstance(pred, dict):
                for m in METADATA_FIELDS:
                    if m in pred and pred.get(m) is not None:
                        decision_entry[m] = pred.get(m)

            # Preserve reference to original prediction id if present
            if "id" in pred:
                decision_entry["id"] = pred.get("id")

            decisions.append(decision_entry)

        preds_ref = prediction_result.meta.get("predictions_ref", "predictions")
        return DecisionResult(predictions_ref=preds_ref, decisions=decisions)

    # ---- Private helpers ----
    def _apply_threshold(self, anomaly_score: float, threshold: float) -> tuple[bool, DecisionReason]:
        """Return (is_anomaly, reason) using a simple threshold policy.

        Inclusive threshold: anomaly when anomaly_score >= threshold.
        """
        is_anom = anomaly_score >= threshold
        return is_anom, DecisionReason.SCORE_THRESHOLD

    def _compute_prediction_confidence(self, probs: Optional[Iterable[float]], anomaly_score: float) -> PredictionConfidence:
        """Compute a `PredictionConfidence` instance.

        Strategy:
        - If `probs` are provided, use the maximum predicted probability
          as the confidence and method `max_prob`.
        - Otherwise, derive confidence as `1.0 - anomaly_score` with method
          `anomaly_inverse`.
        """
        if probs:
            try:
                probs_list = list(float(p) for p in probs)
                mx = max(probs_list) if probs_list else 0.0
                mx = max(0.0, min(1.0, mx))
                return PredictionConfidence(confidence_score=float(mx), method="max_prob")
            except Exception:
                self._logger.exception("Failed to compute confidence from probs; falling back to anomaly score")

        # Fallback
        conf_score = 1.0 - float(anomaly_score)
        conf_score = max(0.0, min(1.0, conf_score))
        return PredictionConfidence(confidence_score=conf_score, method="anomaly_inverse")


__all__ = ["DecisionEngine", "DecisionEngineError"]
