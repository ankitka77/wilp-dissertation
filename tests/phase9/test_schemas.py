import json
from pathlib import Path


def test_manifest_schema_exists():
    p = Path("phase9/schemas/manifest.schema.json")
    assert p.exists()
    data = json.loads(p.read_text())
    assert data.get("title") == "Phase Manifest"


def test_artifact_schema_exists():
    p = Path("phase9/schemas/artifact.schema.json")
    assert p.exists()
    data = json.loads(p.read_text())
    assert data.get("title") == "Artifact Record"
