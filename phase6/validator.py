"""Validation utilities for Phase 6.

`Validator` evaluates a model on a validation DataLoader, computes top-K
metrics via `MetricsProvider`, and returns a `ValidationResult` describing
the run. The implementation is intentionally conservative about model
assumptions: it prefers `predict_topk` and `predict_probs` methods on the
model but will raise a `ValidationError` if required methods are missing.
"""
from __future__ import annotations

from typing import Any, Iterable, List, Optional
import logging

from phase6.types import ValidationResult
from phase6.metrics import MetricsProvider

logger = logging.getLogger("project")


class ValidationError(RuntimeError):
    """Raised when validation cannot be completed due to model or data issues."""


class Validator:
    """Run validation epochs and compute metrics.

    Parameters
    ----------
    config:
        Phase 6 `Config` instance (not used directly in this minimal
        implementation but accepted for interface compatibility).
    logger:
        Logger instance for diagnostic messages.
    metrics:
        Metrics provider; defaults to `MetricsProvider`.
    """

    def __init__(self, config: Any, logger: Optional[logging.Logger] = None, metrics: Any = MetricsProvider) -> None:
        self._config = config
        self._logger = logger or logging.getLogger("project")
        self._metrics = metrics

    def validate(self, model: Any, val_loader: Iterable) -> ValidationResult:
        """Validate `model` over `val_loader` and return a `ValidationResult`.

        The `model` is expected to implement two methods:
        - `predict_topk(inputs, k)` -> Iterable[Iterable[int]]
        - `predict_probs(inputs)` -> Iterable[Iterable[float]]

        Raises
        ------
        ValidationError
            If the model does not expose required prediction methods or if
            the data from `val_loader` is malformed.
        """
        # Verify model interface
        if not hasattr(model, "predict_topk") or not hasattr(model, "predict_probs"):
            msg = "Model must implement 'predict_topk' and 'predict_probs' methods"
            self._logger.error(msg)
            raise ValidationError(msg)

        all_preds_topk: List[List[int]] = []
        all_probs: List[List[float]] = []
        all_targets: List[int] = []
        metrics_time_series: List[Any] = []

        # Iterate over validation data
        for batch_idx, batch in enumerate(val_loader):
            try:
                inputs = batch.get("inputs")
                targets = batch.get("targets")
                if targets is None:
                    # Nothing to validate against
                    raise ValidationError("Validation batch missing 'targets'")

                # Obtain predictions
                k = int(getattr(self._config, "top_k", 5))
                preds_topk = list(model.predict_topk(inputs, k))
                probs = list(model.predict_probs(inputs))

                # Collect for aggregate metrics
                all_preds_topk.extend(preds_topk)
                all_probs.extend(probs)
                all_targets.extend(list(targets))

                # Compute per-batch metrics
                batch_metrics = self._metrics.batch_metrics(preds_topk, probs, targets, k)
                batch_metrics["batch_idx"] = batch_idx
                metrics_time_series.append(batch_metrics)
            except ValidationError:
                raise
            except Exception as exc:
                self._logger.exception("Error during validation loop at batch %s: %s", batch_idx, exc)
                raise ValidationError(f"Error during validation loop: {exc}") from exc

        # Aggregate metrics across the full validation set
        try:
            topk_acc = self._metrics.topk_accuracy(all_preds_topk, all_targets, int(getattr(self._config, "top_k", 5)))
        except Exception:
            topk_acc = None

        # Placeholder for val_loss (model may provide a loss; left None if unavailable)
        val_loss = None

        # Early stopping and checkpoint selection policy: conservative defaults
        should_early_stop = False
        best_checkpoint_candidate = None

        return ValidationResult(val_loss=val_loss, topk_accuracy=topk_acc, metrics_time_series=metrics_time_series, should_early_stop=should_early_stop, best_checkpoint_candidate=best_checkpoint_candidate)

    # Private helpers could be added for more advanced policies


__all__ = ["Validator", "ValidationError"]
