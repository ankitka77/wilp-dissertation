from phase8.core.artifact_store import ArtifactStore
from phase8.core.experiment_manager import ExperimentManager
from phase8.core.dataset_manager import DatasetManager
from phase8.evaluators.fusion_evaluator import FusionEvaluator


def test_fusion_integration_end_to_end(tmp_path):
    root = tmp_path / "fi"
    store = ArtifactStore(root)
    exp = ExperimentManager(store)
    ds = DatasetManager(store)

    # register datasets
    ds.register_dataset("kpi_ds", "desc", {})
    ds.register_dataset("dl_ds", "desc", {})

    # write ground truth and predictions
    store.write_artifact("kpi_ds", "ground_truth.csv", b"1\n0\n1\n")
    store.write_artifact("kpi_ds", "predictions.csv", b"1\n1\n0\n")
    store.write_artifact("dl_ds", "predictions.seq", b"1 0 1\n")
    # deep log ground truth (flattened to match KPI length)
    store.write_artifact("dl_ds", "ground_truth.seq", b"1 0 1\n")

    exp.create_experiment("fusion_ex")
    fe = FusionEvaluator(exp, ds, store)
    res = fe.evaluate("fusion_ex", "kpi_ds", "dl_ds")

    # verify artifacts
    summary = store.read_json("fusion_ex", "evaluation/fusion_summary.json")
    assert summary["experiment_id"] == "fusion_ex"
