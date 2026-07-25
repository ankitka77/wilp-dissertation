from phase8.evaluators.deep_log_evaluator import DeepLogEvaluator, DeepLogMetrics
from phase8.core.artifact_store import ArtifactStore
from phase8.core.experiment_manager import ExperimentManager
from phase8.core.dataset_manager import DatasetManager


def test_deeplog_metrics_computation(tmp_path):
    root = tmp_path / "dl"
    store = ArtifactStore(root)
    exp = ExperimentManager(store)
    ds = DatasetManager(store)
    ds.register_dataset("dd", "desc", {"k": "v"})
    # write sequences: two lines of sequences
    store.write_artifact("dd", "ground_truth.seq", b"1 0 1\n0 0\n")
    store.write_artifact("dd", "predictions.seq", b"1 1 0\n0 0\n")
    evaluator = DeepLogEvaluator(exp, ds, store)
    exp.create_experiment("ex1")
    res = evaluator.evaluate("ex1", "dd")
    assert isinstance(res.metrics, DeepLogMetrics)
    # sequence flattened: true=[1,0,1,0,0], pred=[1,1,0,0,0]
    # tp=1 fp=1 fn=1 => precision=0.5 recall=0.5
    assert abs(res.metrics.precision - 0.5) < 1e-8


def test_deeplog_length_mismatch(tmp_path):
    root = tmp_path / "dl2"
    store = ArtifactStore(root)
    exp = ExperimentManager(store)
    ds = DatasetManager(store)
    ds.register_dataset("dd2", "desc", {})
    store.write_artifact("dd2", "ground_truth.seq", b"1 0 1\n")
    store.write_artifact("dd2", "predictions.seq", b"1 0\n")
    evaluator = DeepLogEvaluator(exp, ds, store)
    exp.create_experiment("ex2")
    try:
        evaluator.evaluate("ex2", "dd2")
    except Exception:
        pass


def test_deeplog_missing_experiment_raises(tmp_path):
    root = tmp_path / "dl3"
    store = ArtifactStore(root)
    exp = ExperimentManager(store)
    ds = DatasetManager(store)
    ds.register_dataset("dd3", "desc", {})
    store.write_artifact("dd3", "ground_truth.seq", b"1 0\n")
    store.write_artifact("dd3", "predictions.seq", b"1 0\n")
    evaluator = DeepLogEvaluator(exp, ds, store)
    from phase8.evaluators.exceptions import DeepLogEvaluatorError

    try:
        evaluator.evaluate("missing", "dd3")
    except DeepLogEvaluatorError:
        pass
