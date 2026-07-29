from pathlib import Path
import json

from phase9.manifest.models import ArtifactRecord
from phase9.artifact.registry import ArtifactRegistry
from phase9.table_generator.generator import TableGenerator
from phase9.figure_generator.generator import FigureGenerator


def test_asset_catalog_aggregation(tmp_path: Path):
    a1 = ArtifactRecord(id="a1", phase=5, type="dataset", relative_path="a1.json")
    reg = ArtifactRegistry([a1], tmp_path)

    tg = TableGenerator(reg, tmp_path)
    table_assets = tg.generate()
    fg = FigureGenerator(reg, tmp_path)
    fig_assets = fg.generate()

    # asset_catalog.json generation mimicked by pipeline; here we'll just combine
    assets_all = table_assets + fig_assets
    assert any(a.asset_type == "table" for a in assets_all)
    assert any(a.asset_type == "figure" for a in assets_all)
