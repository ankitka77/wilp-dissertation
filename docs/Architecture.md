# Proposed System Architecture

## KPI Pipeline

AIOps KPI Dataset
↓
Data Cleaning
↓
Feature Engineering
↓
KPI Anomaly Detection Model
↓
KPI Anomaly Score

## Log Pipeline

HDFS Dataset
↓
Sequence Processing
↓
Log Anomaly Detection Model
↓
Log Anomaly Score

## Fusion Layer
KPI Score + Log Score
        ↓
Weighted Fusion
        ↓
Fault Classification

## Outputs:
* Normal
* Warning
* Anomaly
* Potential Fault

---

# Model Selection Strategy

## Phase 1 (Baseline)

### KPI Model

Baseline Model: Isolation Forest

Reason:
* Unsupervised
* Minimal labeled data requirement
* Fast
* Explainable
* Suitable for anomaly detection

Advanced Model: LSTM

Reason:
* Captures temporal dependencies
* Suitable for time-series modeling

### Log Model

Baseline Model: Random Forest

Input: Event_occurrence_matrix.csv

Reason:
* Fast baseline
* Easy interpretation

Advanced Model: DeepLog-style LSTM

Input: Event_traces.csv

Reason:
* Based on literature
* Sequence anomaly detection

---

# Fusion Strategy

Initial Fusion Approach:

Weighted anomaly scoring

Example:

Final Score =
0.5 × KPI Score +
0.5 × Log Score

Classification Rules:

0.0 – 0.3 → Normal

0.3 – 0.6 → Warning

0.6 – 0.8 → Anomaly

0.8 – 1.0 → Potential Fault

Thresholds to be experimentally tuned.

---

# Project Folder Structure

project/

├── docs/

│ ├── PMS.md

│ ├── Datasets.md

│ ├── Architecture.md

│ └── Literature_Review.md

├── data/

│ ├── kpi/

│ └── logs/

├── notebooks/

├── src/

│ ├── preprocessing/

│ ├── kpi_model/

│ ├── log_model/

│ ├── fusion/

│ ├── evaluation/

│ └── visualization/

├── reports/

├── tests/

└── README.md