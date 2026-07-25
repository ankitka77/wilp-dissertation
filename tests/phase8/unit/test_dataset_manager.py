from pathlib import Path
import pytest

from phase8.core.artifact_store import ArtifactStore
from phase8.core.dataset_manager import DatasetManager, DatasetExistsError, DatasetNotFoundError


def test_register_and_get(tmp_path):
    root = tmp_path / "ds"
    store = ArtifactStore(root)
    mgr = DatasetManager(store)
    m = mgr.register_dataset("d1", "desc", {"type": "csv"})
    assert m.dataset_id == "d1"
    loaded = mgr.get_manifest("d1")
    assert loaded.dataset_id == "d1"


def test_register_existing_raises(tmp_path):
    root = tmp_path / "ds2"
    store = ArtifactStore(root)
    mgr = DatasetManager(store)
    mgr.register_dataset("d2", None, {"type": "csv"})
    with pytest.raises(DatasetExistsError):
        mgr.register_dataset("d2", None, {"type": "csv"})


def test_get_missing_raises(tmp_path):
    root = tmp_path / "ds3"
    store = ArtifactStore(root)
    mgr = DatasetManager(store)
    with pytest.raises(DatasetNotFoundError):
        mgr.get_manifest("nope")
