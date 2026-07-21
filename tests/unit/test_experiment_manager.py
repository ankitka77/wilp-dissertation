import json
import logging
from pathlib import Path

import pytest

from phase6.config import Config
from phase6.experiment_manager import ExperimentManager, ExperimentError


def test_start_and_finalize_experiment(tmp_path):
    cfg = Config(experiment_root=str(tmp_path / "experiments"))
    logger = logging.getLogger("project.test_experiment_manager")
    manager = ExperimentManager(root=Path(cfg.experiment_root), config=cfg, logger=logger)

    info = manager.start_experiment(name="unit-test")

    # Ensure directories were created
    assert Path(info.path).exists()
    assert Path(info.models_path).exists()
    assert Path(info.reports_path).exists()
    assert Path(info.plots_path).exists()
    assert Path(info.manifests_path).exists()

    summary = {"status": "ok", "count": 1}
    manifest_path = manager.finalize_experiment(info, summary)
    assert Path(manifest_path).exists()

    # Validate manifest contents
    with open(manifest_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    assert data == summary


def test_start_experiment_creation_failure(tmp_path):
    # Simulate a file where a directory should be to trigger failure
    bad_root = tmp_path / "experiments"
    bad_root.write_text("i am a file, not a directory")

    cfg = Config(experiment_root=str(bad_root))
    logger = logging.getLogger("project.test_experiment_manager")
    manager = ExperimentManager(root=Path(cfg.experiment_root), config=cfg, logger=logger)

    with pytest.raises(ExperimentError):
        manager.start_experiment(name="will-fail")


def test_finalize_raises_when_missing_manifest_dir(tmp_path):
    cfg = Config(experiment_root=str(tmp_path / "experiments"))
    logger = logging.getLogger("project.test_experiment_manager")
    manager = ExperimentManager(root=Path(cfg.experiment_root), config=cfg, logger=logger)

    # Construct a fake ExperimentInfo-like object with a non-existent manifests_path
    class FakeInfo:
        experiment_id = "nope"
        manifests_path = str(tmp_path / "does_not_exist")

    fake = FakeInfo()
    with pytest.raises(ExperimentError):
        manager.finalize_experiment(fake, {"a": 1})
