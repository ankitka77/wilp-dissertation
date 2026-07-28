"""Bootstrap utility for Phase 8 metadata initialization.

Creates experiment metadata and dataset manifests needed by Phase 8
(e.g. when running on a fresh checkout). The script is idempotent and
intentionally minimal: it only creates experiment and dataset entries
via the existing managers.

Usage:
    python -m phase8.bootstrap <experiment_id> <kpi_dataset_id> <deeplog_dataset_id> [--artifact-root PATH]

Behavior:
- Creates the experiment via `ExperimentManager.create_experiment` unless it already exists.
- Registers the KPI dataset via `DatasetManager.register_dataset` unless it already exists.
- Registers the DeepLog dataset via `DatasetManager.register_dataset` unless it already exists.

Exit codes:
- 0 on success (including when items already exist)
- non-zero for unexpected errors
"""
from __future__ import annotations

from pathlib import Path
import argparse
import logging
import sys
import shutil
import csv
from typing import Optional

from phase8.core.artifact_store import ArtifactStore
from phase8.core.experiment_manager import ExperimentManager, ExperimentExistsError
from phase8.core.dataset_manager import DatasetManager, DatasetExistsError


def _configure_project_logger(level_name: Optional[str] = "INFO") -> logging.Logger:
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
    parser = argparse.ArgumentParser(description="Bootstrap Phase 8 metadata (experiments & datasets)")
    parser.add_argument("experiment_id", help="Experiment id to create")
    parser.add_argument("kpi_dataset_id", help="KPI dataset id to register")
    parser.add_argument("deeplog_dataset_id", help="DeepLog dataset id to register")
    parser.add_argument("--artifact-root", required=False, help="Root directory for artifacts (defaults to artifacts/phase8)")
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent
    artifact_root = (Path(args.artifact_root) if args.artifact_root else repo_root / "artifacts" / "phase8")

    logger = _configure_project_logger()

    try:
        store = ArtifactStore(artifact_root)
        exp_mgr = ExperimentManager(store)
        ds_mgr = DatasetManager(store)

        # 1) Create experiment (idempotent)
        try:
            exp_mgr.create_experiment(args.experiment_id)
            logger.info("Created experiment %s", args.experiment_id)
        except ExperimentExistsError:
            logger.info("Experiment already exists: %s", args.experiment_id)

        # 2) Register KPI dataset (idempotent)
        try:
            ds_mgr.register_dataset(
                dataset_id=args.kpi_dataset_id,
                description="Phase 8 KPI dataset",
                source={
                    "type": "kpi",
                    "phase": "phase4",
                    "artifact": "artifacts/phase4/latest/anomaly_predictions.csv",
                },
            )
            logger.info("Registered KPI dataset %s", args.kpi_dataset_id)
        except DatasetExistsError:
            logger.info("KPI dataset already registered: %s", args.kpi_dataset_id)

        # 3) Register DeepLog dataset (idempotent)
        try:
            ds_mgr.register_dataset(
                dataset_id=args.deeplog_dataset_id,
                description="Phase 8 DeepLog dataset",
                source={
                    "type": "deeplog",
                    "phase": "phase6",
                    "artifact": "artifacts/phase6/latest/predictions.csv",
                },
            )
            logger.info("Registered DeepLog dataset %s", args.deeplog_dataset_id)
        except DatasetExistsError:
            logger.info("DeepLog dataset already registered: %s", args.deeplog_dataset_id)

        # ---- Artifact staging: copy published artifacts from earlier phases ----
        try:

            # Phase 4
            src4 = repo_root / "artifacts" / "phase4" / "latest"
            dst4 = repo_root / "artifacts" / "phase8" / "phase4" / "latest"
            logger.info("Copying published Phase 4 artifacts...")
            try:
                if not src4.exists():
                    logger.warning("Published Phase 4 artifacts not found: %s", str(src4))
                else:
                    dst4.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(str(src4), str(dst4), dirs_exist_ok=True)
                    logger.info("Published Phase 4 artifacts copied successfully.")
            except Exception as exc:  # non-fatal
                logger.warning("Failed to copy Phase 4 artifacts from %s to %s: %s", str(src4), str(dst4), exc)

            # Phase 6
            src6 = repo_root / "artifacts" / "phase6" / "latest"
            dst6 = repo_root / "artifacts" / "phase8" / "phase6" / "latest"
            logger.info("Copying published Phase 6 artifacts...")
            try:
                if not src6.exists():
                    logger.warning("Published Phase 6 artifacts not found: %s", str(src6))
                else:
                    dst6.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(str(src6), str(dst6), dirs_exist_ok=True)
                    logger.info("Published Phase 6 artifacts copied successfully.")
            except Exception as exc:  # non-fatal
                logger.warning("Failed to copy Phase 6 artifacts from %s to %s: %s", str(src6), str(dst6), exc)

            # Phase 7
            src7 = repo_root / "artifacts" / "phase7" / "latest"
            dst7 = repo_root / "artifacts" / "phase8" / "phase7" / "latest"
            logger.info("Copying published Phase 7 artifacts...")
            try:
                if not src7.exists():
                    logger.warning("Published Phase 7 artifacts not found: %s", str(src7))
                else:
                    dst7.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(str(src7), str(dst7), dirs_exist_ok=True)
                    logger.info("Published Phase 7 artifacts copied successfully.")
            except Exception as exc:
                logger.warning("Failed to copy Phase 7 artifacts from %s to %s: %s", str(src7), str(dst7), exc)

        except Exception:
            logger.exception("Unexpected error during artifact staging; continuing")

        # ---- KPI ground-truth staging ----
        try:
            src_gt = repo_root / "data" / "kpi" / "train.csv"
            dst_dir = repo_root / "artifacts" / "phase8" / args.kpi_dataset_id
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst_gt = dst_dir / "ground_truth.csv"

            logger.info("Staging KPI ground truth dataset...")
            if not src_gt.exists():
                logger.warning("KPI training dataset not found: %s", str(src_gt))
            else:
                try:
                    with src_gt.open("r", encoding="utf-8", newline="") as inf:
                        reader = csv.DictReader(inf)
                        fieldnames = ["timestamp", "KPI ID", "label"]
                        with dst_gt.open("w", encoding="utf-8", newline="") as outf:
                            writer = csv.DictWriter(outf, fieldnames=fieldnames)
                            writer.writeheader()
                            for row in reader:
                                out_row = {k: row.get(k, "") for k in fieldnames}
                                writer.writerow(out_row)
                    logger.info("KPI ground truth written to: %s", str(dst_gt))
                except Exception as exc:
                    logger.warning("Failed to write KPI ground truth to %s: %s", str(dst_gt), exc)
        except Exception:
            logger.exception("Unexpected error during KPI ground-truth staging; continuing")

        logger.info("Bootstrap completed successfully.")

        return 0

    except Exception:
        logger = logging.getLogger("project")
        logger.exception("Unexpected error during Phase 8 bootstrap")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
