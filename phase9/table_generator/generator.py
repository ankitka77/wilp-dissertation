from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any
import csv
import logging
import time

from phase9.assets.models import AssetModel, AssetCatalog
from phase9.artifact.registry import ArtifactRegistry
from phase9.utils.jsonyaml import dump_json


logger = logging.getLogger(__name__)


class TableGenerationError(Exception):
    pass


class TableGenerator:
    """Generate tables (CSV/Markdown/JSON) from the ArtifactRegistry and
    aggregated metadata/metrics. Writes assets and returns AssetModel list.
    """

    def __init__(self, registry: ArtifactRegistry, output_root: Path | str):
        self.registry = registry
        self.output_root = Path(output_root)
        self.tables_dir = self.output_root / "tables"
        self.tables_dir.mkdir(parents=True, exist_ok=True)

    def _write_csv(self, path: Path, rows: List[Dict[str, Any]], headers: List[str]) -> None:
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers)
            writer.writeheader()
            for r in rows:
                writer.writerow({k: r.get(k) for k in headers})

    def _write_markdown(self, path: Path, rows: List[Dict[str, Any]], headers: List[str]) -> None:
        with path.open("w", encoding="utf-8") as fh:
            fh.write("| " + " | ".join(headers) + " |\n")
            fh.write("| " + " | ".join(["---"] * len(headers)) + " |\n")
            for r in rows:
                fh.write("| " + " | ".join(str(r.get(h, "")) for h in headers) + " |\n")

    def generate(self) -> List[AssetModel]:
        logger.info("Starting table generation")
        try:
            assets: List[AssetModel] = []
            rows = []
            for a in self.registry.artifacts:
                rows.append({
                    "id": a.id,
                    "phase": a.phase,
                    "type": a.type,
                    "relative_path": a.relative_path,
                    "resolved_path": a.resolved_path or "",
                    "checksum": a.checksum or "",
                    "size_bytes": a.size_bytes or 0,
                })

            headers = ["id", "phase", "type", "relative_path", "resolved_path", "checksum", "size_bytes"]

            # artifact inventory CSV
            csv_path = self.tables_dir / "artifact_inventory.csv"
            md_path = self.tables_dir / "artifact_inventory.md"
            json_path = self.tables_dir / "artifact_inventory.json"

            self._write_csv(csv_path, rows, headers)
            self._write_markdown(md_path, rows, headers)
            dump_json(json_path, {"rows": rows})

            created_at = time.ctime()
            asset = AssetModel(
                asset_id="artifact_inventory",
                asset_type="table",
                category="artifact_inventory",
                title="Artifact Inventory",
                caption="List of artifacts discovered and resolved",
                description="Comprehensive inventory of discovered artifacts",
                source_module="phase9.table_generator",
                source_data=["artifact_registry.json"],
                created_at=created_at,
                relative_path=str(csv_path.relative_to(self.output_root)),
                filename=csv_path.name,
                output_format="csv",
                report_section="Inventory",
                generation_version="1.0",
            )
            assets.append(asset)

            # phase summary table
            phase_counts = self.registry.statistics().get("phase_counts", {})
            rows2 = [{"phase": p, "count": phase_counts[p]} for p in sorted(phase_counts.keys())]
            csv2 = self.tables_dir / "phase_summary.csv"
            self._write_csv(csv2, rows2, ["phase", "count"])
            dump_json(self.tables_dir / "phase_summary.json", {"rows": rows2})

            asset2 = AssetModel(
                asset_id="phase_summary",
                asset_type="table",
                category="phase_summary",
                title="Phase Summary",
                caption="Count of artifacts per phase",
                description="Counts grouped by producing phase",
                source_module="phase9.table_generator",
                source_data=["registry_statistics.json"],
                created_at=created_at,
                relative_path=str(csv2.relative_to(self.output_root)),
                filename=csv2.name,
                output_format="csv",
                report_section="Summary",
                generation_version="1.0",
            )
            assets.append(asset2)

            # write summaries
            dump_json(self.output_root / "table_summary.json", {"generated_at": created_at, "assets": [a.model_dump() for a in assets]})

            logger.info("Table generation complete, wrote %d tables", len(assets))
            return assets

        except Exception as exc:
            logger.exception("Table generation failed: %s", exc)
            raise TableGenerationError(str(exc))


__all__ = ["TableGenerator", "TableGenerationError"]
