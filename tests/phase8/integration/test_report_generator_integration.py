from phase8.core.artifact_store import ArtifactStore, ArtifactStoreError
from phase8.core.experiment_manager import ExperimentManager
from phase8.reporting.report_generator import ReportGenerator, REPORT_PDF, REPORT_METADATA
from phase8.reporting.exceptions import ReportGenerationError


def test_generate_report_success(tmp_path):
    store = ArtifactStore(tmp_path / "r1")
    exp = ExperimentManager(store)
    gen = ReportGenerator(exp, store)

    exp.create_experiment("r_exp")
    # create some evaluator and statistical artifacts
    store.write_json("r_exp", "evaluation/kpi_summary.json", {"precision": 0.8, "recall": 0.7, "f1": 0.75})
    store.write_json("r_exp", "analysis/statistics.json", {"metrics": {"precision": {"mean": 0.8, "count": 1}, "recall": {"mean": 0.7, "count": 1}, "f1": {"mean": 0.75, "count": 1}}})
    # create a small visualization PNG (reuse matplotlib)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import io

    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    store.write_artifact("r_exp", "visualization/sample.png", buf.read())

    model = gen.generate_report("r_exp")
    data = store.read_artifact("r_exp", REPORT_PDF)
    assert data[:4] == b"%PDF"
    meta = store.read_json("r_exp", REPORT_METADATA)
    assert meta["report"] == REPORT_PDF


def test_generate_report_missing_content_raises(tmp_path):
    store = ArtifactStore(tmp_path / "r2")
    exp = ExperimentManager(store)
    gen = ReportGenerator(exp, store)

    exp.create_experiment("r2_exp")
    try:
        gen.generate_report("r2_exp")
    except ReportGenerationError:
        return
    assert False, "Expected ReportGenerationError when no reportable artifacts"


def test_generate_report_write_failure_raises(tmp_path):
    class BrokenStore(ArtifactStore):
        def write_artifact(self, run_id: str, relative_path: str, data: bytes):
            if relative_path == REPORT_PDF:
                raise ArtifactStoreError("no space")
            return super().write_artifact(run_id, relative_path, data)

    store = BrokenStore(tmp_path / "r3")
    exp = ExperimentManager(store)
    gen = ReportGenerator(exp, store)

    exp.create_experiment("r3_exp")
    store.write_json("r3_exp", "evaluation/kpi_summary.json", {"precision": 0.5})
    store.write_json("r3_exp", "analysis/statistics.json", {"metrics": {"precision": {"mean": 0.5, "count": 1}}})
    try:
        gen.generate_report("r3_exp")
    except ReportGenerationError:
        return
    assert False, "Expected ReportGenerationError when report write fails"
