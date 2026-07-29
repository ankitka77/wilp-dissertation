from pathlib import Path
import json

from phase9.manifest.models import ArtifactRecord
from phase9.artifact.registry import ArtifactRegistry
from phase9.metrics.collector import MetricsCollector


def make_artifact(id: str, phase: int, atype: str, size: int = None, validation: dict = None, **kw):
    return ArtifactRecord(id=id, phase=phase, type=atype, relative_path=f"{id}.dat", size_bytes=size, validation=validation or {}, **kw)


def test_metrics_collector_writes_metrics(tmp_path: Path):
    a1 = make_artifact("a1", 5, "dataset", size=1024, validation={"status": "ok"})
    a2 = make_artifact("a2", 6, "model", size=2048, validation={"status": "warning"})
    registry = ArtifactRegistry([a1, a2], tmp_path)

    mc = MetricsCollector(registry, tmp_path)
    res = mc.collect()

    metrics_file = tmp_path / "metrics_summary.json"
    stats_file = tmp_path / "project_statistics.json"
    assert metrics_file.exists()
    assert stats_file.exists()
    data = json.loads(metrics_file.read_text())
    assert data.get("total_artifacts") == 2
    assert data.get("validation").get("validated") == 1
