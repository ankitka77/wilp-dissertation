import copy
import pytest

from phase9.manifest.adapter import ManifestAdapter, ManifestAdapterError


def canonical_sample():
    return {
        "manifest_version": "1.0",
        "phase": 6,
        "artifacts": [{"id": "m1", "relative_path": "a/b/file.txt", "type": "model"}],
        "generated_timestamp": "2020-01-01T00:00:00Z",
        "experiment_id": "exp-1",
    }


def legacy_phase6_sample():
    return {
        "manifest_version": "1.0",
        "generated_on": "2020-01-01T00:00:00Z",
        "phase": "phase6",
        "artifacts": {
            "file1": {"path": "models/file1.pt", "type": "model", "producer": "train"}
        },
        "training_summary": {"steps": 100},
        "model_spec": {"framework": "pytorch"},
        "config_snapshot": {"lr": 0.001},
        "git": {"commit": "abc123"},
        "experiment_id": "exp-legacy",
        "warnings": ["w1"],
        "notes": "legacy run",
    }


def test_adapter_idempotent_on_canonical():
    data = canonical_sample()
    out = ManifestAdapter.canonicalize(copy.deepcopy(data))
    assert out["phase"] == data["phase"]
    assert out["artifacts"] == data["artifacts"]


def test_adapter_converts_legacy_phase6_and_preserves_fields():
    legacy = legacy_phase6_sample()
    out = ManifestAdapter.canonicalize(legacy)
    assert out["generated_timestamp"] == legacy["generated_on"]
    assert out["phase"] == 6
    assert isinstance(out["artifacts"], list)
    assert any(a["relative_path"].endswith("models/file1.pt") for a in out["artifacts"])
    # preserved fields should be present in generator
    assert "training_summary" in out.get("generator", {}) or "training_summary" in legacy


def test_adapter_raises_when_missing_phase():
    bad = {"artifacts": []}
    with pytest.raises(ManifestAdapterError):
        ManifestAdapter.canonicalize(bad)
