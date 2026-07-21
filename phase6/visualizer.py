"""Visualization utilities for Phase 6.

Produces plots for training metrics and prediction summaries. The module
uses `matplotlib` for rendering and writes files to the experiment's
`plots` directory.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, List, Tuple
import logging

logger = logging.getLogger("project")


class VisualizerError(RuntimeError):
    """Raised when visualization cannot be produced or saved."""


class Visualizer:
    """Create and persist plots for training and prediction summaries.

    Parameters
    ----------
    experiment_info:
        `ExperimentInfo` providing canonical `plots_path`.
    logger:
        Optional logger; defaults to the centralized project logger.
    config:
        `Config` instance (not required by this minimal implementation but
        accepted for API compatibility).
    """

    def __init__(self, experiment_info: Any, logger: logging.Logger | None = None, config: Any | None = None) -> None:
        self._experiment_info = experiment_info
        self._logger = logger or logging.getLogger("project")
        self._config = config

        # Ensure plots directory exists
        Path(self._experiment_info.plots_path).mkdir(parents=True, exist_ok=True)

    def plot_training_metrics(self, training_result: Any) -> List[str]:
        """Plot training metrics (loss and top-k accuracy) and return file paths.

        Returns two files: loss plot and accuracy plot, saved in both PNG and
        SVG formats (four files total). Filenames are deterministic.
        """
        # Import matplotlib lazily to avoid heavy import at module import time
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except Exception as exc:
            self._logger.exception("matplotlib not available: %s", exc)
            raise VisualizerError("matplotlib is required for plotting") from exc

        # Extract epoch metrics safely
        try:
            epochs = [int(m.get("epoch", i)) for i, m in enumerate(training_result.epoch_metrics, start=1)]
            losses = [float(m.get("loss", 0.0)) for m in training_result.epoch_metrics]
            accuracies = [float(m.get("topk_accuracy", 0.0)) for m in training_result.epoch_metrics]
        except Exception as exc:
            self._logger.exception("Invalid training_result format: %s", exc)
            raise VisualizerError("Invalid training_result format") from exc

        out_paths: List[str] = []

        # Loss plot
        try:
            fig1, ax1 = plt.subplots()
            ax1.plot(epochs, losses, marker="o")
            ax1.set_xlabel("epoch")
            ax1.set_ylabel("loss")
            ax1.set_title("Training Loss")
            loss_base = Path(self._experiment_info.plots_path) / "training_loss"
            for suffix in (".png", ".svg"):
                p = loss_base.with_suffix(suffix)
                self._safe_save_fig(fig1, p)
                out_paths.append(str(p))
            plt.close(fig1)
        except Exception as exc:
            self._logger.exception("Failed to create loss plot: %s", exc)
            raise VisualizerError("Failed to create loss plot") from exc

        # Accuracy plot
        try:
            fig2, ax2 = plt.subplots()
            ax2.plot(epochs, accuracies, marker="o")
            ax2.set_xlabel("epoch")
            ax2.set_ylabel("topk_accuracy")
            ax2.set_title("Top-K Accuracy")
            acc_base = Path(self._experiment_info.plots_path) / "training_topk_accuracy"
            for suffix in (".png", ".svg"):
                p = acc_base.with_suffix(suffix)
                self._safe_save_fig(fig2, p)
                out_paths.append(str(p))
            plt.close(fig2)
        except Exception as exc:
            self._logger.exception("Failed to create accuracy plot: %s", exc)
            raise VisualizerError("Failed to create accuracy plot") from exc

        return out_paths

    def plot_predictions_summary(self, decision_result: Any, top_n: int = 10) -> str:
        """Create a bar plot summarizing top `top_n` anomalous examples.

        Returns the path to the PNG file created.
        """
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except Exception as exc:
            self._logger.exception("matplotlib not available: %s", exc)
            raise VisualizerError("matplotlib is required for plotting") from exc

        try:
            scores, labels = self._aggregate_prediction_stats(decision_result)
        except Exception as exc:
            self._logger.exception("Failed to aggregate prediction stats: %s", exc)
            raise VisualizerError("Failed to aggregate prediction stats") from exc

        # Select top_n by score
        paired = sorted(zip(scores, labels), key=lambda x: x[0], reverse=True)[:top_n]
        sel_scores = [s for s, _ in paired]
        sel_labels = [label for _, label in paired]

        try:
            fig, ax = plt.subplots(figsize=(8, max(2, 0.3 * len(sel_labels))))
            y_pos = list(range(len(sel_labels)))
            ax.barh(y_pos, sel_scores, align="center")
            ax.set_yticks(y_pos)
            ax.set_yticklabels(sel_labels)
            ax.invert_yaxis()
            ax.set_xlabel("anomaly_score")
            ax.set_title("Top anomalous predictions")

            out_path = Path(self._experiment_info.plots_path) / "predictions_summary.png"
            self._safe_save_fig(fig, out_path)
            plt.close(fig)
        except Exception as exc:
            self._logger.exception("Failed to create predictions summary plot: %s", exc)
            raise VisualizerError("Failed to create predictions summary plot") from exc

        return str(out_path)

    # ---- Private helpers ----
    def _safe_save_fig(self, fig: Any, path: Path) -> None:
        """Save matplotlib `fig` to `path` atomically using a .tmp file.

        The temporary filename preserves the original image extension (e.g.
        `training_loss.tmp.png`) so that matplotlib can infer the output
        format correctly.
        """
        # Create a tmp name that ends with the original suffix (e.g. .tmp.png)
        suffix = path.suffix
        tmp = path.with_suffix(".tmp" + suffix)
        try:
            fig.savefig(str(tmp), bbox_inches="tight")
            tmp.replace(path)
        finally:
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception as exc:
                self._logger.debug("Temporary figure cleanup failed for %s: %s", tmp, exc)

    def _aggregate_prediction_stats(self, decision_result: Any) -> Tuple[List[float], List[str]]:
        """Return parallel lists of (score, label) for decision entries.

        Score is derived from `confidence.confidence_score` if present,
        otherwise falls back to `confidence_score` key or 0.0. Label is the
        `id` if present or stringified index.
        """
        if not hasattr(decision_result, "decisions"):
            raise VisualizerError("decision_result must have 'decisions' attribute")

        scores: List[float] = []
        labels: List[str] = []
        for idx, d in enumerate(decision_result.decisions):
            conf = d.get("confidence") or {}
            score = 0.0
            try:
                if isinstance(conf, dict) and "confidence_score" in conf:
                    score = float(conf.get("confidence_score", 0.0))
                else:
                    # Attempt common alternate key
                    score = float(d.get("confidence_score", 0.0))
            except Exception:
                self._logger.exception("Invalid confidence format for decision %s", idx)
                score = 0.0

            label = str(d.get("id", idx))
            scores.append(score)
            labels.append(label)

        return scores, labels


__all__ = ["Visualizer", "VisualizerError"]
