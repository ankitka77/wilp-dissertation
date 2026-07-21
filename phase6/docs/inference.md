Module: inference.py

1. Purpose
- Run model inference on test sequences, produce per-event top-k predictions, predicted probabilities, and compute raw anomaly scores.

2. Public Classes
- `InferenceEngine` (`model_spec`, `config`, `device`, `logger`)

3. Dataclasses
- `PredictionResult` (see shared dataclasses)

4. Enumerations
- None

5. Public Methods
- `InferenceEngine.run(self, model, test_loader, top_k=None) -> PredictionResult`
  - Raises: `InferenceError`
- `InferenceEngine.format_for_reports(self, prediction_result) -> dict[str, Any]`

6. Private Methods
- `_batch_infer`, `_compute_anomaly_scores`

7. Module Inputs
- Model instance, test DataLoader

8. Module Outputs
- `PredictionResult` and formatted dicts

9. Dependencies
- model_spec.py, persistence.py, metrics.py, types.py
