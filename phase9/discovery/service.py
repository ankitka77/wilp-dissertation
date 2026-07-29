from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timezone

from phase9.config.loader import load_config
from phase9.utils.jsonyaml import dump_json
from phase9.utils.fs import ensure_dir
from phase9.exceptions import ManifestError, FileSystemError, RecoverableError
from phase9.manifest import ManifestParser, models as manifest_models


logger = logging.getLogger(__name__)


class DiscoveryService:
    """Discover artifacts for configured phases and produce discovery_index.json.

    Usage:
        svc = DiscoveryService(config)
        svc.discover()
    """

    def __init__(self, config=None):
        self.config = config or load_config()
        self.artifacts_root = Path(self.config.output.artifacts_root)
        self.discovery_index: Dict[str, Any] = {"phases": [], "discovered_at": datetime.now(timezone.utc).isoformat()}

    def _phase_path(self, phase: int) -> Path:
        return Path(f"artifacts/phase{phase}/latest")

    def discover_phase(self, phase: int) -> Dict[str, Any]:
        phase_entry: Dict[str, Any] = {"phase": phase, "discovered_at": datetime.now(timezone.utc).isoformat(), "manifest_found": False, "manifest_path": None, "manifest_version": None, "artifact_count": 0, "artifact_ids": [], "validation": None, "paths": []}
        p = self._phase_path(phase)
        phase_entry["scanned_path"] = str(p)
        if not p.exists() or not p.is_dir():
            msg = f"Phase directory missing: {p}"
            logger.warning(msg)
            phase_entry["error"] = msg
            return phase_entry

        # look for manifest files (json or yaml)
        manifest_json = p / "manifest.json"
        manifest_yaml = p / "manifest.yaml"
        manifest_path: Optional[Path] = None
        if manifest_json.exists():
            manifest_path = manifest_json
        elif manifest_yaml.exists():
            manifest_path = manifest_yaml

        if manifest_path:
            phase_entry["manifest_found"] = True
            phase_entry["manifest_path"] = str(manifest_path)
            try:
                parser = ManifestParser()
                pm = parser.parse(manifest_path)
                phase_entry["manifest_version"] = pm.manifest_version
                phase_entry["artifact_count"] = len(pm.artifacts)
                phase_entry["artifact_ids"] = [a.id for a in pm.artifacts]
                phase_entry["paths"] = [a.relative_path for a in pm.artifacts]
            except ManifestError as e:
                logger.error("Manifest parsing failed: %s", e)
                phase_entry["manifest_error"] = str(e)
                # mark as recoverable and continue
            except Exception as e:  # pragma: no cover - defensive
                logger.exception("Unexpected error parsing manifest for phase %s", phase)
                phase_entry["manifest_error"] = str(e)
        else:
            # filesystem fallback - list files
            logger.info("No manifest for phase %s; performing filesystem discovery", phase)
            files = []
            try:
                for root, _, filenames in os.walk(p):
                    for fn in filenames:
                        fp = Path(root) / fn
                        rel = fp.relative_to(p)
                        files.append(str(rel))
                        phase_entry["artifact_ids"].append(fn)
                        phase_entry["paths"].append(str(rel))
                phase_entry["artifact_count"] = len(files)
            except OSError as e:
                logger.exception("Filesystem error while discovering phase %s: %s", phase, e)
                phase_entry["error"] = str(e)

        return phase_entry

    def discover(self, phases: Optional[List[int]] = None, output_dir: Optional[Path] = None) -> Dict[str, Any]:
        phases = phases or list(self.config.discovery.phases)
        out = Path(output_dir or self.artifacts_root)
        ensure_dir(out)

        for phase in phases:
            logger.info("Discovering phase %s", phase)
            try:
                entry = self.discover_phase(phase)
                self.discovery_index["phases"].append(entry)
            except RecoverableError as e:
                logger.warning("Recoverable error discovering phase %s: %s", phase, e)
            except Exception as e:
                logger.exception("Fatal error during discovery of phase %s: %s", phase, e)
                raise

        # write discovery index
        discovery_path = out / "discovery_index.json"
        dump_json(discovery_path, self.discovery_index)
        logger.info("Wrote discovery index to %s", discovery_path)
        return self.discovery_index
