Module: config.py

1. Purpose
- Centralized configuration provider. Load runtime configuration (YAML/JSON/env) and provide a validated `Config` object consumed by other modules.

2. Public Classes
- `ConfigLoader`
  - Responsibilities: load config from file and environment, validate, apply defaults.
  - Attributes: `config_path: str`, `overrides: dict[str, Any]`
  - Lifecycle: instantiate → `load()` → returns `Config` dataclass.

3. Dataclasses
- `Config`
  - Fields (type, default):
    - `learning_rate: float` (0.001)
    - `batch_size: int` (256)
    - `epochs: int` (10)
    - `optimizer: str` ("adam")
    - `scheduler: str | None` (None)
    - `dropout: float` (0.2)
    - `hidden_size: int` (128)
    - `embedding_dim: int` (128)
    - `sequence_length: int` (50)
    - `top_k: int` (5)
    - `threshold: float | None` (None)
    - `random_seed: int` (42)
    - `artifact_root: str` ("artifacts/phase6")
    - `experiment_root: str` ("<artifact_root>/experiments")
    - `logging_level: str` ("INFO")
    - `device: str` ("cpu")
    - `pad_token: int` (0)
    - `vocab_unknown_token: int` (0)
    - `num_workers: int` (4)
    - `checkpoint_interval_epochs: int` (1)
    - `max_checkpoints: int` (5)
    - `save_format: str` ("bin")
    - `git_info_source: str | None` (None)
    - `notes: str | None` (None)

4. Enumerations
- None

5. Public Methods
- `ConfigLoader.load(self) -> Config`
  - Read config file and env overrides, validate types and bounds, return `Config`.
  - Exceptions: `ConfigurationError`.

6. Private Methods
- `_apply_env_overrides(...)`, `_validate_bounds(...)` (validation helpers)

7. Module Inputs
- Path to config file (YAML/JSON) and optional overrides dict.

8. Module Outputs
- `Config` dataclass instance.

9. Dependencies
- None
