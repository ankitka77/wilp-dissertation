# Phase 2 – KPI Dataset Analysis

## Overview

Phase 2 focuses on understanding and validating the AIOps KPI dataset. This phase includes:

- **Data Loading**: Robust loading of training and test CSV files with error handling
- **Schema Validation**: Comprehensive schema validation with detailed error reporting
- **Dataset Profiling**: Statistical analysis and summary generation
- **Exploratory Visualizations**: Five different visualization types for data exploration

## Folder Structure

```
wilp-dissertation/
├── data/
│   └── kpi/
│       ├── train.csv        # Training dataset (1,048,576 rows)
│       └── test.csv         # Test dataset (1,048,576 rows)
├── src/
│   └── data/
│       ├── __init__.py
│       ├── data_loader.py       # Load datasets from CSV
│       ├── schema_validator.py   # Validate dataset schemas
│       └── dataset_profiler.py   # Generate profiling statistics
├── reports/
│   └── phase2/
│       ├── plots/                # Generated visualizations
│       ├── dataset_summary.csv
│       ├── descriptive_statistics.csv
│       ├── kpi_distribution.csv
│       ├── anomaly_distribution.csv
│       └── validation_report.txt
├── tests/
│   └── unit/
│       └── test_phase2_kpi_analysis.py  # Comprehensive unit tests
└── phase2_analysis.py           # Main execution script
```

## Module Descriptions

### data_loader.py

**Purpose**: Load KPI datasets from CSV files with validation and error handling.

**Key Classes**:
- `DataLoader`: Main data loading class
- `DataloadResult`: NamedTuple containing load results and errors

**Features**:
- Validates file existence before loading
- Handles CSV parsing errors gracefully
- Returns pandas DataFrames with proper type conversions
- Comprehensive logging of all operations
- Ability to load both datasets simultaneously with partial success handling

**Usage**:
```python
from data.data_loader import DataLoader

loader = DataLoader("data/kpi")
train_df = loader.load_train_data()
test_df = loader.load_test_data()

# Or load both with error handling
result = loader.load_both()
if result.errors:
    print("Warnings:", result.errors)
```

### schema_validator.py

**Purpose**: Validate dataset schemas against expected requirements.

**Key Classes**:
- `SchemaValidator`: Main validation class
- `ValidationResult`: Dataclass containing validation results and metadata

**Validation Checks**:
1. Required columns present
2. Correct data types
3. No missing values
4. No duplicate rows
5. Valid label values (0 or 1) for training data
6. Non-null KPI IDs
7. KPI ID consistency between train and test

**Features**:
- Detailed validation reports with pass/fail status
- Error and warning classifications
- KPI ID analysis and cross-validation
- CSV report generation

**Usage**:
```python
from data.schema_validator import SchemaValidator

validator = SchemaValidator()
train_result = validator.validate_train_schema(train_df)
test_result = validator.validate_test_schema(test_df)

if train_result.is_valid:
    print("✓ Training schema valid")
else:
    print("✗ Errors:", train_result.errors)

# Generate detailed report
kpi_analysis = validator.validate_kpi_ids(train_df, test_df)
validator.generate_validation_report(train_result, test_result, kpi_analysis)
```

### dataset_profiler.py

**Purpose**: Generate statistical profiles and summaries of datasets.

**Key Classes**:
- `DatasetProfiler`: Main profiling class

**Reports Generated**:

1. **Dataset Summary**
   - Number of rows, columns, KPI IDs
   - Anomaly and normal record counts
   - Anomaly percentages

2. **Descriptive Statistics**
   - Min, max, mean, median, standard deviation
   - 25th and 75th percentiles

3. **KPI Analysis**
   - Records per KPI ID
   - Anomaly count per KPI ID
   - Anomaly percentage per KPI ID

4. **Anomaly Distribution**
   - Normal vs anomaly record counts
   - Percentage distribution

**Usage**:
```python
from data.dataset_profiler import DatasetProfiler

profiler = DatasetProfiler("reports/phase2")

# Generate and save all reports
profiler.save_all_reports(train_df, test_df)

# Or generate individual reports
summary = profiler.generate_dataset_summary(train_df, test_df)
stats = profiler.generate_descriptive_statistics(train_df)
kpi_analysis = profiler.generate_kpi_analysis(train_df, test_df)
```

### visualization/plotter.py (Enhanced)

**Purpose**: Generate exploratory visualizations for KPI data.

**Key Classes**:
- `VisualizationService`: Visualization generation class

**Plots Generated**:
1. **KPI ID Distribution**: Bar chart showing records per KPI ID
2. **Anomaly Distribution**: Distribution of normal vs anomaly records
3. **KPI Value Histogram**: Distribution of all KPI values
4. **KPI Value Boxplot**: Boxplot of KPI values
5. **KPI Distribution by ID**: Boxplot grouped by KPI ID

**Usage**:
```python
from visualization.plotter import VisualizationService

viz = VisualizationService("reports/phase2/plots")

# Generate all plots
viz.generate_all_plots(train_df, test_df)

# Or generate individual plots
viz.plot_kpi_id_distribution(train_df, "training")
viz.plot_anomaly_distribution(train_df)
```

## Execution

### Method 1: Run Main Script

Execute the complete Phase 2 analysis:

```bash
cd d:\WILP\ Dissertation\wilp-dissertation
python phase2_analysis.py
```

**Output**:
- All validation reports saved to `reports/phase2/`
- All CSV reports saved to `reports/phase2/`
- All plots saved to `reports/phase2/plots/`
- Detailed console logging showing all operations

### Method 2: Run Individual Components

```python
from pathlib import Path
from common.logging_utils import configure_logging
from common.settings import load_settings
from data.data_loader import DataLoader
from data.schema_validator import SchemaValidator
from data.dataset_profiler import DatasetProfiler
from visualization.plotter import VisualizationService

# Configure logging
logger = configure_logging("config/logging.yaml")
settings = load_settings(Path("config/settings.yaml"))

# Load data
loader = DataLoader("data/kpi")
train_df = loader.load_train_data()
test_df = loader.load_test_data()

# Validate schema
validator = SchemaValidator()
train_result = validator.validate_train_schema(train_df)
test_result = validator.validate_test_schema(test_df)

# Profile dataset
profiler = DatasetProfiler("reports/phase2")
profiler.save_all_reports(train_df, test_df)

# Generate visualizations
viz = VisualizationService("reports/phase2/plots")
viz.generate_all_plots(train_df, test_df)
```

## Running Tests

### Run All Phase 2 Tests

```bash
cd d:\WILP\ Dissertation\wilp-dissertation
python -m pytest tests/unit/test_phase2_kpi_analysis.py -v
```

### Run Specific Test Class

```bash
python -m pytest tests/unit/test_phase2_kpi_analysis.py::TestDataLoader -v
python -m pytest tests/unit/test_phase2_kpi_analysis.py::TestSchemaValidator -v
python -m pytest tests/unit/test_phase2_kpi_analysis.py::TestDatasetProfiler -v
```

### Run with Coverage

```bash
python -m pytest tests/unit/test_phase2_kpi_analysis.py --cov=src/data --cov-report=html
```

## Data Schema

### Training Dataset (train.csv)

| Column   | Type    | Description                              |
|----------|---------|------------------------------------------|
| timestamp| object  | ISO format timestamp                     |
| value    | float64 | KPI numeric value                        |
| label    | int64   | Anomaly label (0=normal, 1=anomaly)     |
| KPI ID   | object  | Unique KPI identifier                    |

**Statistics**:
- Training Rows: 1,048,576
- Unique KPI IDs: 10

### Test Dataset (test.csv)

| Column   | Type    | Description                    |
|----------|---------|--------------------------------|
| timestamp| object  | ISO format timestamp           |
| value    | float64 | KPI numeric value              |
| KPI ID   | object  | Unique KPI identifier          |

**Statistics**:
- Test Rows: 1,048,576
- Unique KPI IDs: 16

## Generated Outputs

### Validation Report (validation_report.txt)

Comprehensive validation report including:
- Training and test schema validation status
- Validation check results
- Error and warning lists
- KPI ID analysis

### CSV Reports

1. **dataset_summary.csv**: High-level dataset statistics
2. **descriptive_statistics.csv**: Statistical measures for KPI values
3. **kpi_distribution.csv**: Per-KPI statistics (records, anomalies)
4. **anomaly_distribution.csv**: Anomaly vs normal distribution

### Plots (PNG files)

1. `01_kpi_id_distribution_training.png` - Training KPI distribution
2. `01_kpi_id_distribution_testing.png` - Test KPI distribution
3. `02_anomaly_distribution.png` - Anomaly vs normal records
4. `03_kpi_value_histogram_training.png` - Training value histogram
5. `03_kpi_value_histogram_testing.png` - Test value histogram
6. `04_kpi_value_boxplot_training.png` - Training value boxplot
7. `04_kpi_value_boxplot_testing.png` - Test value boxplot
8. `05_kpi_value_by_id_training.png` - Training values by KPI ID
9. `05_kpi_value_by_id_testing.png` - Test values by KPI ID

## Code Quality

All Phase 2 modules follow these standards:

- ✓ Type hints on all functions and parameters
- ✓ Comprehensive docstrings for classes and methods
- ✓ Production-quality error handling
- ✓ Structured logging throughout
- ✓ No hard-coded paths (uses configuration)
- ✓ Modular, reusable design
- ✓ Full test coverage (20 unit tests)
- ✓ Follows PEP 8 style guidelines

## Logging

The project uses a centralized logging configuration (config/logging.yaml):

- **Console Output**: INFO level and above
- **File Output**: INFO level and above to `data/logs/project.log`
- **Format**: `timestamp | level | logger | message`

Phase 2 modules log:
- Files being loaded
- Validation check results
- Generated reports
- Generated visualizations
- Any errors or warnings

## Next Steps

Phase 2 is complete. The next phase is:

**Phase 3 – KPI Feature Engineering**
- Generate lag features (lag-1, lag-5, lag-10)
- Generate rolling features (mean and std)
- Optional time features (hour of day, day of week)
- Feature validation reports

Do not implement feature engineering or any models until Phase 3 is approved.
