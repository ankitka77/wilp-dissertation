# Anomaly and Fault Detection in Wireless System

## Overview

This project is being developed as part of the M.Tech (AI/ML) program at BITS Pilani.

The objective is to develop a machine-learning framework for anomaly and fault detection in wireless systems by combining:

- KPI-based anomaly detection
- Log-based anomaly detection

The project focuses on telecom Operations and Maintenance (O&M) use cases.

## Phase 1 Status

Current phase implemented: Project Setup

Implemented in this phase:

- Project package structure under src
- Logging configuration framework
- Configuration management framework
- Unit test framework with pytest
- Skeleton modules for preprocessing, KPI model, log model, fusion, evaluation, and visualization

## Project Structure

Key source directories:

- src/preprocessing
- src/kpi_model
- src/log_model
- src/fusion
- src/evaluation
- src/visualization
- src/common

Configuration:

- config/settings.yaml
- config/logging.yaml

Tests:

- tests/unit

## Environment Setup

1. Create and activate a virtual environment.
2. Install dependencies:

	python -m pip install -r requirements.txt

3. Run tests:

	pytest

## Documentation

Refer to:

- docs/PMS.md
- docs/Datasets.md
- docs/Architecture.md
- docs/Literature_Review.md
- docs/Development_Roadmap.md

## Technology Stack

- Python
- Pandas
- NumPy
- Scikit-Learn
- TensorFlow/Keras
- Matplotlib
- Pytest

## Author

M.Tech AI/ML Dissertation Project
BITS Pilani (WILP)