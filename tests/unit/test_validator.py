from phase6.validator import Validator, ValidationError
from phase6.config import Config
from phase6.types import ValidationResult


class DummyModel:
    def __init__(self, topk_responses, prob_responses):
        self._topk = topk_responses
        self._probs = prob_responses

    def predict_topk(self, inputs, k):
        # Return a slice matching the batch size
        n = len(inputs) if inputs is not None else 0
        return self._topk[:n]

    def predict_probs(self, inputs):
        n = len(inputs) if inputs is not None else 0
        return self._probs[:n]


def make_val_loader():
    # Create two batches
    batch1 = {"inputs": [[1, 2], [3, 4]], "targets": [2, 99]}
    batch2 = {"inputs": [[5]], "targets": [5]}
    return [batch1, batch2]


def test_validator_happy_path():
    cfg = Config(top_k=2)
    val_loader = make_val_loader()

    # Dummy model returns predictions matching targets for some examples
    topk = [[1, 2], [3, 4], [5, 6]]
    probs = [[0.1, 0.9], [0.6, 0.4], [0.8, 0.2]]
    model = DummyModel(topk_responses=topk, prob_responses=probs)

    validator = Validator(config=cfg)
    result = validator.validate(model, val_loader)
    assert isinstance(result, ValidationResult)
    assert isinstance(result.metrics_time_series, list)


def test_validator_missing_methods():
    cfg = Config()

    class BadModel:
        pass

    validator = Validator(config=cfg)
    try:
        validator.validate(BadModel(), [])
        assert False, "ValidationError expected"
    except ValidationError:
        pass
