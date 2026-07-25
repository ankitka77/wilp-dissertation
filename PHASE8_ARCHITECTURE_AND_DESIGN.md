# Phase 8 — Architecture and Design

Project: ANOMALY AND FAULT DETECTION IN WIRELESS SYSTEMS
Phase: 8 — Evaluation, Validation, Benchmarking, and Analysis

> Note: This document is an architecture and research-design specification only. It contains no implementation code.

---

**Contents**

1. Objectives
2. Scope
3. Research Questions
4. Research Hypotheses
5. Functional Requirements
6. Non-Functional Requirements
7. High-Level Architecture
8. Overall Data Flow
9. Major Components
10. Responsibilities of each component
11. Component interactions
12. Required inputs
13. Generated outputs
14. Evaluation metrics
15. Experimental workflow
16. Statistical analysis workflow
17. Visualization workflow
18. Reports and artifacts to generate
19. Recommended directory structure
20. Testing strategy
21. Completion criteria
22. Risks and mitigation
23. Assumptions
24. Future extensibility

**Research Traceability Matrix**

25. Critical review (missing components, weak areas, improvements)

---

## 1. Objectives

- Provide a complete, reproducible, statistically rigorous evaluation of the system built in Phases 1–7.
- Demonstrate the relative performance of the KPI model, DeepLog model, and Fusion model across representative datasets and failure modes.
- Evaluate pipeline engineering qualities: runtime, throughput, determinism, reproducibility, robustness, and artifact quality.
- Produce dissertation-ready artefacts (figures, tables, statistical tests, manifests) required for Results, Evaluation, and Analysis chapters.

## 2. Scope

In-scope:
- Offline evaluation of KPI model, DeepLog model, and Fusion model using available datasets and labels.
- Pipeline-level engineering evaluation and profiling for batch evaluation runs.
- Robustness experiments (missing/corrupted data, time shifts, label noise).
- Statistical analysis, visualization, and artifact generation for dissertation.

Out-of-scope:
- Developing new ML models or retraining models as primary research (unless explicitly required by a sub-experiment and documented).
- Real-time deployment and online A/B experiments (Phase 8 focuses on offline evaluation with possible notes on productionization).

## 3. Research Questions

RQ1 — Per-model performance: What are the detection strengths and weaknesses of the KPI model, DeepLog, and Fusion when evaluated on the same datasets and metrics?

RQ2 — Fusion value: Does Fusion improve detection (F1/recall) over the best individual model? Under what conditions (missing sources, noise, varying window sizes) does Fusion help or hurt?

RQ3 — Robustness: How do models and pipeline behave under missing inputs, corrupted inputs, and time misalignment?

RQ4 — Engineering quality: What are end-to-end runtime, throughput, determinism, and resource characteristics of the pipeline? Are artifacts consistently generated and versioned for reproducibility?

RQ5 — Generalization: Do observed results hold across datasets, device types, and different temporal windows?

## 4. Research Hypotheses

H1: Fusion achieves a statistically significant improvement in F1-score vs the best single model (α = 0.05) on the primary test dataset.

H2: Under partial source availability (e.g., KPI missing 50% of windows), Fusion maintains higher recall than any single source model, with acceptable precision degradation.

H3: Pipeline outputs are deterministic across repeated runs when executed with identical inputs, fixed seeds, and environment snapshot (file checksums identical when normalized).

H4: Under injected label noise, Fusion’s relative AUC degradation is smaller than that of individual models (i.e. Fusion is more robust to label noise).

## 5. Functional Requirements

- FR1 — Experiment orchestration: Provide a declarative experiment matrix (YAML/JSON) describing dataset, models, seeds, thresholds, and perturbations.
- FR2 — Reproducible run manifest: Each experiment must produce a manifest capturing config, code commit, environment hash, inputs, and outputs.
- FR3 — Per-model evaluator: Standardized plugin interface returning per-window prediction scores and labels.
- FR4 — Fusion evaluator: Use production `FusionOrchestrator` to produce fused outputs in evaluation mode.
- FR5 — Pipeline profiler: Capture per-stage runtime, CPU, memory, and I/O.
- FR6 — Robustness runner: Parameterized injection of missing data, corruption, time shifts, and label noise.
- FR7 — Statistical engine: Implement/define paired tests, bootstrap CI, DeLong/paired permutation for AUC, and multiple-test correction.
- FR8 — Visualization and artifactory: Produce high-quality plots (ROC/PR/Calibration), tables, and LaTeX-ready outputs.
- FR9 — Artifact storage: Consistent on-disk layout for predictions, metrics, plots, and manifests.

## 6. Non-Functional Requirements

- NFR1 — Reproducibility: Runs reproducible on same commit and environment; manifest must capture checksum of code and environment details.
- NFR2 — Determinism mode: Option to enforce deterministic execution (fixed seeds, deterministic sorts) in the evaluation harness.
- NFR3 — Scalability: Support single-machine batch runs and parallelized large experiments (config-driven). 
- NFR4 — Traceability: All outputs link back to inputs and config via manifest.
- NFR5 — Performance measurement fidelity: Profiling overhead minimal and measured separately.
- NFR6 — Maintainability: Modular component design with clear contracts.

## 7. High-Level Architecture

ASCII diagram (compact):

```
+--------------------+        +-----------------------+        +---------------------+
| Experiment Manager | -----> |     Dataset Manager    | -----> | Per-Model Evaluator  |
+--------------------+        +-----------------------+        +---------------------+
        |                                                           |        |
        |                                                           v        v
        |                                                   +----------------------+  
        |                                                   | Fusion Evaluator     | 
        |                                                   +----------------------+  
        v                                                              |             
+--------------------+   <--- Profiler & Validator  -->  +-----------------------+       
| Artifact Store     |                                  | Pipeline Profiler     |       
+--------------------+                                  +-----------------------+       
        |                                                              |             
        +---------------> Statistical Engine <-------------------------+             
                         (paired tests, bootstrap)                             
                                   |                                           
                                   v                                           
                          Visualization & Report Generator                     
                                   |                                           
                                   v                                           
                              Dissertation Artifacts                           
```

High-level: Experiment Manager coordinates Dataset Manager, Evaluators, Profiler, and Statistical Engine; Artifact Store centralizes outputs; Visualization & Report Generator creates final dissertation artifacts.

## 8. Overall Data Flow

1. Experiment Manager reads experiment matrix (YAML) -> creates run directory + manifest.
2. Dataset Manager loads raw KPI/log sources, applies deterministic splitting and pre-processing, writes split artifacts to experiment folder.
3. Per-Model Evaluators read split artifacts and model artifacts, produce per-window scores and predictions; write to Artifact Store.
4. Fusion Evaluator reads model predictions and executes `FusionOrchestrator` to produce fused predictions and reports.
5. Pipeline Profiler collects per-stage timings and resource metrics concurrently.
6. Robustness Runner triggers variant runs with perturbed inputs; outputs stored separately.
7. Statistical Engine ingests metrics across runs to compute CIs, p-values, and effect sizes.
8. Visualization engine consumes results and Statistical Engine outputs to produce figures and tables.
9. Report Generator bundles figures, tables, and a narrative skeleton for dissertation chapters.

## 9. Major Components

- Experiment Manager
- Dataset Manager
- KPI Evaluator
- DeepLog Evaluator
- Fusion Evaluator
- Robustness Runner
- Pipeline Profiler and Validator
- Artifact Store
- Statistical Engine
- Visualization Engine
- Report Generator

## 10. Responsibilities of each component

Experiment Manager
- Create unique run IDs, set seeds, snapshot code commit and environment, launch runs, manage parallelization.

Dataset Manager
- Deterministic preprocessing, create splits (temporal and stratified), provide sample-level metadata for per-entity evaluation.

KPI Evaluator
- Load KPI model artifact and produce per-window numeric scores and binary predictions, metadata about missingness.

DeepLog Evaluator
- Run DeepLog inference producing per-window or per-event anomaly scores and any per-event metadata.

Fusion Evaluator
- Run production `FusionOrchestrator` in evaluation mode (no artifact overwrite or with namespaced outputs), produce fused scores and labels.

Robustness Runner
- Create perturbed datasets (missing, corrupt, shifted timestamps, label noise) and drive re-runs; parameter sweep support.

Pipeline Profiler
- Collect stage-level runtime, memory, CPU, and I/O; optionally produce cProfile traces or flamegraphs for hot-path analysis.

Artifact Store
- Provide canonical layout for artifacts and implement cleanup/archival policies; ensure manifests included.

Statistical Engine
- Run paired tests, compute bootstrapped CIs, DeLong/AUC tests or permutation equivalents; correct for multiple comparisons.

Visualization Engine
- Generate publication-quality plots and LaTeX-ready table outputs; ensure consistent styling across figures.

Report Generator
- Aggregate results, embed plots and tables into a structured dissertation-ready artifact bundle.

## 11. Component interactions

- Evaluators and Fusion Evaluator write standardized prediction CSVs to Artifact Store using agreed schema: `window_ts, window_end_ts, entity_id, score, label, source, metadata`.
- Fusion Evaluator reads those CSVs and executes deterministic Fusion pipelines.
- Profiler wraps calls to Evaluators and records start/end + resource snapshots; Profiler writes metadata into run manifest.
- Statistical Engine fetches metrics summary across runs to compute significance and effect sizes.
- Visualization Engine consumes Statistical Engine outputs and raw predictions for figures.

## 12. Required inputs

- Raw KPI datasets with timestamps and labels (or label generation mapping).
- Raw Log datasets (preprocessed to the same windowing granularity) and labels.
- Model artifacts: KPI model export and DeepLog export or inference wrappers.
- Fusion configuration and production code (Phase 7 artifacts).
- Experiment config matrix with seeds and perturbation definitions.
- Environment description (container image, or conda/requirements lockfile).

## 13. Generated outputs

- Predictions: `predictions/<model>/<run>/predictions.csv`.
- Fused predictions: `predictions/fusion/<run>/fused_predictions.csv`.
- Metrics: `metrics/<run>/metrics.csv` (per-window/per-entity aggregated metrics), `metrics/summary.csv`.
- Manifests: `experiments/<run>/manifest.json` (config, code sha, env, seed, inputs list).
- Profiling outputs: `profiling/<run>/profile.txt`, `profiling/<run>/flamegraph.svg` (optional).
- Visuals: `plots/<run>/*.png|.svg|.pdf` and `tables/<run>/*.tex`.
- Statistical results: `stats/<run>/paired_tests.json`, `stats/<run>/bootstrap_cis.json`.
- Results bundle: `phase8/results/<timestamp>.zip`.

## 14. Evaluation metrics

Per standard practice, define primary and secondary metrics.

Primary metrics (detection quality):
- Precision, Recall, F1-score (per-window and macro/micro aggregates)
- ROC-AUC and PR-AUC (with CIs)
- Average Precision (AP)

Secondary metrics (calibration & ranking):
- Brier score, calibration curves, reliability diagrams
- Confusion matrix (per-threshold)

Engineering metrics:
- End-to-end latency (ms or seconds per experiment)
- Per-stage latency (ingest, align, aggregate, normalize, decision, artifact)
- Throughput (windows/sec)
- Peak memory (MB)
- Disk I/O (MB/sec)
- Determinism indicator: artifact checksum equality after canonicalization

Robustness metrics:
- Delta-F1, Delta-AUC under perturbation levels
- Percentage of runs failing due to data issues

Statistical reporting:
- 95% bootstrap CIs for metrics
- p-values for paired tests, corrected for multiple comparisons
- Effect sizes (Cohen’s d, odds ratio)

## 15. Experimental workflow

Design:
- Define baseline experiment and variant experiments in the experiment matrix.
- Baseline: nominal dataset + standard pre-processing + default thresholds.
- Variants: missingness levels (10%, 30%, 50%), label-noise levels (5%, 10%, 20%), timestamp shifts (+/- 1, 5 minutes).

Execution steps (per experiment):
1. Experiment Manager creates run directory `experiments/<id>/` and writes manifest.
2. Dataset Manager produces deterministic splits and copies datasets into run folder.
3. Run KPI Evaluator -> produce `predictions/kpi/<id>`.
4. Run DeepLog Evaluator -> produce `predictions/deeplog/<id>`.
5. Run Fusion Evaluator -> produce `predictions/fusion/<id>`.
6. Compute metrics and store `metrics/<id>/`.
7. Profiler outputs written; Statistical Engine schedules bootstraps and paired tests.
8. Visualization Engine produces figures and tables; Report Generator bundles everything.

Repetition:
- Repeat runs for bootstrap samples or for different seeds (N runs; recommended N ≥ 30 for stable bootstrap CIs).

Automation:
- Provide a runner that accepts a single YAML and executes steps 1–8. Provide a dry-run mode.

## 16. Statistical analysis workflow

Pre-registration: define primary endpoints (e.g., F1 difference Fusion vs best single model) and tests.

1. For each run, compute per-window predictions and metrics.
2. Aggregate per-run metrics into a table for cross-run analysis.
3. Compute bootstrap CIs for AUC/F1 (stratified by entity/time as needed).
4. For pairwise comparisons (e.g., Fusion vs KPI): run paired permutation test on metric differences or McNemar for binary predictions.
5. For AUC comparisons: use DeLong where applicable or paired bootstrap when DeLong assumptions are not met.
6. Adjust p-values for multiple comparisons (Benjamini–Hochberg) when testing multiple models/datasets.
7. Record effect sizes and sample sizes; produce an interpretation guidance section.

## 17. Visualization workflow

- Use a consistent theme and palette across all figures.
- Save all figures in vector format (SVG/PDF) when possible; include PNG for web previews.

Required figures:
- ROC curves for KPI, DeepLog, and Fusion with CI ribbons.
- PR curves with average precision and CI.
- Calibration plots and Brier scores.
- Confusion matrices (heatmaps) at chosen thresholds.
- Per-stage latency bar charts and throughput timelines.
- Robustness plots: delta-F1/AUC vs perturbation level.
- Scatter plots or stacked contribution plots showing KPI/log contributions to fused decisions.

Each figure must include a short caption, data provenance (manifest id), and an explanation of what it demonstrates.

## 18. Reports and artifacts to generate

- `phase8/results/README.md` describing runs and how to reproduce.
- `phase8/results/main_report.pdf` (or LaTeX source) containing: methods, experiments, tables, figures, statistical conclusions, limitations.
- A `supplementary/` bundle for raw outputs, large tables, and additional figures.
- A `data-dictionary.md` describing columns in predictions and metrics.

## 19. Recommended directory structure

```
phase8/
  configs/
    experiments.yaml
  experiments/
    <run-id>/
      manifest.json
      inputs/
      predictions/
      metrics/
      plots/
      profiling/
      stats/
  evaluators/
  profiler/
  stat/
  visuals/
  notebooks/
  docs/
  results/
```

## 20. Testing strategy

- Unit tests: for configuration parsing, manifest generation, deterministic-split logic, and statistical utilities.
- Integration tests: end-to-end runs on tiny deterministic datasets (already used in Phase 7 style). Verify outputs and manifest keys.
- Reproducibility tests: repeated-run checksums with canonicalization (strip generated timestamps) to verify determinism.
- Robustness tests: intentionally corrupted datasets to confirm expected errors or graceful degradation.
- Performance smoke tests: minimal-scale runs for CI profiling to ensure no regression in pipeline time.

## 21. Completion criteria

- Primary experiments executed with pre-registered analysis plan.
- All primary and secondary research questions answered with statistical evidence.
- Publication-quality figures and tables generated for Results & Evaluation chapters.
- Reproducibility verified: all runs reproducible using manifest + environment snapshot.
- Code and artifacts archived in a single results bundle with README and reproduction instructions.

## 22. Risks and mitigation

- Poor data labeling: run label-quality audits; restrict analyses to high-confidence segments.
- Non-determinism from environment: run within containers and capture environment hashes; supply deterministic mode.
- Large computational cost: stage experiments, run small representative experiments first, and scale on cluster.
- Multiple comparisons: pre-register tests and use FDR corrections.

## 23. Assumptions

- Model artifacts from Phase 7 are available and deterministic for inference.
- Ground-truth labels exist for evaluation windows (or can be derived/validated).
- Infrastructure supports reproducible execution (container/conda) and sufficient compute for experiments.
- Evaluation uses offline batch processing.

## 24. Future extensibility

- Add streaming evaluation module for online latency and real-time behavior.
- Add MLOps integrations: model registry, CI re-evaluation on model or dataset updates.
- Add adversarial evaluation module.
- Extend to cross-site evaluation (multi-dataset generalization studies).

---

## Research Traceability Matrix

The matrix below maps research questions and hypotheses to experiments, metrics, expected outputs, and dissertation chapters where evidence will be used.

| RQ | Hypothesis | Experiment(s) | Evaluation Metric(s) | Expected Output(s) | Dissertation Chapter/Section |
|----|------------|---------------|----------------------|---------------------|-----------------------------|
| RQ1 | — | Baseline evaluation on primary dataset (per-model) | Precision, Recall, F1, ROC-AUC, PR-AUC | `metrics/<run>/metrics.csv`, ROC/PR plots | Results: Per-model performance (Ch. 4/5 Results) |
| RQ2 | H1 | Paired evaluation: Fusion vs best single model (baseline) | Paired F1 difference, paired permutation test, bootstrap CI | `stats/<run>/paired_tests.json`, difference tables, figure | Results: Fusion value (Ch. 4/5) |
| RQ3 | H2, H4 | Robustness experiments: missingness sweep, label-noise sweep, timestamp shifts | Delta-F1, Delta-AUC across perturbation levels | robustness plots, delta-metrics CSV | Robustness Analysis (Ch. 5) |
| RQ4 | H3 | Determinism tests: repeated runs with fixed seed & manifest | Artifact checksum equality (after canonicalization), per-stage runtime variance | determinism report, profiler outputs | Pipeline Evaluation (Ch. 3/4) |
| RQ5 | — | Cross-dataset runs (if available) | Per-model metrics across datasets; generalization delta | comparison tables, per-dataset ROC/PR plots | Generalization and Limitations (Ch. 6) |

Notes:
- Each experiment writes a `manifest.json` linking it to the RQ entries above.
- No experiment should be created without mapping to at least one RQ/Hypothesis in this matrix.

---

## 25. Critical review (missing components, weak areas, improvements)

1. Missing components or suggested additions
   - **Ground-truth quality auditor**: a small module to compute label consistency, label coverage per-entity, and annotation confidence. Justification: low-quality labels can invalidate statistical claims.
   - **Experiment registry with provenance UI**: web-based dashboard to browse run manifests, metrics, and artifacts (optional but improves research reproducibility and reviewer inspection).
   - **Automation for pre-registered analysis**: ensure the statistical analysis pipeline reads a pre-registered plan to reduce p-hacking risk.

2. Weak areas and mitigations
   - **Label scarcity**: if some devices or time periods have sparse labels, emphasize stratified analyses and report underpowered segments clearly.
   - **Multiple comparisons**: ensure the matrix documents primary vs exploratory analyses and apply corrections for exploratory tests.

3. Better alternatives
   - For AUC comparison, use paired bootstrap if DeLong assumptions are not met; specify fallback strategies in the stat engine.

4. Architectural improvements
   - Enforce a single canonical prediction schema for all evaluators; add a schema validator early in the pipeline.
   - Provide a canonical manifest normalizer that removes runtime-only fields (timestamps) for deterministic checksum comparisons.

5. Final assessment
   - The proposed architecture is complete and modular and directly supports dissertation objectives. Add the ground-truth auditor and manifest UI (optional) to improve reviewer confidence and traceability.

---

### Appendix: Example manifest schema (informative only)

```json
{
  "run_id": "2026-07-25T12-00-00-exp1",
  "commit": "<git-sha>",
  "config": "configs/exp1.yaml",
  "seed": 42,
  "env": {
    "container": "image:tag",
    "python": "3.13.5",
    "requirements_hash": "..."
  },
  "inputs": ["data/kpi/test.csv", "data/log/test.csv"],
  "outputs": ["predictions/kpi/exp1/predictions.csv", "predictions/fusion/exp1/fused_predictions.csv"],
  "start_ts": "2026-07-25T12:00:00Z",
  "end_ts": "2026-07-25T12:05:00Z"
}
```

---

End of Phase 8 Architecture and Design specification.
