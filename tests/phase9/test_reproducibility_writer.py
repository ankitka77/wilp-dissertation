from pathlib import Path
import json
import time

from phase9.reproducibility.writer import ReproducibilityWriter


def test_reproducibility_writer_creates_artifacts(tmp_path: Path):
    # create minimal outputs that writer will checksum
    (tmp_path / "canonical_manifest.json").write_text(json.dumps({"foo": 1}))
    (tmp_path / "artifact_registry.json").write_text(json.dumps({"artifacts": []}))
    (tmp_path / "validation_report.json").write_text(json.dumps({"ok": True}))
    (tmp_path / "asset_catalog.json").write_text(json.dumps({"assets": []}))
    (tmp_path / "metadata_summary.json").write_text(json.dumps({}))
    (tmp_path / "metrics_summary.json").write_text(json.dumps({}))
    (tmp_path / "project_statistics.json").write_text(json.dumps({}))
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "report.json").write_text(json.dumps({}))
    (tmp_path / "package").mkdir()
    (tmp_path / "package" / "package_manifest.json").write_text(json.dumps({}))

    rw = ReproducibilityWriter(tmp_path)
    start = time.time()
    time.sleep(0.01)
    result = rw.write(start_ts=start, end_ts=time.time(), config_path=None)

    assert (tmp_path / "reproducibility_manifest.json").exists()
    assert (tmp_path / "environment_snapshot.json").exists()
    assert (tmp_path / "dependency_snapshot.json").exists()
    assert (tmp_path / "execution_summary.json").exists()
    assert (tmp_path / "configuration_snapshot.json").exists()
    assert isinstance(result.get("reproducibility_manifest"), str)
