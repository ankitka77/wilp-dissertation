Module: persistence.py

1. Purpose
- Save and load model artifacts and associated metadata consistently and atomically. Provide checksums and integrity metadata.

2. Public Classes
- `PersistenceManager` (`experiment_path`, `logger`, `config`)

3. Dataclasses
- `PersistenceInfo` (`path`, `metadata_path`, `checksum`, `created_on`, `checkpoint_type`)

4. Enumerations
- `CheckpointType` (in types)

5. Public Methods
- `save_model(self, model_obj, metadata, checkpoint_type) -> PersistenceInfo`
  - Raises: `ModelPersistenceError`
- `load_model(self, path) -> tuple[Any, ModelMetadata]`
  - Raises: `ModelPersistenceError`, `InferenceError`
- `list_checkpoints(self) -> list[PersistenceInfo]`

6. Private Methods
- `_atomic_write_file`, `_compute_checksum`, `_prune_old_checkpoints`

7. Module Inputs
- Model objects, ModelMetadata, experiment paths

8. Module Outputs
- Files and `PersistenceInfo`

9. Dependencies
- experiment_manager.py, types.py, logger.py, hashlib, json
