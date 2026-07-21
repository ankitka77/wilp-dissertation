import json
from pathlib import Path

from phase6.report_generator import ReportGenerator
from phase6.types import ExperimentInfo, TrainingResult, DecisionResult, ManifestInfo
from phase6.config import Config


def make_experiment_info(tmp_path: Path) -> ExperimentInfo:
    exp_dir = tmp_path / "exp"
    reports = exp_dir / "reports"
    manifests = exp_dir / "manifests"
    models = exp_dir / "models"
    plots = exp_dir / "plots"
    for p in (reports, manifests, models, plots):
        p.mkdir(parents=True, exist_ok=True)
    return ExperimentInfo(experiment_id="exp1", path=str(exp_dir), models_path=str(models), reports_path=str(reports), plots_path=str(plots), manifests_path=str(manifests), created_on="2026-01-01T00:00:00Z")


def test_write_training_metrics(tmp_path: Path):
    exp = make_experiment_info(tmp_path)
    rg = ReportGenerator(experiment_info=exp, config=Config())

    tr = TrainingResult(status=None, epoch_metrics=[{"epoch": 1, "loss": 0.5}], final_checkpoint=None, best_checkpoint=None, num_epochs_run=1)
    p = rg.write_training_metrics(tr)
    assert Path(p).exists()
    with Path(p).open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["num_epochs_run"] == 1


def test_write_predictions_and_manifest(tmp_path: Path):
    exp = make_experiment_info(tmp_path)
    rg = ReportGenerator(experiment_info=exp, config=Config())

    decisions = [
        {"index": 0, "id": "a", "is_anomaly": False, "reason": "NOT_APPLICABLE", "confidence": {"confidence_score": 0.9, "method": "max_prob"}},
        {"index": 1, "id": "b", "is_anomaly": True, "reason": "SCORE_THRESHOLD", "confidence": {"confidence_score": 0.2, "method": "max_prob"}},
    ]
    dr = DecisionResult(predictions_ref="preds", decisions=decisions)
    p = rg.write_predictions(dr)
    assert Path(p).exists()
    # CSV should contain header and two rows
    with Path(p).open("r", encoding="utf-8") as fh:
        content = fh.read()
    assert "index" in content
    assert "a" in content and "b" in content

    manifest = ManifestInfo(manifest_version="1.0", generated_on="2026-01-01T00:00:00Z", phase="phase6", inputs={}, artifacts={}, model_spec={}, model_metadata={}, training_summary={}, git={}, config_snapshot={}, experiment_id="exp1")
    mpath = rg.write_manifest(manifest)
    assert Path(mpath).exists()
    with Path(mpath).open("r", encoding="utf-8") as fh:
        m = json.load(fh)
    assert m["phase"] == "phase6"


def test_write_experiment_summary(tmp_path: Path):
    exp = make_experiment_info(tmp_path)
    rg = ReportGenerator(experiment_info=exp, config=Config())
    summary = {"a": 1}
    p = rg.write_experiment_summary(summary)
    assert Path(p).exists()
    with Path(p).open("r", encoding="utf-8") as fh:
        s = json.load(fh)
    assert s == summary
