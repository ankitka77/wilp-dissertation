"""Unit tests for Phase 4 KPI anomaly detection with Isolation Forest."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from evaluation.evaluator import Evaluator
from infrastructure.experiment_manager import ExperimentManager
from models.isolation_forest_model import IsolationForestModel


class TestIsolationForestModel:
    """Tests for the Isolation Forest model implementation."""

    def sample_frame(self) -> pd.DataFrame:
        """Create a small synthetic feature frame for testing."""
        return pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=20, freq="h"),
                "KPI ID": ["KPI-1"] * 20,
                "label": [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1],
                "value": [10.0, 10.2, 10.1, 10.3, 10.4, 10.2, 10.5, 10.6, 100.0, 101.0, 10.7, 10.4, 10.8, 10.9, 10.5, 10.6, 10.7, 10.8, 99.0, 100.5],
                "lag_1": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "rolling_mean_5": [10.0, 10.1, 10.2, 10.3, 10.4, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9, 10.8, 10.7, 10.6, 10.5, 10.4, 10.3, 10.2, 10.1],
            }
        )

    def test_training_and_prediction(self) -> None:
        """The model should train and produce predictions and scores."""
        frame = self.sample_frame()
        model = IsolationForestModel(random_state=42, contamination=0.2)

        model.train(frame)
        predictions = model.predict(frame)
        scores = model.predict_scores(frame)

        assert len(predictions) == len(frame)
        assert len(scores) == len(frame)
        assert set(predictions.unique()) <= {0, 1}

    def test_eval_returns_expected_metrics(self) -> None:
        """Evaluation should return standard metrics."""
        frame = self.sample_frame()
        model = IsolationForestModel(random_state=42, contamination=0.2)

        model.train(frame)
        predictions = model.predict(frame)
        metrics = model.evaluate(frame, frame["label"].to_numpy(), predictions)

        assert set(metrics.keys()) >= {"accuracy", "precision", "recall", "f1", "roc_auc"}
        assert 0.0 <= metrics["accuracy"] <= 1.0

    def test_save_and_load_model(self) -> None:
        """The model should persist and reload with predictive capability."""
        frame = self.sample_frame()
        model = IsolationForestModel(random_state=7, contamination=0.15)
        model.train(frame)

        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "model.pkl"
            model.save(path)
            loaded = IsolationForestModel.load(path)
            predictions = loaded.predict(frame)

        assert len(predictions) == len(frame)

    def test_prepare_features_converts_to_memory_efficient_numeric_dtype(self) -> None:
        """Feature preparation should produce compact numeric columns for large datasets."""
        frame = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=5, freq="h"),
                "KPI ID": ["KPI-1"] * 5,
                "label": [0, 0, 1, 0, 1],
                "value": [10.0, 11.0, "12.5", None, 14.0],
                "lag_1": [0.0, 1.0, 2.0, 3.0, 4.0],
                "rolling_mean_5": [1.0, 2.0, 3.0, 4.0, 5.0],
            }
        )
        model = IsolationForestModel(random_state=42)

        prepared = model._prepare_features(frame)

        assert prepared.shape[1] == 3
        assert prepared.dtypes.apply(lambda dtype: dtype == np.float32).all()
        assert prepared.isna().sum().sum() == 0


class TestEvaluator:
    """Tests for the evaluation component."""

    def test_evaluator_computes_metrics(self) -> None:
        """The evaluator should compute the expected metric set."""
        evaluator = Evaluator()
        y_true = [0, 1, 1, 0, 1]
        y_pred = [0, 1, 0, 0, 1]
        y_scores = [0.1, 0.9, 0.8, 0.2, 0.95]

        metrics = evaluator.evaluate(y_true, y_pred, y_scores)

        assert set(metrics.keys()) >= {"accuracy", "precision", "recall", "f1", "roc_auc"}
        assert metrics["roc_auc"] >= 0.0


class TestExperimentManager:
    """Tests for experiment tracking and artifact creation."""

    def test_experiment_manager_creates_expected_artifacts(self) -> None:
        """The experiment manager should create a structured experiment directory."""
        with TemporaryDirectory() as tmp_dir:
            manager = ExperimentManager(output_dir=Path(tmp_dir))
            experiment_id = manager.start_experiment({"name": "phase4_test"})
            manager.log_metrics({"accuracy": 0.95})
            manager.log_predictions(pd.DataFrame({"timestamp": ["2024-01-01"], "KPI ID": ["KPI-1"], "prediction": [1], "anomaly_score": [0.9]}))
            manager.log_model(Path(tmp_dir) / "model.pkl")
            manager.log_plot(Path(tmp_dir) / "plot.png", "roc_curve")
            record = manager.finalize()

            assert experiment_id.startswith("experiment_")
            assert record["experiment_id"] == experiment_id
            assert (Path(tmp_dir) / "experiments" / experiment_id / "config.json").exists()
            assert (Path(tmp_dir) / "experiments" / experiment_id / "metrics.json").exists()
            assert (Path(tmp_dir) / "experiments" / experiment_id / "predictions.csv").exists()
            assert (Path(tmp_dir) / "experiments" / experiment_id / "README.txt").exists()
