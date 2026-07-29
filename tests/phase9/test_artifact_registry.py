from pathlib import Path
import json

from phase9.manifest.models import ArtifactRecord
from phase9.artifact.registry import ArtifactRegistry


def test_registry_lookups(tmp_path: Path):
    a1 = ArtifactRecord(id="a1", phase=5, type="model_metadata", relative_path="m1.json", resolved_path=str(tmp_path / "m1.json"))
    a2 = ArtifactRecord(id="a2", phase=6, type="data", relative_path="d.csv", resolved_path=str(tmp_path / "d.csv"))
    reg = ArtifactRegistry([a1, a2], tmp_path)
    assert reg.lookup_by_id("a1") is not None
    assert len(reg.lookup_by_phase(5)) == 1
    assert len(reg.lookup_by_type("data")) == 1
    reg.persist()
    assert (tmp_path / "artifact_registry.json").exists()
