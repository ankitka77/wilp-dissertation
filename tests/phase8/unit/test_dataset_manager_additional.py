from pathlib import Path
import pytest

from phase8.core.artifact_store import ArtifactStore, ArtifactStoreError
from phase8.core.dataset_manager import DatasetManager


def test_list_datasets_skips_dirs_without_manifest(tmp_path):
    root = tmp_path / "dsroot"
    store = ArtifactStore(root)
    mgr = DatasetManager(store)

    # create orphan directory without manifest
    (root / "orphan_ds").mkdir(parents=True, exist_ok=True)

    # register a real dataset
    mgr.register_dataset("dgood", "desc", {"source": "x"})

    datasets = mgr.list_datasets()
    ids = {d.dataset_id for d in datasets}
    assert "dgood" in ids
    assert "orphan_ds" not in ids


def test_register_dataset_propagates_artifactstore_error(tmp_path):
    class BrokenStore(ArtifactStore):
        def write_json(self, *args, **kwargs):
            raise ArtifactStoreError("io error")

    store = BrokenStore(tmp_path / "broken_ds")
    mgr = DatasetManager(store)
    with pytest.raises(ArtifactStoreError):
        mgr.register_dataset("bad", "desc", {"k": "v"})
