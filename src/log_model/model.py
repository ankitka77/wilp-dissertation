"""Log anomaly model skeleton.

Note:
This module provides a lightweight scaffold for log anomaly detection models.
It is intentionally minimal because Phase 5 implements preprocessing under
`src/log_processing` while model-specific implementations (for example
DeepLog/LSTM-based models planned for Phase 6) should be added here.

The package is preserved for forward development and backward-compatibility
so that downstream code can import `src.log_model` without changes.
"""

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
