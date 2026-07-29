from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any
import logging
import time

from phase9.manifest.models import ArtifactRecord
from phase9.artifact.registry import ArtifactRegistry
from phase9.utils.jsonyaml import dump_json
from .models import ProjectMetadata, PhaseSummary, ArtifactMetadata


logger = logging.getLogger(__name__)


class MetadataAggregationError(Exception):
    pass


class MetadataAggregator:
    """Aggregate metadata from the authoritative ArtifactRegistry into a
    canonical project-level metadata summary used by downstream generators.

    The aggregator consumes the in-memory `ArtifactRegistry` produced by the
    validation stage and writes `metadata_summary.json` to the configured
    output directory.
    """

    def __init__(self, registry: ArtifactRegistry, output_root: Path | str):
        self.registry = registry
        self.output_root = Path(output_root)

    def _artifact_to_meta(self, a: ArtifactRecord) -> ArtifactMetadata:
        return ArtifactMetadata(
            id=a.id,
            phase=a.phase,
            type=a.type,
            relative_path=a.relative_path,
            resolved_path=a.resolved_path,
            checksum=a.checksum,
            size_bytes=a.size_bytes,
            last_modified=a.last_modified,
            metadata=a.metadata or {},
            validation=a.validation or {},
        )

    def aggregate(self) -> ProjectMetadata:
        """Perform aggregation and write metadata_summary.json.

        Returns the ProjectMetadata model for further programmatic use.
        """
        logger.info("Starting metadata aggregation")
        try:
            artifacts = [self._artifact_to_meta(a) for a in self.registry.artifacts]

            # phase summaries
            phases: Dict[int, PhaseSummary] = {}
            for a in artifacts:
                ps = phases.setdefault(a.phase, PhaseSummary(phase=a.phase))
                ps.artifact_count += 1
                ps.types[a.type] = ps.types.get(a.type, 0) + 1
                exp_id = (a.metadata or {}).get("experiment_id")
                if exp_id and exp_id not in ps.experiments:
                    ps.experiments.append(exp_id)

            # lineage & dependencies heuristics
            lineage: Dict[str, List[str]] = {}
            dependencies: Dict[str, List[str]] = {}
            for a in artifacts:
                aid = a.id
                # producer-provided lineage
                md = a.metadata or {}
                parents = md.get("parents") or md.get("derived_from") or []
                if isinstance(parents, list) and parents:
                    lineage[aid] = parents
                # dependency relationships from metadata
                deps = md.get("dependencies") or []
                if isinstance(deps, list) and deps:
                    dependencies[aid] = deps

            # completeness: basic coverage metrics
            completeness = {
                "artifacts_with_metadata": sum(1 for a in artifacts if a.metadata),
                "artifacts_with_checksum": sum(1 for a in artifacts if a.checksum),
                "total_artifacts": len(artifacts),
            }

            project_meta = ProjectMetadata(
                produced_at=time.ctime(),
                artifact_count=len(artifacts),
                artifacts=artifacts,
                phases=[ph for ph in sorted(phases.values(), key=lambda x: x.phase)],
                lineage=lineage,
                dependencies=dependencies,
                completeness=completeness,
            )

            self.output_root.mkdir(parents=True, exist_ok=True)
            dump_json(self.output_root / "metadata_summary.json", project_meta.model_dump())
            logger.info("Wrote metadata_summary.json to %s", self.output_root)
            return project_meta

        except Exception as exc:
            logger.exception("Metadata aggregation failed: %s", exc)
            raise MetadataAggregationError(str(exc))


__all__ = ["MetadataAggregator", "MetadataAggregationError"]
