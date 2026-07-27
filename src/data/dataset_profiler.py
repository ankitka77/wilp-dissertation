"""Dataset profiling module for KPI datasets.

This module provides functionality to analyze and profile KPI datasets,
generating summary statistics, descriptive statistics, and KPI-specific analysis.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger("project")

HIGHLY_IMBALANCED_THRESHOLD = 1
MODERATELY_IMBALANCED_THRESHOLD = 10


class DatasetProfiler:
    """Profile and analyze KPI datasets.

    This class generates:
    - Dataset summary statistics (including timestamp analysis)
    - Descriptive statistics for KPI values
    - KPI-specific analysis (including per-KPI timestamp ranges)
    - Timestamp analysis (overall and per-KPI)
    - Reports in CSV and other formats
    """

    def __init__(self, output_dir: str | Path = "artifacts/reports/phase2"):
        """Initialize DatasetProfiler.

        Args:
            output_dir: Directory to save profiling reports. Defaults to "artifacts/reports/phase2".
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"DatasetProfiler initialized with output dir: {self.output_dir}")

    def generate_dataset_summary(
        self, train_df: pd.DataFrame, test_df: pd.DataFrame | None = None
    ) -> pd.DataFrame:
        """Generate dataset summary statistics.

        Args:
            train_df: Training DataFrame.
            test_df: Optional test DataFrame.

        Returns:
            DataFrame containing summary statistics.
        """
        logger.info("Generating dataset summary")

        summary_data: dict[str, list[Any]] = {
            "Metric": [],
            "Training": [],
        }

        if test_df is not None:
            summary_data["Testing"] = []

        # Number of rows
        summary_data["Metric"].append("Number of Rows")
        summary_data["Training"].append(len(train_df))
        if test_df is not None:
            summary_data["Testing"].append(len(test_df))

        # Number of columns
        summary_data["Metric"].append("Number of Columns")
        summary_data["Training"].append(len(train_df.columns))
        if test_df is not None:
            summary_data["Testing"].append(len(test_df.columns))

        # Number of unique KPI IDs
        summary_data["Metric"].append("Number of KPI IDs")
        summary_data["Training"].append(train_df["KPI ID"].nunique())
        if test_df is not None:
            summary_data["Testing"].append(test_df["KPI ID"].nunique())

        # Anomaly and normal counts (training only, as test has no labels)
        if "label" in train_df.columns:
            anomalies = (train_df["label"] == 1).sum()
            normals = (train_df["label"] == 0).sum()

            summary_data["Metric"].append("Number of Anomalies")
            summary_data["Training"].append(anomalies)
            if test_df is not None:
                summary_data["Testing"].append("N/A (No labels)")

            summary_data["Metric"].append("Number of Normal Records")
            summary_data["Training"].append(normals)
            if test_df is not None:
                summary_data["Testing"].append("N/A (No labels)")

            summary_data["Metric"].append("Anomaly Percentage (%)")
            anomaly_pct = anomalies / len(train_df) * 100
            summary_data["Training"].append(f"{anomaly_pct:.2f}")
            if test_df is not None:
                summary_data["Testing"].append("N/A (No labels)")

            if anomaly_pct < HIGHLY_IMBALANCED_THRESHOLD:
                imbalance = "Highly Imbalanced"
            elif anomaly_pct < MODERATELY_IMBALANCED_THRESHOLD:
                imbalance = "Moderately Imbalanced"
            else:
                imbalance = "Balanced"

            summary_data["Metric"].append("Class Imbalance")
            summary_data["Training"].append(imbalance)
            if test_df is not None:
                summary_data["Testing"].append("N/A (No labels)")

        # Timestamp analysis
        if "timestamp" in train_df.columns:
            train_df_ts = pd.to_datetime(train_df["timestamp"], errors="coerce")
            train_min_ts = train_df_ts.min()
            train_max_ts = train_df_ts.max()
            train_time_span = str(train_max_ts - train_min_ts) if pd.notna(train_min_ts) and pd.notna(train_max_ts) else "N/A"

            summary_data["Metric"].append("Min Timestamp")
            summary_data["Training"].append(train_min_ts)
            if test_df is not None:
                test_df_ts = pd.to_datetime(test_df["timestamp"], errors="coerce")
                test_min_ts = test_df_ts.min()
                summary_data["Testing"].append(test_min_ts)

            summary_data["Metric"].append("Max Timestamp")
            summary_data["Training"].append(train_max_ts)
            if test_df is not None:
                test_df_ts = pd.to_datetime(test_df["timestamp"], errors="coerce")
                test_max_ts = test_df_ts.max()
                summary_data["Testing"].append(test_max_ts)

            summary_data["Metric"].append("Time Span")
            summary_data["Training"].append(train_time_span)
            if test_df is not None:
                test_df_ts = pd.to_datetime(test_df["timestamp"], errors="coerce")
                test_min_ts = test_df_ts.min()
                test_max_ts = test_df_ts.max()
                test_time_span = str(test_max_ts - test_min_ts) if pd.notna(test_min_ts) and pd.notna(test_max_ts) else "N/A"
                summary_data["Testing"].append(test_time_span)

        summary_df = pd.DataFrame(summary_data)
        logger.info("Dataset summary generated successfully")

        return summary_df

    def generate_descriptive_statistics(self, df: pd.DataFrame, dataset_type: str = "training") -> pd.DataFrame:
        """Generate descriptive statistics for KPI values.

        Args:
            df: DataFrame to analyze.
            dataset_type: Label for the dataset type (e.g., "training" or "testing").

        Returns:
            DataFrame containing descriptive statistics.
        """
        logger.info(f"Generating descriptive statistics for {dataset_type} data")

        stats_data: dict[str, list[Any]] = {
            "Statistic": ["Count", "Min", "Max", "Mean", "Median", "Std Dev", "25th Percentile", "75th Percentile", "IQR"],
            dataset_type.capitalize(): [],
        }

        values = df["value"]

        q1 = values.quantile(0.25)
        q3 = values.quantile(0.75)
        iqr = q3 - q1

        stats_values = [
            len(values),
            values.min(),
            values.max(),
            values.mean(),
            values.median(),
            values.std(),
            q1,
            q3,
            iqr
        ]

        stats_data[dataset_type.capitalize()] = stats_values

        stats_df = pd.DataFrame(stats_data)
        logger.info("Descriptive statistics generated successfully")

        return stats_df

    def generate_kpi_analysis(self, train_df: pd.DataFrame, test_df: pd.DataFrame | None = None) -> pd.DataFrame:
        """Generate KPI-specific analysis.

        Analyzes records per KPI ID, anomaly count, anomaly percentage, and timestamp ranges.

        Args:
            train_df: Training DataFrame.
            test_df: Optional test DataFrame.

        Returns:
            DataFrame containing KPI-specific analysis.
        """
        logger.info("Generating KPI analysis")

        kpi_data: dict[str, list[Any]] = {
            "KPI ID": [],
            "Train Records": [],
            "Train Anomalies": [],
            "Train Anomaly %": [],
        }

        if test_df is not None:
            kpi_data["Test Records"] = []

        # Add timestamp columns if available
        has_timestamps = "timestamp" in train_df.columns
        if has_timestamps:
            kpi_data["Train First Timestamp"] = []
            kpi_data["Train Last Timestamp"] = []
            if test_df is not None:
                kpi_data["Test First Timestamp"] = []
                kpi_data["Test Last Timestamp"] = []

        # Get training KPI IDs
        train_kpi_ids = sorted(train_df["KPI ID"].unique())

        for kpi_id in train_kpi_ids:
            kpi_train_df = train_df[train_df["KPI ID"] == kpi_id]
            train_count = len(kpi_train_df)
            train_anomalies = 0
            train_anomaly_pct = 0.0

            if "label" in kpi_train_df.columns:
                train_anomalies = (kpi_train_df["label"] == 1).sum()
                train_anomaly_pct = (train_anomalies / train_count * 100) if train_count > 0 else 0.0

            kpi_data["KPI ID"].append(kpi_id)
            kpi_data["Train Records"].append(train_count)
            kpi_data["Train Anomalies"].append(train_anomalies)
            kpi_data["Train Anomaly %"].append(f"{train_anomaly_pct:.2f}")

            # Timestamp analysis per KPI
            if has_timestamps:
                kpi_train_ts = pd.to_datetime(kpi_train_df["timestamp"], errors="coerce")
                train_first_ts = kpi_train_ts.min()
                train_last_ts = kpi_train_ts.max()
                kpi_data["Train First Timestamp"].append(train_first_ts)
                kpi_data["Train Last Timestamp"].append(train_last_ts)

            if test_df is not None:
                kpi_test_df = test_df[test_df["KPI ID"] == kpi_id]
                test_count = len(kpi_test_df)
                kpi_data["Test Records"].append(test_count)

                if has_timestamps:
                    kpi_test_ts = pd.to_datetime(kpi_test_df["timestamp"], errors="coerce")
                    test_first_ts = kpi_test_ts.min()
                    test_last_ts = kpi_test_ts.max()
                    kpi_data["Test First Timestamp"].append(test_first_ts)
                    kpi_data["Test Last Timestamp"].append(test_last_ts)

        kpi_df = pd.DataFrame(kpi_data)
        logger.info("KPI analysis generated successfully")

        return kpi_df

    def generate_anomaly_distribution(self, train_df: pd.DataFrame) -> pd.DataFrame:
        """Generate anomaly distribution analysis.

        Args:
            train_df: Training DataFrame with labels.

        Returns:
            DataFrame containing anomaly distribution.
        """
        logger.info("Generating anomaly distribution")

        if "label" not in train_df.columns:
            logger.warning("Training data has no 'label' column; skipping anomaly distribution")
            return pd.DataFrame()

        anomaly_counts = train_df["label"].value_counts().reset_index()
        anomaly_counts.columns = ["Label", "Count"]
        anomaly_counts["Label"] = anomaly_counts["Label"].map({0: "Normal", 1: "Anomaly"})

        total_records = len(train_df)
        anomaly_counts["Percentage"] = (anomaly_counts["Count"] / total_records * 100).round(2)

        logger.info("Anomaly distribution generated successfully")

        return anomaly_counts

    def save_all_reports(
        self,
        train_df: pd.DataFrame,
        test_df: pd.DataFrame | None = None,
    ) -> None:
        """Generate and save all profiling reports.

        Args:
            train_df: Training DataFrame.
            test_df: Optional test DataFrame.
        """
        logger.info("Saving all profiling reports")

        # Dataset summary
        summary_df = self.generate_dataset_summary(train_df, test_df)
        summary_path = self.output_dir / "dataset_summary.csv"
        summary_df.to_csv(summary_path, index=False)
        logger.info(f"Dataset summary saved to {summary_path}")
        summary_stats = self.get_summary_statistics(train_df)

        json_path = self.output_dir / "dataset_summary.json"

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(
                summary_stats,
                f,
                indent=4,
                default=str
            )

        logger.info(f"Dataset summary JSON saved to {json_path}")

        # Descriptive statistics
        desc_stats_train = self.generate_descriptive_statistics(train_df, "Training")
        if test_df is not None:
            desc_stats_test = self.generate_descriptive_statistics(test_df, "Testing")
            desc_stats = desc_stats_train.merge(desc_stats_test, on="Statistic", how="outer")
        else:
            desc_stats = desc_stats_train

        desc_path = self.output_dir / "descriptive_statistics.csv"
        desc_stats.to_csv(desc_path, index=False)
        logger.info(f"Descriptive statistics saved to {desc_path}")

        # KPI analysis
        kpi_analysis = self.generate_kpi_analysis(train_df, test_df)
        kpi_path = self.output_dir / "kpi_distribution.csv"
        kpi_analysis.to_csv(kpi_path, index=False)
        logger.info(f"KPI analysis saved to {kpi_path}")

        # Anomaly distribution
        if "label" in train_df.columns:
            anomaly_dist = self.generate_anomaly_distribution(train_df)
            anomaly_path = self.output_dir / "anomaly_distribution.csv"
            anomaly_dist.to_csv(anomaly_path, index=False)
            logger.info(f"Anomaly distribution saved to {anomaly_path}")

        # Timestamp analysis
        timestamp_analysis = self.generate_timestamp_analysis(train_df, test_df)
        if not timestamp_analysis.empty:
            ts_path = self.output_dir / "timestamp_analysis.csv"
            timestamp_analysis.to_csv(ts_path, index=False)
            logger.info(f"Timestamp analysis saved to {ts_path}")

        logger.info("All profiling reports saved successfully")

    def generate_timestamp_analysis(self, train_df: pd.DataFrame, test_df: pd.DataFrame | None = None) -> pd.DataFrame:
        """Generate detailed timestamp analysis.

        Analyzes timestamp ranges, duration, and coverage for the datasets.

        Args:
            train_df: Training DataFrame.
            test_df: Optional test DataFrame.

        Returns:
            DataFrame containing timestamp analysis.
        """
        logger.info("Generating timestamp analysis")

        if "timestamp" not in train_df.columns:
            logger.warning("No timestamp column found; returning empty DataFrame")
            return pd.DataFrame()

        ts_data: dict[str, list[Any]] = {
            "Metric": [],
            "Training": [],
        }

        if test_df is not None:
            ts_data["Testing"] = []

        # Train dataset timestamps
        train_ts = pd.to_datetime(train_df["timestamp"], errors="coerce")
        train_min = train_ts.min()
        train_max = train_ts.max()
        train_span = train_max - train_min if pd.notna(train_min) and pd.notna(train_max) else pd.NaT

        ts_data["Metric"].append("First Timestamp")
        ts_data["Training"].append(train_min)
        if test_df is not None:
            test_ts = pd.to_datetime(test_df["timestamp"], errors="coerce")
            test_min = test_ts.min()
            ts_data["Testing"].append(test_min)

        ts_data["Metric"].append("Last Timestamp")
        ts_data["Training"].append(train_max)
        if test_df is not None:
            test_ts = pd.to_datetime(test_df["timestamp"], errors="coerce")
            test_max = test_ts.max()
            ts_data["Testing"].append(test_max)

        ts_data["Metric"].append("Time Span")
        ts_data["Training"].append(str(train_span) if pd.notna(train_span) else "N/A")
        if test_df is not None:
            test_ts = pd.to_datetime(test_df["timestamp"], errors="coerce")
            test_min = test_ts.min()
            test_max = test_ts.max()
            test_span = test_max - test_min if pd.notna(test_min) and pd.notna(test_max) else pd.NaT
            ts_data["Testing"].append(str(test_span) if pd.notna(test_span) else "N/A")

        ts_data["Metric"].append("Number of Unique Timestamps")
        ts_data["Training"].append(train_ts.nunique())
        if test_df is not None:
            ts_data["Testing"].append(test_ts.nunique())

        ts_df = pd.DataFrame(ts_data)
        logger.info("Timestamp analysis generated successfully")

        return ts_df

    def get_summary_statistics(self, train_df: pd.DataFrame) -> dict[str, Any]:
        """Get summary statistics as a dictionary.

        Args:
            train_df: Training DataFrame.

        Returns:
            Dictionary containing summary statistics.
        """
        logger.info("Generating summary statistics dictionary")

        stats = {
            "total_records": len(train_df),
            "total_columns": len(train_df.columns),
            "kpi_count": train_df["KPI ID"].nunique(),
        }

        if "label" in train_df.columns:
            stats["anomaly_count"] = (train_df["label"] == 1).sum()
            stats["normal_count"] = (train_df["label"] == 0).sum()
            stats["anomaly_percentage"] = (stats["anomaly_count"] / len(train_df) * 100)
            anomaly_pct = stats["anomaly_percentage"]

            if anomaly_pct < HIGHLY_IMBALANCED_THRESHOLD:
                imbalance_classification = "Highly Imbalanced"
            elif anomaly_pct < MODERATELY_IMBALANCED_THRESHOLD:
                imbalance_classification = "Moderately Imbalanced"
            else:
                imbalance_classification = "Balanced"

            stats["class_imbalance"] = (
                imbalance_classification
            )

        # Timestamp statistics
        if "timestamp" in train_df.columns:
            train_ts = pd.to_datetime(train_df["timestamp"], errors="coerce")
            stats["min_timestamp"] = train_ts.min()
            stats["max_timestamp"] = train_ts.max()
            if pd.notna(stats["min_timestamp"]) and pd.notna(stats["max_timestamp"]):
                stats["time_span"] = stats["max_timestamp"] - stats["min_timestamp"]
            stats["unique_timestamps"] = train_ts.nunique()

        return stats
