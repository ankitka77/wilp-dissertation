Module: logger.py

1. Purpose
- Provide a centralized, repeatable logger factory that other modules import.

2. Public Classes
- `LoggerFactory`
  - Responsibilities: create and configure named loggers tied to an experiment.
  - Attributes: `config: Config`, `experiment_path: str | None`.
  - Lifecycle: instantiate → `get_logger(name: str)` returns configured `logging.Logger`.

3. Dataclasses
- None

4. Enumerations
- None

5. Public Methods
- `LoggerFactory.get_logger(self, name: str) -> logging.Logger`
  - Ensures file handler exists at `<experiment_path>/logs/<name>.log` and returns logger.

6. Private Methods
- `_ensure_log_dir(path: str)`, `_configure_handler(...)`

7. Module Inputs
- `Config` and optional `experiment_path`.

8. Module Outputs
- `logging.Logger` objects.

9. Dependencies
- `config.py`
