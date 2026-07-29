from pathlib import Path
import json
import time
import pytest

from phase9.reproducibility.writer import ReproducibilityWriter


def test_execution_summary_has_duration(tmp_path: Path):
    rw = ReproducibilityWriter(tmp_path)
    start = time.time()
    end = start + 0.5
    rw.write(start_ts=start, end_ts=end, config_path=None)

    summary = json.loads((tmp_path / "execution_summary.json").read_text())
    assert "duration_seconds" in summary
    assert summary["duration_seconds"] == pytest.approx(0.5, rel=0.1)
