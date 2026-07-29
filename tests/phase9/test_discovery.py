from pathlib import Path

from phase9.discovery.service import DiscoveryService


def sample_manifest_dict():
    return {
        "manifest_version": "1.0",
        "phase": 6,
        "artifacts": [{"id": "a-1", "relative_path": "file.txt", "type": "data"}],
        "generated_timestamp": "2020-01-01T00:00:00Z",
    }


def test_discovery_handles_manifest_and_files(tmp_path, simple_config):
    # setup phase directory and manifest
    p = tmp_path / "artifacts" / "phase6" / "latest"
    p.mkdir(parents=True)
    (p / "manifest.json").write_text("{}")
    # monkeypatch config location via simple_config
    svc = DiscoveryService(config=simple_config)
    # create manifest file where DiscoveryService will look
    real_p = Path("artifacts") / "phase6" / "latest"
    real_p.mkdir(parents=True, exist_ok=True)
    (real_p / "manifest.json").write_text(str(sample_manifest_dict()))

    try:
        idx = svc.discover(phases=[6], output_dir=tmp_path / "out")
        assert isinstance(idx, dict)
        phases = idx.get("phases", [])
        assert any(p.get("phase") == 6 for p in phases)
    finally:
        # cleanup created files
        for f in real_p.glob("*"):
            f.unlink()
        real_p.rmdir()
