"""Entry point to execute the Phase 6 pipeline.

This script constructs the minimal runtime objects required by the
existing Phase 6 implementation and invokes the public orchestration
API. It intentionally performs no changes to the package structure or
public interfaces and only uses existing constructors and methods.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any
import logging

from phase6.config import Config, ConfigLoader, ConfigurationError
from phase6.experiment_manager import ExperimentManager
from phase6.orchestrator import Orchestrator, OrchestrationError


def _configure_project_logger(cfg: Config) -> logging.Logger:
    """Configure and return the centralized project logger based on cfg."""
    logger = logging.getLogger("project")
    level = getattr(logging, (cfg.logging_level or "INFO").upper(), logging.INFO)
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)
        formatter = logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def main() -> int:
    """Run Phase 6 and return an exit code.

    Returns
    -------
    int
        Exit code: 0 success, 1 orchestration error, 2 unexpected error.
    """
    project_root = Path(__file__).resolve().parent

    # Load configuration from repo `config/settings.yaml` when available,
    # falling back to blueprint defaults if loading fails.
    cfg_path = project_root / "config" / "settings.yaml"
    try:
        cfg = ConfigLoader(cfg_path).load()
    except ConfigurationError as exc:
        # Best-effort fallback to defaults
        print(f"Warning: failed to load config file: {exc}; using defaults")
        cfg = Config()

    # Configure logging using the project logger
    logger = _configure_project_logger(cfg)

    # ExperimentManager root derived from config and project layout
    exp_root = (project_root / cfg.experiment_root).resolve()
    exp_manager = ExperimentManager(exp_root, cfg, logger)

    # Instantiate orchestrator with existing public API
    orchestrator = Orchestrator(config=cfg, logger=logger, experiment_manager=exp_manager)

    # Build Phase 5 artifact mapping expected by the Ingestor
    phase5_dir = (project_root / "artifacts" / "reports" / "phase5").resolve()
    paths: Dict[str, Any] = {
        "vocabulary": str((phase5_dir / "event_vocabulary.json")),
        "sequences": str((phase5_dir / "training_sequences.csv")),
        "train": str((phase5_dir / "training_sequences.csv")),
        "test": str((phase5_dir / "test_sequences.csv")),
        "dataset_name": str((phase5_dir / "phase5_manifest.json")),
    }

    try:
        manifest_path = orchestrator.run_phase6(paths)
        print("Phase 6 completed successfully.", manifest_path)
        return 0
    except OrchestrationError as oe:
        print(f"Orchestration failed: {oe}")
        return 1
    except Exception:
        logger.exception("Unhandled exception during Phase 6 execution")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
