"""Dataset Manager for Phase 8.

Provides dataset registration, retrieval of dataset metadata and simple
ingest helpers. The manager stores dataset manifests via the `ArtifactStore`.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional
import json
import logging

from .artifact_store import ArtifactStore, ArtifactEntry, ArtifactStoreError

logger = logging.getLogger("phase8.core.dataset_manager")


class DatasetExistsError(RuntimeError):
    pass


class DatasetNotFoundError(RuntimeError):
    pass


@dataclass
class DatasetManifest:
    dataset_id: str
    description: Optional[str]
    created_at: str
    source: Mapping[str, str]


class DatasetManager:
    """Manage dataset manifests and small ingestion helpers.

    This is intentionally small: actual ingestion pipelines live elsewhere.
    """

    def __init__(self, artifact_store: ArtifactStore) -> None:
        self._store = artifact_store

    def register_dataset(self, dataset_id: str, description: Optional[str], source: Mapping[str, str]) -> DatasetManifest:
        entries = self._store.list_artifacts(dataset_id)
        if entries:
            logger.error("Dataset %s already exists", dataset_id)
            raise DatasetExistsError(dataset_id)
        manifest = DatasetManifest(
            dataset_id=dataset_id,
            description=description,
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            source=dict(source),
        )
        self._store.write_json(dataset_id, "manifest.json", asdict(manifest))
        logger.info("Registered dataset %s", dataset_id)
        return manifest

    def get_manifest(self, dataset_id: str) -> DatasetManifest:
        try:
            data = self._store.read_json(dataset_id, "manifest.json")
            return DatasetManifest(**data)
        except ArtifactStoreError:
            logger.exception("Dataset %s not found", dataset_id)
            raise DatasetNotFoundError(dataset_id)

    def list_datasets(self) -> List[DatasetManifest]:
        root = self._store._root
        results: List[DatasetManifest] = []
        for p in root.iterdir():
            if p.is_dir():
                try:
                    results.append(self.get_manifest(p.name))
                except DatasetNotFoundError:
                    continue
        return results
