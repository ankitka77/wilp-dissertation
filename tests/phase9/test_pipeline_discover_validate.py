from pathlib import Path
import json

from phase9.pipeline import Phase9Pipeline


def make_canonical_manifest(base_dir: Path):
    # DiscoveryService expects manifests under the repo working tree 'artifacts/phaseX/latest'
    p = Path("artifacts") / "phase6" / "latest"
    p.mkdir(parents=True, exist_ok=True)
    data = {
        "manifest_version": "1.0",
        "phase": 6,
        "artifacts": [{"id": "a1", "relative_path": "file1.txt", "type": "data"}],
        "generated_timestamp": "2020-01-01T00:00:00Z",
    }
    (p / "manifest.json").write_text(json.dumps(data))
    return p


def test_pipeline_discover_and_validate(tmp_path, simple_config):
    # prepare manifest in working tree where discover expects
    make_canonical_manifest(tmp_path)
    pipeline = Phase9Pipeline(cfg=simple_config)
    out = tmp_path / "out"
    # run discovery and validation (should produce canonical and registry files)
    pipeline.discover(phases=[6], output_dir=out)
    # now run validate which uses discover internally
    rc = pipeline.validate(phases=[6], strict=False, output_dir=out)
    assert rc == 0
    # Check outputs
    assert (out / "canonical_manifest.json").exists()
    assert (out / "artifact_registry.json").exists() or (out / "artifact_registry.json").exists()
