"""Experiment Manager for Phase 8.

Manages experiment lifecycle: create, list, metadata, checkpointing.
Backed by filesystem layout and reuses the `ArtifactStore` for artifact handling.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional
import json
import logging

from .artifact_store import ArtifactStore, ArtifactEntry, ArtifactStoreError

logger = logging.getLogger("phase8.core.experiment_manager")


class ExperimentExistsError(RuntimeError):
    pass


class ExperimentNotFoundError(RuntimeError):
    pass


@dataclass
class ExperimentMetadata:
    experiment_id: str
    description: Optional[str]
    created_at: str
    tags: Mapping[str, str]


class ExperimentManager:
    """Manages experiments and their metadata.

    The manager stores a small `metadata.json` for each experiment and
    delegates artifact operations to an `ArtifactStore`.
    """

    def __init__(self, artifact_store: ArtifactStore) -> None:
        self._store = artifact_store

    def create_experiment(self, experiment_id: str, description: Optional[str] = None, tags: Optional[Mapping[str, str]] = None) -> ExperimentMetadata:
        """Create a new experiment with metadata.

        Raises ExperimentExistsError if the experiment already exists.
        """
        tags = tags or {}
        # check if exists
        entries = self._store.list_artifacts(experiment_id)
        if entries:
            logger.error("Experiment %s already exists", experiment_id)
            raise ExperimentExistsError(experiment_id)
        meta = ExperimentMetadata(
            experiment_id=experiment_id,
            description=description,
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            tags=dict(tags),
        )
        # persist metadata
        try:
            self._store.write_json(experiment_id, "metadata.json", asdict(meta))
        except ArtifactStoreError as exc:
            logger.exception("Failed to persist metadata for %s", experiment_id)
            raise
        logger.info("Created experiment %s", experiment_id)
        return meta

    def get_metadata(self, experiment_id: str) -> ExperimentMetadata:
        try:
            data = self._store.read_json(experiment_id, "metadata.json")
            return ExperimentMetadata(**data)
        except ArtifactStoreError:
            logger.exception("Experiment %s not found", experiment_id)
            raise ExperimentNotFoundError(experiment_id)

    def list_experiments(self) -> List[ExperimentMetadata]:
        experiments: List[ExperimentMetadata] = []
        # assume each directory under root is an experiment id
        root = self._store._root
        for p in root.iterdir():
            if p.is_dir():
                try:
                    md = self.get_metadata(p.name)
                    experiments.append(md)
                except ExperimentNotFoundError:
                    # skip directories without metadata
                    continue
        return experiments
