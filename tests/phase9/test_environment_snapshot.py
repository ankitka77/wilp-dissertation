from pathlib import Path
import json
import time

from phase9.reproducibility.writer import ReproducibilityWriter


def test_environment_snapshot_contains_fields(tmp_path: Path):
    rw = ReproducibilityWriter(tmp_path)
    start = time.time()
    end = time.time()
    rw.write(start_ts=start, end_ts=end, config_path=None)

    env = json.loads((tmp_path / "environment_snapshot.json").read_text())
    assert "hostname" in env
    assert "os" in env
    assert "python_version" in env
