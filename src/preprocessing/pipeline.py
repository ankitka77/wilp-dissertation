"""Data preprocessing utilities for KPI feature engineering."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from click import group
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logger = logging.getLogger("project")


@dataclass
class FeatureEngineeringConfig:
    """Configuration for KPI feature engineering."""

    lag_values: list[int] = field(default_factory=lambda: [1, 3, 5, 10])
    rolling_windows: list[int] = field(default_factory=lambda: [5, 10, 20])
    ema_periods: list[int] = field(default_factory=lambda: [5, 10, 20])
    normalize: bool = False
    missing_strategy: str = "forward_fill"
    include_timestamp_features: bool = True
    min_periods: int = 1

    def __post_init__(self) -> None:
        self.lag_values = [int(value) for value in self.lag_values]
        self.rolling_windows = [int(value) for value in self.rolling_windows]
        self.ema_periods = [int(value) for value in self.ema_periods]
        if self.missing_strategy not in {"drop", "forward_fill", "backward_fill"}:
            raise ValueError("Unsupported missing value strategy")


class KPIFeatureEngineer:
    """Generate model-ready KPI feature vectors grouped by KPI ID."""

    def __init__(self, config: FeatureEngineeringConfig | None = None) -> None:
        self.config = config or FeatureEngineeringConfig()

    def engineer_features(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Create engineered features for KPI data while preserving the raw value column."""
        if "value" not in frame.columns:
            raise ValueError("Input data must contain a 'value' column")
        if "KPI ID" not in frame.columns:
            raise ValueError("Input data must contain a 'KPI ID' column")

        work_frame = frame.copy()
        if "timestamp" in work_frame.columns:
            work_frame["timestamp"] = pd.to_datetime(work_frame["timestamp"], errors="coerce")

        work_frame = work_frame.sort_values(["KPI ID", "timestamp"], kind="mergesort")
        work_frame["__row_order__"] = np.arange(len(work_frame))

        engineered_groups: list[pd.DataFrame] = []
        for _, group in work_frame.groupby("KPI ID", sort=False):
            engineered_groups.append(self._engineer_group(group))

        engineered = pd.concat(engineered_groups, axis=0)
        engineered = engineered.sort_values("__row_order__").drop(columns="__row_order__")
        engineered = engineered.reset_index(drop=True)
        engineered = self._handle_missing_values(engineered)
        engineered = self._sanitize_feature_dtypes(engineered)
        engineered = engineered.fillna(0.0)
        logger.info("Engineered %s KPI features", len(engineered))
        return engineered

    def _engineer_group(self, group: pd.DataFrame) -> pd.DataFrame:
        """Generate temporal features for one KPI stream."""
        group = group.copy()
        group = group.sort_values("timestamp", kind="mergesort")

        if self.config.include_timestamp_features and "timestamp" in group.columns:
            group["hour"] = group["timestamp"].dt.hour
            group["day"] = group["timestamp"].dt.day
            group["day_of_week"] = group["timestamp"].dt.dayofweek
            group["month"] = group["timestamp"].dt.month
            group["weekend"] = (group["timestamp"].dt.dayofweek >= 5).astype(int)

            group["hour_sin"] = np.sin(
                2 * np.pi * group["hour"] / 24
            )
            group["hour_cos"] = np.cos(
                2 * np.pi * group["hour"] / 24
            )
            group["day_of_week_sin"] = np.sin(
                2 * np.pi * group["day_of_week"] / 7
            )
            group["day_of_week_cos"] = np.cos(
                2 * np.pi * group["day_of_week"] / 7
            )
            
            time_diff = group["timestamp"].diff().dt.total_seconds()
            group["time_diff_seconds"] = time_diff.fillna(0.0)
        else:
            group["time_diff_seconds"] = 0.0

        for lag in self.config.lag_values:
            group[f"lag_{lag}"] = group["value"].shift(lag)

        for window in self.config.rolling_windows:
            rolling = group["value"].rolling(window=window, min_periods=self.config.min_periods)
            group[f"rolling_mean_{window}"] = rolling.mean()
            group[f"rolling_std_{window}"] = rolling.std(ddof=0)
            group[f"rolling_min_{window}"] = rolling.min()
            group[f"rolling_max_{window}"] = rolling.max()
            group[f"rolling_median_{window}"] = rolling.median()

        for period in self.config.ema_periods:
            group[f"ema_{period}"] = group["value"].ewm(span=period, adjust=False).mean()

        group["diff_prev"] = group["value"].diff()
        group["pct_change"] = group["value"].pct_change()
        group["pct_change"] = group["pct_change"].replace([np.inf, -np.inf], np.nan)
        group["first_derivative"] = group["diff_prev"] / group["time_diff_seconds"].replace(0, np.nan)
        group["first_derivative"] = group["first_derivative"].replace([np.inf, -np.inf], np.nan)

        value_std = group["value"].std(ddof=0)
        if np.isclose(value_std, 0.0):
            group["z_score"] = 0.0
        else:
            group["z_score"] = (group["value"] - group["value"].mean()) / value_std

        if self.config.normalize:
            value_min = group["value"].min()
            value_max = group["value"].max()
            value_range = value_max - value_min
            if np.isclose(value_range, 0.0):
                group["value_normalized"] = 0.0
            else:
                group["value_normalized"] = (group["value"] - value_min) / value_range

        return group

    def _handle_missing_values(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Apply the configured missing value strategy to engineered features."""
        if self.config.missing_strategy == "drop":
            return frame.dropna(axis=0, how="any").reset_index(drop=True)
        
        feature_columns = [
            col for col in frame.columns
            if col not in {"timestamp", "KPI ID", "label"}
        ]

        if self.config.missing_strategy == "forward_fill":
            frame[feature_columns] = frame[feature_columns].ffill()
            frame[feature_columns] = frame[feature_columns].bfill()
            return frame.reset_index(drop=True)
        if self.config.missing_strategy == "backward_fill":
            frame[feature_columns] = frame[feature_columns].bfill()
            frame[feature_columns] = frame[feature_columns].ffill()
            return frame.reset_index(drop=True)
        return frame

    def _sanitize_feature_dtypes(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Ensure engineered feature columns are numeric where appropriate."""
        for column in frame.columns:
            if column in {"timestamp", "KPI ID", "label"}:
                continue
            if pd.api.types.is_bool_dtype(frame[column]):
                frame[column] = frame[column].astype(int)
            elif pd.api.types.is_numeric_dtype(frame[column]) or pd.api.types.is_bool_dtype(frame[column]):
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
        return frame

    def validate_features(self, frame: pd.DataFrame) -> dict[str, Any]:
        """Validate engineered features for NaNs, infinities and dtypes."""
        issues: list[str] = []
        if frame.empty:
            issues.append("Feature frame is empty")
            return {"is_valid": False, "issues": issues}

        feature_columns = [
            column
            for column in frame.columns
            if column not in {"timestamp", "KPI ID", "label"}
        ]

        for column in feature_columns:
            numeric_values = pd.to_numeric(frame[column], errors="coerce")
            if numeric_values.isna().any():
                issues.append(f"{column} contains missing values")

            if np.isinf(numeric_values).any():
                issues.append(f"{column} contains infinite values")

            if not pd.api.types.is_numeric_dtype(frame[column]):
                issues.append(f"{column} has an unsupported dtype")

        return {"is_valid": not issues, "issues": issues}

    def generate_feature_reports(self, frame: pd.DataFrame, output_dir: str | Path = "reports/phase3") -> dict[str, Path]:
        """Create feature summary, statistics, and correlation reports."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        feature_columns = [
            column
            for column in frame.columns
            if column not in {"timestamp", "KPI ID", "label"}
            and pd.api.types.is_numeric_dtype(frame[column])
        ]

        if not feature_columns:
            raise ValueError("No numeric engineered features were generated")

        feature_summary = pd.DataFrame(
            {
                "feature_name": feature_columns,
                "datatype": [str(frame[column].dtype) for column in feature_columns],
                "missing_values": [int(frame[column].isna().sum()) for column in feature_columns],
                "mean": [float(frame[column].mean()) for column in feature_columns],
                "std": [float(frame[column].std(ddof=0)) for column in feature_columns],
                "min": [float(frame[column].min()) for column in feature_columns],
                "max": [float(frame[column].max()) for column in feature_columns],
            }
        )
        summary_path = output_path / "feature_summary.csv"
        feature_summary.to_csv(summary_path, index=False)

        feature_statistics = frame[feature_columns].describe().T.reset_index()
        feature_statistics = feature_statistics.rename(columns={"index": "feature_name"})
        statistics_path = output_path / "feature_statistics.csv"
        feature_statistics.to_csv(statistics_path, index=False)

        correlation_matrix = frame[feature_columns].corr(numeric_only=True)
        correlation_path = output_path / "feature_correlation.csv"
        correlation_matrix.to_csv(correlation_path)

        return {
            "summary": summary_path,
            "statistics": statistics_path,
            "correlation": correlation_path,
        }

    def fit_transform_kpi(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Fit preprocessing logic on KPI data and return transformed output."""
        return self.engineer_features(frame)

    def transform_kpi(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Apply already-fitted KPI preprocessing transformations."""
        return self.engineer_features(frame)

    def build_log_sequences(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Build sequence-ready log representation from parsed events."""
        raise NotImplementedError("Phase 6+ will implement log sequence processing.")
    
    def get_feature_columns(self, frame: pd.DataFrame) -> list[str]:
        excluded = {"timestamp", "KPI ID", "label"}
        return [column for column in frame.columns if column not in excluded]

    def get_numeric_feature_columns(self, frame: pd.DataFrame):
        return [column for column in self.get_feature_columns(frame) if pd.api.types.is_numeric_dtype(frame[column])]

@dataclass
class PreprocessingPipeline:
    """Compatibility wrapper for the KPI feature engineering workflow."""

    config: FeatureEngineeringConfig = field(default_factory=FeatureEngineeringConfig)

    def __post_init__(self) -> None:
        self.feature_engineer = KPIFeatureEngineer(self.config)

    def fit_transform_kpi(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Fit preprocessing logic on KPI data and return transformed output."""
        return self.feature_engineer.engineer_features(frame)

    def transform_kpi(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Apply already-fitted KPI preprocessing transformations."""
        return self.feature_engineer.engineer_features(frame)

    def build_log_sequences(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Build sequence-ready log representation from parsed events."""
        raise NotImplementedError("Phase 6+ will implement log sequence processing.")
