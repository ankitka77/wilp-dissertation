from pathlib import Path
import json

from phase9.manifest.models import ArtifactRecord
from phase9.artifact.registry import ArtifactRegistry
from phase9.aggregator.aggregator import MetadataAggregator


def make_artifact(id: str, phase: int, atype: str, **kw):
    return ArtifactRecord(id=id, phase=phase, type=atype, relative_path=f"{id}.json", **kw)


def test_metadata_aggregator_writes_summary(tmp_path: Path):
    a1 = make_artifact("a1", 5, "dataset", metadata={"experiment_id": "exp1"}, checksum="abc")
    a2 = make_artifact("a2", 6, "model", metadata={"experiment_id": "exp1", "dependencies": ["a1"]})
    registry = ArtifactRegistry([a1, a2], tmp_path)

    agg = MetadataAggregator(registry, tmp_path)
    project_meta = agg.aggregate()

    out_file = tmp_path / "metadata_summary.json"
    assert out_file.exists()
    data = json.loads(out_file.read_text())
    assert data.get("artifact_count") == 2
    assert isinstance(data.get("phases"), list)
    assert "a1" in [a.get("id") for a in data.get("artifacts")]
