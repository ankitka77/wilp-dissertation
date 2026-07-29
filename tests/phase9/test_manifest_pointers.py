from pathlib import Path
import json
import pytest

from phase9.manifest.parser import ManifestParser
from phase9.exceptions import ManifestError


def canonical_manifest_dict():
    return {
        "manifest_version": "1.0",
        "phase": 6,
        "artifacts": [{"id": "a1", "relative_path": "file1.txt", "type": "data"}],
        "generated_timestamp": "2020-01-01T00:00:00Z",
    }


def test_pointer_absolute_path_resolves(tmp_path, parser):
    target = tmp_path / "phase6" / "latest" / "manifest.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(canonical_manifest_dict()))

    pointer = tmp_path / "phase6" / "latest" / "latest" / "manifest.json"
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(json.dumps({"manifest_path": str(target)}))

    pm = parser.parse(pointer)
    assert pm.phase == 6
    assert len(pm.artifacts) == 1


def test_pointer_relative_path_resolves(tmp_path, parser):
    target = tmp_path / "phase6" / "latest" / "manifest.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(canonical_manifest_dict()))

    pointer = tmp_path / "phase6" / "latest" / "pointer.json"
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(json.dumps({"manifest_path": "manifest.json"}))

    pm = parser.parse(pointer)
    assert pm.phase == 6
    assert pm.artifact_count == 1 if hasattr(pm, 'artifact_count') else len(pm.artifacts)


def test_pointer_missing_target_raises(tmp_path, parser):
    pointer = tmp_path / "phase6" / "latest" / "manifest.json"
    pointer.parent.mkdir(parents=True)
    pointer.write_text(json.dumps({"manifest_path": "does_not_exist.json"}))

    with pytest.raises(ManifestError) as exc:
        parser.parse(pointer)

    assert "manifest pointer target not found" in str(exc.value.message) or "target" in str(exc.value.context)


def test_canonical_manifest_no_pointer(tmp_path, parser):
    m = tmp_path / "phase6" / "latest" / "manifest.json"
    m.parent.mkdir(parents=True)
    m.write_text(json.dumps(canonical_manifest_dict()))

    pm = parser.parse(m)
    assert pm.phase == 6
    assert len(pm.artifacts) == 1
