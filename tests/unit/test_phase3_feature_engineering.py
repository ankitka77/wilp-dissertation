"""Unit tests for Phase 3 – KPI Feature Engineering."""

from __future__ import annotations

import project_bootstrap  # noqa: F401
from pathlib import Path

import numpy as np
import pandas as pd

from preprocessing.pipeline import FeatureEngineeringConfig, KPIFeatureEngineer

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


class TestKPIFeatureEngineer:
    """Test suite for KPI feature engineering pipeline."""

    def sample_frame(self) -> pd.DataFrame:
        """Create a small sample KPI DataFrame."""
        return pd.DataFrame(
            {
                "timestamp": pd.to_datetime(
                    [
                        "2021-01-01 00:00:00",
                        "2021-01-01 00:01:00",
                        "2021-01-01 00:02:00",
                        "2021-01-01 00:03:00",
                        "2021-01-01 00:04:00",
                        "2021-01-01 00:05:00",
                    ]
                ),
                "value": [10.0, 12.0, 13.0, 15.0, 14.0, 16.0],
                "label": [0, 0, 1, 0, 0, 1],
                "KPI ID": ["KPI-1", "KPI-1", "KPI-1", "KPI-1", "KPI-1", "KPI-1"],
            }
        )

    def test_lag_generation(self) -> None:
        """Lag features should be generated for each KPI stream."""
        engineer = KPIFeatureEngineer(
            config=FeatureEngineeringConfig(lag_values=[1, 3], rolling_windows=[2], ema_periods=[2])
        )
        result = engineer.engineer_features(self.sample_frame())

        assert "lag_1" in result.columns
        assert "lag_3" in result.columns

    def test_rolling_feature_generation(self) -> None:
        """Rolling statistics should be created for configured windows."""
        engineer = KPIFeatureEngineer(
            config=FeatureEngineeringConfig(lag_values=[1], rolling_windows=[5], ema_periods=[2])
        )
        result = engineer.engineer_features(self.sample_frame())

        assert "rolling_mean_5" in result.columns
        assert "rolling_std_5" in result.columns
        assert "rolling_min_5" in result.columns
        assert "rolling_max_5" in result.columns

    def test_ema_generation(self) -> None:
        """EMA features should be created for configured periods."""
        engineer = KPIFeatureEngineer(
            config=FeatureEngineeringConfig(lag_values=[1], rolling_windows=[2], ema_periods=[2, 3])
        )
        result = engineer.engineer_features(self.sample_frame())

        assert "ema_2" in result.columns
        assert "ema_3" in result.columns

    def test_normalization_feature_generation(self) -> None:
        """Normalization should add a separate feature without overwriting raw value."""
        engineer = KPIFeatureEngineer(
            config=FeatureEngineeringConfig(normalize=True, lag_values=[1], rolling_windows=[2], ema_periods=[2])
        )
        result = engineer.engineer_features(self.sample_frame())

        assert "value_normalized" in result.columns
        assert "value" in result.columns
        assert result["value_normalized"].between(0.0, 1.0).all()

    def test_infinite_values_are_sanitized(self) -> None:
        """Zero-based transitions should not leave infinite percentage-change values behind."""
        frame = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2021-01-01 00:00:00", "2021-01-01 00:01:00", "2021-01-01 00:02:00"]),
                "value": [0.0, 0.0, 2.0],
                "label": [0, 0, 1],
                "KPI ID": ["KPI-1", "KPI-1", "KPI-1"],
            }
        )
        engineer = KPIFeatureEngineer(
            config=FeatureEngineeringConfig(lag_values=[1], rolling_windows=[2], ema_periods=[2])
        )
        result = engineer.engineer_features(frame)
        validation = engineer.validate_features(result)

        assert validation["is_valid"] is True
        assert not np.isinf(result["pct_change"]).any()

    def test_missing_value_strategy_forward_fill(self) -> None:
        """Missing values should be handled according to the configured strategy."""
        engineer = KPIFeatureEngineer(
            config=FeatureEngineeringConfig(
                lag_values=[1], rolling_windows=[2], ema_periods=[2], missing_strategy="forward_fill"
            )
        )
        result = engineer.engineer_features(self.sample_frame())

        assert result.isna().sum().sum() == 0

    def test_feature_validation(self) -> None:
        """Engineered features should pass validation checks."""
        engineer = KPIFeatureEngineer(
            config=FeatureEngineeringConfig(lag_values=[1], rolling_windows=[2], ema_periods=[2])
        )
        result = engineer.engineer_features(self.sample_frame())
        validation = engineer.validate_features(result)

        assert validation["is_valid"] is True
        assert validation["issues"] == []
