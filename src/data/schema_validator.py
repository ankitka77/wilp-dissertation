"""Schema validation module for KPI datasets.

This module provides functionality to validate the structure and content
of KPI datasets against expected schemas.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.api.types import (
    is_datetime64_any_dtype,
    is_integer_dtype,
    is_numeric_dtype,
    is_string_dtype,
)

logger = logging.getLogger("project")


@dataclass
class ValidationResult:
    """Result of schema validation."""

    is_valid: bool
    dataset_type: str
    total_checks: int
    passed_checks: int
    failed_checks: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    kpi_ids: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        """Generate validation summary."""
        return (
            f"{self.dataset_type} Validation: "
            f"{self.passed_checks}/{self.total_checks} checks passed"
        )


class SchemaValidator:
    """Validate KPI dataset schemas.

    This class validates:
    - Required columns
    - Semantic data types (numeric, integer, string)
    - Missing values
    - Duplicate rows
    - Unexpected KPI IDs

    Uses semantic type checking via pandas.api.types for robustness
    across different pandas versions and data loading scenarios.
    """

    # Expected schemas with semantic type descriptions
    # Types: "string", "numeric", "integer"
    TRAIN_SCHEMA = {
        "timestamp": "string",
        "value": "numeric",
        "label": "integer",
        "KPI ID": "string"
    }

    TEST_SCHEMA = {
        "timestamp": "string",
        "value": "numeric",
        "KPI ID": "string"
    }

    def __init__(self):
        """Initialize SchemaValidator."""
        logger.info("SchemaValidator initialized")

    def _check_semantic_type(self, col: pd.Series, expected_type: str) -> bool:
        """Check if column matches expected semantic type.

        Args:
            col: Pandas Series to check.
            expected_type: Semantic type ("string", "numeric", "integer").

        Returns:
            True if column matches the expected semantic type, False otherwise.
        """
        if expected_type == "numeric":
            return is_numeric_dtype(col)
        elif expected_type == "integer":
            return is_integer_dtype(col)
        elif expected_type == "string":
            return (
                is_string_dtype(col)
                or col.dtype == "object"
                or (col.name == "timestamp" and is_datetime64_any_dtype(col))
            )
        else:
            logger.warning(f"Unknown expected type: {expected_type}")
            return False

    def _analyze_kpi_ids(self, df: pd.DataFrame, dataset_type: str = "dataset") -> dict[str, Any]:
        """Analyze KPI IDs in the dataset.

        Args:
            df: DataFrame to analyze.
            dataset_type: Label for the dataset (e.g., "training", "test").

        Returns:
            Dictionary containing KPI ID analysis.
        """
        kpi_ids = sorted(df["KPI ID"].unique())
        kpi_count = len(kpi_ids)

        logger.info(f"{dataset_type.capitalize()} dataset has {kpi_count} unique KPI IDs")

        return {
            "count": kpi_count,
            "ids": kpi_ids,
            "dataset_type": dataset_type,
        }

    def _validate_kpi_ids_cross_dataset(
        self, train_kpi_ids: list[str], test_kpi_ids: list[str]
    ) -> dict[str, Any]:
        """Validate KPI IDs across training and test datasets.

        Args:
            train_kpi_ids: List of KPI IDs in training data.
            test_kpi_ids: List of KPI IDs in test data.

        Returns:
            Dictionary containing cross-dataset KPI analysis.
        """
        train_set = set(train_kpi_ids)
        test_set = set(test_kpi_ids)

        # Find new KPI IDs in test that don't exist in training
        new_kpi_ids = sorted(test_set - train_set)
        overlap_kpi_ids = sorted(train_set & test_set)

        analysis = {
            "train_kpi_ids": train_kpi_ids,
            "test_kpi_ids": test_kpi_ids,
            "overlap_kpi_ids": overlap_kpi_ids,
            "new_kpi_ids": new_kpi_ids,
            "overlap_count": len(overlap_kpi_ids),
            "new_count": len(new_kpi_ids),
        }

        if new_kpi_ids:
            logger.warning(
                f"Found {len(new_kpi_ids)} new KPI IDs in test not in training: {new_kpi_ids}"
            )
        else:
            logger.info("OK - All test KPI IDs present in training set")

        return analysis

    def validate_train_schema(self, df: pd.DataFrame) -> ValidationResult:
        """Validate training dataset schema.

        Args:
            df: Training DataFrame to validate.

        Returns:
            ValidationResult with validation details.
        """
        logger.info("Validating training dataset schema")
        result = ValidationResult(
            is_valid=True, dataset_type="Training", total_checks=0, passed_checks=0, failed_checks=0
        )

        # Check 1: Required columns
        result.total_checks += 1
        required_cols = set(self.TRAIN_SCHEMA.keys())
        actual_cols = set(df.columns)

        if required_cols == actual_cols:
            result.passed_checks += 1
            logger.info("OK - All required columns present")
        else:
            result.is_valid = False
            missing = required_cols - actual_cols
            extra = actual_cols - required_cols
            error_msg = f"Schema mismatch. Missing: {missing}, Extra: {extra}"
            result.errors.append(error_msg)
            logger.error(error_msg)

        # Check 2: Data types
        result.total_checks += 1
        type_mismatches = []
        for col, expected_type in self.TRAIN_SCHEMA.items():
            if col in df.columns:
                if not self._check_semantic_type(df[col], expected_type):
                    type_mismatches.append(f"{col}: expected {expected_type}, got {df[col].dtype}")

        if not type_mismatches:
            result.passed_checks += 1
            logger.info("OK - All columns have correct data types")
        else:
            result.is_valid = False
            error_msg = f"Data type mismatches: {'; '.join(type_mismatches)}"
            result.errors.append(error_msg)
            logger.error(error_msg)

        # Check 3: Missing values
        result.total_checks += 1
        missing_counts = df.isnull().sum()
        if missing_counts.sum() == 0:
            result.passed_checks += 1
            logger.info("OK - No missing values")
        else:
            result.is_valid = False
            missing_info = missing_counts[missing_counts > 0].to_dict()
            error_msg = f"Missing values found: {missing_info}"
            result.errors.append(error_msg)
            logger.error(error_msg)

        # Check 4: Duplicate rows
        result.total_checks += 1
        duplicates = df.duplicated().sum()
        if duplicates == 0:
            result.passed_checks += 1
            logger.info("OK - No duplicate rows")
        else:
            warning_msg = f"Found {duplicates} duplicate rows"
            result.warnings.append(warning_msg)
            logger.warning(warning_msg)
            result.passed_checks += 1  # Warning, not error

        # Check 5: Label values
        result.total_checks += 1
        if "label" in df.columns:
            valid_labels = set(df["label"].unique())
            if valid_labels.issubset({0, 1}):
                result.passed_checks += 1
                logger.info("OK - Label column contains only 0 and 1")
            else:
                result.is_valid = False
                error_msg = f"Invalid label values: {valid_labels}"
                result.errors.append(error_msg)
                logger.error(error_msg)

        # Check 6: Non-null KPI IDs
        result.total_checks += 1
        if df["KPI ID"].isnull().sum() == 0:
            result.passed_checks += 1
            logger.info("OK - All KPI IDs are non-null")
        else:
            result.is_valid = False
            error_msg = f"Found {df['KPI ID'].isnull().sum()} null KPI IDs"
            result.errors.append(error_msg)
            logger.error(error_msg)

        # Check 7: KPI ID analysis
        result.total_checks += 1
        kpi_analysis = self._analyze_kpi_ids(df, "training")
        result.kpi_ids = kpi_analysis
        result.passed_checks += 1
        logger.info(f"OK - KPI ID analysis: {kpi_analysis['count']} unique KPI IDs")

        result.failed_checks = result.total_checks - result.passed_checks
        logger.info(result.summary())

        return result

    def validate_test_schema(self, df: pd.DataFrame) -> ValidationResult:
        """Validate test dataset schema.

        Args:
            df: Test DataFrame to validate.

        Returns:
            ValidationResult with validation details.
        """
        logger.info("Validating test dataset schema")
        result = ValidationResult(is_valid=True, dataset_type="Test", total_checks=0, passed_checks=0, failed_checks=0)

        # Check 1: Required columns
        result.total_checks += 1
        required_cols = set(self.TEST_SCHEMA.keys())
        actual_cols = set(df.columns)

        if required_cols == actual_cols:
            result.passed_checks += 1
            logger.info("OK - All required columns present")
        else:
            result.is_valid = False
            missing = required_cols - actual_cols
            extra = actual_cols - required_cols
            error_msg = f"Schema mismatch. Missing: {missing}, Extra: {extra}"
            result.errors.append(error_msg)
            logger.error(error_msg)

        # Check 2: Data types
        result.total_checks += 1
        type_mismatches = []
        for col, expected_type in self.TEST_SCHEMA.items():
            if col in df.columns:
                if not self._check_semantic_type(df[col], expected_type):
                    type_mismatches.append(f"{col}: expected {expected_type}, got {df[col].dtype}")

        if not type_mismatches:
            result.passed_checks += 1
            logger.info("OK - All columns have correct data types")
        else:
            result.is_valid = False
            error_msg = f"Data type mismatches: {'; '.join(type_mismatches)}"
            result.errors.append(error_msg)
            logger.error(error_msg)

        # Check 3: Missing values
        result.total_checks += 1
        missing_counts = df.isnull().sum()
        if missing_counts.sum() == 0:
            result.passed_checks += 1
            logger.info("OK - No missing values")
        else:
            result.is_valid = False
            missing_info = missing_counts[missing_counts > 0].to_dict()
            error_msg = f"Missing values found: {missing_info}"
            result.errors.append(error_msg)
            logger.error(error_msg)

        # Check 4: Duplicate rows
        result.total_checks += 1
        duplicates = df.duplicated().sum()
        if duplicates == 0:
            result.passed_checks += 1
            logger.info("OK - No duplicate rows")
        else:
            warning_msg = f"Found {duplicates} duplicate rows"
            result.warnings.append(warning_msg)
            logger.warning(warning_msg)
            result.passed_checks += 1  # Warning, not error

        # Check 5: Non-null KPI IDs
        result.total_checks += 1
        if df["KPI ID"].isnull().sum() == 0:
            result.passed_checks += 1
            logger.info("OK - All KPI IDs are non-null")
        else:
            result.is_valid = False
            error_msg = f"Found {df['KPI ID'].isnull().sum()} null KPI IDs"
            result.errors.append(error_msg)
            logger.error(error_msg)

        # Check 6: KPI ID analysis
        result.total_checks += 1
        kpi_analysis = self._analyze_kpi_ids(df, "test")
        result.kpi_ids = kpi_analysis
        result.passed_checks += 1
        logger.info(f"OK - KPI ID analysis: {kpi_analysis['count']} unique KPI IDs")

        result.failed_checks = result.total_checks - result.passed_checks
        logger.info(result.summary())

        return result

    def validate_kpi_ids(
        self, train_df: pd.DataFrame, test_df: pd.DataFrame | None = None
    ) -> dict[str, Any]:
        """Validate KPI IDs across datasets.

        Args:
            train_df: Training DataFrame.
            test_df: Optional test DataFrame.

        Returns:
            Dictionary containing KPI ID analysis.
        """
        logger.info("Performing cross-dataset KPI ID validation")

        train_kpi_ids = sorted(train_df["KPI ID"].unique())
        logger.info(f"Training dataset has {len(train_kpi_ids)} unique KPI IDs: {train_kpi_ids}")

        analysis = {
            "train_kpi_ids": train_kpi_ids,
            "train_kpi_count": len(train_kpi_ids),
        }

        if test_df is not None:
            test_kpi_ids = sorted(test_df["KPI ID"].unique())
            logger.info(f"Test dataset has {len(test_kpi_ids)} unique KPI IDs: {test_kpi_ids}")

            # Perform cross-dataset analysis
            cross_analysis = self._validate_kpi_ids_cross_dataset(train_kpi_ids, test_kpi_ids)
            analysis.update(cross_analysis)
            analysis["test_kpi_count"] = len(test_kpi_ids)  # Add test count explicitly

            if cross_analysis["new_count"] > 0:
                logger.warning(
                    f"Warning: {cross_analysis['new_count']} new KPI IDs in test: {cross_analysis['new_kpi_ids']}"
                )
            else:
                logger.info("OK - All test KPI IDs are present in training set")

        return analysis

    def generate_validation_report(
        self,
        train_result: ValidationResult,
        test_result: ValidationResult | None = None,
        kpi_analysis: dict[str, Any] | None = None,
        output_path: str | Path = "artifacts/reports/phase2/validation_report.txt",
    ) -> None:
        """Generate validation report file.

        Args:
            train_result: Training validation result.
            test_result: Optional test validation result.
            kpi_analysis: Optional KPI ID analysis.
            output_path: Path to save the report.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", encoding="utf-8") as f:
            f.write("=" * 70 + "\n")
            f.write("KPI DATASET VALIDATION REPORT\n")
            f.write("=" * 70 + "\n\n")

            # Training validation
            f.write("TRAINING DATASET VALIDATION\n")
            f.write("-" * 70 + "\n")
            f.write(f"Timestamp: {train_result.timestamp}\n")
            f.write(f"Status: {'VALID' if train_result.is_valid else 'INVALID'}\n")
            f.write(f"Checks Passed: {train_result.passed_checks}/{train_result.total_checks}\n\n")

            if train_result.errors:
                f.write("Errors:\n")
                for i, error in enumerate(train_result.errors, 1):
                    f.write(f"  {i}. {error}\n")
                f.write("\n")

            if train_result.warnings:
                f.write("Warnings:\n")
                for i, warning in enumerate(train_result.warnings, 1):
                    f.write(f"  {i}. {warning}\n")
                f.write("\n")

            # Test validation
            if test_result:
                f.write("\nTEST DATASET VALIDATION\n")
                f.write("-" * 70 + "\n")
                f.write(f"Timestamp: {test_result.timestamp}\n")
                f.write(f"Status: {'VALID' if test_result.is_valid else 'INVALID'}\n")
                f.write(f"Checks Passed: {test_result.passed_checks}/{test_result.total_checks}\n\n")

                if test_result.errors:
                    f.write("Errors:\n")
                    for i, error in enumerate(test_result.errors, 1):
                        f.write(f"  {i}. {error}\n")
                    f.write("\n")

                if test_result.warnings:
                    f.write("Warnings:\n")
                    for i, warning in enumerate(test_result.warnings, 1):
                        f.write(f"  {i}. {warning}\n")
                    f.write("\n")

            # KPI Analysis
            if kpi_analysis:
                f.write("\nKPI ID ANALYSIS\n")
                f.write("=" * 70 + "\n")

                # Training KPI IDs
                f.write(f"\nTRAINING KPI IDs ({kpi_analysis['train_kpi_count']} unique):\n")
                f.write(f"  {kpi_analysis['train_kpi_ids']}\n")

                # Test KPI IDs and comparison
                if "test_kpi_ids" in kpi_analysis:
                    test_count = len(kpi_analysis['test_kpi_ids'])
                    f.write(f"\nTEST KPI IDs ({test_count} unique):\n")
                    f.write(f"  {kpi_analysis['test_kpi_ids']}\n")

                    # Overlap analysis
                    if "overlap_kpi_ids" in kpi_analysis:
                        f.write(f"\nOVERLAP KPI IDs ({kpi_analysis['overlap_count']} present in both):\n")
                        f.write(f"  {kpi_analysis['overlap_kpi_ids']}\n")

                    # New/Unexpected KPI IDs
                    if "new_kpi_ids" in kpi_analysis and kpi_analysis["new_count"] > 0:
                        f.write(f"\nWARNING: NEW/UNEXPECTED KPI IDs in Test ({kpi_analysis['new_count']} only in test):\n")
                        f.write(f"  {kpi_analysis['new_kpi_ids']}\n")
                        f.write(
                            "\n  NOTE: These " + str(kpi_analysis["new_count"]) + " KPI IDs appear in the test set but NOT in the training set.\n"
                        )
                        f.write("  This is an important dataset characteristic to consider for model development.\n")
                    elif "new_count" in kpi_analysis and kpi_analysis["new_count"] == 0:
                        f.write("\nOK - All test KPI IDs are present in the training set (no new KPI IDs)\n")

            f.write("\n" + "=" * 70 + "\n")
            f.write("END OF REPORT\n")
            f.write("=" * 70 + "\n")

        logger.info(f"Validation report saved to {output_path}")
