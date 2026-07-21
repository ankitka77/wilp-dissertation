"""Phase 6 package initializer.

This file makes the `phase6` directory a proper Python package so tests
and external imports can load submodules. It intentionally performs no
imports to avoid side effects at package import time.
"""

__all__ = [
    "config",
    "dataset",
    "decision_engine",
    "experiment_manager",
    "inference",
    "ingest",
    "logger",
    "metrics",
    "model_spec",
    "persistence",
    "report_generator",
    "sequence_encoder",
    "trainer",
    "types",
    "validator",
    "visualizer",
    "orchestrator",
]
