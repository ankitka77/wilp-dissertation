from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ArtifactMetadata(BaseModel):
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


class PhaseSummary(BaseModel):
    phase: int
    artifact_count: int = 0
    types: Dict[str, int] = Field(default_factory=dict)
    experiments: List[str] = Field(default_factory=list)


class ProjectMetadata(BaseModel):
    produced_at: str
    artifact_count: int
    artifacts: List[ArtifactMetadata]
    phases: List[PhaseSummary]
    lineage: Dict[str, List[str]] = Field(default_factory=dict)
    dependencies: Dict[str, List[str]] = Field(default_factory=dict)
    completeness: Dict[str, Any] = Field(default_factory=dict)


__all__ = ["ArtifactMetadata", "PhaseSummary", "ProjectMetadata"]
