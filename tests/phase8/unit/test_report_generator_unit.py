import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from phase8.core.artifact_store import ArtifactStore, ArtifactStoreError
from phase8.core.experiment_manager import ExperimentManager
from phase8.reporting.report_generator import ReportGenerator, REPORT_PDF, REPORT_METADATA, STATISTICS_PATH
from phase8.reporting.exceptions import ReportGenerationError


def _make_sample_png_bytes():
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def test_build_report_model_experiment_not_found(tmp_path):
    store = ArtifactStore(tmp_path / "u1")
    exp = ExperimentManager(store)
    gen = ReportGenerator(exp, store)

    try:
        gen.build_report_model("no_such_exp")
    except ReportGenerationError:
        return
    assert False, "Expected ReportGenerationError for missing experiment"


def test_generate_report_with_corrupted_visualization(tmp_path):
    store = ArtifactStore(tmp_path / "u2")
    exp = ExperimentManager(store)
    gen = ReportGenerator(exp, store)

    exp.create_experiment("u2_exp")
    store.write_json("u2_exp", "evaluation/kpi_summary.json", {"precision": 0.6})
    store.write_json("u2_exp", "analysis/statistics.json", {"metrics": {"precision": {"mean": 0.6, "count": 1}}})
    # write a corrupted visualization (not a PNG)
    store.write_artifact("u2_exp", "visualization/broken.png", b"not a png")

    model = gen.generate_report("u2_exp")
    data = store.read_artifact("u2_exp", REPORT_PDF)
    assert data[:4] == b"%PDF"
    meta = store.read_json("u2_exp", REPORT_METADATA)
    assert meta["report"] == REPORT_PDF


def test_read_json_safe_handles_store_errors(tmp_path):
    class BrokenReadStore(ArtifactStore):
        def read_json(self, run_id: str, relative_path: str):
            if relative_path == STATISTICS_PATH:
                raise ArtifactStoreError("boom")
            return super().read_json(run_id, relative_path)

    store = BrokenReadStore(tmp_path / "u3")
    exp = ExperimentManager(store)
    gen = ReportGenerator(exp, store)

    exp.create_experiment("u3_exp")
    # write only KPI summary; statistics read will raise and should be treated as missing
    store.write_json("u3_exp", "evaluation/kpi_summary.json", {"precision": 0.9})

    model = gen.build_report_model("u3_exp")
    # statistics should be an empty mapping in the model
    assert model.statistical_summary == {}
