from pathlib import Path
import json

from phase9.manifest.models import ArtifactRecord
from phase9.artifact.registry import ArtifactRegistry
from phase9.table_generator.generator import TableGenerator


def make_artifact(id: str, phase: int, atype: str, size: int = None, **kw):
    return ArtifactRecord(id=id, phase=phase, type=atype, relative_path=f"{id}.dat", size_bytes=size, **kw)


def test_table_generator_creates_tables(tmp_path: Path):
    a1 = make_artifact("a1", 5, "dataset", size=100)
    a2 = make_artifact("a2", 6, "model", size=200)
    registry = ArtifactRegistry([a1, a2], tmp_path)

    tg = TableGenerator(registry, tmp_path)
    assets = tg.generate()

    assert (tmp_path / "tables" / "artifact_inventory.csv").exists()
    assert (tmp_path / "tables" / "artifact_inventory.md").exists()
    assert (tmp_path / "tables" / "artifact_inventory.json").exists()
    assert (tmp_path / "table_summary.json").exists()
    assert len(assets) >= 1
