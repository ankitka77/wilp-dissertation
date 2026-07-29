from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass
class Phase9Error(Exception):
    message: str
    context: Dict[str, Any]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"Phase9Error: {self.message}"

    def to_dict(self) -> Dict[str, Any]:
        return {"message": self.message, "context": self.context}


class ConfigError(Phase9Error):
    pass


class FileSystemError(Phase9Error):
    pass


class ValidationError(Phase9Error):
    pass


class ManifestError(Phase9Error):
    pass


class ArtifactError(Phase9Error):
    pass


class PackagingError(Phase9Error):
    pass


class ReportGenerationError(Phase9Error):
    pass


class RecoverableError(Phase9Error):
    """Errors that allow the pipeline to continue with warnings."""


class FatalError(Phase9Error):
    """Errors that should abort the pipeline."""


__all__ = [
    "Phase9Error",
    "ConfigError",
    "FileSystemError",
    "ValidationError",
    "ManifestError",
    "ArtifactError",
    "PackagingError",
    "ReportGenerationError",
    "RecoverableError",
    "FatalError",
]
