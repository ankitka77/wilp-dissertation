"""Unit tests for Phase 2 – KPI Dataset Analysis."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
import pytest

from data.data_loader import DataLoader, DataloadResult
from data.dataset_profiler import DatasetProfiler
from data.schema_validator import SchemaValidator, ValidationResult


class TestDataLoader:
    """Test suite for DataLoader class."""

    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary directory with test data."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create training CSV
            train_data = {
                "timestamp": ["2021-01-01 00:00:00", "2021-01-01 01:00:00"],
                "value": [100.5, 102.3],
                "label": [0, 1],
                "KPI ID": ["KPI-1", "KPI-1"],
            }
            train_df = pd.DataFrame(train_data)
            train_df.to_csv(tmpdir_path / "train.csv", index=False)

            # Create test CSV
            test_data = {
                "timestamp": ["2021-02-01 00:00:00", "2021-02-01 01:00:00"],
                "value": [105.0, 103.2],
                "KPI ID": ["KPI-1", "KPI-2"],
            }
            test_df = pd.DataFrame(test_data)
            test_df.to_csv(tmpdir_path / "test.csv", index=False)

            yield tmpdir_path

    def test_load_train_data_success(self, temp_data_dir):
        """Test successful training data loading."""
        loader = DataLoader(temp_data_dir)
        df = loader.load_train_data()

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert list(df.columns) == ["timestamp", "value", "label", "KPI ID"]

    def test_load_test_data_success(self, temp_data_dir):
        """Test successful test data loading."""
        loader = DataLoader(temp_data_dir)
        df = loader.load_test_data()

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert list(df.columns) == ["timestamp", "value", "KPI ID"]

    def test_load_both_success(self, temp_data_dir):
        """Test loading both datasets."""
        loader = DataLoader(temp_data_dir)
        result = loader.load_both()

        assert isinstance(result, DataloadResult)
        assert result.train_df is not None
        assert result.test_df is not None
        assert len(result.errors) == 0

    def test_load_train_data_missing_file(self):
        """Test loading with missing training file."""
        loader = DataLoader("/nonexistent/path")

        with pytest.raises(FileNotFoundError):
            loader.load_train_data()

    def test_load_test_data_missing_file(self):
        """Test loading with missing test file."""
        loader = DataLoader("/nonexistent/path")

        with pytest.raises(FileNotFoundError):
            loader.load_test_data()

    def test_validate_file_paths_success(self, temp_data_dir):
        """Test file path validation with existing files."""
        loader = DataLoader(temp_data_dir)
        assert loader.validate_file_paths() is True

    def test_validate_file_paths_failure(self):
        """Test file path validation with missing files."""
        loader = DataLoader("/nonexistent/path")
        assert loader.validate_file_paths() is False


class TestSchemaValidator:
    """Test suite for SchemaValidator class."""

    @pytest.fixture
    def valid_train_df(self):
        """Create valid training DataFrame."""
        return pd.DataFrame({
            "timestamp": ["2021-01-01 00:00:00", "2021-01-01 01:00:00"],
            "value": [100.5, 102.3],
            "label": [0, 1],
            "KPI ID": ["KPI-1", "KPI-1"],
        })

    @pytest.fixture
    def valid_test_df(self):
        """Create valid test DataFrame."""
        return pd.DataFrame({
            "timestamp": ["2021-02-01 00:00:00", "2021-02-01 01:00:00"],
            "value": [105.0, 103.2],
            "KPI ID": ["KPI-1", "KPI-2"],
        })

    @pytest.fixture
    def invalid_train_df(self):
        """Create invalid training DataFrame (missing label column)."""
        return pd.DataFrame({
            "timestamp": ["2021-01-01 00:00:00", "2021-01-01 01:00:00"],
            "value": [100.5, 102.3],
            "KPI ID": ["KPI-1", "KPI-1"],
        })

    def test_validate_train_schema_valid(self, valid_train_df):
        """Test validation of valid training schema."""
        validator = SchemaValidator()
        result = validator.validate_train_schema(valid_train_df)

        assert isinstance(result, ValidationResult)
        assert result.dataset_type == "Training"
        assert result.is_valid is True
        assert result.passed_checks == result.total_checks

    def test_validate_test_schema_valid(self, valid_test_df):
        """Test validation of valid test schema."""
        validator = SchemaValidator()
        result = validator.validate_test_schema(valid_test_df)

        assert isinstance(result, ValidationResult)
        assert result.dataset_type == "Test"
        assert result.is_valid is True
        assert result.passed_checks == result.total_checks

    def test_validate_train_schema_invalid_missing_column(self, invalid_train_df):
        """Test validation with missing column."""
        validator = SchemaValidator()
        result = validator.validate_train_schema(invalid_train_df)

        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_validate_kpi_ids(self, valid_train_df, valid_test_df):
        """Test KPI ID validation."""
        validator = SchemaValidator()
        analysis = validator.validate_kpi_ids(valid_train_df, valid_test_df)

        assert "train_kpi_ids" in analysis
        assert "train_kpi_count" in analysis
        assert "test_kpi_ids" in analysis
        assert "test_kpi_count" in analysis

    def test_validation_result_summary(self, valid_train_df):
        """Test ValidationResult summary method."""
        validator = SchemaValidator()
        result = validator.validate_train_schema(valid_train_df)

        summary = result.summary()
        assert "Training Validation" in summary or "Validation" in summary
        assert "checks passed" in summary

    def test_generate_validation_report(self, valid_train_df, valid_test_df):
        """Test validation report generation."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            validator = SchemaValidator()
            train_result = validator.validate_train_schema(valid_train_df)
            test_result = validator.validate_test_schema(valid_test_df)
            kpi_analysis = validator.validate_kpi_ids(valid_train_df, valid_test_df)

            report_path = tmpdir_path / "validation_report.txt"
            validator.generate_validation_report(train_result, test_result, kpi_analysis, report_path)

            assert report_path.exists()
            content = report_path.read_text()
            assert "VALIDATION REPORT" in content
            assert "TRAINING" in content
            assert "TEST" in content


class TestDatasetProfiler:
    """Test suite for DatasetProfiler class."""

    @pytest.fixture
    def sample_train_df(self):
        """Create sample training DataFrame."""
        return pd.DataFrame({
            "timestamp": pd.date_range("2021-01-01", periods=10),
            "value": [100.0 + i * 2.5 for i in range(10)],
            "label": [0, 1, 0, 1, 0, 0, 1, 0, 0, 0],
            "KPI ID": ["KPI-1"] * 5 + ["KPI-2"] * 5,
        })

    @pytest.fixture
    def sample_test_df(self):
        """Create sample test DataFrame."""
        return pd.DataFrame({
            "timestamp": pd.date_range("2021-02-01", periods=6),
            "value": [110.0 + i * 3.0 for i in range(6)],
            "KPI ID": ["KPI-1"] * 3 + ["KPI-2"] * 3,
        })

    def test_generate_dataset_summary_training_only(self, sample_train_df):
        """Test dataset summary generation with training data only."""
        with TemporaryDirectory() as tmpdir:
            profiler = DatasetProfiler(tmpdir)
            summary = profiler.generate_dataset_summary(sample_train_df)

            assert isinstance(summary, pd.DataFrame)
            assert "Metric" in summary.columns
            assert "Training" in summary.columns
            assert len(summary) > 0

    def test_generate_dataset_summary_with_test(self, sample_train_df, sample_test_df):
        """Test dataset summary generation with both training and test data."""
        with TemporaryDirectory() as tmpdir:
            profiler = DatasetProfiler(tmpdir)
            summary = profiler.generate_dataset_summary(sample_train_df, sample_test_df)

            assert isinstance(summary, pd.DataFrame)
            assert "Training" in summary.columns
            assert "Testing" in summary.columns

    def test_generate_descriptive_statistics(self, sample_train_df):
        """Test descriptive statistics generation."""
        with TemporaryDirectory() as tmpdir:
            profiler = DatasetProfiler(tmpdir)
            stats = profiler.generate_descriptive_statistics(sample_train_df)

            assert isinstance(stats, pd.DataFrame)
            assert "Statistic" in stats.columns
            assert len(stats) > 0
            assert "Min" in stats["Statistic"].values or "mean" in str(stats).lower()

    def test_generate_kpi_analysis(self, sample_train_df, sample_test_df):
        """Test KPI analysis generation."""
        with TemporaryDirectory() as tmpdir:
            profiler = DatasetProfiler(tmpdir)
            kpi_analysis = profiler.generate_kpi_analysis(sample_train_df, sample_test_df)

            assert isinstance(kpi_analysis, pd.DataFrame)
            assert "KPI ID" in kpi_analysis.columns
            assert "Train Records" in kpi_analysis.columns
            assert len(kpi_analysis) == 2  # Two KPI IDs

    def test_generate_anomaly_distribution(self, sample_train_df):
        """Test anomaly distribution generation."""
        with TemporaryDirectory() as tmpdir:
            profiler = DatasetProfiler(tmpdir)
            anomaly_dist = profiler.generate_anomaly_distribution(sample_train_df)

            assert isinstance(anomaly_dist, pd.DataFrame)
            assert "Label" in anomaly_dist.columns
            assert "Count" in anomaly_dist.columns
            assert len(anomaly_dist) == 2  # Normal and Anomaly

    def test_save_all_reports(self, sample_train_df, sample_test_df):
        """Test saving all reports."""
        with TemporaryDirectory() as tmpdir:
            profiler = DatasetProfiler(tmpdir)
            profiler.save_all_reports(sample_train_df, sample_test_df)

            assert (Path(tmpdir) / "dataset_summary.csv").exists()
            assert (Path(tmpdir) / "descriptive_statistics.csv").exists()
            assert (Path(tmpdir) / "kpi_distribution.csv").exists()
            assert (Path(tmpdir) / "anomaly_distribution.csv").exists()

    def test_get_summary_statistics(self, sample_train_df):
        """Test getting summary statistics as dictionary."""
        with TemporaryDirectory() as tmpdir:
            profiler = DatasetProfiler(tmpdir)
            stats = profiler.get_summary_statistics(sample_train_df)

            assert isinstance(stats, dict)
            assert "total_records" in stats
            assert "kpi_count" in stats
            assert stats["total_records"] == 10
            assert stats["kpi_count"] == 2

    def test_generate_timestamp_analysis(self, sample_train_df, sample_test_df):
        """Test timestamp analysis generation."""
        with TemporaryDirectory() as tmpdir:
            profiler = DatasetProfiler(tmpdir)
            ts_analysis = profiler.generate_timestamp_analysis(sample_train_df, sample_test_df)

            assert isinstance(ts_analysis, pd.DataFrame)
            assert "Metric" in ts_analysis.columns
            assert "Training" in ts_analysis.columns
            assert "Testing" in ts_analysis.columns
            # Should include: First Timestamp, Last Timestamp, Time Span, Unique Timestamps
            assert len(ts_analysis) >= 3

    def test_timestamp_analysis_in_kpi_analysis(self, sample_train_df, sample_test_df):
        """Test that KPI analysis includes timestamp columns."""
        with TemporaryDirectory() as tmpdir:
            profiler = DatasetProfiler(tmpdir)
            kpi_analysis = profiler.generate_kpi_analysis(sample_train_df, sample_test_df)

            # Should include timestamp columns for each KPI
            assert "Train First Timestamp" in kpi_analysis.columns
            assert "Train Last Timestamp" in kpi_analysis.columns
            assert "Test First Timestamp" in kpi_analysis.columns
            assert "Test Last Timestamp" in kpi_analysis.columns

    def test_timestamp_statistics_in_summary(self, sample_train_df):
        """Test that summary statistics include timestamp information."""
        with TemporaryDirectory() as tmpdir:
            profiler = DatasetProfiler(tmpdir)
            stats = profiler.get_summary_statistics(sample_train_df)

            assert "min_timestamp" in stats
            assert "max_timestamp" in stats
            assert "time_span" in stats
            assert "unique_timestamps" in stats
            assert pd.notna(stats["min_timestamp"])
            assert pd.notna(stats["max_timestamp"])

    def test_save_all_reports_with_timestamp_analysis(self, sample_train_df, sample_test_df):
        """Test that all reports including timestamp analysis are saved."""
        with TemporaryDirectory() as tmpdir:
            profiler = DatasetProfiler(tmpdir)
            profiler.save_all_reports(sample_train_df, sample_test_df)

            assert (Path(tmpdir) / "dataset_summary.csv").exists()
            assert (Path(tmpdir) / "descriptive_statistics.csv").exists()
            assert (Path(tmpdir) / "kpi_distribution.csv").exists()
            assert (Path(tmpdir) / "anomaly_distribution.csv").exists()
            assert (Path(tmpdir) / "timestamp_analysis.csv").exists()

            # Verify timestamp analysis content
            ts_df = pd.read_csv(Path(tmpdir) / "timestamp_analysis.csv")
            assert "Metric" in ts_df.columns
            assert len(ts_df) >= 3
