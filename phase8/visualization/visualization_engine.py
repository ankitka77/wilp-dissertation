"""Visualization Engine for Phase 8 Milestone 5.

Consumes `analysis/statistics.json` artifacts and produces PNG figures
persisted through the `ArtifactStore`. Uses matplotlib for rendering.
"""
from __future__ import annotations

from typing import List, Mapping, Optional
from dataclasses import dataclass
import io
import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from phase8.core.artifact_store import ArtifactStore, ArtifactStoreError
from phase8.core.experiment_manager import ExperimentManager, ExperimentNotFoundError
from phase8.visualization.exceptions import VisualizationError

logger = logging.getLogger("phase8.visualization")


# output filenames
PRECISION_PNG = "visualization/precision_comparison.png"
RECALL_PNG = "visualization/recall_comparison.png"
F1_PNG = "visualization/f1_comparison.png"
SUMMARY_PNG = "visualization/summary_statistics.png"
EXPERIMENT_COMPARISON_PNG = "visualization/experiment_comparison.png"

SUPPORTED_METRICS = ("precision", "recall", "f1")


@dataclass(frozen=True)
class PlotSpec:
    path: str
    metric: Optional[str] = None


class VisualizationEngine:
    """Produce PNG visualizations from `analysis/statistics.json` artifacts.

    Public API:
    - `visualize_experiment(experiment_id)`
    - `visualize_experiments(experiment_ids)`
    """

    def __init__(self, experiment_manager: ExperimentManager, artifact_store: ArtifactStore) -> None:
        self._exp = experiment_manager
        self._store = artifact_store

    def _load_stats(self, experiment_id: str) -> Mapping:
        try:
            return self._store.read_json(experiment_id, "analysis/statistics.json")
        except ArtifactStoreError as exc:
            logger.error("Missing statistics for experiment %s", experiment_id)
            raise VisualizationError("missing statistics") from exc

    def _render_png_bytes(self, fig) -> bytes:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    def _plot_metric_bar(self, means: List[float], cis: List[Optional[float]], labels: List[str], title: str) -> bytes:
        fig, ax = plt.subplots(figsize=(6, 4))
        x = range(len(means))
        ax.bar(x, means, yerr=[(m - (ci if ci is not None else m)) for m, ci in zip(means, cis)], capsize=5)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha="right")
        ax.set_ylabel("Score")
        ax.set_ylim(0, 1)
        ax.set_title(title)
        fig.tight_layout()
        return self._render_png_bytes(fig)

    def visualize_experiment(self, experiment_id: str) -> List[PlotSpec]:
        """Create a set of visualizations for a single experiment.

        Returns list of PlotSpec with paths written to ArtifactStore.
        """
        try:
            self._exp.get_metadata(experiment_id)
        except ExperimentNotFoundError as exc:
            logger.error("Experiment %s not found", experiment_id)
            raise VisualizationError("experiment not found") from exc

        stats = self._load_stats(experiment_id)
        metrics = stats.get("metrics", {})
        labels = [experiment_id]

        written: List[PlotSpec] = []
        try:
            for metric in SUPPORTED_METRICS:
                mdoc = metrics.get(metric, {})
                mean = mdoc.get("mean")
                ci_low = mdoc.get("ci_low")
                ci_high = mdoc.get("ci_high")
                if mean is None:
                    # skip missing metrics
                    continue
                ci = None
                if ci_low is not None and ci_high is not None:
                    ci = abs(mean - ci_low)
                png = self._plot_metric_bar([mean], [ci], labels, f"{metric.title()} (mean ±95% CI)")
                path = PRECISION_PNG if metric == "precision" else RECALL_PNG if metric == "recall" else F1_PNG
                self._store.write_artifact(experiment_id, path, png)
                written.append(PlotSpec(path=path, metric=metric))

            # summary plot: show all means side-by-side
            means = []
            cis = []
            for metric in SUPPORTED_METRICS:
                mdoc = metrics.get(metric, {})
                mean = mdoc.get("mean")
                ci_low = mdoc.get("ci_low")
                ci_high = mdoc.get("ci_high")
                if mean is None:
                    continue
                means.append(float(mean))
                cis.append(abs(mean - ci_low) if (ci_low is not None) else None)
            if means:
                png = self._plot_metric_bar(means, cis, [m.title() for m in SUPPORTED_METRICS[:len(means)]], "Summary Metrics")
                self._store.write_artifact(experiment_id, SUMMARY_PNG, png)
                written.append(PlotSpec(path=SUMMARY_PNG))

        except ArtifactStoreError as exc:
            logger.exception("Failed to write visualization artifacts for %s", experiment_id)
            raise VisualizationError("failed to persist visualizations") from exc

        return written

    def visualize_experiments(self, experiment_ids: List[str]) -> PlotSpec:
        """Create a comparison plot for multiple experiments.

        Produces a single PNG comparing metric means across experiments and
        writes it under the synthetic run id `aggregated`.
        """
        collected_means = {m: [] for m in SUPPORTED_METRICS}
        labels = []
        for eid in experiment_ids:
            try:
                stats = self._store.read_json(eid, "analysis/statistics.json")
            except ArtifactStoreError:
                # try evaluator summaries fallback
                try:
                    stats = self._store.read_json(eid, "evaluation/kpi_summary.json")
                    # normalize into metrics-like structure
                    stats = {"metrics": {m: {"mean": stats.get(m)} for m in SUPPORTED_METRICS}}
                except ArtifactStoreError:
                    logger.debug("Skipping %s: no stats or summaries", eid)
                    continue
            mdoc = stats.get("metrics", {})
            any_present = False
            for m in SUPPORTED_METRICS:
                mean = mdoc.get(m, {}).get("mean") if isinstance(mdoc.get(m, {}), dict) else mdoc.get(m)
                if mean is not None:
                    collected_means[m].append(float(mean))
                    any_present = True
                else:
                    collected_means[m].append(None)
            if any_present:
                labels.append(eid)

        if not labels:
            raise VisualizationError("no statistics to visualize")

        # build summary matrix per metric for the labels
        means_per_metric = []
        for m in SUPPORTED_METRICS:
            vals = [v if v is not None else 0.0 for v in collected_means[m][: len(labels)]]
            means_per_metric.append(vals)

        # create grouped bar chart
        try:
            fig, ax = plt.subplots(figsize=(8, 4))
            import numpy as np

            x = np.arange(len(labels))
            width = 0.2
            for i, vals in enumerate(means_per_metric):
                ax.bar(x + i * width, vals, width, label=SUPPORTED_METRICS[i].title())
            ax.set_xticks(x + width)
            ax.set_xticklabels(labels, rotation=45, ha="right")
            ax.set_ylim(0, 1)
            ax.set_ylabel("Score")
            ax.set_title("Experiment Comparison")
            ax.legend()
            fig.tight_layout()
            png = self._render_png_bytes(fig)
            self._store.write_artifact("aggregated", EXPERIMENT_COMPARISON_PNG, png)
            return PlotSpec(path=EXPERIMENT_COMPARISON_PNG)
        except ArtifactStoreError as exc:
            logger.exception("Failed to write aggregated visualization")
            raise VisualizationError("failed to persist aggregated visualization") from exc
