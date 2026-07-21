import dataclasses
import json
import pytest

from phase6 import types


def test_enums_exist_and_values():
    assert types.TrainingStatus.NOT_STARTED.name == "NOT_STARTED"
    assert types.CheckpointType.FINAL.value == "FINAL"
    assert types.DecisionReason.SCORE_THRESHOLD.value == "SCORE_THRESHOLD"


def test_modelspect_immutable():
    spec = types.ModelSpec(
        vocab_size=10,
        embedding_dim=16,
        hidden_size=32,
        num_layers=1,
        dropout=0.1,
        rnn_type="LSTM",
        output_type="softmax",
        sequence_length=50,
        top_k=5,
        pad_token=0,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.vocab_size = 20


def test_phase5inputs_fields_and_mutability():
    vocab = {"tA": 1, "tB": 2}
    event_map = {1: "tA", 2: "tB"}
    p5 = types.Phase5Inputs(vocabulary=vocab, event_id_map=event_map, train_df=None, test_df=None, dataset_name="dset")
    assert p5.vocabulary is vocab
    assert p5.dataset_name == "dset"
    # mutable container
    p5.vocabulary["tC"] = 3
    assert p5.vocabulary["tC"] == 3


def test_manifestinfo_serializable():
    manifest = types.ManifestInfo(
        manifest_version="1.0",
        generated_on="2026-07-18T00:00:00Z",
        phase="phase6_deeplog",
        inputs={"vocabulary": "path/to/vocab.json"},
        artifacts={"predictions_csv": "path/to/predictions.csv"},
        model_spec={"vocab_size": 10},
        model_metadata={"model_name": "m"},
        training_summary={"epochs": 1},
        git={"branch": "main", "commit": "abc"},
        config_snapshot={"batch_size": 32},
        experiment_id="exp-1",
        notes=None,
        status="COMPLETED",
        warnings=[],
    )
    as_dict = dataclasses.asdict(manifest)
    json_str = json.dumps(as_dict)
    assert "phase6_deeplog" in json_str


def test_prediction_confidence_and_persistenceinfo():
    pc = types.PredictionConfidence(confidence_score=0.75, method="prob_sum")
    assert 0.0 <= pc.confidence_score <= 1.0
    pi = types.PersistenceInfo(
        path="artifacts/phase6/models/m.bin",
        metadata_path="artifacts/phase6/models/m.metadata.json",
        checksum="deadbeef",
        created_on="2026-07-18T00:00:00Z",
        checkpoint_type=types.CheckpointType.BEST,
    )
    assert pi.checkpoint_type == types.CheckpointType.BEST
