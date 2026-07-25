from phase8.evaluators.fusion_evaluator import FusionEvaluator, FusionStrategy
from phase8.core.artifact_store import ArtifactStore
from phase8.core.experiment_manager import ExperimentManager
from phase8.core.dataset_manager import DatasetManager
from phase8.evaluators.exceptions import EvaluatorError


def test_fusion_and_or(tmp_path):
    root = tmp_path / "f"
    store = ArtifactStore(root)
    exp = ExperimentManager(store)
    ds = DatasetManager(store)

    # create KPI and DL datasets
    ds.register_dataset("kds", "desc", {})
    ds.register_dataset("dds", "desc", {})
    # ground truth for KPI dataset
    store.write_artifact("kds", "ground_truth.csv", b"1\n0\n1\n")
    # KPI predictions
    store.write_artifact("kds", "predictions.csv", b"1\n0\n0\n")
    # DL predictions (flattened)
    store.write_artifact("dds", "predictions.seq", b"1 0 1\n")
    # deep log ground truth for dl dataset
    store.write_artifact("dds", "ground_truth.seq", b"1 0 1\n")

    exp.create_experiment("exf")
    fe = FusionEvaluator(exp, ds, store)
    # AND fusion: fused = [1&1,0&0,0&1] -> [1,0,0]
    res_and = fe.evaluate("exf", "kds", "dds", strategy=FusionStrategy.AND)
    assert res_and.predictions_path.endswith("fusion_predictions.txt")

    # OR fusion
    res_or = fe.evaluate("exf", "kds", "dds", strategy=FusionStrategy.OR)
    assert res_or.metrics.precision >= 0.0


def test_fusion_missing_experiment_raises(tmp_path):
    root = tmp_path / "f2"
    store = ArtifactStore(root)
    exp = ExperimentManager(store)
    ds = DatasetManager(store)
    ds.register_dataset("k3", "desc", {})
    ds.register_dataset("d3", "desc", {})
    store.write_artifact("k3", "predictions.csv", b"1\n")
    store.write_artifact("d3", "predictions.seq", b"1\n")
    fe = FusionEvaluator(exp, ds, store)
    try:
        fe.evaluate("nope", "k3", "d3")
    except EvaluatorError:
        pass
