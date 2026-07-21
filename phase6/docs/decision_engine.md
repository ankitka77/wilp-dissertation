Module: decision_engine.py

1. Purpose
- Convert raw prediction outputs and anomaly scores into final binary decisions and attach decision metadata (reason, confidence).

2. Public Classes
- `DecisionEngine` (`config`, `logger`)

3. Dataclasses
- `DecisionResult` (contains `predictions_ref` and `decisions` list)

4. Enumerations
- `DecisionReason` (in types)

5. Public Methods
- `DecisionEngine.decide(self, prediction_result, threshold=None) -> DecisionResult`
  - Raises: `DecisionEngineError`

6. Private Methods
- `_apply_threshold`, `_compute_prediction_confidence`

7. Module Inputs
- PredictionResult, `Config`

8. Module Outputs
- DecisionResult

9. Dependencies
- metrics.py, types.py, config.py
