from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List
import logging
import json
import time

from phase9.assets.models import AssetCatalog, AssetModel
from phase9.utils.jsonyaml import load_json, dump_json


logger = logging.getLogger(__name__)


class ReportGenerationError(Exception):
    pass


class ReportGenerator:
    """Template-driven report generator. Consumes `asset_catalog.json` and
    the aggregated metadata/metrics to assemble Markdown, HTML and JSON reports.
    """

    def __init__(self, output_root: Path | str, templates_root: Path | None = None):
        self.output_root = Path(output_root)
        self.reports_dir = self.output_root / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.templates_root = Path(templates_root) if templates_root else Path(__file__).parent / "templates"

    def _load_catalog(self) -> AssetCatalog:
        catalog_path = self.output_root / "asset_catalog.json"
        data = load_json(catalog_path)
        return AssetCatalog(**data)

    def _load_json_if_exists(self, p: Path) -> Dict[str, Any]:
        if p.exists():
            try:
                return load_json(p)
            except Exception:
                logger.exception("Failed to read JSON %s", p)
        return {}

    def _render_template(self, tpl_path: Path, context: Dict[str, Any]) -> str:
        txt = tpl_path.read_text(encoding="utf-8")
        # Simple str.format templating — templates must use {key} placeholders.
        try:
            return txt.format(**context)
        except Exception as exc:
            logger.exception("Template rendering failed for %s: %s", tpl_path, exc)
            raise

    def generate(self) -> List[Path]:
        logger.info("Starting report generation")
        try:
            catalog = self._load_catalog()

            # Load supporting summary files
            metadata = self._load_json_if_exists(self.output_root / "metadata_summary.json")
            metrics = self._load_json_if_exists(self.output_root / "metrics_summary.json")
            stats = self._load_json_if_exists(self.output_root / "project_statistics.json")

            context = {
                "generated_at": time.ctime(),
                "catalog": json.dumps([a.model_dump() for a in catalog.assets], indent=2),
                "metadata_summary": json.dumps(metadata, indent=2),
                "metrics_summary": json.dumps(metrics, indent=2),
                "project_statistics": json.dumps(stats, indent=2),
            }

            out_files: List[Path] = []
            # Markdown
            md_tpl = self.templates_root / "report.md.tpl"
            md_out = self.reports_dir / "report.md"
            md_text = self._render_template(md_tpl, context)
            md_out.write_text(md_text, encoding="utf-8")
            out_files.append(md_out)

            # HTML
            html_tpl = self.templates_root / "report.html.tpl"
            html_out = self.reports_dir / "report.html"
            html_text = self._render_template(html_tpl, context)
            html_out.write_text(html_text, encoding="utf-8")
            out_files.append(html_out)

            # JSON report
            json_out = self.reports_dir / "report.json"
            dump_json(json_out, {"generated_at": time.ctime(), "catalog": [a.model_dump() for a in catalog.assets], "metadata_summary": metadata, "metrics_summary": metrics, "project_statistics": stats})
            out_files.append(json_out)

            logger.info("Report generation complete, wrote %d files", len(out_files))
            return out_files

        except Exception as exc:
            logger.exception("Report generation failed: %s", exc)
            raise ReportGenerationError(str(exc))


__all__ = ["ReportGenerator", "ReportGenerationError"]
