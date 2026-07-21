import pytest

from phase6.config import Config
from phase6.model_spec import ModelSpecFactory, ModelSpec
from phase6.config import ConfigurationError


def test_create_model_spec_success():
    cfg = Config()
    factory = ModelSpecFactory(cfg)
    overrides = {"vocab_size": 100, "sequence_length": 50}
    spec = factory.create_model_spec(overrides)
    assert isinstance(spec, ModelSpec)
    assert spec.vocab_size == 100
    assert spec.sequence_length == 50


def test_create_model_spec_missing_dataset_metadata():
    cfg = Config()
    factory = ModelSpecFactory(cfg)
    with pytest.raises(ConfigurationError):
        factory.create_model_spec({})


def test_create_model_spec_invalid_values():
    cfg = Config()
    factory = ModelSpecFactory(cfg)
    with pytest.raises(ConfigurationError):
        factory.create_model_spec({"vocab_size": 0, "sequence_length": 10})


def test_create_model_spec_unsupported_rnn_type():
    cfg = Config()
    factory = ModelSpecFactory(cfg)
    with pytest.raises(ConfigurationError):
        factory.create_model_spec({"vocab_size": 10, "sequence_length": 10, "rnn_type": "GRU"})
