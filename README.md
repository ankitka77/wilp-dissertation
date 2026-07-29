# Anomaly and Fault Detection in Wireless Systems

## Project Overview

This project is part of an M.Tech (AI/ML) dissertation at BITS Pilani. The goal is to build a machine-learning framework for anomaly and fault detection in wireless systems using:

- KPI-based anomaly detection
- Log-based anomaly detection
- Later-stage fusion of KPI and log signals

The project currently has Phase 2 implemented and working end to end for KPI dataset analysis.

## Current Status

Implemented and working now:

- Project configuration and logging setup
- KPI training/test data loading
- KPI schema validation
- KPI dataset profiling and report generation
- Exploratory plot generation
- A simple weighted fusion scaffold
- Basic evaluation utilities
- Unit tests for the implemented functionality

Phase-level status:

- Phase 1: Project setup completed
- Phase 2: KPI dataset analysis completed and runnable
- Later phases: preprocessing, KPI modeling, log modeling, fusion expansion, and evaluation remain scaffolded or partially planned

## How To Run

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run tests:

```powershell
pytest -q
```

Run the current Phase 2 pipeline:

```powershell
python phase2_analysis.py
```

Run the Phase 3 feature engineering pipeline:

```powershell
python phase3_feature_engineering.py
```

Run the Phase 4 anomaly detection pipeline:

```powershell
python phase4_analysis.py
```

Phase 3 outputs are written to:

- data/processed/kpi_features_train.csv
- data/processed/kpi_features_test.csv
- artifacts/reports/phase3/feature_summary.csv
- artifacts/reports/phase3/feature_statistics.csv
- artifacts/reports/phase3/feature_correlation.csv
- artifacts/plots/

Phase 4 outputs are written to:

- artifacts/models/
- artifacts/reports/phase4/
- artifacts/experiments/
- artifacts/plots/

## Data Placement

Place your datasets exactly here:

- Training data: `data/kpi/train.csv`
- Test data: `data/kpi/test.csv`

Important notes:

- The filenames must be exactly `train.csv` and `test.csv`
- The pipeline reads them relative to the repository root
- The current loader expects the KPI files under `data/kpi`

Expected column layout:

- Training data: `timestamp`, `value`, `label`, `KPI ID`
- Test data: `timestamp`, `value`, `KPI ID`

## Output Locations

When you run `phase2_analysis.py`, the generated artifacts are written to:

- `artifacts/reports/phase2/validation_report.txt`
- `artifacts/reports/phase2/dataset_summary.csv`
- `artifacts/reports/phase2/dataset_summary.json`
- `artifacts/reports/phase2/descriptive_statistics.csv`
- `artifacts/reports/phase2/kpi_distribution.csv`
- `artifacts/reports/phase2/anomaly_distribution.csv`
- `artifacts/reports/phase2/timestamp_analysis.csv`
- `artifacts/plots/`

## Repository Layout

```text
wilp-dissertation/
├── .env
├── .gitignore
├── README.md
├── phase2_analysis.py
├── pytest.ini
├── requirements-dev.txt
├── requirements.txt
├── config/
│   ├── logging.yaml
│   └── settings.yaml
├── data/
│   ├── kpi/
│   │   ├── train.csv
│   │   └── test.csv
│   └── logs/
├── docs/
├── notebooks/
├── papers/
├── reports/
│   └── phase2/
│       ├── plots/
│       ├── anomaly_distribution.csv
│       ├── dataset_summary.csv
│       ├── dataset_summary.json
│       ├── descriptive_statistics.csv
│       ├── kpi_distribution.csv
│       ├── timestamp_analysis.csv
│       └── validation_report.txt
├── src/
│   ├── __init__.py
│   ├── common/
│   │   ├── __init__.py
│   │   ├── logging_utils.py
│   │   └── settings.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── data_loader.py
│   │   ├── dataset_profiler.py
│   │   └── schema_validator.py
│   ├── evaluation/
│   │   ├── __init__.py
│   │   └── metrics.py
│   ├── fusion/
│   │   ├── __init__.py
│   │   └── fusion_engine.py
│   ├── kpi_model/
│   │   ├── __init__.py
│   │   └── model.py
│   ├── log_model/
│   │   ├── __init__.py
│   │   └── model.py
│   ├── preprocessing/
│   │   ├── __init__.py
│   │   └── pipeline.py
│   └── visualization/
│       ├── __init__.py
│       └── plotter.py
└── tests/
  ├── conftest.py
  ├── phase9/
  │   ├── test_config.py
  │   ├── test_discovery_manifest.py
  │   ├── test_exceptions.py
  │   ├── test_logging.py
  │   ├── test_schemas.py
  │   └── test_utils.py
  └── unit/
    ├── test_phase2_kpi_analysis.py
    └── test_project_setup.py
```

### Root Directory

The root contains project-wide entry points and configuration:

- `phase2_analysis.py`: Main script that runs the full Phase 2 workflow
- `requirements.txt`: Runtime dependencies
- `requirements-dev.txt`: Extra development dependencies
- `pytest.ini`: Pytest configuration
- `.env`: Local environment overrides for development
- `README.md`: Project overview and usage guide
- `PHASE2_*.md`: Phase 2 delivery, implementation, checklist, summary, and quick reference documents

### `config/`

Project configuration files.

- `settings.yaml`: Main project settings such as project name, environment, and base paths
- `logging.yaml`: Logging configuration used by the application logger

### `data/`

Project data storage.

- `data/kpi/`: Input KPI datasets used by the current pipeline
- `data/logs/`: Log output directory used by the configured logger

### `reports/`

Generated analysis outputs.

- `artifacts/reports/phase2/`: Phase 2 analysis artifacts
- `artifacts/plots/`: Saved PNG plots generated by the visualization module

### `docs/`

Reference documentation and project notes.

Typical contents here include:

- Architecture notes
- Dataset documentation
- Literature review material
- Development roadmap documents

### `notebooks/`

Interactive notebooks for experiments, analysis, or prototype work.

### `papers/`

Research papers, references, and supporting academic material used for the dissertation.

### `src/`

Main Python source code.

#### `src/common/`

Shared utilities used across the project.

- `settings.py`: Loads YAML settings and optional environment overrides from `.env`
- `logging_utils.py`: Configures the project logger from `config/logging.yaml`
- `__init__.py`: Marks the directory as a package

#### `src/data/`

KPI dataset loading, validation, and profiling logic.

- `data_loader.py`: Loads `train.csv` and `test.csv` from `data/kpi`, parses timestamps, and returns both datasets
- `schema_validator.py`: Validates required columns, data types, KPI IDs, missing values, duplicates, and validation reports
- `dataset_profiler.py`: Produces dataset summary statistics, descriptive stats, KPI-level analysis, anomaly distribution, and timestamp analysis
- `__init__.py`: Marks the directory as a package

#### `src/preprocessing/`

Preprocessing scaffolding for later phases.

- `pipeline.py`: Placeholder for KPI and log preprocessing workflows
- `__init__.py`: Package marker

#### `src/kpi_model/`

KPI anomaly detection model scaffolding.

- `model.py`: Base KPI anomaly model interface with `fit` and `predict` placeholders
- `__init__.py`: Package marker

#### `src/log_model/`

Log anomaly detection model scaffolding.

- `model.py`: Base log anomaly model interface with `fit` and `predict` placeholders
- `__init__.py`: Package marker

#### `src/log_processing/`

- Phase 5 log preprocessing and preparation utilities.

- This package contains loaders, parsers, template miners, vocabulary builders, sequence builders, validators, profilers and report generators used to convert raw system logs (HDFS/BGL style) into the sequence-based datasets required by later models (e.g., DeepLog in Phase 6).

- All Phase 5 *preprocessing* logic is intentionally placed under `src/log_processing` to avoid ambiguity with model implementations.

#### `src/log_model/` (retained as future model package)

- Purpose: a lightweight scaffold reserved for Phase 6/7 model implementations (e.g., DeepLog/sequence models) and for backwards-compatibility references in earlier phases.

- Current state: contains a minimal `LogAnomalyModel` scaffold (see `src/log_model/model.py`) and is not used for Phase 5 preprocessing. It is preserved so Phase 6 model development can target a dedicated package without impacting Phase 1–5 code paths.

- If you prefer to remove the package now and reintroduce it later, let me know; keeping it avoids breaking any code that may import `src.log_model` and clarifies where DeepLog model code should live.

#### `src/fusion/`

Fusion logic that combines KPI and log signals.

- `fusion_engine.py`: Defines the base fusion interface and a simple `WeightedFusionEngine`
- `__init__.py`: Exports the fusion engine classes

#### `src/evaluation/`

Evaluation utilities for anomaly detection results.

- `metrics.py`: Wraps standard classification metrics such as accuracy, precision, recall, F1, and ROC-AUC
- `__init__.py`: Exports the evaluation service

#### `src/visualization/`

Plot generation for dataset exploration.

- `plotter.py`: Creates KPI distribution plots, anomaly plots, histograms, boxplots, and per-KPI value distribution plots
- `__init__.py`: Package marker

### `tests/`

Automated tests.

- `tests/unit/test_project_setup.py`: Smoke tests for configuration, logging, and fusion setup
- `tests/unit/test_phase2_kpi_analysis.py`: Unit tests for data loading, schema validation, dataset profiling, and report generation
- `tests/conftest.py`: Shared pytest fixtures and test setup

## Configuration Notes

The project uses YAML configuration files and a small optional `.env` file.

- `config/settings.yaml` is the main settings file
- `config/logging.yaml` controls logging behavior
- `.env` can override runtime values such as:
  - `WILP_ENVIRONMENT`
  - `WILP_RANDOM_SEED`
  - `WILP_LOG_LEVEL`

## Notes On The Current Pipeline

The Phase 2 runner performs the following steps:

1. Loads KPI train/test CSV files
2. Validates dataset schema
3. Generates a validation report
4. Generates profiling CSV/JSON outputs
5. Generates visualizations into `artifacts/plots`

The current implementation is now runnable on Windows and uses a headless plotting backend so the pipeline can complete without a GUI Tk installation.

## Technology Stack

- Python
- Pandas
- NumPy
- SciPy
- Scikit-Learn
- TensorFlow/Keras
- Matplotlib
- Pytest

## Author

M.Tech AI/ML Dissertation Project
BITS Pilani (WILP)
