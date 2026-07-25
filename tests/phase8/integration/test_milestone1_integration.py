import tempfile
from pathlib import Path

import pytest

from phase8.core.artifact_store import ArtifactStore
from phase8.core.experiment_manager import ExperimentManager
from phase8.core.dataset_manager import DatasetManager


def test_integration_create_experiment_and_dataset(tmp_path):
    root = tmp_path / "phase8"
    store = ArtifactStore(root)
    exp = ExperimentManager(store)
    ds = DatasetManager(store)

    m = ds.register_dataset("ds1", "desc", {"uri": "s3://bucket/key"})
    assert m.dataset_id == "ds1"

    e = exp.create_experiment("exp1", "desc")
    assert e.experiment_id == "exp1"

    # write artifact and read via store
    store.write_artifact("exp1", "outputs/x.txt", b"ok")
    data = store.read_artifact("exp1", "outputs/x.txt")
    assert data == b"ok"
