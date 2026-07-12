"""Abstract base model interface for anomaly detection workflows."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import pandas as pd

from version import PROJECT_VERSION


class BaseModel(ABC):
    """Common interface for anomaly detection models."""

    def __init__(self, model_name: str | None = None, model_version: str | None = None) -> None:
        self.model_name = model_name or self.__class__.__name__
        self.model_version = model_version or "1.0.0"
        self._is_trained = False

    @abstractmethod
    def train(self, frame: pd.DataFrame, **kwargs: Any) -> None:
        """Train the model on the provided feature frame."""

    @abstractmethod
    def predict(self, frame: pd.DataFrame, **kwargs: Any) -> pd.Series:
        """Generate predicted labels for the provided feature frame."""

    @abstractmethod
    def evaluate(self, frame: pd.DataFrame, y_true: Any, y_pred: Any, **kwargs: Any) -> dict[str, Any]:
        """Evaluate the model outputs against ground truth."""

    @abstractmethod
    def save(self, path: str | Path) -> None:
        """Persist the trained model artifact."""

    @classmethod
    @abstractmethod
    def load(cls, path: str | Path) -> "BaseModel":
        """Load a persisted model artifact."""

    def get_model_info(self) -> dict[str, Any]:
        """Return descriptive metadata for the current model."""
        return {
            "project_version": PROJECT_VERSION,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "algorithm": self.__class__.__name__,
            "author": "BITS Pilani WILP",
            "num_features_used": None,
        }
