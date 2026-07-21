"""Training orchestration for Phase 6.

`Trainer` manages the training loop, optional validation calls via the
`Validator`, and checkpointing. It returns a `TrainingResult` summarizing the
run. This module assumes persistence and model interfaces described in the
implementation blueprint are available at runtime.
"""
from __future__ import annotations

from typing import Any, Iterable, List, Optional, Dict
import logging
from dataclasses import asdict

from phase6.types import TrainingResult, TrainingStatus, CheckpointType, PersistenceInfo
from phase6.config import Config

logger = logging.getLogger("project")


class TrainingError(RuntimeError):
    """Raised when training cannot proceed due to an unrecoverable issue."""


class Trainer:
    """Manage the training loop and checkpointing.

    Parameters
    ----------
    model_spec:
        Model specification (not used directly but accepted for API
        compatibility).
    config:
        Phase 6 `Config` instance controlling training parameters.
    logger:
        Logger for diagnostics.
    experiment_info:
        Optional experiment bookkeeping info used when saving checkpoints.
    """

    def __init__(self, model_spec: Any, config: Config, logger: Optional[logging.Logger] = None, experiment_info: Optional[Any] = None) -> None:
        self.model_spec = model_spec
        if not isinstance(config, Config):
            raise TrainingError("Trainer requires a valid Config instance")
        self.config = config
        self.logger = logger or logging.getLogger("project")
        self.experiment_info = experiment_info

    def train(self, model: Any, train_loader: Iterable, val_loader: Optional[Iterable] = None) -> TrainingResult:
        """Run the training loop and optionally validate.

        The `model` must provide either `train_epoch(train_loader)` or a
        `train_step(inputs, targets)` API. Validation is performed using
        `phase6.validator.Validator` when `val_loader` is provided.

        Raises
        ------
        TrainingError
            On missing model APIs or persistence failures.
        """
        # Initialize training result
        result = TrainingResult(status=TrainingStatus.RUNNING, epoch_metrics=[], final_checkpoint=None, best_checkpoint=None, num_epochs_run=0)

        # Optionally import Validator lazily to avoid circular imports
        validator = None
        if val_loader is not None:
            from phase6.validator import Validator

            validator = Validator(config=self.config, logger=self.logger)

        best_topk = -1.0
        best_checkpoint: Optional[Dict[str, Any]] = None

        try:
            epochs = int(getattr(self.config, "epochs", 1))
            interval = int(getattr(self.config, "checkpoint_interval_epochs", 1))
            max_checkpoints = int(getattr(self.config, "max_checkpoints", 0))

            for epoch in range(1, epochs + 1):
                # Run training for one epoch
                train_loss = None
                if hasattr(model, "train_epoch"):
                    train_loss = model.train_epoch(train_loader)
                elif hasattr(model, "train_step"):
                    # Aggregate per-batch losses
                    losses: List[float] = []
                    for batch in train_loader:
                        inputs = batch.get("inputs")
                        targets = batch.get("targets")
                        loss = model.train_step(inputs, targets)
                        try:
                            losses.append(float(loss))
                        except (TypeError, ValueError) as exc:
                            self.logger.debug("Skipping non-numeric loss value: %s", exc)
                    train_loss = float(sum(losses) / len(losses)) if losses else None
                else:
                    raise TrainingError("Model must implement 'train_epoch' or 'train_step'")

                # Validation: compute validation loss and top-k accuracy when a
                # Validator is available. We must not update gradients during
                # validation. Use a separate iterator for loss computation and
                # for the Validator to avoid consuming the same generator twice
                # (DataFrame-based iterators are single-use generators).
                val_loss = None
                topk_acc = None
                if validator is not None:
                    # mypy: ensure val_loader is not None when calling validate
                    assert val_loader is not None
                    try:
                        import pandas as _pd  # type: ignore
                    except Exception:
                        _pd = None

                    # Helper to create a fresh iterator from a pandas DataFrame
                    def _df_iter_from_df(df):
                        records = df.to_dict(orient="records")

                        def _iter():
                            batch_size = int(getattr(self.config, "batch_size", 32) or 32)
                            batch_inputs = []
                            batch_targets = []
                            for rec in records:
                                if "inputs" in rec:
                                    seq = rec.get("inputs")
                                elif "sequence_events" in rec:
                                    seq = rec.get("sequence_events")
                                elif "input_sequence" in rec:
                                    seq = rec.get("input_sequence")
                                else:
                                    seq = rec

                                target = rec.get("targets") or rec.get("next_event_target")
                                if target is None:
                                    try:
                                        target = seq[-1] if seq else None
                                    except Exception:
                                        target = None

                                batch_inputs.append(seq)
                                batch_targets.append(target)
                                if len(batch_inputs) >= batch_size:
                                    yield {"inputs": list(batch_inputs), "targets": list(batch_targets)}
                                    batch_inputs = []
                                    batch_targets = []
                            if batch_inputs:
                                yield {"inputs": list(batch_inputs), "targets": list(batch_targets)}

                        return _iter

                    # Prepare two independent iterators when val_loader is a DataFrame
                    if _pd is not None and isinstance(val_loader, _pd.DataFrame):
                        val_iter_for_loss = _df_iter_from_df(val_loader)()
                        val_iter_for_validator = _df_iter_from_df(val_loader)()
                    else:
                        # For non-DataFrame iterables try to reuse the iterable
                        # directly. Many dataloaders are re-iterable (support
                        # multiple passes), so provide the same object to both
                        # consumers; they will obtain fresh iterators when
                        # iterated over.
                        val_iter_for_loss = val_loader
                        val_iter_for_validator = val_loader

                    # Compute validation loss without affecting gradients
                    try:
                        import torch
                        import torch.nn as _nn
                    except Exception:
                        torch = None
                        _nn = None

                    if torch is None or _nn is None:
                        # If torch is not available, skip loss computation but
                        # still run the Validator to compute accuracy.
                        pass
                    else:
                        criterion = _nn.CrossEntropyLoss()
                        total_vloss = 0.0
                        total_vexamples = 0
                        model_device = None
                        try:
                            model_device = next(model.parameters()).device
                        except Exception:
                            model_device = None

                        model.eval()
                        with torch.no_grad():
                            for batch in val_iter_for_loss:
                                try:
                                    inputs = batch.get("inputs")
                                    targets = batch.get("targets")
                                    if targets is None:
                                        continue

                                    # Prepare model inputs using model helper
                                    device = model_device
                                    try:
                                        x = model._prepare_inputs_for_inference(inputs, device=device)
                                    except Exception:
                                        # If model does not expose the helper,
                                        # skip this batch for val_loss
                                        continue

                                    # Build target tensor
                                    try:
                                        import numpy as _np
                                        y = torch.tensor(_np.asarray(targets), dtype=torch.long, device=device)
                                    except Exception:
                                        # If targets cannot be tensorized, skip
                                        continue

                                    logits = model._forward_logits(x, None)
                                    try:
                                        loss = criterion(logits, y)
                                    except Exception:
                                        # Unable to compute loss for this batch
                                        continue

                                    bsz = int(logits.shape[0])
                                    total_vloss += float(loss.item()) * bsz
                                    total_vexamples += bsz
                                except Exception:
                                    # Non-fatal: skip malformed validation batch
                                    continue

                        if total_vexamples > 0:
                            val_loss = float(total_vloss / total_vexamples)

                    # Run Validator to compute aggregated accuracy and per-batch metrics
                    vres = validator.validate(model, val_iter_for_validator)
                    # Prefer computed val_loss when available; otherwise accept
                    # any val_loss returned by Validator (legacy).
                    if vres is not None and getattr(vres, "topk_accuracy", None) is not None:
                        topk_acc = vres.topk_accuracy
                    # If Validator provided a val_loss (legacy), use it only if
                    # we did not compute one above.
                    if val_loss is None and vres is not None:
                        try:
                            val_loss = vres.val_loss
                        except Exception:
                            pass
                    # Early stopping consideration
                    if vres.should_early_stop:
                        self.logger.info("Early stopping at epoch %s", epoch)
                        result.epoch_metrics.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss, "topk_accuracy": topk_acc})
                        result.num_epochs_run = epoch
                        result.status = TrainingStatus.COMPLETED
                        result.best_checkpoint = best_checkpoint
                        return result

                # Checkpointing
                if interval > 0 and epoch % interval == 0 and max_checkpoints > 0:
                    try:
                        ckpt = self._save_checkpoint(model, epoch, CheckpointType.INTERMEDIATE)
                        # For simplicity, update best_checkpoint if no best yet
                        if best_checkpoint is None:
                            best_checkpoint = ckpt
                    except TrainingError:
                        self.logger.exception("Failed to save checkpoint at epoch %s", epoch)
                        raise

                # Update best based on topk_acc
                if topk_acc is not None and isinstance(topk_acc, (int, float)):
                    try:
                        if float(topk_acc) > best_topk:
                            best_topk = float(topk_acc)
                            # Save best checkpoint if persistence available
                            if max_checkpoints > 0:
                                best_checkpoint = self._save_checkpoint(model, epoch, CheckpointType.BEST)
                    except TrainingError:
                        # Non-fatal: log and continue
                        self.logger.exception("Failed to save best checkpoint at epoch %s", epoch)

                # Record epoch metrics
                result.epoch_metrics.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss, "topk_accuracy": topk_acc})

            result.num_epochs_run = epochs
            result.status = TrainingStatus.COMPLETED
            result.best_checkpoint = best_checkpoint

        except TrainingError:
            result.status = TrainingStatus.FAILED
            raise
        except Exception as exc:
            result.status = TrainingStatus.FAILED
            self.logger.exception("Unhandled error during training: %s", exc)
            raise TrainingError(f"Unhandled error during training: {exc}") from exc

        return result

    def _save_checkpoint(self, model_obj: Any, epoch: int, checkpoint_type: CheckpointType) -> Dict[str, Any]:
        """Persist a model checkpoint using the `persistence` module.

        The exact persistence API is assumed to exist as `phase6.persistence.save_checkpoint`.

        Returns
        -------
        Dict[str, Any]
            JSON-serializable mapping describing the persisted checkpoint.
        """
        try:
            import phase6.persistence as persistence
        except Exception as exc:
            msg = "Persistence module not available for saving checkpoints"
            self.logger.error(msg)
            raise TrainingError(msg) from exc

        if not hasattr(persistence, "save_checkpoint"):
            msg = "persistence.save_checkpoint not available"
            self.logger.error(msg)
            raise TrainingError(msg)

        try:
            # `persistence.save_checkpoint` expects a mapping containing
            # `experiment_path`; adapt `experiment_info` (which may be an
            # ExperimentInfo dataclass) into the expected dict form.
            exp_info_param = self.experiment_info
            if not isinstance(exp_info_param, dict):
                try:
                    exp_info_param = {
                        "experiment_path": getattr(self.experiment_info, "path", None),
                        "name": getattr(self.experiment_info, "experiment_id", None),
                    }
                except Exception:
                    exp_info_param = {"experiment_path": None}

            info = persistence.save_checkpoint(experiment_info=exp_info_param, model_spec=self.model_spec, epoch=epoch, checkpoint_type=checkpoint_type, model_obj=model_obj, config=self.config, logger=self.logger)
        except Exception as exc:
            self.logger.exception("Failed to save checkpoint via persistence: %s", exc)
            raise TrainingError(f"Failed to save checkpoint: {exc}") from exc

        # Normalize to a JSON-serializable mapping
        if isinstance(info, PersistenceInfo):
            return asdict(info)
        try:
            return dict(info)
        except Exception:
            raise TrainingError("persistence.save_checkpoint did not return a valid PersistenceInfo or mapping")


__all__ = ["Trainer", "TrainingError"]
