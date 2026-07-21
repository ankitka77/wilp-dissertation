from pathlib import Path

from phase6.visualizer import Visualizer, VisualizerError
from phase6.types import ExperimentInfo, TrainingResult, DecisionResult
from phase6.config import Config


def make_experiment_info(tmp_path: Path) -> ExperimentInfo:
    exp_dir = tmp_path / "expviz"
    reports = exp_dir / "reports"
    manifests = exp_dir / "manifests"
    models = exp_dir / "models"
    plots = exp_dir / "plots"
    for p in (reports, manifests, models, plots):
        p.mkdir(parents=True, exist_ok=True)
    return ExperimentInfo(experiment_id="expviz", path=str(exp_dir), models_path=str(models), reports_path=str(reports), plots_path=str(plots), manifests_path=str(manifests), created_on="2026-01-01T00:00:00Z")


def test_plot_training_metrics(tmp_path: Path):
    exp = make_experiment_info(tmp_path)
    viz = Visualizer(experiment_info=exp, config=Config())
    tr = TrainingResult(status=None, epoch_metrics=[{"epoch": 1, "loss": 0.5, "topk_accuracy": 0.2}, {"epoch": 2, "loss": 0.4, "topk_accuracy": 0.3}], final_checkpoint=None, best_checkpoint=None, num_epochs_run=2)
    paths = viz.plot_training_metrics(tr)
    assert isinstance(paths, list)
    assert all(Path(p).exists() for p in paths)


def test_plot_predictions_summary(tmp_path: Path):
    exp = make_experiment_info(tmp_path)
    viz = Visualizer(experiment_info=exp, config=Config())
    decisions = [
        {"index": 0, "id": "a", "confidence": {"confidence_score": 0.9}},
        {"index": 1, "id": "b", "confidence": {"confidence_score": 0.1}},
    ]
    dr = DecisionResult(predictions_ref="p", decisions=decisions)
    out = viz.plot_predictions_summary(dr, top_n=2)
    assert Path(out).exists()


def test_plot_predictions_summary_invalid_input(tmp_path: Path):
    exp = make_experiment_info(tmp_path)
    viz = Visualizer(experiment_info=exp, config=Config())
    try:
        viz.plot_predictions_summary("bad")
        assert False, "VisualizerError expected"
    except VisualizerError:
        pass
