# Phase 2 – Quick Reference Guide

## What Was Implemented

**Phase 2 – KPI Dataset Analysis** has been fully implemented with production-quality code.

### 📦 Deliverables

| Component | Files | Status |
|-----------|-------|--------|
| **Data Loading** | `src/data/data_loader.py` | ✅ Complete |
| **Schema Validation** | `src/data/schema_validator.py` | ✅ Complete |
| **Dataset Profiling** | `src/data/dataset_profiler.py` | ✅ Complete |
| **Visualization** | `src/visualization/plotter.py` | ✅ Enhanced |
| **Unit Tests** | `tests/unit/test_phase2_kpi_analysis.py` | ✅ 20/20 pass |
| **Main Script** | `phase2_analysis.py` | ✅ Complete |
| **Documentation** | `docs/PHASE2_README.md` | ✅ Complete |

---

## How to Use

### Option 1: Run Complete Analysis (Recommended)

```bash
cd d:\WILP\ Dissertation\wilp-dissertation
python phase2_analysis.py
```

**Output**:
- Validation report: `reports/phase2/validation_report.txt`
- CSV reports: `reports/phase2/*.csv` (4 files)
- Visualizations: `reports/phase2/plots/*.png` (9 files)
- Detailed console logs showing all operations

### Option 2: Use Individual Modules

```python
from src.data.data_loader import DataLoader
from src.data.schema_validator import SchemaValidator
from src.data.dataset_profiler import DatasetProfiler
from src.visualization.plotter import VisualizationService

# Load data
loader = DataLoader("data/kpi")
train_df = loader.load_train_data()
test_df = loader.load_test_data()

# Validate
validator = SchemaValidator()
train_result = validator.validate_train_schema(train_df)

# Profile
profiler = DatasetProfiler("reports/phase2")
profiler.save_all_reports(train_df, test_df)

# Visualize
viz = VisualizationService("reports/phase2/plots")
viz.generate_all_plots(train_df, test_df)
```

---

## Run Tests

```bash
# All Phase 2 tests
python -m pytest tests/unit/test_phase2_kpi_analysis.py -v

# Specific test class
python -m pytest tests/unit/test_phase2_kpi_analysis.py::TestDataLoader -v

# With coverage report
python -m pytest tests/unit/test_phase2_kpi_analysis.py --cov=src/data --cov-report=html
```

**Test Results**: 20/20 tests passing ✅

---

## Modules Overview

### 1. DataLoader
**Purpose**: Load KPI datasets with error handling

```python
loader = DataLoader("data/kpi")
train_df = loader.load_train_data()      # 1,048,576 rows, 4 columns
test_df = loader.load_test_data()        # 1,048,576 rows, 3 columns
result = loader.load_both()              # Returns both with error list
```

### 2. SchemaValidator
**Purpose**: Validate dataset schemas and integrity

```python
validator = SchemaValidator()
train_result = validator.validate_train_schema(train_df)
test_result = validator.validate_test_schema(test_df)

# Generate detailed report
kpi_analysis = validator.validate_kpi_ids(train_df, test_df)
validator.generate_validation_report(train_result, test_result, kpi_analysis)
```

**Checks Performed**:
- ✓ Required columns present
- ✓ Correct data types
- ✓ No missing values
- ✓ No duplicate rows
- ✓ Valid label values (0 or 1)
- ✓ Non-null KPI IDs
- ✓ KPI ID consistency

### 3. DatasetProfiler
**Purpose**: Generate statistical profiles and reports

```python
profiler = DatasetProfiler("reports/phase2")

# Generate all reports
profiler.save_all_reports(train_df, test_df)

# Individual reports
summary = profiler.generate_dataset_summary(train_df, test_df)
stats = profiler.generate_descriptive_statistics(train_df)
kpi_df = profiler.generate_kpi_analysis(train_df, test_df)
anomaly_df = profiler.generate_anomaly_distribution(train_df)
```

**Reports Generated**:
- dataset_summary.csv
- descriptive_statistics.csv
- kpi_distribution.csv
- anomaly_distribution.csv

### 4. VisualizationService
**Purpose**: Generate exploratory visualizations

```python
viz = VisualizationService("reports/phase2/plots")
viz.generate_all_plots(train_df, test_df)  # Generates all 9 plots
```

**Plots Generated**:
1. KPI ID distribution (training & testing)
2. Anomaly distribution
3. KPI value histogram (training & testing)
4. KPI value boxplot (training & testing)
5. KPI value by ID (training & testing)

---

## Generated Reports

### CSV Reports

**dataset_summary.csv**
- 8 metrics (rows, columns, KPI counts, anomaly counts, percentages)

**descriptive_statistics.csv**
- 8 statistics (min, max, mean, median, std, percentiles)
- Columns for training and testing data

**kpi_distribution.csv**
- One row per KPI ID
- Records count, anomaly count, anomaly percentage

**anomaly_distribution.csv**
- Distribution of normal vs anomaly records
- Counts and percentages

### Validation Report

**validation_report.txt**
- Training schema validation (6 checks)
- Test schema validation (5 checks)
- KPI ID analysis
- Errors and warnings

### Visualization Plots (PNG)

9 high-resolution plots (300 DPI):
- 01_kpi_id_distribution_training.png
- 01_kpi_id_distribution_testing.png
- 02_anomaly_distribution.png
- 03_kpi_value_histogram_training.png
- 03_kpi_value_histogram_testing.png
- 04_kpi_value_boxplot_training.png
- 04_kpi_value_boxplot_testing.png
- 05_kpi_value_by_id_training.png
- 05_kpi_value_by_id_testing.png

---

## Data Schema

### Training Data (train.csv)
```
1,048,576 rows × 4 columns
- timestamp: ISO format datetime
- value: float (KPI values)
- label: int (0=normal, 1=anomaly)
- KPI ID: string (10 unique IDs in training)
```

### Test Data (test.csv)
```
1,048,576 rows × 3 columns
- timestamp: ISO format datetime
- value: float (KPI values)
- KPI ID: string (16 unique IDs in test)
Note: No labels in test data
```

---

## Code Quality

✅ **Type Hints**: All functions type-hinted  
✅ **Docstrings**: All classes and methods documented  
✅ **Error Handling**: Comprehensive exception handling  
✅ **Logging**: Debug, info, warning, error levels  
✅ **Testing**: 20 comprehensive unit tests  
✅ **Style**: PEP 8 compliant  

---

## Logging

All Phase 2 modules log to:
- **Console**: INFO level and above
- **File**: `data/logs/project.log`
- **Format**: `timestamp | level | logger | message`

Example log output:
```
2026-06-08 14:30:45 | INFO | project | Loading training data from data/kpi/train.csv
2026-06-08 14:30:46 | INFO | project | Successfully loaded 1048576 training records
2026-06-08 14:30:46 | INFO | project | Validating training dataset schema
2026-06-08 14:30:47 | INFO | project | ✓ All required columns present
```

---

## Folder Structure

```
wilp-dissertation/
├── src/
│   └── data/
│       ├── __init__.py (NEW)
│       ├── data_loader.py (NEW)
│       ├── schema_validator.py (NEW)
│       └── dataset_profiler.py (NEW)
├── reports/
│   └── phase2/ (NEW)
│       ├── plots/ (NEW)
│       ├── dataset_summary.csv
│       ├── descriptive_statistics.csv
│       ├── kpi_distribution.csv
│       ├── anomaly_distribution.csv
│       └── validation_report.txt
├── tests/
│   └── unit/
│       └── test_phase2_kpi_analysis.py (NEW)
└── phase2_analysis.py (NEW)
```

---

## Important Notes

### ⚠️ DO NOT IMPLEMENT
- Feature engineering (Phase 3)
- Isolation Forest model (Phase 4)
- LSTM model (Phase 5)
- Any anomaly detection logic
- Fusion layer (Phase 9)

### ✅ PHASE 2 ONLY
Only Phase 2 functionality is implemented. No future phases included.

### 📊 Anomaly Analysis
- Anomaly labels only available in training data
- Test data has no labels (as specified)
- Anomaly percentages calculated per KPI ID

### 🔍 KPI IDs
- Training: 10 unique KPI IDs
- Test: 16 unique KPI IDs
- Validation checks for unexpected test KPI IDs

---

## Next Steps

Phase 2 is complete and ready. The next phase is:

**Phase 3 – KPI Feature Engineering**
- Lag features (lag-1, lag-5, lag-10)
- Rolling features (mean and std)
- Optional time features
- Feature validation

Do not proceed until Phase 2 is reviewed and approved.

---

## Quick Commands Reference

```bash
# Run complete analysis
python phase2_analysis.py

# Run all tests
python -m pytest tests/unit/test_phase2_kpi_analysis.py -v

# Run specific test
python -m pytest tests/unit/test_phase2_kpi_analysis.py::TestDataLoader::test_load_train_data_success -v

# Run with coverage
python -m pytest tests/unit/test_phase2_kpi_analysis.py --cov=src/data --cov-report=html

# Import individual modules (in Python)
from src.data.data_loader import DataLoader
from src.data.schema_validator import SchemaValidator
from src.data.dataset_profiler import DatasetProfiler
from src.visualization.plotter import VisualizationService
```

---

## Support

All modules include:
- Comprehensive docstrings
- Type hints
- Error messages
- Logging statements
- Unit tests

See `docs/PHASE2_README.md` for detailed module documentation.
