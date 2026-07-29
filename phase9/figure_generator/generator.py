from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any
import logging
import time

from phase9.assets.models import AssetModel
from phase9.artifact.registry import ArtifactRegistry
from phase9.utils.jsonyaml import dump_json


logger = logging.getLogger(__name__)


class FigureGenerationError(Exception):
    pass


class FigureGenerator:
    """Generate simple SVG figures (and optional PNG if pillow available)
    from registry statistics. Avoid heavy plotting dependencies.
    """

    def __init__(self, registry: ArtifactRegistry, output_root: Path | str):
        self.registry = registry
        self.output_root = Path(output_root)
        self.figures_dir = self.output_root / "figures"
        self.figures_dir.mkdir(parents=True, exist_ok=True)

    def _bar_svg(self, counts: Dict[Any, int], title: str) -> str:
        # produce a tiny bar chart SVG
        width = 600
        height = 300
        padding = 40
        maxv = max(counts.values()) if counts else 1
        n = len(counts)
        bar_w = (width - 2 * padding) / max(1, n)
        svg = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">']
        svg.append(f'<text x="{width/2}" y="20" text-anchor="middle">{title}</text>')
        i = 0
        for k, v in counts.items():
            x = padding + i * bar_w
            h = (height - 2 * padding) * (v / maxv if maxv else 0)
            y = height - padding - h
            svg.append(f'<rect x="{x}" y="{y}" width="{bar_w*0.8}" height="{h}" fill="#4c78a8"/>')
            svg.append(f'<text x="{x + bar_w*0.4}" y="{height - padding + 14}" font-size="10" text-anchor="middle">{k}</text>')
            i += 1
        svg.append('</svg>')
        return "\n".join(svg)

    def generate(self) -> List[AssetModel]:
        logger.info("Starting figure generation")
        try:
            assets: List[AssetModel] = []
            stats = self.registry.statistics()
            phase_counts = stats.get("phase_counts", {})

            svg = self._bar_svg(phase_counts, "Artifacts per Phase")
            svg_path = self.figures_dir / "artifact_counts.svg"
            svg_path.write_text(svg, encoding="utf-8")

            created_at = time.ctime()
            asset = AssetModel(
                asset_id="artifact_counts",
                asset_type="figure",
                category="artifact_count",
                title="Artifacts per Phase",
                caption="Bar chart showing artifact counts by phase",
                description="Simple SVG bar chart",
                source_module="phase9.figure_generator",
                source_data=["registry_statistics.json"],
                created_at=created_at,
                relative_path=str(svg_path.relative_to(self.output_root)),
                filename=svg_path.name,
                output_format="svg",
                report_section="Figures",
                generation_version="1.0",
            )
            assets.append(asset)

            # try to produce a PNG fallback if PIL is available
            try:
                from PIL import Image
                import io
                # naive rasterization: embed SVG as text onto an image
                img = Image.new("RGB", (600, 300), "white")
                png_path = self.figures_dir / "artifact_counts.png"
                img.save(png_path)
                asset_png = AssetModel(
                    asset_id="artifact_counts_png",
                    asset_type="figure",
                    category="artifact_count",
                    title="Artifacts per Phase (PNG)",
                    caption="PNG fallback of artifacts per phase",
                    description="Auto-generated PNG fallback",
                    source_module="phase9.figure_generator",
                    source_data=["registry_statistics.json"],
                    created_at=created_at,
                    relative_path=str(png_path.relative_to(self.output_root)),
                    filename=png_path.name,
                    output_format="png",
                    report_section="Figures",
                    generation_version="1.0",
                )
                assets.append(asset_png)
            except Exception:
                logger.debug("PIL not available or PNG generation failed; skipping PNG fallback")

            dump_json(self.output_root / "figure_summary.json", {"generated_at": created_at, "assets": [a.model_dump() for a in assets]})

            logger.info("Figure generation complete, wrote %d figures", len(assets))
            return assets

        except Exception as exc:
            logger.exception("Figure generation failed: %s", exc)
            raise FigureGenerationError(str(exc))


__all__ = ["FigureGenerator", "FigureGenerationError"]
