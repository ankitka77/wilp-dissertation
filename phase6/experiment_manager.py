"""Experiment manager for Phase 6.

This module implements the `ExperimentManager` responsible for creating and
bookkeeping experiment directories and providing standardized locations for
artifacts. The implementation follows the frozen Phase 6 blueprint and does
not change any external interfaces.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import json
import logging
import re
import uuid

from phase6.config import Config
from phase6.types import ExperimentInfo

LOGGER_NAME = "project"


class ExperimentError(RuntimeError):
    """Raised for experiment management failures."""


class ExperimentManager:
    """Create and manage experiment directories.

    Parameters
    ----------
    root:
        Filesystem root under which experiments are stored. May be a
        ``str`` or ``pathlib.Path``.
    config:
        Phase 6 `Config` instance used to derive defaults and validate
        behaviour.
    logger:
        A configured `logging.Logger` instance. The manager uses this for
        informational and error messages.
    """

    def __init__(self, root: str | Path, config: Config, logger: logging.Logger) -> None:
        if not isinstance(config, Config):
            raise ExperimentError("ExperimentManager requires a valid Config instance")
        if logger is None or not isinstance(logger, logging.Logger):
            raise ExperimentError("ExperimentManager requires a valid Logger instance")

        self._config = config
        self._root = Path(root) if not isinstance(root, Path) else root
        self._logger = logger

    def start_experiment(self, name: Optional[str] = None, tags: Optional[List[str]] = None) -> ExperimentInfo:
        """Start a new experiment by creating a uniquely-named experiment
        directory and standard subdirectories.

        Parameters
        ----------
        name:
            Optional human-readable name used as part of the experiment id.
        tags:
            Optional list of tags for bookkeeping (not persisted by this
            implementation but accepted for future compatibility).

        Returns
        -------
        ExperimentInfo
            Dataclass containing canonical string paths and identifier.

        Raises
        ------
        ExperimentError
            If directories cannot be created or an unexpected filesystem
            error occurs.
        """
        experiment_id = self._make_unique_experiment_id(name=name, tags=tags)
        exp_path = (self._root / experiment_id).resolve()

        self._logger.debug("Starting experiment %s at %s", experiment_id, exp_path)

        if exp_path.exists():
            msg = f"Experiment path already exists: {exp_path}"
            self._logger.error(msg)
            raise ExperimentError(msg)

        try:
            paths = self._ensure_dirs(exp_path)
        except ExperimentError:
            raise
        except Exception as exc:
            msg = f"Unexpected error while creating experiment directories: {exc}"
            self._logger.exception(msg)
            raise ExperimentError(msg) from exc

        created_on = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

        info = ExperimentInfo(
            experiment_id=experiment_id,
            path=str(paths["experiment"]),
            models_path=str(paths["models"]),
            reports_path=str(paths["reports"]),
            plots_path=str(paths["plots"]),
            manifests_path=str(paths["manifests"]),
            created_on=created_on,
        )

        # Persist a lightweight experiment metadata file for discoverability
        try:
            meta_path = Path(info.path) / "experiment_info.json"
            with meta_path.open("w", encoding="utf-8") as fh:
                json.dump(asdict(info), fh, indent=2)
        except Exception:
            # Metadata persistence is best-effort; do not fail the experiment
            # creation if writing this file does not succeed.
            self._logger.exception("Failed to write experiment metadata file: %s", meta_path)

        self._logger.info("Experiment started: %s", experiment_id)
        return info

    def finalize_experiment(self, experiment_info: ExperimentInfo, summary: Dict) -> str:
        """Finalize an experiment by persisting a summary manifest.

        Parameters
        ----------
        experiment_info:
            `ExperimentInfo` returned by :meth:`start_experiment`.
        summary:
            JSON-serializable mapping containing summary information to
            persist as the experiment manifest.

        Returns
        -------
        str
            Absolute path to the written manifest file.

        Raises
        ------
        ExperimentError
            If the manifest cannot be written or the experiment directory is
            missing.
        """
        if not isinstance(experiment_info, ExperimentInfo):
            raise ExperimentError("experiment_info must be an ExperimentInfo instance")

        manifests_dir = Path(experiment_info.manifests_path)
        if not manifests_dir.exists():
            msg = f"Manifests directory does not exist: {manifests_dir}"
            self._logger.error(msg)
            raise ExperimentError(msg)

        manifest_path = manifests_dir / "manifest.json"
        try:
            with manifest_path.open("w", encoding="utf-8") as fh:
                json.dump(summary, fh, indent=2)
        except Exception as exc:
            msg = f"Failed to write manifest file: {manifest_path}: {exc}"
            self._logger.exception(msg)
            raise ExperimentError(msg) from exc

        self._logger.info("Experiment finalized: %s; manifest=%s", experiment_info.experiment_id, manifest_path)
        return str(manifest_path.resolve())

    def _make_unique_experiment_id(self, name: Optional[str] = None, tags: Optional[List[str]] = None) -> str:
        """Create a filesystem-safe, unique experiment identifier.

        The identifier includes an ISO-like UTC timestamp, an optional
        sanitized name, and an 8-character UUID suffix to ensure uniqueness.
        """
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        base = (name or "exp").strip()
        # Sanitize to filesystem safe characters
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", base)[:64].lower() or "exp"
        suffix = uuid.uuid4().hex[:8]
        return f"{ts}_{safe}_{suffix}"

    def _ensure_dirs(self, experiment_path: Path) -> Dict[str, Path]:
        """Create the experiment directory structure.

        Returns a mapping of logical names to Path objects.
        """
        try:
            experiment_path.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            msg = f"Experiment directory already exists: {experiment_path}"
            self._logger.error(msg)
            raise ExperimentError(msg)
        except Exception as exc:
            msg = f"Unable to create experiment directory: {experiment_path}: {exc}"
            self._logger.exception(msg)
            raise ExperimentError(msg) from exc

        models = experiment_path / "models"
        reports = experiment_path / "reports"
        plots = experiment_path / "plots"
        manifests = experiment_path / "manifests"

        try:
            for p in (models, reports, plots, manifests):
                p.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            msg = f"Failed to create standard subdirectories under {experiment_path}: {exc}"
            self._logger.exception(msg)
            raise ExperimentError(msg) from exc

        return {
            "experiment": experiment_path,
            "models": models,
            "reports": reports,
            "plots": plots,
            "manifests": manifests,
        }


__all__ = ["ExperimentManager", "ExperimentInfo", "ExperimentError"]
