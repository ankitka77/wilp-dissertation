"""Log anomaly model skeleton."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class LogAnomalyModel:
    """Base scaffold for log anomaly detection models."""

    model_name: str = "log-baseline"

    def fit(self, features: pd.DataFrame, labels: pd.Series | None = None) -> None:
        """Train log anomaly model."""
        raise NotImplementedError("Phase 7+ will implement log model training.")

    def predict(self, features: pd.DataFrame) -> pd.Series:
        """Generate log anomaly predictions or scores."""
        raise NotImplementedError("Phase 7+ will implement log prediction logic.")
