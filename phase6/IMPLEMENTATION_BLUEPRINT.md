Implementation Blueprint — Phase 6 DeepLog

This file contains the authoritative implementation blueprint for Phase 6. It is derived from the frozen architecture in `docs/phase6_architecture.md` and provides module-level specifications and shared dataclasses, exceptions, configuration parameters, artifact schemas, execution flow, dependency graph, and unit-test plans.

Follow the repository's architecture strictly: do not rename, add, remove, split, or merge modules; do not change data flow or interfaces.

Contents
- Global conventions
- Module-by-module implementation specification (config.py, logger.py, types.py, ingest.py, sequence_encoder.py, dataset.py, model_spec.py, trainer.py, validator.py, metrics.py, inference.py, decision_engine.py, persistence.py, experiment_manager.py, report_generator.py, visualizer.py, orchestrator.py)
- Shared dataclasses
- Exception definitions
- Configuration parameters
- Artifact schemas
- Execution flow
- Dependency graph
- Unit test plan

Refer to `phase6/docs/` for per-module developer-friendly markdown files.

---

GLOBAL CONVENTIONS
- Use explicit type annotations for all public method signatures.
- Use dataclasses for structured data. Mark immutable dataclasses `frozen=True` where noted.
- All filesystem paths in artifacts and manifests must be workspace-relative strings.
- Modules must not raise generic exceptions; use the custom exceptions defined in this blueprint.
- All JSON artifacts must be UTF-8 with stable pretty-print formatting (indent=2).
- Timestamps must be ISO8601 in UTC.

---

The complete, detailed per-module specifications, shared dataclasses, configuration param lists, artifact schemas, execution flow, dependency graph and unit test plan are included here and are identical to the per-module files under `phase6/docs/`.

Please use the per-module files for implementation reference.
