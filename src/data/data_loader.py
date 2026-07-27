"""Data loading module for KPI datasets.

This module provides functionality to load KPI training and test datasets
with validation and error handling.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import NamedTuple

import pandas as pd

logger = logging.getLogger("project")


class DataloadResult(NamedTuple):
    """Result of data loading operation."""

    train_df: pd.DataFrame | None
    test_df: pd.DataFrame | None
    errors: list[str]


class DataLoader:
    """Load and validate KPI datasets from CSV files.

    This class handles:
    - File existence validation
    - CSV loading with error handling
    - Data type conversions
    - Missing file detection
    """

    def __init__(self, data_dir: str | Path = "data/kpi"):
        """Initialize DataLoader.

        Args:
            data_dir: Path to the directory containing KPI CSV files.
                     Defaults to "data/kpi".
        """
        self.data_dir = Path(data_dir)
        self.train_path = self.data_dir / "train.csv"
        self.test_path = self.data_dir / "test.csv"

    def load_train_data(self) -> pd.DataFrame:
        """Load training dataset.

        Returns:
            DataFrame containing training data.

        Raises:
            FileNotFoundError: If train.csv does not exist.
            pd.errors.ParserError: If CSV parsing fails.
            ValueError: If loaded data is empty.
        """
        logger.info(f"Loading training data from {self.train_path}")

        if not self.train_path.exists():
            error_msg = f"Training data file not found: {self.train_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        try:
            df = pd.read_csv(self.train_path, dtype={"KPI ID": str})
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(
                    df["timestamp"],
                    errors="coerce"
                )
            logger.info(f"Successfully loaded {len(df)} training records")

            if df.empty:
                raise ValueError("Training dataset is empty")

            return df

        except pd.errors.ParserError as e:
            error_msg = f"Failed to parse training CSV: {e}"
            logger.error(error_msg)
            raise
        except Exception as e:
            error_msg = f"Unexpected error loading training data: {e}"
            logger.error(error_msg)
            raise

    def load_test_data(self) -> pd.DataFrame:
        """Load test dataset.

        Returns:
            DataFrame containing test data.

        Raises:
            FileNotFoundError: If test.csv does not exist.
            pd.errors.ParserError: If CSV parsing fails.
            ValueError: If loaded data is empty.
        """
        logger.info(f"Loading test data from {self.test_path}")

        if not self.test_path.exists():
            error_msg = f"Test data file not found: {self.test_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        try:
            df = pd.read_csv(self.test_path, dtype={"KPI ID": str})
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(
                    df["timestamp"],
                    errors="coerce"
                )
            logger.info(f"Successfully loaded {len(df)} test records")

            if df.empty:
                raise ValueError("Test dataset is empty")

            return df

        except pd.errors.ParserError as e:
            error_msg = f"Failed to parse test CSV: {e}"
            logger.error(error_msg)
            raise
        except Exception as e:
            error_msg = f"Unexpected error loading test data: {e}"
            logger.error(error_msg)
            raise

    def load_both(self) -> DataloadResult:
        """Load both training and test datasets.

        This method attempts to load both datasets and returns results
        with any errors that occurred.

        Returns:
            DataloadResult containing both DataFrames (or None if failed)
            and a list of error messages.
        """
        train_df = None
        test_df = None
        errors = []

        try:
            train_df = self.load_train_data()
        except Exception as e:
            errors.append(f"Training data load error: {str(e)}")

        try:
            test_df = self.load_test_data()
        except Exception as e:
            errors.append(f"Test data load error: {str(e)}")

        if errors:
            logger.warning(f"Data loading completed with {len(errors)} error(s)")

        return DataloadResult(train_df=train_df, test_df=test_df, errors=errors)

    def validate_file_paths(self) -> bool:
        """Validate that both data files exist.

        Returns:
            True if both files exist, False otherwise.
        """
        train_exists = self.train_path.exists()
        test_exists = self.test_path.exists()

        if not train_exists:
            logger.error(f"Training file not found: {self.train_path}")

        if not test_exists:
            logger.error(f"Test file not found: {self.test_path}")

        return train_exists and test_exists
