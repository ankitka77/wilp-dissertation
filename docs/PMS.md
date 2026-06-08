# Project Master Specification (PMS)

Version: 1.0

Project Title:
ANOMALY AND FAULT DETECTION IN WIRELESS SYSTEM

Degree Program:
M.Tech in Artificial Intelligence and Machine Learning

Institution:
BITS Pilani (WILP)

---

# 1. Project Overview

## Problem Statement

The rapid evolution of 4G LTE and 5G wireless communication systems has resulted in highly complex and large-scale telecom nfrastructures. These networks continuously generate large volumes of operational data in the form of system logs (including application logs), alarms, notifications and Key Performance Indicators (KPIs). Monitoring and maintaining the health of such networks require intelligent mechanisms to detect anomalies and predict faults in a timely and efficient manner. It is important because any failure in these telecom networks can cause widespread service disruption and customer dissatisfaction.

Modern wireless communication systems consist of multiple,  interconnected hardware and software components operating across different protocol layers and distributed network elements. During fault investigation, engineers are often required to analyze large volumes of logs generated at different layers and components, making the process highly complex, time-consuming, and dependent on expert knowledge.

The broad area of this project lies in the application of Artificial Intelligence and Machine Learning techniques for anomaly detection and fault prediction in wireless communication systems, specifically focusing on Operations and Maintenance (O&M) aspects of telecom networks. The project emphasizes the analysis of structured KPI timeseries data and structured/unstructured system logs to identify abnormal behaviour patterns associated with system degradation, cell downtime, and infrastructure failures. 

Recent research such as DeepLog demonstrates the effectiveness of sequence-based learning for log anomaly detection, while studies on KPI analytics in telecom networks highlight the importance of time-series modelling and adaptive thresholding for identifying anomalies in operational metrics. Most existing approaches focus either on KPI-based analysis or log-based analysis independently.

This project aims to bridge this gap by combining both KPI-based and log-based approaches to develop a simple and effective anomaly and fault detection framework for wireless systems. 

This research project focuses on the following application areas:
* Machine Learning for telecom network monitoring
* Log-based anomaly detection using sequence modelling
* Time-series analysis of KPI data
* Predictive fault detection in wireless systems for early warning

---

# 2. Research Motivation

Wireless systems generate two major categories of operational data:

* KPI time-series
* System logs

Most existing approaches focus on one of the following:

1. KPI-based anomaly detection
2. Log-based anomaly detection

However, real-world telecom faults often manifest through both:

* KPI degradation
* abnormal system events
* service instability

The project investigates whether combining both information sources can improve fault detection capability.

---

# 3. Research Gap

Existing literature indicates:

* DeepLog focuses only on logs.
* KPI anomaly detection papers focus only on KPI time-series.
* Limited work exists on lightweight hybrid anomaly detection frameworks that combine KPI and log analytics for telecom O&M applications.

Research Gap:

Development of a lightweight hybrid anomaly detection framework combining KPI and log analytics for wireless system fault detection.

---

# 4. Project Objectives

## Primary Objectives
The objectives of my project are as follows:
* Detect anomalies in KPI time-series.
* Detect anomalies in system logs.
* Develop KPI-based anomaly detection models.
* Develop log-based anomaly detection models.
* Combine KPI and log anomaly signals.
* Generate unified fault prediction.
* Evaluate anomaly detection performance.

## Secondary Objectives

* Compare statistical and machine learning methods.
* Study behavior of telecom temporal KPI anomalies.
* Study sequence-based log anomalies.
* Build a reproducible research prototype.

---

# 5. Project Scope

## Included

* Offline analysis of telecom KPI data related to system performance and availability
* Analysis of system logs for detecting abnormal event sequences
* Detection of anomalies in KPI time-series data
* Detection of anomalies in log sequences using sequence modelling
* Integration of KPI-based and log-based anomaly detection methods
* Development of machine learning models for anomaly detection and fault prediction
* Evaluation of the proposed system using experimental datasets
* Result visualization

## Excluded

* Real-time deployment
* Live telecom network integration
* OSS integration
* O-RAN control loops
* Mobility optimization
* Handover optimization
* Call-processing optimization
* Radio resource allocation and management

---

# 6. Target O&M Use Cases

The system should detect anomalies associated with:

## Infrastructure Health

* Server downtime
* Process failure
* Service restart loops
* Resource exhaustion, including CPU, Disk and memory

## Network Health

* Cell downtime
* Node degradation
* Availability reduction
* Abnormal traffic behavior

## Operational Anomalies

* Sudden KPI spikes
* KPI drops
* Persistent KPI degradation
* Abnormal event sequences

---

# 7. Selected Datasets

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

# 8. Literature Foundation

## Paper 1

DeepLog: Anomaly Detection and Diagnosis from System Logs through Deep Learning - ACM Digital Library 3133956.3134015

Authors: 
Min Du, Feifei Li, Guineng Zheng, Vivek Srikumar

Problem Addressed:
Modern distributed systems generate massive volumes of log data. Traditional rule-based and keyword-based monitoring approaches struggle to identify anomalies hidden within complex log sequences. The paper addresses the problem of automatically detecting anomalous system behavior from log data without requiring manually crafted rules. The authors aim to learn normal execution patterns from historical logs and identify deviations that may indicate failures or abnormal system behavior.

Methodology:
The authors first parse raw logs into structured event templates and assign unique event identifiers to each template. Log events are then treated as sequential data. An LSTM-based neural network is trained on normal log sequences to learn the expected next event in a sequence. During inference, if the observed next event is not among the top predicted events, the sequence is flagged as anomalous. The model can therefore detect anomalies by identifying deviations from learned normal execution patterns.

Key Contributions:
* LSTM-based log anomaly detection
* Sequence modeling of system events

Limitations:
* Uses only logs
* No KPI information

Project Relevance:
Foundation for log anomaly module.

---

## Paper 2

Log-based Anomaly Detection with Deep Learning: How Far Are We? - arXiv-2202.04301v2 

Authors: 
Van-Hoang Le, Hongyu Zhang

Problem Addressed:
A large number of deep learning techniques have been proposed for log anomaly detection, including LSTM-based models, autoencoders, transformers, and graph-based approaches. However, there is limited understanding of their comparative performance, evaluation challenges, dataset limitations, and practical deployment considerations. The paper addresses the need for a comprehensive review of deep learning methods for log anomaly detection and identifies current research gaps and challenges.

Methodology:
The paper performs a systematic literature survey of deep learning approaches used for log anomaly detection. The authors analyze the complete pipeline, including log parsing, feature extraction, sequence construction, model training, anomaly detection, and evaluation. Various model families such as LSTM, CNN, Autoencoder, Transformer, and Graph Neural Network approaches are compared. The paper also reviews commonly used datasets, evaluation metrics, and experimental methodologies to assess the strengths and weaknesses of existing solutions.

Key Contributions:
* Survey of modern log anomaly detection
* Evaluation challenges
* Dataset limitations

Limitations:
* Uses only logs
* No KPI information

Project Relevance:
Guidance for model selection and evaluation.

---

## Paper 3

Classification of Anomalies in Telecommunication Network KPI Time Series - arXiv-2308.16279

Authors: 
Korantin Bordeau–Aubert, Justin Whatley, Sylvain Nadeau, Tristan Glatard, Brigitte Jaumard

Problem Addressed:
Telecommunication networks continuously generate KPI time-series data that are used for operational monitoring. Traditional threshold-based monitoring systems often fail to distinguish between normal fluctuations and genuine anomalies. The paper addresses the problem of identifying and classifying different types of anomalies in telecom KPI time-series so that network operators can better understand network degradation and abnormal behavior.

Methodology:
The authors analyze telecom KPI time-series and define a taxonomy of anomaly types, including sudden spikes, sudden drops, persistent degradation, and contextual anomalies. Statistical and machine learning techniques are applied to identify abnormal KPI behavior. The study focuses on understanding the characteristics of KPI anomalies and developing methods for anomaly classification rather than merely detecting whether an anomaly exists. The methodology emphasizes temporal behavior analysis and anomaly categorization within telecom operational data.

Key Contributions:
* KPI anomaly taxonomy
* Time-series anomaly analysis

Project Relevance:
Foundation for KPI anomaly module.

---

## Paper 4

Adaptive Thresholding Heuristic for KPI Anomaly Detection - arXiv-Paper4 - 2308.10504v1

Authors: 
Ebenezer R.H.P. Isaac, Akshat Sharma

Problem Addressed:
Static threshold-based monitoring is widely used in telecom and IT operations, but fixed thresholds often generate excessive false alarms or fail to detect genuine anomalies. KPI values frequently exhibit seasonality, trends, and workload-dependent variations. The paper addresses the challenge of dynamically identifying anomalies in KPI time-series while accounting for normal variations in system behavior.

Methodology:
The authors propose an adaptive thresholding framework that dynamically adjusts anomaly detection thresholds based on the statistical characteristics of KPI time-series. Historical KPI behavior is analyzed to establish expected operating ranges, and deviations beyond adaptive thresholds are identified as anomalies. The methodology incorporates temporal trends and seasonality to reduce false positives. The proposed approach is evaluated on operational KPI datasets and compared with traditional static threshold methods to demonstrate improved anomaly detection performance.

Key Contributions:
* KPI thresholding methods
* Telecom KPI anomaly behavior

Project Relevance:
Baseline KPI anomaly detection strategy.

---

# 9. Proposed System Architecture

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

# 10. KPI Feature Engineering

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

---

# 11. Model Selection Strategy

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

# 12. Fusion Strategy

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

# 13. Evaluation Metrics

Classification Metrics

* Accuracy
* Precision
* Recall
* F1 Score

Ranking Metrics

* ROC-AUC

Operational Metrics

* Detection rate
* False alarm rate

---

# 14. Project Folder Structure

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

---

# 15. Technology Stack

Programming Language:

* Python 3.11+

Libraries:

* Pandas
* NumPy
* Scikit-Learn
* TensorFlow/Keras
* Matplotlib
* Seaborn
* Jupyter Notebook

Development Environment:

* VS Code
* Git
* GitHub

---

# 16. Deliverables

The final project should provide:

* KPI anomaly detection engine
* Log anomaly detection engine
* Fusion engine
* Evaluation framework
* Visualizations dashboard (offline)
* Experiment reports
* Dissertation-ready results with figures

---

# 17. Future Enhancements

Potential future work:

* Explainable AI (SHAP)
* Root Cause Analysis
* Graph Neural Networks
* Transformer-based anomaly detection
* Real-time deployment
* Telecom OSS integration
* O-RAN integration
* Real-time streaming log analysis for early detection of faults

---

# 18. Instructions for Future LLM-Assisted Development

Whenever generating code:

1. Follow PMS.md as the source of truth.
2. Use modular architecture.
3. Generate production-quality Python code.
4. Include type hints and documentation.
5. Include unit tests where practical.
6. Prefer explainable models first.
7. Ensure reproducibility.
8. Generate publication-quality visualizations.
9. Do not invent dataset columns.
10. Use actual dataset schema described in this PMS.
11. Generate code phase-by-phase, not all at once.
12. Maintain consistency with dissertation objectives.