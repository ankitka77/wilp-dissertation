from phase6.decision_engine import DecisionEngine, DecisionEngineError
from phase6.config import Config
from phase6.types import PredictionResult


def make_prediction_result():
    preds = [
        {"probs": [0.9, 0.1], "anomaly_score": 0.1, "id": "a"},
        {"probs": [0.2, 0.8], "anomaly_score": 0.6, "id": "b"},
        {"probs": [0.4, 0.6], "anomaly_score": 0.5, "id": "c"},
        # entry without probs exercises fallback confidence
        {"anomaly_score": 0.3, "id": "d"},
    ]
    meta = {"predictions_ref": "test_preds"}
    return PredictionResult(predictions=preds, meta=meta)


def test_decision_engine_happy_path():
    cfg = Config(threshold=0.5)
    engine = DecisionEngine(config=cfg)
    pr = make_prediction_result()
    result = engine.decide(pr)
    assert result.predictions_ref == "test_preds"
    assert len(result.decisions) == 4
    # First: anomaly_score 0.1 -> not anomaly
    assert result.decisions[0]["is_anomaly"] is False
    # Second: 0.6 -> anomaly
    assert result.decisions[1]["is_anomaly"] is True
    # Third: 0.5 -> anomaly (inclusive)
    assert result.decisions[2]["is_anomaly"] is True
    # Fourth: has no probs, confidence should be derived
    conf = result.decisions[3]["confidence"]
    assert conf["method"] == "anomaly_inverse"


def test_decision_engine_missing_threshold_and_override():
    # When no threshold configured, provide it explicitly
    cfg = Config(threshold=None)
    engine = DecisionEngine(config=cfg)
    pr = make_prediction_result()
    result = engine.decide(pr, threshold=0.5)
    assert isinstance(result.predictions_ref, str)


def test_decision_engine_errors():
    cfg = Config(threshold=None)
    engine = DecisionEngine(config=cfg)
    try:
        engine.decide("not a prediction result")
        assert False, "DecisionEngineError expected"
    except DecisionEngineError:
        pass
