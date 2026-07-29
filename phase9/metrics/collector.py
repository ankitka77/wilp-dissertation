from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List
import logging
import statistics
import time

from phase9.artifact.registry import ArtifactRegistry
from phase9.utils.jsonyaml import dump_json


logger = logging.getLogger(__name__)


class MetricsCollectionError(Exception):
    pass


class MetricsCollector:
    """Collect project-wide metrics and statistics from an ArtifactRegistry.

    Produces `project_statistics.json` and `metrics_summary.json` under the
    configured output directory.
    """

    def __init__(self, registry: ArtifactRegistry, output_root: Path | str):
        self.registry = registry
        self.output_root = Path(output_root)

    def _safe_stat(self, values: List[int]) -> Dict[str, Any]:
        if not values:
            return {"count": 0, "min": None, "max": None, "mean": None, "median": None}
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
        }

    def collect(self) -> Dict[str, Any]:
        logger.info("Starting metrics collection")
        try:
            artifacts = self.registry.artifacts

            # basic counts
            total = len(artifacts)
            per_phase = {}
            per_type = {}
            validated = 0
            warnings = 0
            errors = 0

            sizes = []
            ages = []

            for a in artifacts:
                per_phase[a.phase] = per_phase.get(a.phase, 0) + 1
                per_type[a.type] = per_type.get(a.type, 0) + 1
                if a.validation and isinstance(a.validation, dict):
                    status = a.validation.get("status")
                    if status == "ok":
                        validated += 1
                    elif status == "warning":
                        warnings += 1
                    elif status == "error":
                        errors += 1
                if a.size_bytes:
                    sizes.append(a.size_bytes)
                # last_modified parsed as timestamp string; best-effort compute age is skipped if absent
                # If last_modified is ISO8601 we could compute, but keep simple here

            size_stats = self._safe_stat(sizes)

            # dependency statistics
            dep_counts = [len(self.registry.lookup_by_metadata_key("dependencies", d)) for d in range(0)]
            # fallback: compute dependency out-degree per artifact from metadata
            dep_out = {}
            for a in artifacts:
                deps = (a.metadata or {}).get("dependencies") or []
                dep_out[a.id] = len(deps)

            metrics = {
                "collected_at": time.ctime(),
                "total_artifacts": total,
                "per_phase": per_phase,
                "per_type": per_type,
                "validation": {"validated": validated, "warnings": warnings, "errors": errors},
                "size_statistics": size_stats,
                "dependency_out_degree": dep_out,
            }

            # project statistics (more human focused)
            stats = {
                "generated_at": time.ctime(),
                "artifact_count": total,
                "phase_counts": per_phase,
                "type_counts": per_type,
            }

            self.output_root.mkdir(parents=True, exist_ok=True)
            dump_json(self.output_root / "metrics_summary.json", metrics)
            dump_json(self.output_root / "project_statistics.json", stats)
            logger.info("Wrote metrics_summary.json and project_statistics.json to %s", self.output_root)

            return {"metrics": metrics, "statistics": stats}

        except Exception as exc:
            logger.exception("Metrics collection failed: %s", exc)
            raise MetricsCollectionError(str(exc))


__all__ = ["MetricsCollector", "MetricsCollectionError"]
