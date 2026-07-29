from __future__ import annotations

from typing import List, Dict, Any, Optional
from pathlib import Path
from collections import defaultdict, Counter
import logging

from phase9.manifest.models import ArtifactRecord
from phase9.utils.jsonyaml import dump_json


logger = logging.getLogger(__name__)


class ArtifactRegistry:
    """In-memory registry of artifacts with lookup APIs and persistence helpers."""

    def __init__(self, artifacts: List[ArtifactRecord], output_root: Path | str):
        self.artifacts = list(artifacts)
        self.output_root = Path(output_root)
        self.by_id: Dict[str, ArtifactRecord] = {}
        self.by_phase: Dict[int, List[ArtifactRecord]] = defaultdict(list)
        self.by_type: Dict[str, List[ArtifactRecord]] = defaultdict(list)
        self.by_filename: Dict[str, List[ArtifactRecord]] = defaultdict(list)
        self._build_indexes()

    def _build_indexes(self) -> None:
        for a in self.artifacts:
            self.by_id[a.id] = a
            self.by_phase[a.phase].append(a)
            self.by_type[a.type].append(a)
            fname = Path(a.relative_path).name
            self.by_filename[fname].append(a)

    # Lookup APIs
    def lookup_by_phase(self, phase: int) -> List[ArtifactRecord]:
        return list(self.by_phase.get(phase, []))

    def lookup_by_id(self, artifact_id: str) -> Optional[ArtifactRecord]:
        return self.by_id.get(artifact_id)

    def lookup_by_type(self, atype: str) -> List[ArtifactRecord]:
        return list(self.by_type.get(atype, []))

    def lookup_by_filename(self, filename: str) -> List[ArtifactRecord]:
        return list(self.by_filename.get(filename, []))

    def lookup_by_tag(self, tag: str) -> List[ArtifactRecord]:
        res = []
        for a in self.artifacts:
            if a.metadata and isinstance(a.metadata, dict) and tag in a.metadata.get("tags", []):
                res.append(a)
        return res

    def lookup_by_metadata_key(self, key: str, value: Any) -> List[ArtifactRecord]:
        res = []
        for a in self.artifacts:
            if a.metadata and isinstance(a.metadata, dict) and a.metadata.get(key) == value:
                res.append(a)
        return res

    def lookup_by_producer(self, producer: str) -> List[ArtifactRecord]:
        return self.lookup_by_metadata_key("producer", producer)

    def lookup_by_experiment_id(self, experiment_id: str) -> List[ArtifactRecord]:
        return [a for a in self.artifacts if a.metadata and a.metadata.get("experiment_id") == experiment_id]

    # Persistence
    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": __import__("time").ctime(),
            "artifact_count": len(self.artifacts),
            "artifacts": [a.model_dump() for a in self.artifacts],
        }

    def statistics(self) -> Dict[str, Any]:
        phases = Counter(a.phase for a in self.artifacts)
        types = Counter(a.type for a in self.artifacts)
        return {
            "artifact_count": len(self.artifacts),
            "phase_counts": dict(phases),
            "type_counts": dict(types),
        }

    def persist(self) -> None:
        self.output_root.mkdir(parents=True, exist_ok=True)
        dump_json(self.output_root / "artifact_registry.json", self.to_dict())
        dump_json(self.output_root / "registry_statistics.json", self.statistics())
        logger.info("Persisted artifact registry and statistics to %s", self.output_root)


__all__ = ["ArtifactRegistry"]
