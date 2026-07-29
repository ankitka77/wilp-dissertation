import os
from pathlib import Path
import tempfile
import yaml

from phase9.config.loader import load_config
from phase9.config.settings import Phase9Settings


def test_load_default(tmp_path: Path):
    cfg = load_config()
    assert isinstance(cfg, Phase9Settings)


def test_load_from_file(tmp_path: Path):
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump({"logging": {"level": "DEBUG"}}))
    cfg = load_config(p)
    assert cfg.logging.level == "DEBUG"


def test_overrides(tmp_path: Path):
    cfg = load_config(overrides={"logging": {"level": "WARNING"}})
    assert cfg.logging.level == "WARNING"
