# Phase 3 Implementation Summary

## Objective

Phase 3 implements KPI feature engineering for the AIOps dataset without introducing any ML models. The pipeline generates temporal, lag-based, rolling, EMA, rate-of-change, and normalization features while preserving the raw value column.

## Implemented Components

- FeatureEngineeringConfig for configurable lag, rolling, EMA, normalization, and missing-value handling.
- KPIFeatureEngineer for grouped-by-KPI feature generation and validation.
- Phase 3 execution script for end-to-end dataset processing and output generation.
- Visualization helpers for correlation, feature distributions, and rolling mean examples.

## Outputs

- Processed datasets: data/processed/kpi_features_train.csv and data/processed/kpi_features_test.csv
- Reports: reports/phase3/feature_summary.csv, reports/phase3/feature_statistics.csv, reports/phase3/feature_correlation.csv
- Visualizations: reports/phase3/plots/06_feature_correlation_heatmap.png, 07_feature_distributions.png, 08_rolling_mean_example.png

## Execution

Run:

```powershell
python phase3_feature_engineering.py
```
