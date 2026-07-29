from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
import logging
import time

from phase9.config.loader import load_config
from phase9.logging.logger import configure_logging, get_logger
from phase9.discovery.service import DiscoveryService
from phase9.manifest.parser import ManifestParser
from phase9.artifact.resolver import ArtifactResolver
from phase9.artifact.validator import ArtifactValidator
from phase9.artifact.registry import ArtifactRegistry
from phase9.aggregator import MetadataAggregator
from phase9.metrics import MetricsCollector
from phase9.table_generator import TableGenerator
from phase9.figure_generator import FigureGenerator
from phase9.report_generator import ReportGenerator
from phase9.packaging import PackagingManager
from phase9.reproducibility import ReproducibilityWriter
from phase9.utils.jsonyaml import dump_json


logger = logging.getLogger(__name__)


class Phase9Pipeline:
    """Coordinate Phase 9 orchestration without implementing business logic.

    This class delegates discovery, parsing, resolution, validation and registry
    construction to the respective modules and only manages their invocation
    order, configuration and output persistence.
    """

    def __init__(self, cfg=None):
        self.cfg = cfg or load_config()
        self.logger = get_logger("phase9.pipeline")

    def initialize_logging(self, level: Optional[str] = None) -> None:
        if level:
            self.cfg.logging.level = level
        configure_logging(self.cfg)
        self.logger = get_logger("phase9.pipeline")

    def prepare_output_directory(self, output_dir: Optional[Path]) -> Path:
        out = Path(output_dir) if output_dir else Path(self.cfg.output.artifacts_root)
        out.mkdir(parents=True, exist_ok=True)
        return out

    def discover(self, phases: Optional[List[int]] = None, output_dir: Optional[Path] = None) -> Dict[str, Any]:
        """Run discovery and manifest parsing; write canonical manifest to output_dir.

        Returns the discovery index dictionary.
        """
        self.logger.info("Starting discovery pipeline")
        svc = DiscoveryService(config=self.cfg)
        discovery_index = svc.discover(phases=phases, output_dir=output_dir)

        # parse manifests collected in discovery index
        parser = ManifestParser()
        manifests = []
        for p in discovery_index.get("phases", []):
            if p.get("manifest_found") and p.get("manifest_path"):
                try:
                    pm = parser.parse(Path(p.get("manifest_path")))
                    manifests.append(pm)
                except Exception as e:
                    self.logger.error("Failed to parse manifest %s: %s", p.get("manifest_path"), e)

        out = self.prepare_output_directory(output_dir)
        canonical_path = out / "canonical_manifest.json"
        if manifests:
            parser.merge(manifests, canonical_path)
        else:
            dump_json(canonical_path, {"produced_at": None, "source_phases": [], "artifacts": [], "manifest_versions": {}})

        self.logger.info("Discovery pipeline complete, outputs at %s", out)
        return discovery_index

    def validate(self, phases: Optional[List[int]] = None, strict: bool = False, output_dir: Optional[Path] = None) -> int:
        """Full validate pipeline: discovery → parse → resolve → validate → registry.

        Returns 0 on success, non-zero on recoverable failure.
        """
        self.logger.info("Starting validate pipeline")
        out = self.prepare_output_directory(output_dir)

        discovery_index = self.discover(phases=phases, output_dir=out)

        # load canonical manifest
        parser = ManifestParser()
        manifests = []
        for p in discovery_index.get("phases", []):
            if p.get("manifest_found") and p.get("manifest_path"):
                try:
                    pm = parser.parse(Path(p.get("manifest_path")))
                    manifests.append(pm)
                except Exception as e:
                    self.logger.error("Failed to parse manifest %s: %s", p.get("manifest_path"), e)

        if not manifests:
            self.logger.error("No manifests found to validate")
            return 2

        canonical = parser.merge(manifests, out / "canonical_manifest.json")

        # resolution
        resolver = ArtifactResolver()
        resolved_artifacts, resolver_report = resolver.resolve(canonical)

        # validation
        validator = ArtifactValidator()
        validation_report = validator.validate(resolved_artifacts, strict=strict)
        dump_json(out / "validation_report.json", validation_report)

        # registry
        registry = ArtifactRegistry(resolved_artifacts, out)
        registry.persist()

        # Aggregation and metrics (post-registry)
        try:
            aggregator = MetadataAggregator(registry, out)
            aggregator.aggregate()
        except Exception:
            self.logger.exception("Metadata aggregation failed; continuing to metrics collection")

        try:
            collector = MetricsCollector(registry, out)
            collector.collect()
        except Exception:
            self.logger.exception("Metrics collection failed")

        self.logger.info("Validate pipeline complete. Outputs written to %s", out)
        return 0

    def _run_to_registry(self, phases: Optional[List[int]] = None, strict: bool = False, output_dir: Optional[Path] = None):
        """Run discovery → parse → resolve → validate → registry and return (registry, out)

        This helper centralizes the common pipeline sequence so `aggregate` and
        `validate` can reuse orchestration without duplication.
        """
        out = self.prepare_output_directory(output_dir)

        discovery_index = self.discover(phases=phases, output_dir=out)

        # load canonical manifest
        parser = ManifestParser()
        manifests = []
        for p in discovery_index.get("phases", []):
            if p.get("manifest_found") and p.get("manifest_path"):
                try:
                    pm = parser.parse(Path(p.get("manifest_path")))
                    manifests.append(pm)
                except Exception as e:
                    self.logger.error("Failed to parse manifest %s: %s", p.get("manifest_path"), e)

        if not manifests:
            self.logger.error("No manifests found to process")
            return None, out

        canonical = parser.merge(manifests, out / "canonical_manifest.json")

        # resolution
        resolver = ArtifactResolver()
        resolved_artifacts, resolver_report = resolver.resolve(canonical)

        # validation
        validator = ArtifactValidator()
        validation_report = validator.validate(resolved_artifacts, strict=strict)
        dump_json(out / "validation_report.json", validation_report)

        # registry
        registry = ArtifactRegistry(resolved_artifacts, out)
        registry.persist()

        return registry, out

    def aggregate(self, phases: Optional[List[int]] = None, strict: bool = False, output_dir: Optional[Path] = None) -> int:
        """Run the full aggregation pipeline ending with metadata and metrics generation.

        Returns 0 on success, non-zero on recoverable failure.
        """
        self.logger.info("Starting aggregate pipeline")
        registry, out = self._run_to_registry(phases=phases, strict=strict, output_dir=output_dir)
        if registry is None:
            self.logger.error("Aggregate pipeline aborted: no registry produced")
            return 2

        try:
            aggregator = MetadataAggregator(registry, out)
            aggregator.aggregate()
        except Exception as e:
            self.logger.exception("Aggregation failed: %s", e)
            return 3

        try:
            collector = MetricsCollector(registry, out)
            collector.collect()
        except Exception as e:
            self.logger.exception("Metrics collection failed: %s", e)
            return 4

        # Table & Figure generation
        try:
            tg = TableGenerator(registry, out)
            table_assets = tg.generate()
        except Exception as e:
            self.logger.exception("Table generation failed: %s", e)
            return 5

        try:
            fg = FigureGenerator(registry, out)
            fig_assets = fg.generate()
        except Exception as e:
            self.logger.exception("Figure generation failed: %s", e)
            return 6

        # asset catalog
        try:
            from phase9.assets.models import AssetCatalog
            catalog = AssetCatalog(generated_at=__import__("time").ctime(), assets=[a for a in []])
            # gather assets from table and figure generators
            assets_all = table_assets + fig_assets
            catalog.assets = [a for a in assets_all]
            dump_json(out / "asset_catalog.json", {"generated_at": catalog.generated_at, "assets": [a.model_dump() for a in catalog.assets]})
        except Exception:
            self.logger.exception("Failed to write asset catalog")

        self.logger.info("Aggregate pipeline complete. Outputs written to %s", out)
        return 0

    def generate_report(self, phases: Optional[List[int]] = None, strict: bool = False, output_dir: Optional[Path] = None) -> int:
        """Run the full pipeline and then generate reports and package outputs.

        Returns 0 on success, non-zero on recoverable failure.
        """
        self.logger.info("Starting report generation pipeline")
        # reuse aggregate which already performs discovery->tables/figures and writes asset_catalog
        code = self.aggregate(phases=phases, strict=strict, output_dir=output_dir)
        if code != 0:
            self.logger.error("Aggregate stage failed with code %s", code)
            return code

        out = self.prepare_output_directory(output_dir)
        try:
            rg = ReportGenerator(out)
            rg.generate()
        except Exception as e:
            self.logger.exception("Report generation failed: %s", e)
            return 7

        try:
            pm = PackagingManager(out)
            pm.package()
        except Exception as e:
            self.logger.exception("Packaging failed: %s", e)
            return 8

        self.logger.info("Report & Packaging pipeline complete. Outputs at %s", out)
        return 0

    def run(self, phases: Optional[List[int]] = None, strict: bool = False, output_dir: Optional[Path] = None, config_path: Optional[Path] = None) -> int:
        """Execute the complete Phase 9 workflow end-to-end and produce reproducibility outputs.

        Returns 0 on success, or a non-zero exit code for failures in specific stages.
        """
        self.logger.info("Starting full Phase 9 run")
        start_ts = time.time()
        code = self.generate_report(phases=phases, strict=strict, output_dir=output_dir)
        if code != 0:
            self.logger.error("generate_report failed with code %s", code)
            return code

        out = self.prepare_output_directory(output_dir)
        try:
            rw = ReproducibilityWriter(out)
            rw.write(start_ts=start_ts, end_ts=time.time(), config_path=config_path)
        except Exception as e:
            self.logger.exception("Reproducibility writing failed: %s", e)
            return 9

        self.logger.info("Full run complete. Outputs at %s", out)
        return 0
