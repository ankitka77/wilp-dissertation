"""Phase 3 – KPI Feature Engineering execution script."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from common.logging_utils import configure_logging
from common.settings import load_settings
from data.data_loader import DataLoader
from preprocessing.pipeline import FeatureEngineeringConfig, KPIFeatureEngineer, PreprocessingPipeline
from visualization.plotter import VisualizationService


def main() -> bool:
    """Execute the Phase 3 feature engineering workflow."""
    logger = configure_logging("config/logging.yaml")
    logger.info("=" * 70)
    logger.info("PHASE 3 – KPI FEATURE ENGINEERING")
    logger.info("=" * 70)

    try:
        settings = load_settings(Path("config/settings.yaml"))
        logger.info("Loaded settings for %s", settings.project.name)

        data_loader = DataLoader(settings.paths.data_dir + "/kpi")
        load_result = data_loader.load_both()
        if load_result.errors or load_result.train_df is None or load_result.test_df is None:
            logger.error("Unable to load KPI datasets")
            return False

        feature_config = FeatureEngineeringConfig(
            lag_values=settings.feature_engineering.lag_values,
            rolling_windows=settings.feature_engineering.rolling_windows,
            ema_periods=settings.feature_engineering.ema_periods,
            normalize=settings.feature_engineering.normalize,
            missing_strategy=settings.feature_engineering.missing_strategy,
            include_timestamp_features=settings.feature_engineering.include_timestamp_features,
        )
        engineer = KPIFeatureEngineer(config=feature_config)
        pipeline = PreprocessingPipeline(config=feature_config)

        train_features = pipeline.fit_transform_kpi(load_result.train_df)
        test_features = pipeline.transform_kpi(load_result.test_df)

        output_dir = Path(settings.paths.reports_dir) / "phase3"
        output_dir.mkdir(parents=True, exist_ok=True)
        processed_dir = Path(settings.paths.data_dir) / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)

        train_output = processed_dir / "kpi_features_train.csv"
        test_output = processed_dir / "kpi_features_test.csv"
        train_features.to_csv(train_output, index=False)
        test_features.to_csv(test_output, index=False)
        logger.info("Saved processed datasets to %s and %s", train_output, test_output)

        engineer.generate_feature_reports(train_features, output_dir)
        logger.info("Generated feature reports in %s", output_dir)

        visualization_service = VisualizationService(output_dir / "plots")
        visualization_service.generate_phase3_plots(train_features)
        logger.info("Generated Phase 3 visualizations")

        validation = engineer.validate_features(train_features)
        logger.info("Feature validation status: %s", validation)

        return True
    except Exception as exc:  # pragma: no cover - runtime guard
        logger.error("Phase 3 feature engineering failed: %s", exc, exc_info=True)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
