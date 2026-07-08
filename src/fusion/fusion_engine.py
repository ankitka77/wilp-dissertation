"""Fusion layer skeleton combining KPI and log anomaly scores."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FusionEngine:
    """Base fusion interface."""

    def fuse(self, kpi_score, log_score):
        """
        Combine KPI anomaly score and log anomaly score.

        Parameters
        ----------
        kpi_score : float
        log_score : float

        Returns
        -------
        str
            Final anomaly classification.

        Notes
        -----
        Actual fusion logic will be implemented in Phase 9.
        """
        raise NotImplementedError


@dataclass
class WeightedFusionEngine(FusionEngine):
    """Simple weighted average fusion for KPI and log scores."""

    kpi_weight: float = 0.5
    log_weight: float = 0.5

    def __post_init__(self) -> None:
        total = self.kpi_weight + self.log_weight
        if total == 0:
            raise ValueError("Fusion weights must not both be zero")

    def fuse(self, kpi_score, log_score):
        """Return the weighted anomaly score."""

        total = self.kpi_weight + self.log_weight
        return ((kpi_score * self.kpi_weight) + (log_score * self.log_weight)) / total

    def classify(self, score: float, threshold: float = 0.5) -> str:
        """Classify the fused score into anomaly or normal."""

        return "Anomaly" if score >= threshold else "Normal"
