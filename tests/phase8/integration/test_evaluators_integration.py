from phase8.core.artifact_store import ArtifactStore
from phase8.core.experiment_manager import ExperimentManager
from phase8.core.dataset_manager import DatasetManager
from phase8.evaluators.kpi_evaluator import KPIEvaluator
from phase8.evaluators.deep_log_evaluator import DeepLogEvaluator


def test_kpi_and_deeplog_end_to_end(tmp_path):
    root = tmp_path / "p8"
    store = ArtifactStore(root)
    exp = ExperimentManager(store)
    ds = DatasetManager(store)

    # dataset for KPI
    ds.register_dataset("kpi_ds", "desc", {})
    store.write_artifact("kpi_ds", "ground_truth.csv", b"1\n0\n1\n")
    store.write_artifact("kpi_ds", "predictions.csv", b"1\n0\n1\n")

    # dataset for DeepLog
    ds.register_dataset("dl_ds", "desc", {})
    store.write_artifact("dl_ds", "ground_truth.seq", b"1 0\n1 0\n")
    store.write_artifact("dl_ds", "predictions.seq", b"1 0\n1 1\n")

    exp.create_experiment("ex_kpi")
    exp.create_experiment("ex_dl")

    kpi_eval = KPIEvaluator(exp, ds, store)
    dl_eval = DeepLogEvaluator(exp, ds, store)

    kres = kpi_eval.evaluate("ex_kpi", "kpi_ds")
    dres = dl_eval.evaluate("ex_dl", "dl_ds")

    # artifacts should be present
    assert store.read_json("ex_kpi", "evaluation/kpi_summary.json")["experiment_id"] == "ex_kpi"
    assert store.read_json("ex_dl", "evaluation/deeplog_summary.json")["experiment_id"] == "ex_dl"
