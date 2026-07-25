"""Artifact Store for Phase 8.

Provides a small, well-specified API for atomic artifact writes, reads,
checksums and listings used by Experiment Manager and other Phase8 modules.

This module is intentionally lightweight and filesystem-backed. It is
designed for easy unit testing and for later extension (S3/GCS adapters).
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional
import json
import logging
import os
import tempfile

logger = logging.getLogger("phase8.core.artifact_store")


class ArtifactStoreError(RuntimeError):
    """Base error for artifact store failures."""


@dataclass(frozen=True)
class ArtifactEntry:
    path: str
    size: int
    sha256: str


class ArtifactStore:
    """Filesystem-backed artifact store.

    Usage:
        store = ArtifactStore(root_dir=Path("./experiments"))
        entry = store.write_artifact("run-1", "predictions/kpi.csv", b"data...")
        data = store.read_artifact("run-1", "predictions/kpi.csv")
    """

    def __init__(self, root_dir: Path) -> None:
        if not isinstance(root_dir, Path):
            root_dir = Path(root_dir)
        self._root = root_dir
        self._root.mkdir(parents=True, exist_ok=True)

    # Paths --------------------------------------------------------------
    def _run_dir(self, run_id: str) -> Path:
        return self._root / run_id

    def _artifact_path(self, run_id: str, relative: str) -> Path:
        return self._run_dir(run_id) / relative

    # Core API ----------------------------------------------------------
    def write_artifact(self, run_id: str, relative_path: str, data: bytes) -> ArtifactEntry:
        """Atomically write `data` to `run_id`/`relative_path` and return an ArtifactEntry.

        The method writes to a temporary file in the destination directory and
        renames it into place to ensure atomicity.
        """
        run_dir = self._run_dir(run_id)
        dest = self._artifact_path(run_id, relative_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        # write to temp file then move
        fd, tmp = tempfile.mkstemp(dir=str(dest.parent))
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            # compute checksum and size
            sha = self._compute_sha256(Path(tmp))
            size = Path(tmp).stat().st_size
            # atomic move
            os.replace(tmp, dest)
            logger.info("Wrote artifact %s for run %s (size=%d sha256=%s)", relative_path, run_id, size, sha)
            return ArtifactEntry(path=str(dest.relative_to(self._root).as_posix()), size=size, sha256=sha)
        except Exception as exc:  # pragma: no cover - robust error path
            # attempt cleanup
            try:
                os.remove(tmp)
            except Exception:
                pass
            logger.exception("Failed to write artifact %s for run %s", relative_path, run_id)
            raise ArtifactStoreError("Failed to write artifact") from exc

    def read_artifact(self, run_id: str, relative_path: str) -> bytes:
        """Read an artifact as bytes.

        Raises ArtifactStoreError if the file is missing or unreadable.
        """
        path = self._artifact_path(run_id, relative_path)
        try:
            with path.open("rb") as fh:
                return fh.read()
        except Exception as exc:
            logger.exception("Failed to read artifact %s for run %s", relative_path, run_id)
            raise ArtifactStoreError("Failed to read artifact") from exc

    def list_artifacts(self, run_id: str) -> List[ArtifactEntry]:
        """List artifacts for a run, returning metadata entries.

        The returned paths are relative to the root artifacts directory.
        """
        run_dir = self._run_dir(run_id)
        if not run_dir.exists():
            return []
        entries: List[ArtifactEntry] = []
        for p in run_dir.rglob("*"):
            if p.is_file():
                rel = str(p.relative_to(self._root).as_posix())
                sha = self._compute_sha256(p)
                size = p.stat().st_size
                entries.append(ArtifactEntry(path=rel, size=size, sha256=sha))
        return entries

    def _compute_sha256(self, path: Path) -> str:
        h = sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def write_json(self, run_id: str, relative_path: str, obj: Mapping) -> ArtifactEntry:
        data = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return self.write_artifact(run_id, relative_path, data)

    def read_json(self, run_id: str, relative_path: str) -> Mapping:
        data = self.read_artifact(run_id, relative_path)
        return json.loads(data.decode("utf-8"))
