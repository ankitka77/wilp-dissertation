from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class ArtifactRecord(BaseModel):
    id: str
    phase: int
    type: str
    relative_path: str
    resolved_path: Optional[str] = None
    checksum: Optional[str] = None
    size_bytes: Optional[int] = None
    last_modified: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    validation: Optional[Dict[str, Any]] = None

    @field_validator("relative_path")
    def no_traversal(cls, v):
        if ".." in v.replace("\\", "/"):
            raise ValueError("relative_path must not contain '..'")
        return v


class PhaseManifest(BaseModel):
    manifest_version: str = Field("1.0")
    phase: int
    experiment_id: Optional[str] = None
    artifacts: List[ArtifactRecord] = Field(default_factory=list)
    generated_timestamp: Optional[str] = None
    generator: Optional[Dict[str, Any]] = None


class CanonicalManifest(BaseModel):
    produced_at: str
    source_phases: List[int]
    artifacts: List[ArtifactRecord]
    manifest_versions: Dict[int, str]

    def model_dump(self, *args, **kwargs):
        # Ensure artifacts are serialized as primitive dicts
        base = super().model_dump(*args, **kwargs)
        base["artifacts"] = [a.model_dump() for a in self.artifacts]
        return base


class ManifestRecord(BaseModel):
    path: str
    phase_manifest: PhaseManifest


__all__ = ["ArtifactRecord", "PhaseManifest", "CanonicalManifest", "ManifestRecord"]
