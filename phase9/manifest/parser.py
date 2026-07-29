from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
import yaml
from datetime import datetime, timezone
import logging

from pydantic import ValidationError
from .adapter import ManifestAdapter, ManifestAdapterError

from .models import PhaseManifest, ArtifactRecord, CanonicalManifest
from phase9.schemas.manifest_schema import validate_manifest_schema
from phase9.exceptions import ManifestError
from phase9.utils.jsonyaml import load_json, load_yaml, dump_json
from phase9.utils.timeutils import now_iso


logger = logging.getLogger(__name__)


class ManifestParser:
    """Parse and normalize upstream manifests into canonical models.

    Public methods:
    - parse(path: Path) -> PhaseManifest
    - merge(manifests: List[PhaseManifest]) -> CanonicalManifest
    """

    def parse(self, path: Path) -> PhaseManifest:
        p = Path(path)
        if not p.exists():
            raise ManifestError(message="manifest file not found", context={"path": str(p)})

        try:
            if p.suffix.lower() in [".json"]:
                raw = load_json(p)
            else:
                raw = load_yaml(p)
                # Normalize any YAML-loaded datetime objects to ISO-8601 strings
                def _normalize_dates(obj):
                    if isinstance(obj, dict):
                        for k, v in list(obj.items()):
                            obj[k] = _normalize_dates(v)
                        return obj
                    if isinstance(obj, list):
                        return [_normalize_dates(x) for x in obj]
                    if isinstance(obj, datetime):
                        # ensure UTC-aware ISO format
                        if obj.tzinfo is None:
                            obj = obj.replace(tzinfo=timezone.utc)
                        return obj.isoformat()
                    return obj

                raw = _normalize_dates(raw)
        except Exception as e:
            logger.exception("Failed to load manifest %s", p)
            raise ManifestError(message="invalid manifest format", context={"path": str(p), "error": str(e)})

        # If this manifest is a pointer (contains manifest_path), resolve target
        try:
            if isinstance(raw, dict) and "manifest_path" in raw and not (isinstance(raw.get("artifacts"), list) and raw.get("phase") is not None):
                target = raw.get("manifest_path")
                # Resolve relative paths against the pointer file
                target_path = Path(target)
                if not target_path.is_absolute():
                    target_path = p.parent / target_path

                if not target_path.exists():
                    raise ManifestError(message="manifest pointer target not found", context={"pointer": str(p), "target": str(target_path)})

                # load the referenced manifest
                try:
                    if target_path.suffix.lower() == ".json":
                        raw = load_json(target_path)
                    else:
                        raw = load_yaml(target_path)
                except Exception as e:
                    logger.exception("Failed to load referenced manifest %s", target_path)
                    raise ManifestError(message="failed to load referenced manifest", context={"target": str(target_path), "error": str(e)})

        except ManifestError:
            raise
        except Exception:
            # Non-pointer processing continues
            pass

        # If raw may be a legacy format, attempt canonicalization before schema validation
        try:
            try:
                raw_canonical = ManifestAdapter.canonicalize(raw, source_path=p)
            except ManifestAdapterError:
                # If adapter cannot canonicalize, fall back to raw
                raw_canonical = raw

            # validate minimal schema
            validate_manifest_schema(raw_canonical)
            raw = raw_canonical
        except Exception as e:
            logger.error("Manifest schema validation failed for %s: %s", p, e)
            raise ManifestError(message="manifest schema validation failed", context={"path": str(p), "error": str(e)})

        # normalize fields and construct PhaseManifest
        try:
            # ensure artifact entries contain required normalized fields
            artifacts = []
            for a in raw.get("artifacts", []):
                ar = ArtifactRecord(
                    id=a.get("id"),
                    phase=raw.get("phase"),
                    type=a.get("type"),
                    relative_path=a.get("relative_path"),
                    checksum=a.get("checksum"),
                    metadata=a.get("metadata"),
                )
                artifacts.append(ar)

            pm = PhaseManifest(
                manifest_version=str(raw.get("manifest_version", "1.0")),
                phase=int(raw.get("phase")),
                experiment_id=raw.get("experiment_id"),
                artifacts=artifacts,
                generated_timestamp=raw.get("generated_timestamp"),
                generator=raw.get("generator"),
            )
        except ValidationError as e:
            logger.exception("Manifest content validation failed for %s", p)
            raise ManifestError(message="manifest content invalid", context={"path": str(p), "error": e.errors()})

        logger.info("Parsed manifest %s (phase %s)", p, pm.phase)
        return pm

    def merge(self, manifests: list[PhaseManifest], output_path: Path) -> CanonicalManifest:
        """Merge multiple PhaseManifest objects into a CanonicalManifest and write to output_path."""
        artifacts = []
        manifest_versions: Dict[int, str] = {}
        phases = []
        for m in manifests:
            phases.append(m.phase)
            manifest_versions[m.phase] = m.manifest_version
            for a in m.artifacts:
                artifacts.append(a)

        canonical = CanonicalManifest(produced_at=now_iso(), source_phases=phases, artifacts=artifacts, manifest_versions=manifest_versions)
        # persist canonical manifest
        dump_json(output_path, canonical.model_dump())
        logger.info("Wrote canonical manifest to %s", output_path)
        return canonical


