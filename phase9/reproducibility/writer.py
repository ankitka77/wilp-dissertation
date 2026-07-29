from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List, Optional
import hashlib
import json
import logging
import platform
import socket
import sys
import time
import locale
import subprocess

try:
    # Python 3.8+ importlib.metadata
    from importlib.metadata import distributions, distribution
except Exception:
    distributions = None

from phase9.utils.jsonyaml import dump_json, load_json


logger = logging.getLogger(__name__)


class ReproducibilityError(Exception):
    pass


class ReproducibilityWriter:
    """Capture execution and environment metadata sufficient for reproducing
    a Phase 9 run. Writes multiple snapshot JSON files under the output root.
    """

    def __init__(self, output_root: Path | str, version: str = "phase9-1.0"):
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.version = version

    def _sha256(self, p: Path) -> str:
        h = hashlib.sha256()
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _collect_file_checksums(self, paths: List[Path]) -> Dict[str, str]:
        checks = {}
        for p in paths:
            try:
                if p.exists():
                    checks[str(p.relative_to(self.output_root))] = self._sha256(p)
            except Exception:
                logger.exception("Failed to checksum %s", p)
        return checks

    def _git_info(self) -> Dict[str, Optional[str]]:
        info = {"commit": None, "branch": None, "tag": None}
        try:
            commit = subprocess.check_output(["git", "rev-parse", "--verify", "HEAD"], stderr=subprocess.DEVNULL).strip().decode()
            info["commit"] = commit
        except Exception:
            logger.debug("Git commit not available")
        try:
            branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL).strip().decode()
            info["branch"] = branch
        except Exception:
            logger.debug("Git branch not available")
        try:
            tag = subprocess.check_output(["git", "describe", "--tags", "--exact-match"], stderr=subprocess.DEVNULL).strip().decode()
            info["tag"] = tag
        except Exception:
            logger.debug("Git tag not available")
        return info

    def _installed_packages(self) -> List[Dict[str, str]]:
        pkgs = []
        if distributions is None:
            return pkgs
        try:
            for d in distributions():
                try:
                    pkgs.append({"name": d.metadata["Name"], "version": d.version})
                except Exception:
                    continue
        except Exception:
            logger.exception("Failed to enumerate installed distributions")
        return pkgs

    def write(self, start_ts: float, end_ts: float, config_path: Optional[Path] = None) -> Dict[str, Any]:
        """Write reproducibility manifests and snapshots.

        Returns a dict summarizing written files and top-level manifest.
        """
        logger.info("Writing reproducibility artifacts")
        try:
            duration = end_ts - start_ts
            generated_at = time.ctime(end_ts)

            # files to checksum (best-effort)
            candidates = [
                self.output_root / "canonical_manifest.json",
                self.output_root / "artifact_registry.json",
                self.output_root / "validation_report.json",
                self.output_root / "asset_catalog.json",
                self.output_root / "metadata_summary.json",
                self.output_root / "metrics_summary.json",
                self.output_root / "project_statistics.json",
                self.output_root / "reports" / "report.json",
                self.output_root / "package" / "package_manifest.json",
            ]

            checks = self._collect_file_checksums(candidates)

            # environment snapshot
            env = {
                "hostname": socket.gethostname(),
                "os": platform.system(),
                "platform": platform.platform(),
                "architecture": platform.machine(),
                "python_version": platform.python_version(),
                "python_build": platform.python_build(),
                "timezone": time.tzname,
                "locale": locale.getlocale(),
                "cwd": str(Path.cwd()),
                "virtual_env": sys.prefix if getattr(sys, "base_prefix", None) != getattr(sys, "prefix", None) else None,
            }

            # dependency snapshot (best-effort)
            deps = self._installed_packages()

            # git info
            git = self._git_info()

            # configuration snapshot: if config_path provided, include its contents and checksum
            config_snapshot = {}
            if config_path and config_path.exists():
                try:
                    cfg = load_json(config_path)
                    config_snapshot = {"path": str(config_path), "content": cfg, "checksum": self._sha256(config_path)}
                except Exception:
                    logger.exception("Failed to read config at %s", config_path)

            # write outputs
            reproducibility_manifest = {
                "generated_at": generated_at,
                "duration_seconds": duration,
                "phase9_version": self.version,
                "checksums": checks,
                "git": git,
            }

            dump_json(self.output_root / "reproducibility_manifest.json", reproducibility_manifest)
            dump_json(self.output_root / "environment_snapshot.json", env)
            dump_json(self.output_root / "dependency_snapshot.json", {"distributions": deps})
            dump_json(self.output_root / "execution_summary.json", {"start_ts": time.ctime(start_ts), "end_ts": time.ctime(end_ts), "duration_seconds": duration})
            dump_json(self.output_root / "configuration_snapshot.json", config_snapshot)

            logger.info("Reproducibility artifacts written to %s", self.output_root)
            return {
                "reproducibility_manifest": str(self.output_root / "reproducibility_manifest.json"),
                "environment_snapshot": str(self.output_root / "environment_snapshot.json"),
                "dependency_snapshot": str(self.output_root / "dependency_snapshot.json"),
                "execution_summary": str(self.output_root / "execution_summary.json"),
                "configuration_snapshot": str(self.output_root / "configuration_snapshot.json"),
            }

        except Exception as exc:
            logger.exception("Failed to write reproducibility artifacts: %s", exc)
            raise ReproducibilityError(str(exc))


__all__ = ["ReproducibilityWriter", "ReproducibilityError"]
