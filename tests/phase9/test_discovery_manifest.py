import os
from pathlib import Path
import shutil
import json

from phase9.discovery.service import DiscoveryService
from phase9.manifest.parser import ManifestParser
from phase9.utils.jsonyaml import dump_json


def make_phase_dir(tmp_path: Path, phase: int, manifest: dict | None = None):
    p = tmp_path / f"artifacts/phase{phase}/latest"
    p.mkdir(parents=True)
    if manifest is not None:
        (p / "manifest.json").write_text(json.dumps(manifest))
    else:
        # create some files
        (p / "file1.txt").write_text("x")
        (p / "file2.txt").write_text("y")
    return p


def test_manifest_first_discovery(tmp_path: Path, monkeypatch):
    # setup fake artifact tree
    root = tmp_path
    m = {"manifest_version": "1.0", "phase": 5, "artifacts": [{"id": "a1", "type": "model_metadata", "relative_path": "model.json"}], "generated_timestamp": "2026-01-01T00:00:00Z"}
    p = make_phase_dir(root, 5, manifest=m)

    # run discovery with patched artifact root
    svc = DiscoveryService()
    # monkeypatch _phase_path to point to tmp_path
    svc._phase_path = lambda phase: root / f"artifacts/phase{phase}/latest"
    out = svc.discover(phases=[5], output_dir=root / "phase9_out")
    assert out["phases"][0]["manifest_found"] is True
    assert out["phases"][0]["artifact_count"] == 1


def test_filesystem_fallback(tmp_path: Path):
    root = tmp_path
    p = make_phase_dir(root, 6, manifest=None)
    svc = DiscoveryService()
    svc._phase_path = lambda phase: root / f"artifacts/phase{phase}/latest"
    out = svc.discover(phases=[6], output_dir=root / "phase9_out")
    assert out["phases"][0]["manifest_found"] is False
    assert out["phases"][0]["artifact_count"] >= 1


def test_manifest_parser_yaml(tmp_path: Path):
    root = tmp_path
    p = root / "artifacts/phase4/latest"
    p.mkdir(parents=True)
    yaml_text = """
manifest_version: "1.0"
phase: 4
artifacts:
  - id: id1
    type: metrics
    relative_path: metrics.json
generated_timestamp: 2026-01-01T00:00:00Z
"""
    (p / "manifest.yaml").write_text(yaml_text)
    parser = ManifestParser()
    pm = parser.parse(p / "manifest.yaml")
    assert pm.phase == 4
    assert len(pm.artifacts) == 1
