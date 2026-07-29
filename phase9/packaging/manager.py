from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List
import hashlib
import logging
import time

from phase9.utils.jsonyaml import dump_json


logger = logging.getLogger(__name__)


class PackagingError(Exception):
    pass


class PackagingManager:
    """Collect Phase 9 outputs into a reproducible package directory structure
    and write `package_manifest.json` and `package_summary.json`.
    """

    def __init__(self, output_root: Path | str, package_version: str = "1.0"):
        self.output_root = Path(output_root)
        self.package_root = self.output_root / "package"
        self.package_root.mkdir(parents=True, exist_ok=True)
        self.package_version = package_version

    def _sha256(self, p: Path) -> str:
        h = hashlib.sha256()
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def package(self) -> Dict[str, Any]:
        logger.info("Starting packaging collection")
        try:
            files = []
            for p in sorted(self.output_root.rglob("*")):
                if p.is_file():
                    # skip files that are inside the package output directory to avoid recursive inclusion
                    if self.package_root == p or self.package_root in p.parents:
                        continue
                    rel = p.relative_to(self.output_root)
                    dest = self.package_root / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    # copy file content to package folder (preserve as-is)
                    data = p.read_bytes()
                    dest.write_bytes(data)
                    checksum = self._sha256(dest)
                    files.append({"path": str(rel), "size": dest.stat().st_size, "sha256": checksum})

            manifest = {
                "generated_at": time.ctime(),
                "package_version": self.package_version,
                "generator_version": "phase9-1.0",
                "files": files,
            }
            dump_json(self.package_root / "package_manifest.json", manifest)
            summary = {"generated_at": time.ctime(), "file_count": len(files)}
            dump_json(self.package_root / "package_summary.json", summary)

            logger.info("Packaging complete: %d files collected", len(files))
            return manifest

        except Exception as exc:
            logger.exception("Packaging failed: %s", exc)
            raise PackagingError(str(exc))


__all__ = ["PackagingManager", "PackagingError"]
