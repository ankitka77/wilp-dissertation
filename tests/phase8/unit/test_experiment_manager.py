from pathlib import Path
import pytest

from phase8.core.artifact_store import ArtifactStore
from phase8.core.experiment_manager import ExperimentManager, ExperimentExistsError, ExperimentNotFoundError


def test_create_and_get_metadata(tmp_path):
    root = tmp_path / "exps"
    store = ArtifactStore(root)
    mgr = ExperimentManager(store)
    meta = mgr.create_experiment("e1", description="desc")
    assert meta.experiment_id == "e1"
    loaded = mgr.get_metadata("e1")
    assert loaded.experiment_id == "e1"


def test_create_existing_raises(tmp_path):
    root = tmp_path / "exps2"
    store = ArtifactStore(root)
    mgr = ExperimentManager(store)
    mgr.create_experiment("e2")
    with pytest.raises(ExperimentExistsError):
        mgr.create_experiment("e2")


def test_get_missing_raises(tmp_path):
    root = tmp_path / "exps3"
    store = ArtifactStore(root)
    mgr = ExperimentManager(store)
    with pytest.raises(ExperimentNotFoundError):
        mgr.get_metadata("nope")
