from pathlib import Path

from phase9.manifest.models import ArtifactRecord
from phase9.artifact.registry import ArtifactRegistry
from phase9.figure_generator.generator import FigureGenerator


def make_artifact(id: str, phase: int, atype: str, **kw):
    return ArtifactRecord(id=id, phase=phase, type=atype, relative_path=f"{id}.dat", **kw)


def test_figure_generator_creates_svg(tmp_path: Path):
    a1 = make_artifact("a1", 4, "metric")
    a2 = make_artifact("a2", 5, "dataset")
    registry = ArtifactRegistry([a1, a2], tmp_path)

    fg = FigureGenerator(registry, tmp_path)
    assets = fg.generate()

    assert (tmp_path / "figures" / "artifact_counts.svg").exists()
    assert (tmp_path / "figure_summary.json").exists()
    assert len(assets) >= 1
