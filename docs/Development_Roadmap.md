# Development Roadmap

Project Title:
ANOMALY AND FAULT DETECTION IN WIRELESS SYSTEM

Version: 1.0

---

# Overview

This document defines the implementation phases for the project.

The project shall be developed incrementally. Each phase must be completed, tested, and documented before moving to the next phase.

The code generation process shall follow this roadmap.

---

# Phase 1 – Project Setup

## Objective

Establish the project structure and development environment.

## Tasks

* Create project folder structure
* Create Python virtual environment
* Install dependencies
* Configure logging
* Configure configuration management
* Configure unit testing framework

## Deliverables

* Working project skeleton
* requirements.txt
* Initial README.md
* Logging framework

---

# Phase 2 – KPI Dataset Analysis

## Objective

Understand and validate the AIOps KPI dataset.

## Tasks

* Load train.csv
* Load test.csv
* Validate schema
* Check missing values
* Analyze KPI IDs
* Generate descriptive statistics
* Create exploratory visualizations

## Deliverables

* Dataset profiling report
* KPI distribution plots
* KPI ID analysis report

---

# Phase 3 – KPI Feature Engineering

## Objective

Generate features suitable for anomaly detection.

## Features

### Raw Features

* value

### Lag Features

* lag_1
* lag_5
* lag_10

### Rolling Features

* rolling_mean_5
* rolling_mean_10
* rolling_std_5
* rolling_std_10

### Optional Time Features

* hour_of_day
* day_of_week

## Deliverables

* Feature engineering pipeline
* Feature validation report

---

# Phase 4 – KPI Baseline Model

## Objective

Develop KPI anomaly detection using Isolation Forest.

## Tasks

* Train Isolation Forest
* Generate anomaly scores
* Compare predictions against labels
* Tune hyperparameters

## Evaluation Metrics

* Accuracy
* Precision
* Recall
* F1 Score
* ROC-AUC

## Deliverables

* Trained KPI anomaly detector
* KPI evaluation report

---

# Phase 5 – KPI Deep Learning Model

## Objective

Develop an LSTM-based KPI anomaly detector.

## Tasks

* Create time-series sequences
* Train LSTM model
* Generate anomaly predictions
* Compare against Isolation Forest

## Deliverables

* Trained LSTM model
* KPI model comparison report

---

# Phase 6 – Log Dataset Analysis

## Objective

Understand and validate HDFS log dataset.

## Files

* anomaly_label.csv
* Event_occurrence_matrix.csv
* Event_traces.csv
* HDFS.log_templates.csv

## Tasks

* Validate schema
* Analyze label distribution
* Analyze event frequencies
* Analyze trace lengths

## Deliverables

* HDFS dataset profiling report

---

# Phase 7 – Log Baseline Model

## Objective

Develop classical log anomaly detector.

## Input

Event_occurrence_matrix.csv

## Model

Random Forest

## Tasks

* Train model
* Generate predictions
* Evaluate performance

## Deliverables

* Baseline log anomaly detector
* Evaluation report

---

# Phase 8 – DeepLog-Style Log Model

## Objective

Develop sequence-based log anomaly detector.

## Input

Event_traces.csv

## Model

LSTM

## Tasks

* Parse event sequences
* Create training sequences
* Train LSTM
* Detect anomalies

## Deliverables

* DeepLog-style implementation
* Evaluation report

---

# Phase 9 – Fusion Layer

## Objective

Combine KPI and log anomaly outputs.

## Inputs

* KPI anomaly score
* Log anomaly score

## Method

Weighted score fusion

Example:

Final Score =
0.5 × KPI Score +
0.5 × Log Score

## Outputs

* Normal
* Warning
* Anomaly
* Potential Fault

## Deliverables

* Fusion engine

---

# Phase 10 – Evaluation and Comparison

## Objective

Compare all implemented approaches.

## Models

### KPI

* Isolation Forest
* LSTM

### Logs

* Random Forest
* DeepLog-style LSTM

### Hybrid

* Fusion model

## Metrics

* Accuracy
* Precision
* Recall
* F1 Score
* ROC-AUC

## Deliverables

* Comparative evaluation report

---

# Phase 11 – Visualization and Reporting

## Objective

Generate dissertation-ready outputs.

## Deliverables

* Confusion matrices
* ROC curves
* KPI anomaly plots
* Log anomaly plots
* Comparative performance charts

---

# Phase 12 – Dissertation Support

## Objective

Generate material required for dissertation writing.

## Deliverables

* Architecture diagrams
* Methodology diagrams
* Dataset summaries
* Experiment summaries
* Result tables

---

# Instructions for LLM-Assisted Development

When generating code:

1. Implement only the current phase.
2. Do not skip phases.
3. Do not implement future phases unless requested.
4. Generate production-quality Python code.
5. Include tests.
6. Include documentation.
7. Ensure reproducibility.
8. Follow PMS.md as the source of truth.