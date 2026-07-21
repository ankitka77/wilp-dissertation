Module: validator.py

1. Purpose
- Evaluate model on validation set, compute metrics (Top-K), support early stopping and checkpoint selection policy.

2. Public Classes
- `Validator` (`config`, `logger`, `metrics`)

3. Dataclasses
- `ValidationResult` (`val_loss`, `topk_accuracy`, `metrics_time_series`, `should_early_stop`, `best_checkpoint_candidate`)

4. Enumerations
- None

5. Public Methods
- `Validator.validate(self, model, val_loader) -> ValidationResult`
  - Raises: `ValidationError`

6. Private Methods
- `_compute_topk`, `_accumulate_metrics`

7. Module Inputs
- Model instance, validation DataLoader

8. Module Outputs
- `ValidationResult`

9. Dependencies
- metrics.py, types.py, logger.py
