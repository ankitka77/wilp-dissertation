Module: orchestrator.py

1. Purpose
- Entrypoint that wires all modules to run a Phase 6 experiment end-to-end and write artifacts and final manifest.

2. Public Classes
- `Orchestrator` (`config`, `logger`, `experiment_manager`)

3. Dataclasses
- None new (uses shared types)

4. Enumerations
- None

5. Public Methods
- `run_phase6(self, paths: dict[str,str], overrides: dict[str,Any] | None = None) -> str`
  - Returns path to `phase6_manifest.json`
  - Raises: `OrchestrationError`
- `_handle_exception(self, exc: Exception) -> None`

6. Private Methods
- `_build_components`, `_finalize_and_write_manifest`

7. Module Inputs
- Path to Phase 5 artifacts and config overrides

8. Module Outputs
- Final manifest path and all artifacts under experiment dir

9. Dependencies
- All modules in this blueprint
