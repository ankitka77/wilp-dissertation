"""Isolation Forest implementation for KPI anomaly detection."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from evaluation.evaluator import Evaluator
from preprocessing.pipeline import KPIFeatureEngineer
from .base_model import BaseModel


class IsolationForestModel(BaseModel):
    """Isolation Forest-based anomaly detector for engineered KPI features."""

    def __init__(
        self,
        n_estimators: int = 100,
        contamination: float = 0.05,
        max_samples: str | int = "auto",
        bootstrap: bool = False,
        random_state: int | None = 42,
        model_name: str | None = None,
        model_version: str | None = None,
    ) -> None:
        super().__init__(model_name=model_name, model_version=model_version)
        self.n_estimators = n_estimators
        self.contamination = contamination
        self.max_samples = max_samples
        self.bootstrap = bootstrap
        self.random_state = random_state
        self._model: IsolationForest | None = None
        self._feature_columns: list[str] = []
        self._evaluator = Evaluator()
        self._feature_engineer = KPIFeatureEngineer()

    def _prepare_features(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Select numeric feature columns and convert them to compact float32 values."""
        if frame.empty:
            raise ValueError("Input frame is empty")

        feature_columns = self._feature_engineer.get_numeric_feature_columns(frame)
        if not feature_columns:
            raise ValueError("No numeric feature columns available for model training")

        prepared_columns: dict[str, pd.Series] = {}
        for column in feature_columns:
            numeric_values = pd.to_numeric(frame[column], errors="coerce")
            prepared_columns[column] = numeric_values.astype(np.float32).fillna(0.0)

        prepared = pd.DataFrame(prepared_columns, index=frame.index)
        self._feature_columns = feature_columns
        return prepared

    def train(self, frame: pd.DataFrame, **kwargs: Any) -> None:
        """Train the Isolation Forest model on engineered KPI features."""
        prepared = self._prepare_features(frame)
        self._model = IsolationForest(
            n_estimators=kwargs.get("n_estimators", self.n_estimators),
            contamination=kwargs.get("contamination", self.contamination),
            max_samples=kwargs.get("max_samples", self.max_samples),
            bootstrap=kwargs.get("bootstrap", self.bootstrap),
            random_state=kwargs.get("random_state", self.random_state),
        )
        self._model.fit(prepared)
        self._is_trained = True

    def predict(self, frame: pd.DataFrame, **kwargs: Any) -> pd.Series:
        """Predict anomaly labels for the provided feature frame."""
        if self._model is None:
            raise ValueError("Model must be trained before predicting")

        prepared = self._prepare_features(frame)
        predictions = self._model.predict(prepared)
        labels = np.where(predictions == -1, 1, 0)
        return pd.Series(labels, index=frame.index, name="prediction")

    def predict_scores(self, frame: pd.DataFrame, **kwargs: Any) -> pd.Series:
        """Generate anomaly scores for the provided feature frame."""
        if self._model is None:
            raise ValueError("Model must be trained before scoring")

        prepared = self._prepare_features(frame)
        decision_scores = self._model.score_samples(prepared)
        normalized_scores = -decision_scores
        return pd.Series(normalized_scores, index=frame.index, name="anomaly_score")

    def evaluate(self, frame: pd.DataFrame, y_true: Any, y_pred: Any, **kwargs: Any) -> dict[str, Any]:
        """Evaluate predictions against ground truth using the shared evaluator."""
        if self._model is None:
            raise ValueError("Model must be trained before evaluation")

        scores = kwargs.get("y_scores")
        if scores is None:
            scores = self.predict_scores(frame)

        return self._evaluator.evaluate(y_true=y_true, y_pred=y_pred, y_scores=scores)

    def save(self, path: str | Path) -> None:
        """Persist the trained model to disk."""
        if self._model is None:
            raise ValueError("Cannot save an untrained model")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": self._model,
            "feature_columns": self._feature_columns,
            "config": {
                "n_estimators": self.n_estimators,
                "contamination": self.contamination,
                "max_samples": self.max_samples,
                "bootstrap": self.bootstrap,
                "random_state": self.random_state,
            },
            "metadata": self.get_model_info(),
        }
        with path.open("wb") as handle:
            pickle.dump(payload, handle)

    @classmethod
    def load(cls, path: str | Path) -> "IsolationForestModel":
        """Load a persisted model from disk."""
        path = Path(path)
        with path.open("rb") as handle:
            payload = pickle.load(handle)

        model = cls(**payload["config"])
        model._model = payload["model"]
        model._feature_columns = payload.get("feature_columns", [])
        model._is_trained = True
        return model

    def get_model_info(self) -> dict[str, Any]:
        """Return model metadata including project version and feature usage."""
        info = super().get_model_info()
        info.update(
            {
                "model_name": self.model_name,
                "model_version": self.model_version,
                "algorithm": "IsolationForest",
                "num_features_used": len(self._feature_columns),
            }
        )
        return info
