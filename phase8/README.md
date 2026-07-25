# Phase 8 - Milestone 1

This folder contains the Phase 8 minimal implementation: Artifact Store, Experiment Manager, and Dataset Manager.

See module docstrings for API details. Use the top-level test suite to run unit and integration tests for Phase 8.

Run tests:

```bash
pytest tests/phase8 -q

Milestone 2 (Evaluators)
-------------------------
Added evaluators in `phase8/evaluators`:
- `KPIEvaluator` — computes binary classification metrics from `ground_truth.csv` and `predictions.csv` under a dataset id and writes `evaluation/kpi_summary.json` under an experiment id.
- `DeepLogEvaluator` — computes sequence-based metrics from `ground_truth.seq` and `predictions.seq` and writes `evaluation/deeplog_summary.json`.

Both evaluators reuse `ArtifactStore`, `DatasetManager`, and `ExperimentManager` and follow Phase 8 design constraints.
```
