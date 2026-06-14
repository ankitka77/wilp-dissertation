"""Visualization module for KPI dataset analysis (Phase 2).

This module provides functionality to generate exploratory visualizations
for KPI datasets.
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

logger = logging.getLogger("project")


class VisualizationService:
    """Generate exploratory visualizations for KPI datasets.

    This class creates:
    - KPI ID distribution plots
    - Anomaly distribution plots
    - KPI value histograms
    - KPI value boxplots
    - KPI value distribution by KPI ID
    """

    def __init__(self, output_dir: str | Path = "reports/phase2/plots"):
        """Initialize VisualizationService.

        Args:
            output_dir: Directory to save visualization plots. Defaults to "reports/phase2/plots".
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"VisualizationService initialized with output dir: {self.output_dir}")

    def plot_kpi_id_distribution(self, df: pd.DataFrame, dataset_type: str = "training") -> None:
        """Plot distribution of records across KPI IDs.

        Args:
            df: DataFrame to analyze.
            dataset_type: Label for dataset (e.g., "training" or "testing").
        """
        logger.info(f"Generating KPI ID distribution plot for {dataset_type} data")

        plt.figure(figsize=(12, 6))

        kpi_counts = df["KPI ID"].value_counts().sort_index()
        kpi_counts.plot(kind="bar", color="steelblue", edgecolor="black", alpha=0.7)

        plt.title(f"KPI ID Distribution ({dataset_type.capitalize()} Dataset)", fontsize=14, fontweight="bold")
        plt.xlabel("KPI ID", fontsize=12)
        plt.ylabel("Number of Records", fontsize=12)
        plt.xticks(rotation=45)
        plt.grid(axis="y", alpha=0.3)
        plt.tight_layout()

        output_path = self.output_dir / f"01_kpi_id_distribution_{dataset_type}.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info(f"KPI ID distribution plot saved to {output_path}")

    def plot_anomaly_distribution(self, df: pd.DataFrame) -> None:
        """Plot distribution of anomalies vs normal records.

        Args:
            df: Training DataFrame with labels.
        """
        logger.info("Generating anomaly distribution plot")

        if "label" not in df.columns:
            logger.warning("Dataset has no 'label' column; skipping anomaly distribution plot")
            return

        plt.figure(figsize=(8, 6))

        anomaly_counts = df["label"].value_counts()
        labels_map = {0: "Normal", 1: "Anomaly"}
        labels = [labels_map.get(idx, str(idx)) for idx in anomaly_counts.index]

        colors = ["green", "red"]
        anomaly_counts.plot(kind="bar", color=colors[:len(anomaly_counts)], edgecolor="black", alpha=0.7)

        plt.title("Anomaly Distribution (Training Dataset)", fontsize=14, fontweight="bold")
        plt.xlabel("Category", fontsize=12)
        plt.ylabel("Number of Records", fontsize=12)
        plt.xticks(range(len(labels)), labels, rotation=0)
        plt.grid(axis="y", alpha=0.3)
        plt.tight_layout()

        output_path = self.output_dir / "02_anomaly_distribution.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info(f"Anomaly distribution plot saved to {output_path}")

    def plot_kpi_value_histogram(self, df: pd.DataFrame, dataset_type: str = "training") -> None:
        """Plot histogram of KPI values.

        Args:
            df: DataFrame to analyze.
            dataset_type: Label for dataset (e.g., "training" or "testing").
        """
        logger.info(f"Generating KPI value histogram for {dataset_type} data")

        plt.figure(figsize=(10, 6))

        plt.hist(df["value"], bins=50, color="steelblue", edgecolor="black", alpha=0.7)

        plt.title(f"KPI Value Distribution ({dataset_type.capitalize()} Dataset)", fontsize=14, fontweight="bold")
        plt.xlabel("KPI Value", fontsize=12)
        plt.ylabel("Frequency", fontsize=12)
        plt.grid(axis="y", alpha=0.3)
        plt.tight_layout()

        output_path = self.output_dir / f"03_kpi_value_histogram_{dataset_type}.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info(f"KPI value histogram saved to {output_path}")

    def plot_kpi_value_boxplot(self, df: pd.DataFrame, dataset_type: str = "training") -> None:
        """Plot boxplot of KPI values.

        Args:
            df: DataFrame to analyze.
            dataset_type: Label for dataset (e.g., "training" or "testing").
        """
        logger.info(f"Generating KPI value boxplot for {dataset_type} data")

        plt.figure(figsize=(10, 6))

        plt.boxplot(df["value"], vert=True, patch_artist=True, widths=0.5)

        plt.title(f"KPI Value Boxplot ({dataset_type.capitalize()} Dataset)", fontsize=14, fontweight="bold")
        plt.ylabel("KPI Value", fontsize=12)
        plt.grid(axis="y", alpha=0.3)
        plt.tight_layout()

        output_path = self.output_dir / f"04_kpi_value_boxplot_{dataset_type}.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info(f"KPI value boxplot saved to {output_path}")

    def plot_kpi_value_distribution_by_id(self, df: pd.DataFrame, dataset_type: str = "training") -> None:
        """Plot KPI value distribution by KPI ID (boxplot).

        Args:
            df: DataFrame to analyze.
            dataset_type: Label for dataset (e.g., "training" or "testing").
        """
        logger.info(f"Generating KPI value distribution by ID plot for {dataset_type} data")

        plt.figure(figsize=(14, 6))

        # Get KPI IDs sorted
        kpi_ids = sorted(df["KPI ID"].unique())

        # Prepare data for boxplot
        data_by_kpi = [df[df["KPI ID"] == kpi_id]["value"].values for kpi_id in kpi_ids]

        plt.boxplot(data_by_kpi, labels=kpi_ids, patch_artist=True)

        plt.title(f"KPI Value Distribution by KPI ID ({dataset_type.capitalize()} Dataset)", fontsize=14, fontweight="bold")
        plt.xlabel("KPI ID", fontsize=12)
        plt.ylabel("KPI Value", fontsize=12)
        plt.xticks(rotation=45)
        plt.grid(axis="y", alpha=0.3)
        plt.tight_layout()

        output_path = self.output_dir / f"05_kpi_value_by_id_{dataset_type}.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info(f"KPI value distribution by ID plot saved to {output_path}")

    def plot_kpi_series(self, frame: pd.DataFrame, value_col: str = "value") -> None:
        """Plot KPI series with anomaly overlays in later phases."""
        raise NotImplementedError("Phase 2+ will add KPI exploratory plots.")

    def plot_model_comparison(self, results: pd.DataFrame) -> None:
        """Visualize model performance comparison in later phases."""
        raise NotImplementedError("Phase 4+ will add model comparison plots.")

    def generate_all_plots(self, train_df: pd.DataFrame, test_df: pd.DataFrame | None = None) -> None:
        """Generate all exploratory plots.

        Args:
            train_df: Training DataFrame.
            test_df: Optional test DataFrame.
        """
        logger.info("Generating all exploratory plots")

        # Training plots
        self.plot_kpi_id_distribution(train_df, "training")
        self.plot_kpi_value_histogram(train_df, "training")
        self.plot_kpi_value_boxplot(train_df, "training")
        self.plot_kpi_value_distribution_by_id(train_df, "training")

        # Anomaly distribution (training only as test has no labels)
        if "label" in train_df.columns:
            self.plot_anomaly_distribution(train_df)

        # Test plots if provided
        if test_df is not None:
            self.plot_kpi_id_distribution(test_df, "testing")
            self.plot_kpi_value_histogram(test_df, "testing")
            self.plot_kpi_value_boxplot(test_df, "testing")
            self.plot_kpi_value_distribution_by_id(test_df, "testing")

        logger.info("All exploratory plots generated successfully")
