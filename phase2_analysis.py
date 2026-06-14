"""Phase 2 – KPI Dataset Analysis execution script.

This script executes the complete Phase 2 analysis:
1. Load KPI datasets
2. Validate schemas
3. Generate profiling reports
4. Generate exploratory visualizations
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from common.logging_utils import configure_logging
from common.settings import load_settings
from data.data_loader import DataLoader
from data.dataset_profiler import DatasetProfiler
from data.schema_validator import SchemaValidator
from visualization.plotter import VisualizationService


def main():
    """Execute Phase 2 KPI Dataset Analysis."""
    # Configure logging
    logger = configure_logging("config/logging.yaml")
    logger.info("=" * 70)
    logger.info("PHASE 2 – KPI DATASET ANALYSIS")
    logger.info("=" * 70)

    try:
        # Load settings
        logger.info("Loading project settings...")
        settings = load_settings(Path("config/settings.yaml"))
        logger.info(f"Project: {settings.project.name}")
        logger.info(f"Environment: {settings.project.environment}")

        # Initialize components
        logger.info("\nInitializing components...")
        data_loader = DataLoader(settings.paths.data_dir + "/kpi")
        schema_validator = SchemaValidator()
        dataset_profiler = DatasetProfiler(settings.paths.reports_dir + "/phase2")
        visualization_service = VisualizationService(settings.paths.reports_dir + "/phase2/plots")

        # Step 1: Load datasets
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

        logger.info(f"✓ Training dataset: {len(train_df)} records")
        logger.info(f"✓ Test dataset: {len(test_df)} records")

        # Step 2: Validate schemas
        logger.info("\n" + "=" * 70)
        logger.info("STEP 2: Validating Schemas")
        logger.info("=" * 70)

        train_validation = schema_validator.validate_train_schema(train_df)
        test_validation = schema_validator.validate_test_schema(test_df)
        kpi_analysis = schema_validator.validate_kpi_ids(train_df, test_df)

        if not train_validation.is_valid:
            logger.error("Training dataset schema validation FAILED")
            logger.error(f"Errors: {train_validation.errors}")
            return False

        if not test_validation.is_valid:
            logger.error("Test dataset schema validation FAILED")
            logger.error(f"Errors: {test_validation.errors}")
            return False

        logger.info("✓ Training dataset schema validation PASSED")
        logger.info("✓ Test dataset schema validation PASSED")
        logger.info(f"✓ KPI analysis: {len(kpi_analysis['train_kpi_ids'])} training KPI IDs, "
                    f"{len(kpi_analysis['test_kpi_ids'])} test KPI IDs")

        # Step 3: Generate validation report
        logger.info("\n" + "=" * 70)
        logger.info("STEP 3: Generating Validation Report")
        logger.info("=" * 70)

        validation_report_path = Path(settings.paths.reports_dir) / "phase2" / "validation_report.txt"
        schema_validator.generate_validation_report(train_validation, test_validation, kpi_analysis, validation_report_path)
        logger.info(f"✓ Validation report saved to {validation_report_path}")

        # Step 4: Generate profiling reports
        logger.info("\n" + "=" * 70)
        logger.info("STEP 4: Generating Profiling Reports")
        logger.info("=" * 70)

        dataset_profiler.save_all_reports(train_df, test_df)
        logger.info("✓ All profiling reports generated:")
        logger.info(f"  - dataset_summary.csv")
        logger.info(f"  - descriptive_statistics.csv")
        logger.info(f"  - kpi_distribution.csv")
        logger.info(f"  - anomaly_distribution.csv")

        # Step 5: Generate visualizations
        logger.info("\n" + "=" * 70)
        logger.info("STEP 5: Generating Visualizations")
        logger.info("=" * 70)

        visualization_service.generate_all_plots(train_df, test_df)
        logger.info("✓ All visualizations generated:")
        logger.info(f"  - KPI ID distributions")
        logger.info(f"  - Anomaly distribution")
        logger.info(f"  - KPI value histograms")
        logger.info(f"  - KPI value boxplots")
        logger.info(f"  - KPI value distributions by ID")

        # Summary statistics
        logger.info("\n" + "=" * 70)
        logger.info("PHASE 2 SUMMARY")
        logger.info("=" * 70)

        summary_stats = dataset_profiler.get_summary_statistics(train_df)
        logger.info(f"Training dataset:")
        logger.info(f"  - Total records: {summary_stats['total_records']:,}")
        logger.info(f"  - KPI IDs: {summary_stats['kpi_count']}")
        logger.info(f"  - Anomalies: {summary_stats.get('anomaly_count', 'N/A'):,}")
        logger.info(f"  - Normal records: {summary_stats.get('normal_count', 'N/A'):,}")
        if 'anomaly_percentage' in summary_stats:
            logger.info(f"  - Anomaly percentage: {summary_stats['anomaly_percentage']:.2f}%")

        logger.info(f"\nTest dataset:")
        logger.info(f"  - Total records: {len(test_df):,}")
        logger.info(f"  - KPI IDs: {test_df['KPI ID'].nunique()}")

        logger.info("\n" + "=" * 70)
        logger.info("PHASE 2 ANALYSIS COMPLETED SUCCESSFULLY")
        logger.info("=" * 70)

        return True

    except Exception as e:
        logger.error(f"Phase 2 analysis failed with error: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
