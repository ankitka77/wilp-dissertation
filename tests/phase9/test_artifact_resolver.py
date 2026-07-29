from pathlib import Path
import json

from phase9.manifest.models import CanonicalManifest, ArtifactRecord
from phase9.artifact.resolver import ArtifactResolver


def test_resolve_existing_and_missing(tmp_path: Path):
    # create fake artifact files
    p1 = tmp_path / "artifacts/phase5/latest/model.json"
    p1.parent.mkdir(parents=True)
    p1.write_text(json.dumps({"model": "x"}))

    a1 = ArtifactRecord(id="a1", phase=5, type="model_metadata", relative_path="model.json")
    a2 = ArtifactRecord(id="a2", phase=5, type="data", relative_path="missing.txt")
    canonical = CanonicalManifest(produced_at="now", source_phases=[5], artifacts=[a1, a2], manifest_versions={5: "1.0"})

    resolver = ArtifactResolver(repo_root=tmp_path)
    resolved, report = resolver.resolve(canonical)
    # a1 should be resolved
    assert any(r.id == "a1" and r.resolved_path is not None for r in resolved)
    # a2 missing
    assert "a2" in report["missing"]
