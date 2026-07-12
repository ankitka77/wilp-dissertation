"""Visualization module for KPI dataset analysis and feature engineering."""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn import metrics

logger = logging.getLogger("project")


class VisualizationService:
    """Generate exploratory visualizations for KPI datasets."""

    def __init__(self, output_dir: str | Path = "artifacts/plots"):
        """Initialize VisualizationService."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("VisualizationService initialized with output dir: %s", self.output_dir)

    def plot_kpi_id_distribution(self, df: pd.DataFrame, dataset_type: str = "training") -> None:
        """Plot distribution of records across KPI IDs."""
        logger.info("Generating KPI ID distribution plot for %s data", dataset_type)

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

        logger.info("KPI ID distribution plot saved to %s", output_path)

    def plot_anomaly_distribution(self, df: pd.DataFrame) -> None:
        """Plot distribution of anomalies vs normal records."""
        logger.info("Generating anomaly distribution plot")

        if "label" not in df.columns:
            logger.warning("Dataset has no 'label' column; skipping anomaly distribution plot")
            return

        plt.figure(figsize=(8, 6))
        anomaly_counts = df["label"].value_counts()
        labels_map = {0: "Normal", 1: "Anomaly"}
        labels = [labels_map.get(idx, str(idx)) for idx in anomaly_counts.index]

        colors = ["green", "red"]
        anomaly_counts.plot(kind="bar", color=colors[: len(anomaly_counts)], edgecolor="black", alpha=0.7)

        plt.title("Anomaly Distribution (Training Dataset)", fontsize=14, fontweight="bold")
        plt.xlabel("Category", fontsize=12)
        plt.ylabel("Number of Records", fontsize=12)
        plt.xticks(range(len(labels)), labels, rotation=0)
        plt.grid(axis="y", alpha=0.3)
        plt.tight_layout()

        output_path = self.output_dir / "02_anomaly_distribution.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info("Anomaly distribution plot saved to %s", output_path)

    def plot_kpi_value_histogram(self, df: pd.DataFrame, dataset_type: str = "training") -> None:
        """Plot histogram of KPI values."""
        logger.info("Generating KPI value histogram for %s data", dataset_type)

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

        logger.info("KPI value histogram saved to %s", output_path)

    def plot_kpi_value_boxplot(self, df: pd.DataFrame, dataset_type: str = "training") -> None:
        """Plot boxplot of KPI values."""
        logger.info("Generating KPI value boxplot for %s data", dataset_type)

        plt.figure(figsize=(10, 6))
        plt.boxplot(df["value"], vert=True, patch_artist=True, widths=0.5)

        plt.title(f"KPI Value Boxplot ({dataset_type.capitalize()} Dataset)", fontsize=14, fontweight="bold")
        plt.ylabel("KPI Value", fontsize=12)
        plt.grid(axis="y", alpha=0.3)
        plt.tight_layout()

        output_path = self.output_dir / f"04_kpi_value_boxplot_{dataset_type}.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info("KPI value boxplot saved to %s", output_path)

    def plot_kpi_value_distribution_by_id(self, df: pd.DataFrame, dataset_type: str = "training") -> None:
        """Plot KPI value distribution by KPI ID (boxplot)."""
        logger.info("Generating KPI value distribution by ID plot for %s data", dataset_type)

        plt.figure(figsize=(14, 6))
        kpi_ids = sorted(df["KPI ID"].unique())
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

        logger.info("KPI value distribution by ID plot saved to %s", output_path)

    def plot_feature_correlation(self, features: pd.DataFrame) -> None:
        """Plot a correlation heatmap for engineered numeric features."""
        numeric_columns = [
            column
            for column in features.columns
            if column not in {"timestamp", "KPI ID", "label"} and pd.api.types.is_numeric_dtype(features[column])
        ]
        if len(numeric_columns) < 2:
            logger.warning("Not enough numeric features for correlation plotting")
            return

        correlation_matrix = features[numeric_columns].corr(numeric_only=True)
        plt.figure(figsize=(14, 10))
        plt.imshow(correlation_matrix, cmap="coolwarm", interpolation="nearest")
        plt.colorbar()
        plt.xticks(range(len(numeric_columns)), numeric_columns, rotation=45, ha="right")
        plt.yticks(range(len(numeric_columns)), numeric_columns)
        plt.title("Feature Correlation Heatmap")
        plt.tight_layout()

        output_path = self.output_dir / "06_feature_correlation_heatmap.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info("Feature correlation heatmap saved to %s", output_path)

    def plot_feature_distributions(self, features: pd.DataFrame) -> None:
        """Plot distributions for the most informative engineered features."""
        numeric_columns = [
            column
            for column in features.columns
            if column not in {"timestamp", "KPI ID", "label"} and pd.api.types.is_numeric_dtype(features[column])
        ]
        if not numeric_columns:
            logger.warning("No numeric features available for distribution plotting")
            return

        plot_columns = numeric_columns[:6]
        fig, axes = plt.subplots(nrows=2, ncols=3, figsize=(15, 10))
        axes = axes.flatten()

        for axis, column in zip(axes, plot_columns):
            axis.hist(features[column].dropna(), bins=30, color="steelblue", alpha=0.7)
            axis.set_title(column)
            axis.set_xlabel("Value")
            axis.set_ylabel("Frequency")

        for axis in axes[len(plot_columns):]:
            axis.axis("off")

        plt.tight_layout()
        output_path = self.output_dir / "07_feature_distributions.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info("Feature distributions saved to %s", output_path)

    def plot_rolling_mean_example(self, features: pd.DataFrame) -> None:
        """Plot a rolling mean example for the first KPI stream."""
        rolling_column = next((column for column in features.columns if column.startswith("rolling_mean_")), None)
        if rolling_column is None:
            logger.warning("Rolling mean feature not found; skipping rolling mean example plot")
            return

        first_kpi = features["KPI ID"].dropna().iloc[0]
        subset = features[features["KPI ID"] == first_kpi].head(80)
        if subset.empty:
            return

        plt.figure(figsize=(12, 6))
        plt.plot(subset["value"], label="value", color="black", alpha=0.6)
        plt.plot(subset[rolling_column], label=rolling_column, color="tab:red", linewidth=2)
        plt.title(f"Rolling Mean Example for {first_kpi}")
        plt.xlabel("Sample")
        plt.ylabel("Value")
        plt.legend()
        plt.grid(alpha=0.3)
        plt.tight_layout()

        output_path = self.output_dir / "08_rolling_mean_example.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info("Rolling mean example saved to %s", output_path)

    def generate_phase3_plots(self, features: pd.DataFrame) -> None:
        """Generate feature-engineering plots for Phase 3."""
        self.plot_feature_correlation(features)
        self.plot_feature_distributions(features)
        self.plot_rolling_mean_example(features)

    def plot_kpi_series(self, frame: pd.DataFrame, value_col: str = "value") -> None:
        """Plot KPI series with anomaly overlays for later phases."""
        if value_col not in frame.columns:
            logger.warning("Column %s not found; skipping KPI series plot", value_col)
            return

        plt.figure(figsize=(12, 6))
        plt.plot(frame.index, frame[value_col], color="steelblue", linewidth=1.2)
        if "prediction" in frame.columns:
            anomalies = frame[frame["prediction"] == 1]
            plt.scatter(anomalies.index, anomalies[value_col], color="red", label="anomaly", zorder=5)
            plt.legend()
        plt.title("KPI Series with Anomaly Overlay")
        plt.xlabel("Sample")
        plt.ylabel(value_col)
        plt.grid(alpha=0.3)
        plt.tight_layout()

        output_path = self.output_dir / "09_anomaly_timeline.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info("Anomaly timeline plot saved to %s", output_path)

    def plot_model_comparison(self, results: pd.DataFrame) -> None:
        """Visualize model performance comparison in later phases."""
        raise NotImplementedError("Phase 4+ will add model comparison plots.")

    def plot_roc_curve(self, y_true: pd.Series | list[int], y_scores: pd.Series | list[float]) -> None:
        """Plot an ROC curve for anomaly detection scores."""
        fpr, tpr, _ = metrics.roc_curve(y_true, y_scores)
        plt.figure(figsize=(8, 6))
        plt.plot(fpr, tpr, label="ROC")
        plt.plot([0, 1], [0, 1], linestyle="--", color="gray")
        plt.title("ROC Curve")
        plt.xlabel("False Positive Rate")
        plt.ylabel("True Positive Rate")
        plt.grid(alpha=0.3)
        plt.tight_layout()

        output_path = self.output_dir / "10_roc_curve.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info("ROC curve plot saved to %s", output_path)

    def plot_precision_recall_curve(self, y_true: pd.Series | list[int], y_scores: pd.Series | list[float]) -> None:
        """Plot a precision-recall curve for anomaly detection scores."""
        precision, recall, _ = metrics.precision_recall_curve(y_true, y_scores)
        plt.figure(figsize=(8, 6))
        plt.plot(recall, precision, label="Precision-Recall")
        plt.title("Precision-Recall Curve")
        plt.xlabel("Recall")
        plt.ylabel("Precision")
        plt.grid(alpha=0.3)
        plt.tight_layout()

        output_path = self.output_dir / "11_precision_recall_curve.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info("Precision-recall curve plot saved to %s", output_path)

    def plot_confusion_matrix(self, y_true: pd.Series | list[int], y_pred: pd.Series | list[int]) -> None:
        """Plot a confusion matrix for predictions."""
        matrix = metrics.confusion_matrix(y_true, y_pred)
        plt.figure(figsize=(7, 6))
        plt.imshow(matrix, cmap="Blues")
        plt.title("Confusion Matrix")
        plt.xlabel("Predicted")
        plt.ylabel("Actual")
        plt.xticks([0, 1], ["Normal", "Anomaly"])
        plt.yticks([0, 1], ["Normal", "Anomaly"])
        plt.colorbar()
        plt.tight_layout()

        output_path = self.output_dir / "12_confusion_matrix.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info("Confusion matrix plot saved to %s", output_path)

    def generate_all_plots(self, train_df: pd.DataFrame, test_df: pd.DataFrame | None = None) -> None:
        """Generate all exploratory plots."""
        logger.info("Generating all exploratory plots")

        self.plot_kpi_id_distribution(train_df, "training")
        self.plot_kpi_value_histogram(train_df, "training")
        self.plot_kpi_value_boxplot(train_df, "training")
        self.plot_kpi_value_distribution_by_id(train_df, "training")

        if "label" in train_df.columns:
            self.plot_anomaly_distribution(train_df)

        if test_df is not None:
            self.plot_kpi_id_distribution(test_df, "testing")
            self.plot_kpi_value_histogram(test_df, "testing")
            self.plot_kpi_value_boxplot(test_df, "testing")
            self.plot_kpi_value_distribution_by_id(test_df, "testing")

        logger.info("All exploratory plots generated successfully")
