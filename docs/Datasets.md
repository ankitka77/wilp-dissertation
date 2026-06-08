# Selected Datasets

## KPI Dataset

Dataset:
AIOps KPI Anomaly Detection Dataset
* Training Rows: 1,048,576
* Test Rows: 1,048,576

Unique KPI Streams:
* Training: 10 KPI IDs
* Testing: 16 KPI IDs

Columns:
* timestamp
* value
* label (train only)
* KPI ID

Characteristics:
* Univariate KPI time-series
* Multiple KPI streams
* Labeled anomalies
* Suitable for anomaly detection benchmarking


## Log Dataset

Dataset:
HDFS Dataset (LogHub)

Files Used:
* anomaly_label.csv
* Event_occurrence_matrix.csv
* Event_traces.csv
* HDFS.log_templates.csv

Characteristics:
* Event sequence data
* Block-level anomaly labels
* Preprocessed event traces
* Suitable for DeepLog-style sequence modeling

---

# KPI Feature Engineering

## Features to Generate:

Current KPI value
* Lag-1
* Lag-5
* Lag-10
* Rolling Mean (5)
* Rolling Mean (10)
* Rolling Standard Deviation (5)
* Rolling Standard Deviation (10)

Optional:
* Hour of Day
* Day of Week