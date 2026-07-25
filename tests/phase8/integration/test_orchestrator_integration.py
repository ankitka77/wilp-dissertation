import io

import matplotlib
matplotlib.use("Agg")

from phase8.core.artifact_store import ArtifactStore
from phase8.core.experiment_manager import ExperimentManager
from phase8.core.dataset_manager import DatasetManager
from phase8.orchestrator import ExperimentOrchestrator


def _write_csv_bytes(store, dataset_id, name, values):
    data = "\n".join(str(int(v)) for v in values).encode("utf-8")
    store.write_artifact(dataset_id, name, data)


def _write_seq_bytes(store, dataset_id, name, sequences):
    # sequences is list of lists
    data = "\n".join(" ".join(str(int(x)) for x in seq) for seq in sequences).encode("utf-8")
    store.write_artifact(dataset_id, name, data)


def test_orchestrator_full_pipeline(tmp_path):
    store = ArtifactStore(tmp_path / "i1")
    exp = ExperimentManager(store)
    ds = DatasetManager(store)

    exp.create_experiment("i1_exp")
    ds.register_dataset("kd", "kpi dataset", {"source": "integration"})
    ds.register_dataset("dd", "deeplog dataset", {"source": "integration"})

    # write ground truth and predictions for KPI
    _write_csv_bytes(store, "kd", "ground_truth.csv", [1, 0, 1, 0])
    _write_csv_bytes(store, "kd", "predictions.csv", [1, 0, 0, 0])

    # write ground truth and predictions for DeepLog (sequences)
    _write_seq_bytes(store, "dd", "ground_truth.seq", [[1, 0], [0, 1]])
    _write_seq_bytes(store, "dd", "predictions.seq", [[1, 0], [1, 0]])

    orch = ExperimentOrchestrator(exp, ds, store)
    res = orch.run("i1_exp", "kd", "dd")

    assert res.status == "success"
    # report artifact should exist
    data = store.read_artifact("i1_exp", "report/experiment_report.pdf")
    assert data[:4] == b"%PDF"
