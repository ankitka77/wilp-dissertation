Module: experiment_manager.py

1. Purpose
- Create and manage experiment directories, provide standardized locations for artifacts, ensure uniqueness and basic bookkeeping.

2. Public Classes
- `ExperimentManager` (`root`, `config`, `logger`)

3. Dataclasses
- `ExperimentInfo` (`experiment_id`, `path`, `models_path`, `reports_path`, `plots_path`, `manifests_path`, `created_on`)

4. Enumerations
- None

5. Public Methods
- `start_experiment(self, name=None, tags=None) -> ExperimentInfo`
  - Raises: `ExperimentError`
- `finalize_experiment(self, experiment_info, summary) -> str`
  - Raises: `ExperimentError`

6. Private Methods
- `_make_unique_experiment_id`, `_ensure_dirs`

7. Module Inputs
- `Config`, optional name/tags

8. Module Outputs
- `ExperimentInfo` and directories on disk

9. Dependencies
- config.py, logger.py, persistence.py, types.py
