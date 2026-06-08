"""Data preprocessing skeleton for KPI and log inputs."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class PreprocessingPipeline:
    """Pipeline placeholder for data cleaning and feature preparation."""

    def fit_transform_kpi(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Fit preprocessing logic on KPI data and return transformed output."""
        raise NotImplementedError("Phase 2+ will implement KPI preprocessing logic.")

    def transform_kpi(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Apply already-fitted KPI preprocessing transformations."""
        raise NotImplementedError("Phase 2+ will implement KPI preprocessing logic.")

    def build_log_sequences(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Build sequence-ready log representation from parsed events."""
        raise NotImplementedError("Phase 6+ will implement log sequence processing.")
