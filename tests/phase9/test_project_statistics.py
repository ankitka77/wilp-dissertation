from pathlib import Path
import json

from phase9.manifest.models import ArtifactRecord
from phase9.artifact.registry import ArtifactRegistry
from phase9.metrics.collector import MetricsCollector


def make_artifact(id: str, phase: int, atype: str, size: int = None, **kw):
    return ArtifactRecord(id=id, phase=phase, type=atype, relative_path=f"{id}.dat", size_bytes=size, **kw)


def test_project_statistics_contains_phase_counts(tmp_path: Path):
    a1 = make_artifact("a1", 4, "metric", size=100)
    a2 = make_artifact("a2", 4, "metric", size=200)
    a3 = make_artifact("a3", 5, "dataset", size=50)
    registry = ArtifactRegistry([a1, a2, a3], tmp_path)

    mc = MetricsCollector(registry, tmp_path)
    res = mc.collect()

    stats_file = tmp_path / "project_statistics.json"
    assert stats_file.exists()
    data = json.loads(stats_file.read_text())
    assert data.get("artifact_count") == 3
    assert data.get("phase_counts").get("4") or data.get("phase_counts").get(4)
