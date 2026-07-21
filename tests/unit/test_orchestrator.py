from pathlib import Path
from types import SimpleNamespace

from phase6.orchestrator import Orchestrator, OrchestrationError
from phase6.config import Config
from phase6.types import ExperimentInfo, PredictionResult, DecisionResult, TrainingResult


class DummyExperimentManager:
    def __init__(self, root: Path):
        self._root = root

    def start_experiment(self, name: str | None = None):
        exp_dir = self._root / (name or "exp")
        reports = exp_dir / "reports"
        manifests = exp_dir / "manifests"
        models = exp_dir / "models"
        plots = exp_dir / "plots"
        for p in (reports, manifests, models, plots):
            p.mkdir(parents=True, exist_ok=True)
        return ExperimentInfo(experiment_id="exp1", path=str(exp_dir), models_path=str(models), reports_path=str(reports), plots_path=str(plots), manifests_path=str(manifests), created_on="2026-01-01T00:00:00Z")

    def finalize_experiment(self, experiment_info, summary):
        # simple no-op
        return str(Path(experiment_info.path) / "finalized.json")


def test_orchestrator_run_phase6_happy_path(tmp_path: Path):
    cfg = Config()
    exp_mgr = DummyExperimentManager(tmp_path)
    orch = Orchestrator(config=cfg, experiment_manager=exp_mgr)

    # Prepare fake components to be returned by _build_components
    def fake_build_components(paths, overrides, exp_info):
        class Ingestor:
            def load(self, p):
                # Return simple Phase5Inputs-like object and None
                return (SimpleNamespace(vocabulary={"a": 1}, train_df=[], test_df=[], dataset_name="ds"), None)

        class MSF:
            def create_model_spec(self, ov):
                # Return a real ModelSpec matching the canonical definition
                from phase6.model_spec import ModelSpec

                return ModelSpec(
                    vocab_size=2,
                    embedding_dim=16,
                    hidden_size=32,
                    num_layers=1,
                    dropout=0.1,
                    rnn_type="LSTM",
                    output_type="softmax",
                    sequence_length=50,
                    top_k=5,
                    pad_token=0,
                )

        class Trainer:
            def train(self, model, train_loader, val_loader):
                return TrainingResult(status=None, epoch_metrics=[], final_checkpoint=None, best_checkpoint=None, num_epochs_run=0)

        class Inference:
            def run(self, model, test_loader, top_k=None):
                return PredictionResult(predictions=[{"anomaly_score": 0.1}], meta={})

        class Decision:
            def decide(self, pr, threshold=None):
                return DecisionResult(predictions_ref="preds", decisions=[{"index": 0, "is_anomaly": False, "reason": "NOT_APPLICABLE", "confidence": {"confidence_score": 1.0, "method": "max_prob"}}])

        class ReportGen:
            def __init__(self, exp_info, logger=None, config=None):
                self._exp = exp_info

            def write_training_metrics(self, tr):
                p = Path(self._exp.reports_path) / "training_metrics.json"
                p.write_text("{}")
                return str(p)

            def write_predictions(self, dr):
                p = Path(self._exp.reports_path) / "predictions.csv"
                p.write_text("index,id\n0,a\n")
                return str(p)

            def write_manifest(self, manifest):
                p = Path(self._exp.manifests_path) / "phase6_manifest.json"
                p.write_text("{}")
                return str(p)

            def write_experiment_summary(self, summary):
                p = Path(self._exp.reports_path) / "experiment_summary.json"
                p.write_text("{}")
                return str(p)

        class Visualizer:
            def __init__(self, *a, **k):
                pass

            def plot_training_metrics(self, tr):
                return []

            def plot_predictions_summary(self, dr, top_n=10):
                return str(Path(self._exp.reports_path) / "pred_summary.png")

        return {
            "ingestor": Ingestor(),
            "model_spec_factory": MSF(),
            "trainer": Trainer(),
            "inference": Inference(),
            "decision_engine": Decision(),
            "report_generator": ReportGen(exp_info),
            "visualizer": Visualizer(),
        }

    # Patch the private builder
    orch._build_components = fake_build_components

    manifest_path = orch.run_phase6(paths={"vocabulary": "v", "sequences": "s"}, overrides={})
    assert isinstance(manifest_path, str)
    assert Path(manifest_path).exists()


def test_orchestrator_handles_build_failure(tmp_path: Path):
    cfg = Config()
    exp_mgr = DummyExperimentManager(tmp_path)
    orch = Orchestrator(config=cfg, experiment_manager=exp_mgr)

    def bad_build(paths, overrides, exp_info):
        raise RuntimeError("boom")

    orch._build_components = bad_build
    try:
        orch.run_phase6(paths={}, overrides=None)
        assert False, "OrchestrationError expected"
    except OrchestrationError:
        pass
