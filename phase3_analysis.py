"""Phase 3 – KPI Feature Engineering execution script.

This script executes the complete Phase 3 workflow:
1. Load KPI datasets
2. Generate engineered features
3. Validate engineered features
4. Generate feature reports
5. Generate feature visualizations
6. Save processed datasets
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from common.logging_utils import configure_logging
from common.settings import load_settings
from data.data_loader import DataLoader
from preprocessing.pipeline import FeatureEngineeringConfig, KPIFeatureEngineer, PreprocessingPipeline
from visualization.plotter import VisualizationService


def main() -> bool:
    """Execute the Phase 3 KPI feature engineering workflow."""
    logger = configure_logging("config/logging.yaml")
    logger.info("=" * 70)
    logger.info("PHASE 3 – KPI FEATURE ENGINEERING")
    logger.info("=" * 70)

    try:
        logger.info("Loading project settings...")
        settings = load_settings(Path("config/settings.yaml"))
        logger.info(f"Project: {settings.project.name}")
        logger.info(f"Environment: {settings.project.environment}")

        logger.info("\nInitializing components...")
        data_loader = DataLoader(settings.paths.data_dir + "/kpi")
        feature_config = FeatureEngineeringConfig(
            lag_values=settings.feature_engineering.lag_values,
            rolling_windows=settings.feature_engineering.rolling_windows,
            ema_periods=settings.feature_engineering.ema_periods,
            normalize=settings.feature_engineering.normalize,
            missing_strategy=settings.feature_engineering.missing_strategy,
            include_timestamp_features=settings.feature_engineering.include_timestamp_features,
        )
        feature_engineer = KPIFeatureEngineer(config=feature_config)
        pipeline = PreprocessingPipeline(config=feature_config)
        visualization_service = VisualizationService(settings.artifacts.plots_root)

        logger.info("\n" + "=" * 70)
        logger.info("STEP 1: Loading Datasets")
        logger.info("=" * 70)
        load_result = data_loader.load_both()

        if load_result.errors:
            logger.error(f"Data loading encountered {len(load_result.errors)} error(s):")
            for error in load_result.errors:
                logger.error(f"  - {error}")
            if load_result.train_df is None or load_result.test_df is None:
                logger.error("Cannot proceed without both training and test datasets")
                return False

        train_df = load_result.train_df
        test_df = load_result.test_df
        logger.info(f"[OK] Training dataset: {len(train_df):,} records")
        logger.info(f"[OK] Test dataset: {len(test_df):,} records")

        logger.info("\n" + "=" * 70)
        logger.info("STEP 2: Generating Engineered Features")
        logger.info("=" * 70)
        train_features = pipeline.fit_transform_kpi(train_df)
        test_features = pipeline.transform_kpi(test_df)
        logger.info(f"[OK] Training features: {train_features.shape[1]} columns")
        logger.info(f"[OK] Test features: {test_features.shape[1]} columns")

        logger.info("\n" + "=" * 70)
        logger.info("STEP 3: Validating Features")
        logger.info("=" * 70)
        train_validation = feature_engineer.validate_features(train_features)
        test_validation = feature_engineer.validate_features(test_features)
        logger.info(f"[OK] Training feature validation: {train_validation}")
        logger.info(f"[OK] Test feature validation: {test_validation}")

        logger.info("\n" + "=" * 70)
        logger.info("STEP 4: Generating Reports")
        logger.info("=" * 70)
        output_dir = settings.artifacts.phase_report_dir("phase3")
        feature_engineer.generate_feature_reports(train_features, output_dir)
        logger.info(f"[OK] Feature reports saved to {output_dir}")

        logger.info("\n" + "=" * 70)
        logger.info("STEP 5: Generating Visualizations")
        logger.info("=" * 70)
        visualization_service.generate_phase3_plots(train_features)
        logger.info("[OK] Feature engineering visualizations generated")

        logger.info("\n" + "=" * 70)
        logger.info("STEP 6: Saving Processed Datasets")
        logger.info("=" * 70)
        processed_dir = Path(settings.paths.data_dir) / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)
        train_output = processed_dir / "kpi_features_train.csv"
        test_output = processed_dir / "kpi_features_test.csv"
        train_features.to_csv(train_output, index=False)
        test_features.to_csv(test_output, index=False)
        logger.info(f"[OK] Training dataset saved to {train_output}")
        logger.info(f"[OK] Test dataset saved to {test_output}")

        logger.info("\n" + "=" * 70)
        logger.info("PHASE 3 FEATURE ENGINEERING COMPLETED SUCCESSFULLY")
        logger.info("=" * 70)
        return True

    except Exception as exc:  # pragma: no cover - runtime guard
        logger.error(f"Phase 3 feature engineering failed with error: {exc}", exc_info=True)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
