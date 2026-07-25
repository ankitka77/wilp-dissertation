from pathlib import Path
import pytest

from phase8.core.artifact_store import ArtifactStore, ArtifactStoreError
from phase8.core.experiment_manager import ExperimentManager


def test_list_experiments_skips_dirs_without_metadata(tmp_path):
    root = tmp_path / "exps"
    store = ArtifactStore(root)
    mgr = ExperimentManager(store)

    # create a directory without metadata
    (root / "orphan").mkdir(parents=True, exist_ok=True)

    # create a valid experiment
    mgr.create_experiment("good", description="ok")

    experiments = mgr.list_experiments()
    ids = {e.experiment_id for e in experiments}
    assert "good" in ids
    assert "orphan" not in ids


def test_create_experiment_propagates_artifactstore_error(monkeypatch, tmp_path):
    # Create a fake ArtifactStore that raises on write_json
    class BrokenStore(ArtifactStore):
        def write_json(self, *args, **kwargs):
            raise ArtifactStoreError("disk full")

    store = BrokenStore(tmp_path / "broken")
    mgr = ExperimentManager(store)
    with pytest.raises(ArtifactStoreError):
        mgr.create_experiment("e-bad", description="will fail")
