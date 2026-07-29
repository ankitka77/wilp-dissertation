from pathlib import Path
import json

from phase9.manifest.models import ArtifactRecord
from phase9.artifact.validator import ArtifactValidator


def test_validate_checksum_and_json(tmp_path: Path):
    p = tmp_path / "artifacts/phase5/latest/meta.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"a": 1}))

    # compute checksum
    from phase9.utils.checksum import sha256_file

    chk = sha256_file(p)

    a = ArtifactRecord(id="a1", phase=5, type="model_metadata", relative_path="meta.json", resolved_path=str(p), checksum=chk)
    v = ArtifactValidator()
    report = v.validate([a])
    assert report["artifacts"][0]["status"] == "valid"


def test_validate_missing(tmp_path: Path):
    a = ArtifactRecord(id="a2", phase=5, type="data", relative_path="nope.txt", resolved_path=None)
    v = ArtifactValidator()
    report = v.validate([a])
    assert report["artifacts"][0]["findings"][0]["message"] == "missing file"
