import json
from pathlib import Path

import pytest

from phase6 import config


def test_load_defaults_when_no_file(tmp_path: Path):
    loader = config.ConfigLoader(config_path=None)
    cfg = loader.load()
    assert cfg.learning_rate == 0.001
    assert cfg.batch_size == 256
    assert cfg.artifact_root.endswith("artifacts/phase6")


def test_load_from_json_file_and_overrides(tmp_path: Path):
    data = {"batch_size": 128, "learning_rate": 0.01}
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(data), encoding="utf-8")

    overrides = {"epochs": 5, "device": "cpu"}
    loader = config.ConfigLoader(config_path=p, overrides=overrides)
    cfg = loader.load()
    assert cfg.batch_size == 128
    assert cfg.learning_rate == 0.01
    assert cfg.epochs == 5


def test_invalid_values_raise_configuration_error(tmp_path: Path):
    data = {"batch_size": -10}
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    loader = config.ConfigLoader(config_path=p)
    with pytest.raises(config.ConfigurationError):
        loader.load()


def test_yaml_requires_pyyaml(tmp_path: Path, monkeypatch):
    p = tmp_path / "cfg.yaml"
    p.write_text("batch_size: 64\n", encoding="utf-8")
    # Simulate missing yaml module by making import('yaml') raise ImportError
    import builtins

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "yaml" or name.startswith("yaml."):
            raise ImportError("No module named yaml")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    loader = config.ConfigLoader(config_path=p)
    with pytest.raises(config.ConfigurationError):
        loader.load()
