Module: metrics.py

1. Purpose
- Provide pure functions to compute metrics: Top-K accuracy, precision, recall, F1, and anomaly score conversions.

2. Public Classes
- `MetricsProvider` (stateless collection of functions)

3. Dataclasses
- None

4. Enumerations
- None

5. Public Methods
- `topk_accuracy(predictions, targets, k) -> float`
- `topk_recall_precision(predictions, targets, k) -> dict`
- `anomaly_score_from_probs(predicted_probs) -> float`
- `batch_metrics(predicted_topk, predicted_probs, targets, k) -> dict`

6. Private Methods
- `_normalize_probs`, `_aggregate_metrics`

7. Module Inputs
- Predictions and targets

8. Module Outputs
- Numeric metrics

9. Dependencies
- None
