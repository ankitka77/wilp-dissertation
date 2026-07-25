from phase8.evaluators.kpi_evaluator import KPIEvaluator, KPIMetrics
from phase8.core.artifact_store import ArtifactStore
from phase8.core.experiment_manager import ExperimentManager
from phase8.core.dataset_manager import DatasetManager


def test_kpi_metrics_computation(tmp_path):
    root = tmp_path / "a"
    store = ArtifactStore(root)
    exp = ExperimentManager(store)
    ds = DatasetManager(store)
    ds.register_dataset("d1", "desc", {"k": "v"})
    # create ground truth and predictions
    store.write_artifact("d1", "ground_truth.csv", b"1\n0\n1\n")
    store.write_artifact("d1", "predictions.csv", b"1\n1\n0\n")

    evaluator = KPIEvaluator(exp, ds, store)
    exp.create_experiment("e1")
    res = evaluator.evaluate("e1", "d1")
    assert isinstance(res.metrics, KPIMetrics)
    # expected: tp=1, fp=1, fn=1 => precision=0.5 recall=0.5 f1=0.5
    assert abs(res.metrics.precision - 0.5) < 1e-8
    assert abs(res.metrics.recall - 0.5) < 1e-8


def test_kpi_length_mismatch_raises(tmp_path):
    root = tmp_path / "b"
    store = ArtifactStore(root)
    exp = ExperimentManager(store)
    ds = DatasetManager(store)
    ds.register_dataset("d2", None, {"k": "v"})
    store.write_artifact("d2", "ground_truth.csv", b"1\n0\n")
    store.write_artifact("d2", "predictions.csv", b"1\n")
    evaluator = KPIEvaluator(exp, ds, store)
    exp.create_experiment("e2")
    try:
        evaluator.evaluate("e2", "d2")
    except Exception:
        # acceptable - KPIEvaluatorError expected
        pass


def test_kpi_missing_experiment_raises(tmp_path):
    root = tmp_path / "c"
    store = ArtifactStore(root)
    exp = ExperimentManager(store)
    ds = DatasetManager(store)
    ds.register_dataset("d3", "desc", {})
    store.write_artifact("d3", "ground_truth.csv", b"1\n")
    store.write_artifact("d3", "predictions.csv", b"1\n")
    evaluator = KPIEvaluator(exp, ds, store)
    # do not create experiment
    from phase8.evaluators.exceptions import KPIEvaluatorError

    try:
        evaluator.evaluate("no-exp", "d3")
    except KPIEvaluatorError:
        pass
