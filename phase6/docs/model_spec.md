Module: model_spec.py

1. Purpose
- Define model hyperparameters and ModelSpec dataclass used in manifests and persisted metadata.

2. Public Classes
- `ModelSpecFactory` (create validated ModelSpec from config and overrides)

3. Dataclasses
- `ModelSpec` (`vocab_size`, `embedding_dim`, `hidden_size`, `num_layers`, `dropout`, `rnn_type`, `output_type`, `sequence_length`, `top_k`, `pad_token`)
- `ModelMetadata` (`model_name`, `version`, `created_on`, `model_spec`, `training_summary_ref`, `artifact_path`, `git`, `config_snapshot`, `checksum`)

4. Enumerations
- None

5. Public Methods
- `ModelSpecFactory.create_model_spec(self, overrides: dict | None) -> ModelSpec` (raises ConfigurationError on invalid inputs)

6. Private Methods
- `_validate_model_spec`

7. Module Inputs
- `Config`, dataset metadata

8. Module Outputs
- `ModelSpec`, `ModelMetadata` (when persisted)

9. Dependencies
- config.py, types.py
