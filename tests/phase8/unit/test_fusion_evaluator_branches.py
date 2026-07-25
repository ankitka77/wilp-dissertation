import collections
from phase8.evaluators.fusion_evaluator import FusionEvaluator, FusionStrategy, FUSION_PREDICTIONS, FUSION_SUMMARY
from phase8.core.artifact_store import ArtifactStore, ArtifactStoreError
from phase8.core.experiment_manager import ExperimentManager
from phase8.core.dataset_manager import DatasetManager
from phase8.evaluators.exceptions import EvaluatorError


def test_prediction_length_mismatch_between_datasets(tmp_path):
    root = tmp_path / "lm"
    store = ArtifactStore(root)
    exp = ExperimentManager(store)
    ds = DatasetManager(store)

    # KPI dataset: 3-length
    ds.register_dataset("kpi_len", "desc", {})
    store.write_artifact("kpi_len", "ground_truth.csv", b"1\n0\n1\n")
    store.write_artifact("kpi_len", "predictions.csv", b"1\n0\n0\n")

    # DL dataset: 2-length (valid internally)
    ds.register_dataset("dl_len", "desc", {})
    store.write_artifact("dl_len", "ground_truth.seq", b"1 0\n")
    store.write_artifact("dl_len", "predictions.seq", b"1 0\n")

    exp.create_experiment("ex_len")
    fe = FusionEvaluator(exp, ds, store)
    try:
        fe.evaluate("ex_len", "kpi_len", "dl_len")
    except EvaluatorError:
        # expected prediction length mismatch
        pass


def test_write_fusion_predictions_failure(tmp_path):
    root = tmp_path / "wf"

    class BrokenWriteStore(ArtifactStore):
        def write_artifact(self, run_id: str, relative_path: str, data: bytes):
            if relative_path == FUSION_PREDICTIONS:
                raise ArtifactStoreError("disk full")
            return super().write_artifact(run_id, relative_path, data)

    store = BrokenWriteStore(root)
    exp = ExperimentManager(store)
    ds = DatasetManager(store)

    ds.register_dataset("kpi_w", "d", {})
    ds.register_dataset("dl_w", "d", {})
    store.write_artifact("kpi_w", "ground_truth.csv", b"1\n")
    store.write_artifact("kpi_w", "predictions.csv", b"1\n")
    store.write_artifact("dl_w", "predictions.seq", b"1\n")
    store.write_artifact("dl_w", "ground_truth.seq", b"1\n")

    exp.create_experiment("ex_w")
    fe = FusionEvaluator(exp, ds, store)
    try:
        fe.evaluate("ex_w", "kpi_w", "dl_w")
    except EvaluatorError:
        pass


def test_transient_read_failure_during_predictions(tmp_path):
    root = tmp_path / "tr"

    class TransientReadStore(ArtifactStore):
        def __init__(self, root):
            super().__init__(root)
            self.counts = collections.Counter()

        def read_artifact(self, run_id: str, relative_path: str) -> bytes:
            key = (run_id, relative_path)
            self.counts[key] += 1
            if self.counts[key] > 1:
                raise ArtifactStoreError("transient IO")
            return super().read_artifact(run_id, relative_path)

    store = TransientReadStore(root)
    exp = ExperimentManager(store)
    ds = DatasetManager(store)

    ds.register_dataset("kpi_t", "d", {})
    ds.register_dataset("dl_t", "d", {})
    store.write_artifact("kpi_t", "ground_truth.csv", b"1\n")
    store.write_artifact("kpi_t", "predictions.csv", b"1\n")
    store.write_artifact("dl_t", "predictions.seq", b"1\n")
    store.write_artifact("dl_t", "ground_truth.seq", b"1\n")

    exp.create_experiment("ex_t")
    fe = FusionEvaluator(exp, ds, store)
    try:
        fe.evaluate("ex_t", "kpi_t", "dl_t")
    except EvaluatorError:
        # expected because second read (during fusion) fails
        pass


def test_failed_read_ground_truth_after_fusion(tmp_path):
    root = tmp_path / "gr"

    class ReadGTFailStore(ArtifactStore):
        def read_artifact(self, run_id: str, relative_path: str) -> bytes:
            # allow initial reads; fail only when reading ground_truth.csv during final metric step
            if relative_path == "ground_truth.csv" and getattr(self, "_allow_first", True) is False:
                raise ArtifactStoreError("no GT")
            # flip flag after first call
            if relative_path == "ground_truth.csv":
                setattr(self, "_allow_first", False)
            return super().read_artifact(run_id, relative_path)

    store = ReadGTFailStore(root)
    exp = ExperimentManager(store)
    ds = DatasetManager(store)

    ds.register_dataset("kpi_g", "d", {})
    ds.register_dataset("dl_g", "d", {})
    store.write_artifact("kpi_g", "ground_truth.csv", b"1\n")
    store.write_artifact("kpi_g", "predictions.csv", b"1\n")
    store.write_artifact("dl_g", "predictions.seq", b"1\n")
    store.write_artifact("dl_g", "ground_truth.seq", b"1\n")

    exp.create_experiment("ex_g")
    fe = FusionEvaluator(exp, ds, store)
    try:
        fe.evaluate("ex_g", "kpi_g", "dl_g")
    except EvaluatorError:
        pass


def test_write_summary_failure(tmp_path):
    root = tmp_path / "ws"

    class BrokenSummaryStore(ArtifactStore):
        def write_json(self, run_id: str, relative_path: str, obj):
            if relative_path == FUSION_SUMMARY:
                raise ArtifactStoreError("no space")
            return super().write_json(run_id, relative_path, obj)

    store = BrokenSummaryStore(root)
    exp = ExperimentManager(store)
    ds = DatasetManager(store)

    ds.register_dataset("kpi_s", "d", {})
    ds.register_dataset("dl_s", "d", {})
    store.write_artifact("kpi_s", "ground_truth.csv", b"1\n")
    store.write_artifact("kpi_s", "predictions.csv", b"1\n")
    store.write_artifact("dl_s", "predictions.seq", b"1\n")
    store.write_artifact("dl_s", "ground_truth.seq", b"1\n")

    exp.create_experiment("ex_s")
    fe = FusionEvaluator(exp, ds, store)
    try:
        fe.evaluate("ex_s", "kpi_s", "dl_s")
    except EvaluatorError:
        pass


def test_empty_predictions_produces_zero_metrics(tmp_path):
    root = tmp_path / "empty"
    store = ArtifactStore(root)
    exp = ExperimentManager(store)
    ds = DatasetManager(store)

    ds.register_dataset("kpi_e", "d", {})
    ds.register_dataset("dl_e", "d", {})
    store.write_artifact("kpi_e", "ground_truth.csv", b"")
    store.write_artifact("kpi_e", "predictions.csv", b"")
    store.write_artifact("dl_e", "predictions.seq", b"")
    store.write_artifact("dl_e", "ground_truth.seq", b"")

    exp.create_experiment("ex_e")
    fe = FusionEvaluator(exp, ds, store)
    res = fe.evaluate("ex_e", "kpi_e", "dl_e")
    assert res.metrics.precision == 0.0
    assert res.metrics.recall == 0.0
