"""KPI anomaly model skeleton."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class KPIAnomalyModel:
    """Base scaffold for KPI anomaly detection models."""

    model_name: str = "kpi-baseline"

    def fit(self, features: pd.DataFrame, labels: pd.Series | None = None) -> None:
        """Train KPI anomaly model."""
        raise NotImplementedError("Phase 4+ will implement KPI model training.")

    def predict(self, features: pd.DataFrame) -> pd.Series:
        """Generate KPI anomaly predictions or scores."""
        raise NotImplementedError("Phase 4+ will implement KPI prediction logic.")
