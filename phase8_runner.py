"""Entry point to execute the Phase 8 Experiment Orchestrator.

This launcher instantiates `ArtifactStore`, `ExperimentManager`, and
`DatasetManager`, composes the existing `ExperimentOrchestrator`, and
invokes its `run` API. It performs orchestration only and does not
implement any business logic.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import logging
import sys

from phase8.core.artifact_store import ArtifactStore
from phase8.core.experiment_manager import ExperimentManager
from phase8.core.dataset_manager import DatasetManager
from phase8.orchestrator import ExperimentOrchestrator


def _configure_project_logger(level_name: str | None = "INFO") -> logging.Logger:
    logger = logging.getLogger("project")
    level = getattr(logging, (level_name or "INFO").upper(), logging.INFO)
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)
        fmt = logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s")
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    return logger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase 8 experiment orchestrator")
    parser.add_argument("experiment_id", help="Experiment id to run")
    parser.add_argument("kpi_dataset_id", help="KPI dataset id to evaluate")
    parser.add_argument("deeplog_dataset_id", help="DeepLog dataset id to evaluate")
    parser.add_argument("--artifact-root", required=False, help="Root directory for artifacts (defaults to artifacts/phase8)")
    args = parser.parse_args(argv)

    project_root = Path(__file__).resolve().parent
    artifact_root = Path(args.artifact_root) if args.artifact_root else project_root / "artifacts" / "phase8"

    logger = _configure_project_logger()

    try:
        store = ArtifactStore(artifact_root)
        exp_mgr = ExperimentManager(store)
        ds_mgr = DatasetManager(store)

        orchestrator = ExperimentOrchestrator(exp_mgr, ds_mgr, store)

        logger.info("Starting Phase 8 ExperimentOrchestrator: experiment=%s", args.experiment_id)
        result = orchestrator.run(args.experiment_id, args.kpi_dataset_id, args.deeplog_dataset_id)

        print("Phase 8 completed successfully.")
        print("Result summary:")
        for k, v in result.__dict__.items():
            print(f"  {k}: {v}")
        return 0
    except Exception:
        logger.exception("Unhandled exception during Phase 8 execution")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
