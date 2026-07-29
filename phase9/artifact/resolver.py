from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Tuple
import logging
import os

from phase9.manifest.models import CanonicalManifest, ArtifactRecord
from phase9.exceptions import ArtifactError


logger = logging.getLogger(__name__)


class ArtifactResolver:
    """Resolve artifact file locations referenced in a CanonicalManifest.

    Rules:
    - For relative paths, resolve against artifacts/phase{n}/latest/ .
    - For absolute paths, verify existence but do not traverse outside published locations unless explicitly referenced.
    - Populate `resolved_path`, `size_bytes`, and `last_modified` on `ArtifactRecord` when found.
    - Collect duplicates and missing files in the resolver report.
    """

    def __init__(self, repo_root: Path | None = None):
        self.repo_root = Path(repo_root) if repo_root else Path.cwd()

    def _phase_root(self, phase: int) -> Path:
        return self.repo_root / Path(f"artifacts/phase{phase}/latest")

    def resolve(self, canonical: CanonicalManifest) -> Tuple[List[ArtifactRecord], Dict[str, List[str]]]:
        resolved: List[ArtifactRecord] = []
        id_map: Dict[str, List[str]] = {}
        missing: List[str] = []

        for a in canonical.artifacts:
            try:
                rp = None
                p = Path(a.relative_path)
                if p.is_absolute():
                    candidate = p
                else:
                    candidate = self._phase_root(a.phase) / p

                # resolve symbolic links where possible but do not require strict existence for path normalization
                try:
                    resolved_path = candidate.resolve()
                except Exception:
                    resolved_path = candidate

                if resolved_path.exists() and resolved_path.is_file():
                    a.resolved_path = str(resolved_path)
                    a.size_bytes = resolved_path.stat().st_size
                    a.last_modified = resolved_path.stat().st_mtime_ns.__str__()
                else:
                    a.resolved_path = None
                    missing.append(a.id)

                # track duplicates by id
                id_map.setdefault(a.id, []).append(str(resolved_path))
                resolved.append(a)
            except Exception as e:
                logger.exception("Failed to resolve artifact %s: %s", a.id, e)
                raise ArtifactError(message="resolver failure", context={"artifact_id": a.id, "error": str(e)})

        # identify duplicate artifact references (same id -> multiple resolved paths)
        duplicates = {k: v for k, v in id_map.items() if len([x for x in v if x and Path(x).exists()]) > 1}

        report = {"missing": missing, "duplicates": duplicates}
        return resolved, report


__all__ = ["ArtifactResolver"]
