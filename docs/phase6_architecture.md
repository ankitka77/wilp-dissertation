**Phase 6 — DeepLog (Architecture)**

This document refines the Phase 6 architecture to follow strict separation of concerns, improved module boundaries, explicit interfaces, and comprehensive manifest/reporting requirements while preserving the overall project design and Phase responsibilities.

Scope and constraints
- Phase 6 implements DeepLog (LSTM) only. It accepts Phase 5 outputs (vocabulary, mapping, training and testing sequences) and produces DeepLog outputs listed in the project specification.
- No KPI processing, Fusion logic, hyperparameter optimization, explainability, or Phase 8/9 responsibilities are included.

Design goals
- Maintain strict separation of responsibilities (single responsibility per module).
- Produce reproducible, versioned artifacts with complete metadata (config and git snapshot).
- Provide clear, stable contracts for Phase 7 consumption.
- Keep APIs minimal and file-based interchange for provenance.

Pipeline (high level)

```mermaid
flowchart LR
  A[Phase5 Outputs] --> B[Input Validation (ingest & validator)]
  B --> C[Dataset Builder]
  C --> D[Sequence Encoder]
  D --> E[Model Spec (DeepLog)]
  E --> F[Trainer]
  F --> G[Validator]
  G --> H[Persistence (checkpoint selection & final save)]
  H --> I[Inference]
  I --> J[Decision Engine]
  J --> K[Report Generator]
  K --> L[Visualizer]
  L --> M[Manifest]
  M --> N[Phase7 Consumer]
```

Folder structure (authoritative)

- phase6/
  - README.md
  - configs/                # example config templates (YAML/JSON) (no code)
  - src/phase6/             # conceptual modules (no implementation code in this doc)
    - __init__.py
    - config.py             # central configuration management
    - logger.py             # centralized logger factory
    - ingest.py             # read & validate Phase 5 outputs
    - sequence_encoder.py   # encode event-id sequences, padding, truncation
    - dataset.py            # Dataset object, batching, loaders, masks
    - model_spec.py         # ModelSpec and ModelMetadata objects
    - trainer.py            # training loop, optimizer, scheduler, checkpoints
    - validator.py          # validation metrics, early stopping, checkpoint selection
    - metrics.py            # reusable metric implementations (Top-K, precision, recall, f1)
    - inference.py          # run model to produce top-k & raw anomaly scores
    - decision_engine.py    # apply thresholds -> final anomaly decisions
    - persistence.py        # save/load models and model metadata
    - experiment_manager.py # experiment lifecycle, artifact dirs, numbering
    - report_generator.py   # CSV/JSON writers and manifest generation
    - visualizer.py         # plotting training/validation/prediction visualizations
    - orchestrator.py       # run_phase6() entrypoint wiring components
    - types.py              # typed schemas and dataclasses for module contracts
  - artifacts/phase6/
    - models/
    - reports/
    - plots/
    - manifests/

Core module responsibilities and interfaces
--------------------------------------------------
For each module below: Inputs, Outputs, Public responsibilities, Dependencies, Artifacts produced.

`config.py`
- Inputs: runtime config file (YAML/JSON) and environment overrides.
- Outputs: `Config` object used across modules.
- Responsibilities: centralize all parameters (lr, batch_size, epochs, optimizer, scheduler, dropout, hidden_size, embedding_dim, top_k, thresholds, sequence_length, seed, artifact paths).
- Dependencies: none.
- Artifacts: none (config snapshot will be saved by `persistence` or `report_generator`).

`logger.py`
- Inputs: config logging parameters (level, file paths).
- Outputs: configured `logger` instances used by other modules.
- Responsibilities: create project logger, experiment-scoped loggers, file and console handlers, formatting, optional rotation.
- Dependencies: `config.py`.
- Artifacts: log files under experiment directory (managed by `experiment_manager`).

`ingest.py`
- Inputs: paths to Phase 5 outputs (vocab JSON/CSV, training_sequences.csv, testing_sequences.csv).
- Outputs: `Phase5Inputs` typed object containing DataFrames/dicts and a `validation_report` of warnings.
- Responsibilities: schema validation, basic sanitization (ensure `input_sequence` and `next_event_target` exist), small fixes (e.g., coercing numeric types).
- Dependencies: `config.py`, `logger.py`, `types.py`.
- Artifacts: validation warnings (logged) and returned `Phase5Inputs`.

`sequence_encoder.py`
- Inputs: `Phase5Inputs.vocabulary`, configuration (pad token, max length).
- Outputs: encoder object with `encode(sequence) -> list[int]` and reverse lookup.
- Responsibilities: event-id encoding/decoding, padding token management, truncation policy, serialization of encoder state.
- Dependencies: `config.py`, `types.py`.
- Artifacts: optional encoder metadata saved via `persistence`.

`dataset.py`
- Inputs: encoded sequences from `sequence_encoder`, config (batch_size, shuffle, max_seq_len).
- Outputs: train/test DataLoader objects or iterables, `DatasetMetadata`.
- Responsibilities: create Dataset object, batching, padding, mask generation, produce anisotropic collate function for variable-length sequences.
- Dependencies: `sequence_encoder.py`, `config.py`.
- Artifacts: none (metadata returned; persisted by experiment manager if requested).

`model_spec.py`
- Inputs: configuration parameters (embedding_dim, hidden_size, num_layers, dropout, vocab_size, sequence_length).
- Outputs: `ModelSpec` and `ModelMetadata` dataclasses.
- Responsibilities: declare model hyperparameters, provide serialization for inclusion in model metadata and manifest.
- Dependencies: `config.py`, `types.py`.
- Artifacts: `ModelSpec` serialized into model metadata by `persistence`.

`trainer.py`
- Inputs: `ModelSpec`, `train_loader`, `val_loader`, `Config`.
- Outputs: `TrainingResult` with metrics per epoch, final checkpoint candidates (paths), training logs.
- Responsibilities: implement the training loop, optimizer and scheduler steps, checkpoint callback invocation.
- Dependencies: `model_spec.py`, `validator.py` (for validation calls), `metrics.py`, `experiment_manager.py`, `logger.py`.
- Artifacts: intermediate checkpoints (managed by `experiment_manager` and `persistence`).

`validator.py`
- Inputs: model instance, `val_loader`, config (top_k, early stopping params).
- Outputs: validation metrics (validation loss, Top-K accuracy/time series), signal for early stopping, selected best checkpoint pointer.
- Responsibilities: compute validation loss and Top-K accuracy, implement early stopping logic and checkpoint selection policy.
- Dependencies: `metrics.py`, `logger.py`.
- Artifacts: validation metric records (returned; persisted by `report_generator`).

`metrics.py`
- Inputs: predictions and targets.
- Outputs: numeric metric values (Top-K accuracy, precision, recall, F1, confusion stats as needed).
- Responsibilities: provide reusable metric implementations used by both validator and report generator.
- Dependencies: none (pure functions).
- Artifacts: none.

`inference.py`
- Inputs: final saved model (via `persistence`), `test_loader`, config (top_k, scoring method).
- Outputs: raw model outputs, `Predictions` structure with `predicted_top_k`, `predicted_probs`, `anomaly_score` per event.
- Responsibilities: run batched inference, compute raw anomaly scores (e.g., negative log-likelihood or model-specific score), format outputs for `decision_engine`.
- Dependencies: `persistence.py`, `config.py`, `types.py`.
- Artifacts: inference logs and in-memory Predictions; persisted CSV/JSON by `report_generator`.

`decision_engine.py`
- Inputs: `Predictions` (raw), config (anomaly threshold, decision policies), optional external thresholds.
- Outputs: final `is_anomaly` flags, `decision_reason` per event/sequence, `PredictionConfidence` fields.
- Responsibilities: apply configurable thresholding, produce final binary decision and a short reason (e.g., "score>threshold"), keep decision logic isolated from model code.
- Dependencies: `config.py`, `logger.py`.
- Artifacts: decision annotations (returned to `report_generator`).

`persistence.py`
- Inputs: model objects, `ModelMetadata` and target save path.
- Outputs: saved model file and metadata JSON; load API returns model and metadata.
- Responsibilities: consistent, versioned saving/loading of models and artifacts, maintain metadata (ModelMetadata including git/config snapshot), compute file checksum.
- Dependencies: `model_spec.py`, `experiment_manager.py`.
- Artifacts: model files and `<name>.metadata.json`.

`experiment_manager.py`
- Inputs: root artifact path (from config), optional experiment id.
- Outputs: experiment directory path, artifact subdirectories, initialized manifest placeholder.
- Responsibilities: create numbered/timestamped experiment directory structure, maintain experiment lifecycle (start, log, finalize), hand over directories to `persistence` and `report_generator`.
- Dependencies: `logger.py`, `config.py`.
- Artifacts: experiment folder and structure; `phase6_manifest` placeholder.

`report_generator.py`
- Inputs: `TrainingResult`, `Predictions` (post-decision), `ModelMetadata`, experiment paths.
- Outputs: CSV/JSON reports, `phase6_manifest.json` written to manifests directory.
- Responsibilities: serialize predictions and metrics to disk, produce manifest listing inputs, artifacts, model metadata, git and config snapshot.
- Dependencies: `persistence.py`, `experiment_manager.py`.
- Artifacts: `predictions.csv`, `topk_predictions.csv`, `training_metrics.json`, `phase6_manifest.json`.

`visualizer.py`
- Inputs: training metrics, validation metrics, predictions.
- Outputs: PNG/SVG plots (loss curve, Top-K accuracy, prediction visualization summaries).
- Responsibilities: produce visualizations and save under `plots/` directory; do not write CSVs (reports only handles data exports).
- Dependencies: `report_generator.py` outputs, `experiment_manager.py` for paths.
- Artifacts: plots in `plots/`.

`orchestrator.py`
- Inputs: config file path or CLI args.
- Outputs: complete experiment run: saved model, predictions, reports, visualizations, manifest.
- Responsibilities: high-level wiring only — call `ingest`, `sequence_encoder`, `dataset`, `trainer`, `validator`, `persistence`, `inference`, `decision_engine`, `report_generator`, `visualizer`, and finalize manifest via `experiment_manager`.
- Dependencies: all modules above.
- Artifacts: none directly beyond what modules produce; orchestrator triggers artifact creation.

Data flow (detailed)
- Phase5 outputs → `ingest` (validate and coerce) → `sequence_encoder` (encode events to numeric sequences) → `dataset` (batching & loaders) → `trainer` (calls `validator` during training) → `persistence` (save best model + metadata) → `inference` (run on test set) → `decision_engine` (apply thresholds) → `report_generator` & `visualizer` (write CSV/JSON and plots) → `phase6_manifest.json`

Artifacts produced (concrete list)
- `artifacts/phase6/models/deeplog-<timestamp>.bin` (or framework-dependent extension)
- `artifacts/phase6/models/deeplog-<timestamp>.metadata.json` (ModelMetadata, git, config snapshot, checksum)
- `artifacts/phase6/reports/training_metrics.json`
- `artifacts/phase6/reports/predictions.csv` (includes `predicted_top_k`, `predicted_probs`, `anomaly_score`, `prediction_confidence`, `is_anomaly`, `decision_reason`)
- `artifacts/phase6/reports/topk_predictions.csv`
- `artifacts/phase6/plots/loss.png`, `plots/topk_accuracy.png`, `plots/prediction_summary.png`
- `artifacts/phase6/manifests/phase6_manifest.json`

Manifest contents (required fields)
- `manifest_version`, `generated_on`, `phase`, `inputs` (paths), `artifacts` (paths), `model_spec`, `model_metadata`, `training_summary`, `git` (branch, commit, tag), `config_snapshot`, `experiment_id`, `notes`.

Phase7 consumption contract
- Phase7 must read `phase6_manifest.json` to locate artifacts.
- Primary Phase7 inputs: `predictions.csv` (canonical columns) and optionally `model` if re-scoring is required.
- The `predictions.csv` must include numeric `anomaly_score`, a JSON array `predicted_top_k` of event_ids, `predicted_probs`, and a `prediction_confidence` field.

Design notes and constraints
- Trainer must depend on `validator` and `metrics`; validation logic is not embedded in `trainer`.
- `experiment_manager` owns experiment directories and numbering; `trainer` and `persistence` must request paths from the manager.
- `decision_engine` is strictly separated from `inference`.
- `config.py` is the single source of configurable parameters; no hard-coded values across modules.
- All saved models must be accompanied by `ModelMetadata` including git and config snapshot.

Compliance checklist
- Preserves existing Phase boundaries.
- No Fusion, KPI processing, explainability, or hyperparameter optimization introduced.
- All outputs remain compatible with Phase7 requirements via manifest and canonical CSV schema.

Next steps (documentation deliverables)
- Update `phase6/README.md` with execution workflow, supported Python version, dependencies, artifact layout, and short module descriptions.
- Provide a short UML/component diagram if required for the dissertation.

