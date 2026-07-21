from phase6.inference import InferenceEngine
from phase6.config import Config
from phase6.types import PredictionResult
from phase6.persistence import InferenceError


class DummyModel:
    def __init__(self, topk_responses, prob_responses):
        self._topk = topk_responses
        self._probs = prob_responses

    def predict_topk(self, inputs, k):
        n = len(inputs) if inputs is not None else 0
        return self._topk[:n]

    def predict_probs(self, inputs):
        n = len(inputs) if inputs is not None else 0
        return self._probs[:n]


def make_test_loader():
    # Two batches: first with two examples, second with one.
    return [
        {"inputs": [[1, 2], [3, 4]], "ids": ["a", "b"]},
        {"inputs": [[5]], "ids": ["c"]},
    ]


def test_inference_happy_path():
    cfg = Config(top_k=2)
    model = DummyModel(topk_responses=[[1, 2], [3, 4], [5, 6]], prob_responses=[[0.1, 0.9], [0.6, 0.4], [0.8, 0.2]])
    engine = InferenceEngine(model_spec=None, config=cfg)
    result = engine.run(model, make_test_loader())
    assert isinstance(result, PredictionResult)
    assert result.meta["num_predictions"] == 3
    assert result.meta["top_k"] == 2
    # Each prediction should contain expected keys
    for pred in result.predictions:
        assert "topk" in pred and "probs" in pred and "anomaly_score" in pred


def test_inference_missing_methods():
    cfg = Config()

    class BadModel:
        pass

    engine = InferenceEngine(model_spec=None, config=cfg)
    try:
        engine.run(BadModel(), [])
        assert False, "InferenceError expected"
    except InferenceError:
        pass
