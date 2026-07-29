from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


class ManifestAdapterError(Exception):
    pass


class ManifestAdapter:
    """Convert known legacy manifest shapes into the Phase 9 canonical manifest dict.

    The adapter attempts lossless normalization where possible and preserves
    unknown fields under `metadata` or `generator` sections.

    """

    @staticmethod
    def canonicalize(raw: Any, source_path: Path | None = None) -> Dict[str, Any]:
        # If it's already in canonical shape (has phase and artifacts list), pass through
        if isinstance(raw, dict) and isinstance(raw.get("artifacts"), list) and raw.get("phase") is not None:
            return raw

        if not isinstance(raw, dict):
            raise ManifestAdapterError("Unsupported manifest structure: expected mapping")

        out: Dict[str, Any] = {}

        # manifest_version passthrough
        if "manifest_version" in raw:
            out["manifest_version"] = raw["manifest_version"]

        # generated_timestamp normalization
        if "generated_timestamp" in raw:
            out["generated_timestamp"] = raw["generated_timestamp"]
        elif "generated_on" in raw:
            out["generated_timestamp"] = raw["generated_on"]

        # phase normalization: accept int or strings like 'phase6' or '6'
        phase = raw.get("phase") or raw.get("phase_id") or raw.get("phase_label")
        if phase is not None:
            try:
                if isinstance(phase, str) and phase.lower().startswith("phase"):
                    phase_num = int("".join(ch for ch in phase if ch.isdigit()))
                else:
                    phase_num = int(phase)
                out["phase"] = phase_num
            except Exception:
                raise ManifestAdapterError("Unable to normalize 'phase' field to integer")

        # experiment id passthrough
        if "experiment_id" in raw:
            out["experiment_id"] = raw["experiment_id"]

        # artifacts normalization: if dict -> list
        artifacts_raw = raw.get("artifacts")
        artifacts: List[Dict[str, Any]] = []

        if artifacts_raw is None:
            # some legacy manifests embed assets under other keys like 'files' or 'outputs'
            for alt in ("files", "outputs", "assets"):
                if alt in raw and isinstance(raw[alt], (list, dict)):
                    artifacts_raw = raw[alt]
                    break

        if isinstance(artifacts_raw, dict):
            # convert mapping to list; each key may be filename or id
            for key, val in artifacts_raw.items():
                art: Dict[str, Any] = {}
                # id inference: prefer explicit id, else use key
                if isinstance(val, dict) and "id" in val:
                    art_id = val["id"]
                else:
                    art_id = str(key)
                art["id"] = art_id

                # relative_path handling
                if isinstance(val, str):
                    art["relative_path"] = val
                elif isinstance(val, dict):
                    # prefer explicit relative_path/path/location keys
                    for path_key in ("relative_path", "path", "location", "file"):
                        if path_key in val:
                            art["relative_path"] = val[path_key]
                            break
                    # type and metadata
                    if "type" in val:
                        art["type"] = val["type"]
                    # everything else goes into metadata
                    meta = {k: v for k, v in val.items() if k not in ("id", "relative_path", "path", "location", "file", "type")}
                    if meta:
                        art["metadata"] = meta
                else:
                    # unknown value shape -> store as metadata
                    art["relative_path"] = str(key)
                    art["metadata"] = {"value": val}

                # ensure required keys
                art.setdefault("type", "unknown")
                art.setdefault("relative_path", "")
                artifacts.append(art)

        elif isinstance(artifacts_raw, list):
            # assume list of canonical-like entries; copy through but ensure keys
            for entry in artifacts_raw:
                if not isinstance(entry, dict):
                    raise ManifestAdapterError("Unsupported artifact entry type in list")
                art = dict(entry)
                # ensure id exists
                if "id" not in art:
                    # try to infer from relative_path
                    rp = art.get("relative_path") or art.get("path")
                    if rp:
                        art["id"] = Path(str(rp)).name
                    else:
                        raise ManifestAdapterError("Artifact missing 'id' and no relative path to infer id")
                artifacts.append(art)

        else:
            artifacts = []

        out["artifacts"] = artifacts

        # preserve other top-level fields into generator if present
        generator = {}
        for k, v in raw.items():
            if k in ("manifest_version", "generated_timestamp", "generated_on", "phase", "phase_id", "phase_label", "experiment_id", "artifacts", "files", "outputs", "assets"):
                continue
            generator[k] = v
        if generator:
            out["generator"] = generator

        # basic validation: phase required
        if "phase" not in out:
            raise ManifestAdapterError("Converted manifest missing required 'phase'")

        return out


__all__ = ["ManifestAdapter", "ManifestAdapterError"]
