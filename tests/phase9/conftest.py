import json
from types import SimpleNamespace
from pathlib import Path
import pytest

from phase9.manifest.parser import ManifestParser


@pytest.fixture
def parser():
    return ManifestParser()


def write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


@pytest.fixture
def write_manifest(tmp_path):
    def _write(name: str, data: dict):
        p = tmp_path / name
        write_json(p, data)
        return p

    return _write


@pytest.fixture
def simple_config(tmp_path):
    # minimal config-like object for logging tests
    log_dir = tmp_path / "logs"
    cfg = SimpleNamespace()
    cfg.logging = SimpleNamespace()
    cfg.logging.level = "INFO"
    cfg.logging.console = False
    cfg.logging.file = True
    cfg.logging.file_path = str(log_dir / "phase9.log")
    cfg.logging.max_bytes = 1024 * 10
    cfg.logging.backup_count = 1
    cfg.output = SimpleNamespace()
    cfg.output.artifacts_root = str(tmp_path / "artifacts")
    cfg.discovery = SimpleNamespace()
    cfg.discovery.phases = [6]
    return cfg
