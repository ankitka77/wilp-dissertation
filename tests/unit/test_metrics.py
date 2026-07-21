import math

from phase6.metrics import MetricsProvider


def test_topk_accuracy_and_precision_recall():
    preds = [[1, 2, 3], [2, 3, 4], [5, 6, 7]]
    targets = [2, 10, 7]
    k = 3
    acc = MetricsProvider.topk_accuracy(preds, targets, k)
    assert math.isclose(acc, 2 / 3)

    pr = MetricsProvider.topk_recall_precision(preds, targets, k)
    assert math.isclose(pr["recall"], acc)
    # precision = tp / (n*k)
    assert math.isclose(pr["precision"], (2) / (3 * k))
    # f1 should be between 0 and 1
    assert 0.0 <= pr["f1"] <= 1.0


def test_anomaly_score_and_batch_metrics():
    preds = [[1, 2], [3, 4]]
    probs = [[0.8, 0.2], [0.4, 0.6]]
    targets = [2, 99]
    k = 2
    score0 = MetricsProvider.anomaly_score_from_probs(probs[0])
    assert math.isclose(score0, 1 - 0.8)

    batch = MetricsProvider.batch_metrics(preds, probs, targets, k)
    assert "topk_accuracy" in batch and "avg_anomaly_score" in batch
    assert 0.0 <= batch["avg_anomaly_score"] <= 1.0
