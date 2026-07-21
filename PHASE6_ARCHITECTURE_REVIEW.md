# Phase 6 Architecture Review

## Executive Summary

This review inspects the repository code related to Phase 6 (DeepLog/LSTM) and reports what is implemented, what is partial, and what is missing to run Phase 6 end-to-end under the current architecture. The repository contains extensive scaffolding (ingest, dataset, encoder, trainer framework, inference framework, persistence manager, reporting, metrics, experiment manager). However, the actual DeepLog/LSTM model and the wiring to instantiate and persist it are not implemented. Several small integration mismatches exist (trainer <> persistence API expectations, orchestrator does not instantiate a model). Below are component-by-component findings and precise required actions.


=============================================
PHASE 6 ARCHITECTURE REVIEW
=============================================

Component: DeepLog / LSTM Model
Status: Missing
Evidence:
- No Phase 6 model implementation file found under `phase6/` (no `phase6/model.py` or `phase6/deeplog.py`).
- `src/log_model/model.py` exists but is a scaffold raising `NotImplementedError`.
- Many docs reference DeepLog (docs/phase6_architecture.md, phase6/README.md), and `requirements.txt` includes `tensorflow>=2.16.0`, indicating intent to use a deep-learning framework, but no code implements the neural network.
Required Action:
- Implement a concrete DeepLog/LSTM model class (within the existing Phase 6 package) exposing the required runtime methods: `train_epoch` or `train_step`, and `predict_topk`, `predict_probs`.


Component: Model Factory / Model Instantiation
Status: Missing / Partial
Evidence:
- `phase6/orchestrator.py` does not create a model instance. `components` built in `_build_components` contains `model_spec_factory`, `trainer`, `inference`, `persistence`, etc., but no `model` key is created.
- `src/infrastructure/model_factory.py` exists but registers only `isolation_forest` (Phase 4) and lives outside `phase6`.
Required Action:
- Provide a Phase 6 model factory or add logic in `phase6/_build_components` (or a designated factory module) that instantiates the DeepLog model given a `ModelSpec` (deterministic mapping from `ModelSpecFactory.create_model_spec`). Ensure this instantiation is added to `components['model']` so `Trainer` and `InferenceEngine` receive the model object.


Component: Orchestrator
Status: Partial
Evidence:
- `phase6/orchestrator.py` assembles components, calls `Ingestor.load`, builds `model_spec` and invokes `trainer.train(model_obj, train_loader, val_loader)` and `inference.run(model_obj, test_loader, ...)`.
- In the current codebase, `model_obj` is `None` because orchestrator does not instantiate a model; orchestrator logging observed (runtime) demonstrates trainer/inference errors when model missing.
Required Action:
- Add model instantiation step in `_build_components` (use `model_spec_factory` output and a Phase 6 model factory) so `components` contains a concrete `model` before calling `trainer` and `inference`.


Component: Trainer
Status: Partial (framework present, integration gaps)
Evidence:
- `phase6/trainer.py` provides a complete training loop scaffold supporting `epochs`, `train_epoch` or `train_step` APIs, validation calls via `Validator`, checkpointing hooks, epoch metrics accumulation, and early stopping logic.
- Trainer expects a persistence API available as `phase6.persistence.save_checkpoint(...)` (module-level function) and fails if not present (`if not hasattr(persistence, "save_checkpoint")`).
- `phase6/persistence.py` implements `PersistenceManager` class methods `save_model` and `load_model`, but no module-level `save_checkpoint` function — an API mismatch.
Required Action:
- Either add a thin adapter `save_checkpoint(...)` in `phase6/persistence.py` that uses a `PersistenceManager` instance to persist a checkpoint and return a `PersistenceInfo`, or modify `Trainer._save_checkpoint` to use the `PersistenceManager` instance provided in components (less intrusive: add adapter function). Ensure the returned object is JSON-serializable or convertible to `PersistenceInfo` as trainer expects.


Component: Dataset (SequenceDataset, DataLoader)
Status: Complete
Evidence:
- `phase6/dataset.py` implements `SequenceDataset`, `DataLoader`, `make_dataloader`, `default_collate_fn`, and padding/mask utilities.
- SequenceDataset.metadata computes `vocab_size`, `max_seq_len`, and `num_batches`.
- `phase5` outputs (training_sequences.csv) contain columns such as `sequence_events`, `input_sequence` etc.; `phase6/ingest.py` contains logic mapping common alternates to `sequence` at runtime (a compatibility helper).
Required Action:
- No implementation required; ensure ingest pipeline is wired to produce sequences (already done). Validate token ids and pad token alignment between `ModelSpec` and `SequenceDataset` at model instantiation time.


Component: Sequence Encoder
Status: Complete
Evidence:
- `phase6/sequence_encoder.py` provides `SequenceEncoder` with encode/decode/pad/truncate/serialize/deserialize.
Required Action:
- No code changes required. Ensure the encoder is created using vocabulary/data from `Ingestor` and passed to model/data pipeline.


Component: Inference
Status: Partial
Evidence:
- `phase6/inference.py` implements `InferenceEngine` with `run`, `_batch_infer`, and formatting helpers; it expects model methods `predict_topk` and `predict_probs`.
- Runtime logs show inference errors when `model` missing or does not implement those methods.
Required Action:
- Implement model-side `predict_topk` and `predict_probs` methods. Once a model is implemented and added to `components`, inference code should operate as designed. Also ensure `test_loader` format conforms to `InferenceEngine` expectation (batches with `inputs` and optional `ids`).


Component: Persistence
Status: Partial
Evidence:
- `phase6/persistence.py` implements `PersistenceManager` class with `save_model`, `load_model`, `list_checkpoints`, and atomic write helpers. Uses `pickle` to persist models and JSON metadata.
- Trainer expects a module-level `save_checkpoint` function; persistence exposes class-based API not matching trainer expectation.
Required Action:
- Provide a compatibility adapter: add `save_checkpoint(...)` module-level function (thin wrapper) that creates or uses a `PersistenceManager` instance and returns a `PersistenceInfo` mapping. Alternatively, update `Trainer._save_checkpoint` to use the `PersistenceManager` instance from `components` — whichever is chosen must preserve existing blueprint API expectations.


Component: Reporting
Status: Complete
Evidence:
- `phase6/report_generator.py` implements `ReportGenerator` with `write_training_metrics`, `write_predictions`, `write_manifest`, and atomic JSON/CSV helpers.
Required Action:
- Ensure `ReportGenerator` is included in `components` (orchestrator already does) and receives `training_result` / `decision_result` where appropriate. No code changes necessary beyond wiring.


Component: Validation
Status: Complete
Evidence:
- `phase6/validator.py` implements `Validator.validate` using `MetricsProvider`, aggregates batch metrics, computes top-k accuracy, and returns `ValidationResult` dataclass.
Required Action:
- No further code required; ensure `Trainer` passes the model and validation DataLoader. The module is ready to run when a model is provided.


Component: Metrics
Status: Complete
Evidence:
- `phase6/metrics.py` implements `MetricsProvider` with top-K accuracy, precision/recall, anomaly score conversion, batch metrics, and normalization.
Required Action:
- None.


Component: Decision Engine
Status: Complete (conditional)
Evidence:
- `phase6/decision_engine.py` implements `DecisionEngine.decide` and uses a configured `threshold` to produce binary decisions and confidence. Requires `PredictionResult` input and a configured threshold (or argument) to operate.
Required Action:
- Provide `threshold` in Config or pass one during orchestration. No code implementation required.


Component: Experiment Manager
Status: Complete
Evidence:
- `phase6/experiment_manager.py` implements `ExperimentManager.start_experiment` and `finalize_experiment` with directory creation and recorded metadata.
Required Action:
- None.


Component: Orchestration Wiring
Status: Partial
Evidence:
- `phase6/orchestrator.py` implements orchestration flow: ingest -> model_spec -> trainer -> inference -> decision -> reports -> manifest. However, orchestrator does not instantiate a model nor provide the persistence adapter expected by trainer.
Required Action:
- Add code to instantiate the model (using `model_spec` and a Phase 6 model factory) and place it in `components['model']` before calling trainer/inference. Add or ensure a persistence adapter function `save_checkpoint` is available (or adjust trainer to use the PersistenceManager instance created in components).


=============================================
MISSING COMPONENTS
=============================================

High Priority
- DeepLog/LSTM model implementation (Phase 6 model class exposing `train_epoch` or `train_step`, `predict_topk`, and `predict_probs`). Without this, no training or inference can occur.
- Model instantiation wiring (a Phase 6 model factory or orchestrator change to create `components['model']`). Orchestrator currently never adds a model object to `components`.
- Trainer <> Persistence integration mismatch: either expose `phase6.persistence.save_checkpoint(...)` adapter or modify `Trainer._save_checkpoint` to use the `PersistenceManager` instance from `components`. This prevents checkpoint saving.

Medium Priority
- A small adapter to ensure `phase6.persistence` exposes the module-level function shape trainer expects (or update trainer). This is necessary for checkpointing to function as designed.
- Ensure decision threshold is configured (Config.threshold) or passed at runtime; DecisionEngine raises an error if threshold is absent.

Low Priority
- Add example configuration or README instructions documenting how to enable/instantiate the DeepLog model and which config keys (sequence_length, vocab_size, pad_token) must align.
- Tests or integration example showing end-to-end Phase6 run (optional but helpful).


=============================================
FILES REQUIRING IMPLEMENTATION
=============================================

- Filename: `phase6/<deep_log_model>.py` (e.g., `phase6/model.py` or `phase6/deeplog.py`)
  - Reason: No Phase 6 model exists; DeepLog/LSTM must be implemented inside Phase 6 package so orchestrator/trainer/inference can load it.
  - What is missing: Concrete model class implementing training API and inference API: `train_epoch(train_loader)` OR `train_step(inputs, targets)`, plus `predict_topk(inputs, k)` and `predict_probs(inputs)`; serialization support (picklable) for persistence; optionally `state_dict`/`load_state_dict` if using TF/Keras provide appropriate serialization.
  - Estimated implementation effort: Large (designing, training loop behavior, handling batch inputs, Keras/TensorFlow code, integration with Dataset and ModelSpec).
  - Implementation vs Integration: Implementation (model code) + Integration (ensure orchestrator instantiates it).

- Filename: `phase6/orchestrator.py` (small modification)
  - Reason: Orchestrator currently does not instantiate a `model` and therefore passes `None` to `Trainer` and `InferenceEngine`.
  - What is missing: A call that creates a model instance (using `ModelSpecFactory` output) and places it in `components['model']` or a small factory import and instantiation step.
  - Estimated implementation effort: Small to Medium (few lines to instantiate and add to components; must ensure model constructor signature matches `ModelSpec`).
  - Implementation vs Integration: Integration.

- Filename: `phase6/persistence.py` (compatibility adapter)
  - Reason: `Trainer` expects `phase6.persistence.save_checkpoint(...)` at module level; persistence defines `PersistenceManager.save_model` instance method.
  - What is missing: A module-level wrapper function `save_checkpoint(experiment_info, model_spec, epoch, checkpoint_type)` (or similar) that constructs/uses a `PersistenceManager` and returns a `PersistenceInfo` (or a mapping that `Trainer._save_checkpoint` can convert to dict/asdict).
  - Estimated implementation effort: Small.
  - Implementation vs Integration: Integration / adapter.

- Filename: `phase6/model_factory.py` (optional)
  - Reason: A dedicated factory that maps `ModelSpec` -> concrete model class makes orchestrator clean. Not strictly required if orchestrator instantiates directly.
  - What is missing: Factory to register and instantiate model classes by spec or name.
  - Estimated implementation effort: Small.
  - Implementation vs Integration: Implementation + Integration.

- Filename: `src/log_model/model.py` (optional alternative)
  - Reason: A placeholder exists here; project authors may prefer implementing models in `src/log_model` rather than `phase6`. This file currently raises `NotImplementedError`.
  - What is missing: Concrete DeepLog implementation or an adapter that forwards to a proper `phase6` model for runtime.
  - Estimated implementation effort: Medium.
  - Implementation vs Integration: Implementation.


=============================================
POTENTIAL RISKS
=============================================

- Serialization/Framework mismatch: Trainer and PersistenceManager currently use `pickle` to persist models. If using TensorFlow/Keras (recommended by `requirements.txt`), additional care is required to persist model weights and metadata in a stable cross-platform format (Keras `save`/`load_model` vs `pickle`). Choose a consistent persistence story.

- API contract mismatch: Trainer expects a module-level `save_checkpoint` function; persistence implements a class. Any implementation must preserve the contract trainer expects, or trainer must be changed. Changing trainer is riskier because it touches training logic; adding a thin adapter in `persistence.py` is safer.

- Determinism requirements: `EventIdMapper` and `ModelSpecFactory` require deterministic behaviors (vocab assignment, spec values). Ensure created model uses `ModelSpec` fields explicitly (embedding dim, pad token, sequence_length) and that tokenization aligns with `SequenceEncoder`.

- Resource consumption: Implementing LSTM/DeepLog with large vocab and long sequences may cause high memory usage; ensure dataset batching, embedding size, and device usage (CPU/GPU) are configurable in `Config`.


=============================================
FINAL ASSESSMENT
=============================================

1. Is the DeepLog/LSTM model implemented?

NO

2. Can Phase 6 currently train a model?

NO
- Reason: No model implementation available and training cannot proceed because `orchestrator` does not instantiate a concrete model and `Trainer` would fail when attempting to save checkpoints (persistence API mismatch).

3. Can Phase 6 currently perform inference?

NO
- Reason: `InferenceEngine` is implemented but requires a model implementing `predict_topk` and `predict_probs`. No such model exists or is instantiated.

4. Can Phase 6 currently produce anomaly predictions?

NO
- Reason: Predictions require a model + inference + decision engine. Model missing prevents end-to-end predictions.

5. What is the MINIMUM work required to consider Phase 6 complete?

Minimum tasks (strictly within the existing architecture, no redesign):

High-priority (minimal viable set):
- Implement a concrete DeepLog/LSTM model class inside the Phase 6 package (file: `phase6/<deep_log_model>.py` or `phase6/model.py`) that:
  - Accepts `ModelSpec` (or parameters matching it) at construction and uses `vocab_size`, `embedding_dim`, `hidden_size`, `num_layers`, `dropout`, `sequence_length`, `pad_token`.
  - Implements training API: either `train_epoch(train_loader)` returning a scalar loss or `train_step(inputs, targets)` returning per-batch loss (either is acceptable because `Trainer` supports both).
  - Implements inference API: `predict_topk(inputs, k)` and `predict_probs(inputs)` returning iterables aligned with batch size.
  - Is serializable by the chosen persistence adapter (or provides a serialization helper that `PersistenceManager.save_model` can consume).

- Ensure orchestrator instantiates the model and places it in `components['model']` before the trainer and inference steps (small change to `phase6/orchestrator.py` to call the model factory or direct constructor using `ModelSpecFactory.create_model_spec`).

- Add a thin persistence adapter in `phase6/persistence.py` (module-level `save_checkpoint`) or update `Trainer._save_checkpoint` to call the `PersistenceManager` instance in components. The adapter should return a `PersistenceInfo` mapping or an object convertible to dict as `Trainer._save_checkpoint` expects.

Medium-priority (to make runs robust):
- Add configuration guidance (Config.threshold) or a default threshold for DecisionEngine.
- Add or adjust examples and small integration tests showing sample dataset → model training → inference → decision → reports.

Low-priority (nice-to-have):
- Provide GPU device selection and careful persistence using framework-native saving (e.g., Keras `model.save`) together with stamped metadata; implement a loader that reconstructs model object + weights in `PersistenceManager.load_model`.

Once the high-priority items are implemented and wired, Phase 6 should be able to train, validate, and run inference for DeepLog-style models using the existing trainer, inference, validator, metrics, report generator, and persistence scaffolding.


---

Reviewed files consulted (non-exhaustive):
- phase6/* (config.py, dataset.py, inference.py, ingest.py, metrics.py, model_spec.py, orchestrator.py, persistence.py, report_generator.py, sequence_encoder.py, trainer.py, validator.py, visualizer.py, experiment_manager.py)
- src/log_model/model.py (scaffold)
- src/infrastructure/model_factory.py (isolation_forest only)
- artifacts/reports/phase5/training_sequences.csv (observed canonical columns)
- docs/* and phase6 design docs referenced in repo


End of review.
