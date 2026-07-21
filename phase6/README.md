# Phase 6 — DeepLog (Design-only)

This folder contains the Phase 6 design specification for DeepLog (LSTM) sequence modeling. It is intentionally code-free — the README documents expected inputs, outputs, artifact layout, and the recommended module responsibilities to maintain clear separation from Phase 5 and Phase 7.

Supported inputs (from Phase 5)
- `event_vocabulary.json` or `event_vocabulary.csv`: mapping `template -> event_id` (deterministic mapping required from Phase 5).
- `training_sequences.csv`: rows with `sequence_id, sequence_events, input_sequence, next_event_target, sequence_length, source, block_id?, session_id?`.
- `test_sequences.csv` or a `split` column indicating test rows.

Primary outputs (artifacts)
- `artifacts/phase6/models/`: saved model files and matched metadata JSON files.
- `artifacts/phase6/reports/predictions.csv`: per-event predictions with `predicted_top_k`, `predicted_probs`, `anomaly_score`, `prediction_confidence`, and `is_anomaly`.
- `artifacts/phase6/reports/training_metrics.json`: per-epoch metrics summary.
- `artifacts/phase6/plots/`: training/validation loss and top-k accuracy plots.
- `artifacts/phase6/manifests/phase6_manifest.json`: canonical manifest describing inputs, artifacts, config snapshot and git metadata.

Quick usage notes (design)
- Phase 6 must accept Phase 5 artifacts as-is and must emit a `phase6_manifest.json` referencing all produced artifacts.
- Trainers and inference code should be experiment-driven and write artifacts under an experiment directory (managed by an `experiment_manager`).

Recommended next steps for implementors
- Create module skeletons according to `docs/phase6_architecture.md` and ensure all artifacts and manifest fields described there are produced.
- Do not implement KPI-level fusion, explainability, or hyperparameter search in Phase 6 — those belong to later phases or to separate tooling.

