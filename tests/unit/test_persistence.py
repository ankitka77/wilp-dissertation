from pathlib import Path

from phase6.persistence import PersistenceManager
from phase6.config import Config
from phase6.types import CheckpointType, ModelMetadata


def test_save_and_load_model(tmp_path):
    exp = tmp_path / "exp"
    cfg = Config(max_checkpoints=5)
    pm = PersistenceManager(experiment_path=exp, config=cfg)

    model_obj = {"weights": [1, 2, 3]}
    metadata = {
        "model_name": "test",
        "version": "v1",
        "created_on": "2020-01-01T00:00:00Z",
        "model_spec": {},
        "training_summary_ref": "ref",
        "artifact_path": "",
        "git": {},
        "config_snapshot": {},
        "checksum": "",
    }

    info = pm.save_model(model_obj, metadata=metadata, checkpoint_type=CheckpointType.INTERMEDIATE)
    assert Path(info.path).exists()
    assert Path(info.metadata_path).exists()

    loaded_obj, loaded_meta = pm.load_model(info.path)
    assert loaded_obj == model_obj
    assert isinstance(loaded_meta, ModelMetadata)


def test_prune_checkpoints(tmp_path):
    exp = tmp_path / "exp"
    cfg = Config(max_checkpoints=1)
    pm = PersistenceManager(experiment_path=exp, config=cfg)

    model_obj = {"a": 1}
    metadata = {"model_name": "t", "version": "v", "created_on": "2020-01-01T00:00:00Z", "model_spec": {}, "training_summary_ref": "r", "artifact_path": "", "git": {}, "config_snapshot": {}, "checksum": ""}

    pm.save_model(model_obj, metadata=metadata, checkpoint_type=CheckpointType.INTERMEDIATE)
    pm.save_model(model_obj, metadata=metadata, checkpoint_type=CheckpointType.INTERMEDIATE)

    cps = pm.list_checkpoints()
    assert len(cps) <= 1
