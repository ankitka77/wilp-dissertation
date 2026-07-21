Module: types.py

1. Purpose
- Central location for shared dataclasses, enums and type aliases used across modules.

2. Public Classes
- None (module exposes dataclasses and enums; not classes).

3. Dataclasses
- `Phase5Inputs`, `DatasetMetadata`, `ModelSpec`, `ModelMetadata`, `TrainingResult`, `ValidationResult`, `PredictionResult`, `DecisionResult`, `ExperimentInfo`, `ManifestInfo`, `PredictionConfidence`, `EncoderState`, `PersistenceInfo`.

4. Enumerations
- `TrainingStatus` (NOT_STARTED, RUNNING, COMPLETED, FAILED)
- `CheckpointType` (INTERMEDIATE, FINAL, BEST)
- `DecisionReason` (SCORE_THRESHOLD, MANUAL_OVERRIDE, NOT_APPLICABLE)

5. Public Methods
- None

6. Private Methods
- None

7. Module Inputs/Outputs
- Exposes dataclass definitions to be imported.

8. Dependencies
- None

Note: keep `types.py` minimal and free of imports that would cause circular dependencies.
