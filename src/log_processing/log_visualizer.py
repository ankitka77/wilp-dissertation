"""Visualization helpers for Phase 5 log analysis."""
from __future__ import annotations

from pathlib import Path
import logging
import matplotlib.pyplot as plt
import pandas as pd

logger = logging.getLogger("project")


class LogVisualizer:
    def __init__(self, output_dir: str | Path = "artifacts/plots/phase5") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def plot_event_frequency(self, event_table: pd.DataFrame) -> Path:
        path = self.output_dir / "01_event_frequency.png"
        plt.figure(figsize=(16, 6))
        event_table.head(30).plot(kind="bar", x="template", y="frequency", legend=False)
        plt.xticks(rotation=30, ha="right")
        plt.subplots_adjust(bottom=0.3)
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()
        return path

    def plot_top_templates(self, event_table: pd.DataFrame) -> Path:
        path = self.output_dir / "02_top_templates.png"
        top = event_table.head(15)
        plt.figure(figsize=(14, 6))
        top.plot(kind="bar", x="template", y="frequency", legend=False)
        plt.xticks(rotation=30, ha="right")
        plt.subplots_adjust(bottom=0.3)
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()
        return path

    def plot_sequence_length_histogram(self, sequences: pd.DataFrame) -> Path:
        path = self.output_dir / "03_sequence_length_distribution.png"
        # ensure we have a sequence_length series; try to compute from sequence_events
        if "sequence_length" not in sequences.columns:
            if "sequence_events" in sequences.columns:
                lengths = sequences["sequence_events"].apply(lambda x: len(x) if hasattr(x, "__len__") and x is not None else 0)
            else:
                logger.info("No sequence_length or sequence_events available; skipping histogram plot")
                return None
        else:
            lengths = sequences["sequence_length"].dropna()

        if len(lengths) == 0:
            logger.info("No sequence lengths to plot; skipping histogram")
            return None

        plt.figure(figsize=(8, 5))
        plt.hist(lengths, bins=30, color="steelblue")
        plt.subplots_adjust(bottom=0.15)
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()
        return path

    def plot_sequence_length_boxplot(self, sequences: pd.DataFrame) -> Path:
        path = self.output_dir / "03b_sequence_length_boxplot.png"
        # similar handling as histogram
        if "sequence_length" not in sequences.columns:
            if "sequence_events" in sequences.columns:
                lengths = sequences["sequence_events"].apply(lambda x: len(x) if hasattr(x, "__len__") and x is not None else 0)
            else:
                logger.info("No sequence_length or sequence_events available; skipping boxplot")
                return None
        else:
            lengths = sequences["sequence_length"].dropna()

        if len(lengths) == 0:
            logger.info("No sequence lengths to plot; skipping boxplot")
            return None

        plt.figure(figsize=(6, 4))
        plt.boxplot(lengths)
        plt.subplots_adjust(bottom=0.15)
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()
        return path

    def plot_train_test_split(self, train: pd.DataFrame, test: pd.DataFrame) -> Path:
        path = self.output_dir / "04_train_test_split.png"
        plt.figure(figsize=(6, 4))
        plt.bar(["train", "test"], [len(train), len(test)], color=["green", "orange"])
        plt.subplots_adjust(bottom=0.15)
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()
        return path
