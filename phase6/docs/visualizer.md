Module: visualizer.py

1. Purpose
- Produce PNG/SVG plots for training (loss, top-k accuracy) and prediction summaries.

2. Public Classes
- `Visualizer` (`experiment_info`, `logger`, `config`)

3. Dataclasses
- None

4. Enumerations
- None

5. Public Methods
- `plot_training_metrics(self, training_result) -> list[str]` (returns created file paths)
- `plot_predictions_summary(self, decision_result, top_n=10) -> str`

6. Private Methods
- `_safe_save_fig`, `_aggregate_prediction_stats`

7. Module Inputs
- TrainingResult, DecisionResult

8. Module Outputs
- Plot files under experiment `plots/`

9. Dependencies
- report_generator.py, experiment_manager.py, logger.py, matplotlib
