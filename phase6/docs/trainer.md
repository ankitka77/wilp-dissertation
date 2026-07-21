Module: trainer.py

1. Purpose
- Manage full training loop orchestration: epochs, optimizer steps, validation calls, checkpointing via `persistence` and `experiment_manager`, and return `TrainingResult`.

2. Public Classes
- `Trainer`
  - Attributes: `model_spec`, `config`, `logger`, `experiment_info`
  - Lifecycle: instantiate → `train(train_loader, val_loader)` → returns `TrainingResult`

3. Dataclasses
- `TrainingResult` (`status`, `epoch_metrics`, `final_checkpoint`, `best_checkpoint`, `num_epochs_run`)

4. Enumerations
- None beyond types.TrainingStatus

5. Public Methods
- `Trainer.train(self, train_loader, val_loader=None) -> TrainingResult`
  - Raises: `TrainingError` on unrecoverable faults
- `_save_checkpoint(self, epoch: int, checkpoint_type: CheckpointType) -> PersistenceInfo`

6. Private Methods
- `_run_epoch`, `_validate_and_maybe_early_stop`

7. Module Inputs
- `ModelSpec`, `Config`, DataLoaders, `ExperimentInfo`

8. Module Outputs
- `TrainingResult`, persisted checkpoints via `persistence`

9. Dependencies
- model_spec.py, validator.py, persistence.py, experiment_manager.py, metrics.py, logger.py, types.py
