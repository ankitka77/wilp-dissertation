Module: report_generator.py

1. Purpose
- Serialize predictions, training metrics, and final manifest to disk under experiment directories.

2. Public Classes
- `ReportGenerator` (`experiment_info`, `logger`, `config`)

3. Dataclasses
- `ManifestInfo` (see shared dataclasses)

4. Enumerations
- None

5. Public Methods
- `write_training_metrics(self, training_result) -> str` (returns path)
- `write_predictions(self, decision_result) -> str` (returns path)
- `write_manifest(self, manifest_info) -> str` (returns manifest path)
- `write_experiment_summary(self, summary) -> str`

6. Private Methods
- `_normalize_predictions_for_csv`, `_atomic_write_json`

7. Module Inputs
- DecisionResult, TrainingResult, ModelMetadata, ExperimentInfo

8. Module Outputs
- `predictions.csv`, `training_metrics.json`, `phase6_manifest.json`

9. Dependencies
- types.py, experiment_manager.py, persistence.py, logger.py
