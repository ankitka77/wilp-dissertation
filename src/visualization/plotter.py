"""Visualization scaffolding for KPI and model outputs."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class VisualizationService:
    """Placeholder plotting service for future phases."""

    def plot_kpi_series(self, frame: pd.DataFrame, value_col: str = "value") -> None:
        """Plot KPI series with anomaly overlays in later phases."""
        raise NotImplementedError("Phase 2+ will add KPI exploratory plots.")

    def plot_model_comparison(self, results: pd.DataFrame) -> None:
        """Visualize model performance comparison in later phases."""
        raise NotImplementedError("Phase 4+ will add model comparison plots.")
