"""Inference utilities for Phase 6.

This module implements the `InferenceEngine` described in the Phase 6
implementation blueprint. The engine runs a model on test sequences and
produces per-event top-k predictions, predicted probabilities, and raw
anomaly scores. The implementation is intentionally conservative about
model assumptions and relies on the canonical shared types and the
centralized logger.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional
import logging

from phase6.types import PredictionResult, JSONDict
from phase6.metrics import MetricsProvider
from phase6.persistence import InferenceError

logger = logging.getLogger("project")


class InferenceEngine:
    """Run model inference on test data and format results for reports.

    Parameters
    ----------
    model_spec:
        Model specification object (kept for compatibility with the
        blueprint; not used directly in this minimal implementation).
    config:
        Configuration object exposing at least `top_k` when not provided
        to `run`.
    device:
        Optional device identifier (kept for API compatibility).
    logger:
        Optional logger instance; defaults to the project's logger.
    """

    def __init__(self, model_spec: Any, config: Any, device: Optional[str] = None, logger: Optional[logging.Logger] = None) -> None:
        self._model_spec = model_spec
        self._config = config
        self._device = device
        self._logger = logger or logging.getLogger("project")

    def run(self, model: Any, test_loader: Iterable[Dict[str, Any]], top_k: Optional[int] = None) -> PredictionResult:
        """Execute inference over `test_loader` and return `PredictionResult`.

        Parameters
        ----------
        model:
            Model object exposing `predict_topk(inputs, k)` and
            `predict_probs(inputs)` methods.
        test_loader:
            Iterable producing batch dictionaries. Each batch MUST contain
            an `inputs` key mapping to a sequence of model inputs. Other
            keys are preserved in the per-example output meta fields if
            present.
        top_k:
            Optional override for number of top predictions to request.

        Returns
        -------
        PredictionResult

        Raises
        ------
        InferenceError
            If the model does not expose the required prediction methods or
            an unexpected error occurs during inference.
        """
        # Validate model interface
        if not hasattr(model, "predict_topk") or not hasattr(model, "predict_probs"):
            msg = "Model must implement 'predict_topk' and 'predict_probs' methods"
            self._logger.error(msg)
            raise InferenceError(msg)

        k = int(top_k if top_k is not None else getattr(self._config, "top_k", 5))

        all_predictions: List[JSONDict] = []

        # If a pandas DataFrame was provided, convert it into an iterator of
        # batch dictionaries so the loop below receives dicts with an
        # `inputs` key instead of iterating column names (strings).
        try:
            import pandas as _pd  # type: ignore
        except Exception:
            _pd = None

        if _pd is not None and isinstance(test_loader, _pd.DataFrame):
            records = test_loader.to_dict(orient="records")
            METADATA_FIELDS = [
                "sequence_id",
                "block_id",
                "source",
                "dataset",
                "session_id",
                "timestamp",
            ]

            def _iter_from_df():
                batch_size = int(getattr(self._config, "batch_size", 32) or 32)
                batch_inputs: List[Any] = []
                batch_ids: List[Any] = []
                batch_meta: List[dict] = []
                for rec in records:
                    if "inputs" in rec:
                        seq = rec.get("inputs")
                    elif "sequence_events" in rec:
                        seq = rec.get("sequence_events")
                    elif "input_sequence" in rec:
                        seq = rec.get("input_sequence")
                    else:
                        seq = rec

                    batch_inputs.append(seq)
                    # preserve an identifier if available
                    batch_ids.append(rec.get("id") or rec.get("index") or None)

                    # Collect a small metadata mapping from a whitelist of fields
                    # when they exist on the source record. Do NOT fabricate
                    # missing fields; only copy what is present.
                    meta = {k: rec.get(k) for k in METADATA_FIELDS if k in rec}
                    batch_meta.append(meta)

                    if len(batch_inputs) >= batch_size:
                        yield {
                            "inputs": list(batch_inputs),
                            "ids": list(batch_ids),
                            "metadata": list(batch_meta),
                        }
                        batch_inputs = []
                        batch_ids = []
                        batch_meta = []
                if batch_inputs:
                    yield {"inputs": list(batch_inputs), "ids": list(batch_ids), "metadata": list(batch_meta)}

            iterator = _iter_from_df()
        else:
            iterator = test_loader

        # Iterate batches and perform batch-level inference
        for batch_idx, batch in enumerate(iterator):
            try:
                batch_preds = self._batch_infer(model, batch, k, batch_idx)
                all_predictions.extend(batch_preds)
            except InferenceError:
                raise
            except Exception as exc:
                self._logger.exception("Error during inference at batch %s: %s", batch_idx, exc)
                raise InferenceError(f"Error during inference: {exc}") from exc

        meta: JSONDict = {
            "num_predictions": len(all_predictions),
            "top_k": k,
        }

        # Compute dataset-level anomaly summary
        try:
            scores = [p.get("anomaly_score", 0.0) for p in all_predictions]
            avg_anomaly = float(sum(scores) / len(scores)) if scores else 0.0
            meta["avg_anomaly_score"] = avg_anomaly
        except Exception:
            self._logger.exception("Failed to compute avg anomaly score")
            meta["avg_anomaly_score"] = 0.0

        return PredictionResult(predictions=all_predictions, meta=meta)

    def format_for_reports(self, prediction_result: PredictionResult) -> Dict[str, Any]:
        """Prepare a JSON-serializable dictionary suitable for reports.

        The returned structure contains a compact summary and the full
        predictions list. Keeping the format simple ensures downstream
        report generators can consume it without tight coupling.
        """
        if not isinstance(prediction_result, PredictionResult):
            raise TypeError("prediction_result must be a PredictionResult")

        out: Dict[str, Any] = {
            "summary": {
                "num_predictions": prediction_result.meta.get("num_predictions", 0),
                "top_k": prediction_result.meta.get("top_k"),
                "avg_anomaly_score": prediction_result.meta.get("avg_anomaly_score", 0.0),
            },
            "predictions": prediction_result.predictions,
        }
        return out

    # ---- Private helpers ----
    def _batch_infer(self, model: Any, batch: Dict[str, Any], k: int, batch_idx: int) -> List[JSONDict]:
        """Run inference for a single batch and return per-example dicts.

        Expected batch format: {"inputs": [...], ...}. Additional keys in the
        batch are not required but are not considered part of the model inputs.
        """
        inputs = batch.get("inputs")
        if inputs is None:
            raise InferenceError("Batch missing 'inputs' key")

        # Obtain model outputs
        preds_topk = list(model.predict_topk(inputs, k))
        probs = list(model.predict_probs(inputs))

        if len(preds_topk) != len(probs):
            self._logger.error("Model returned mismatched lengths for topk and probs")
            raise InferenceError("Model returned mismatched prediction lengths")

        out: List[JSONDict] = []
        for idx, (topk, prob_list) in enumerate(zip(preds_topk, probs)):
            try:
                score = MetricsProvider.anomaly_score_from_probs(prob_list)
            except Exception:
                self._logger.exception("Failed to compute anomaly score for batch %s idx %s", batch_idx, idx)
                score = 0.0

            entry: JSONDict = {
                "batch_idx": batch_idx,
                "index_in_batch": idx,
                "topk": list(topk),
                "probs": list(prob_list),
                "anomaly_score": float(score),
            }

            # Preserve optional identifiers if present
            if "ids" in batch:
                ids = batch.get("ids")
                if ids is not None:
                    try:
                        entry["id"] = ids[idx]
                    except Exception:
                        pass

            # Propagate any whitelisted metadata fields collected from the
            # source records. Only copy fields that were present; do not
            # fabricate missing values.
            if "metadata" in batch:
                metas = batch.get("metadata")
                if metas is not None:
                    try:
                        meta_entry = metas[idx]
                        if isinstance(meta_entry, dict):
                            for k, v in meta_entry.items():
                                # Only set keys with non-None values
                                if v is not None:
                                    entry[k] = v
                    except Exception:
                        pass

            out.append(entry)
        return out

    def _compute_anomaly_scores(self, predicted_probs: Iterable[Iterable[float]]) -> List[float]:
        """Convert lists of predicted probabilities into anomaly scores.

        This is a small adapter around `MetricsProvider.anomaly_score_from_probs`.
        """
        return [MetricsProvider.anomaly_score_from_probs(list(p)) for p in predicted_probs]


__all__ = ["InferenceEngine", "InferenceError"]
