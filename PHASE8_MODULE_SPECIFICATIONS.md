# Phase 8 — Module Specifications

This document is a detailed, implementation-ready design specification for Phase 8 (Evaluation, Validation, Benchmarking, and Analysis). It defines each production module, responsibilities, interfaces, testing scope, and integration details to allow direct implementation without further architectural decisions.

Note: This document contains no code. It is a production design specification only.

---

CONTENTS

- Module Specifications (per-module sections)
  - Experiment Manager
  - Dataset Manager
  - KPI Evaluator
  - DeepLog Evaluator
  - Fusion Evaluator
  - Robustness Runner
  - Pipeline Profiler & Validator
  - Artifact Store
  - Statistical Engine
  - Visualization Engine
  - Report Generator
  - Ground-Truth Auditor
  - Experiment Registry (lightweight dashboard)

- Cross-cutting concerns and implementation plan
  - Overall dependency graph
  - Implementation order
  - Recommended package structure
  - Shared data models
  - Configuration hierarchy
  - Artifact directory hierarchy
  - Naming conventions
  - Coding standards (high-level)
  - Testing hierarchy
  - Acceptance criteria (per module)

---

GENERAL NOTES

- All public interfaces described are design contracts. Implementation must preserve semantics and failure modes described in "Expected Exceptions / Error Handling." 
- All modules must write a manifest fragment to `manifest.json` in the experiment run directory describing inputs, outputs, start/end timestamps, and module-specific diagnostics.
- Determinism: Modules must support a deterministic mode where random seeds and ordering are fixed from Experiment Manager manifest.

---

MODULE SPECIFICATIONS

1) Experiment Manager

1. Module Name
   - Experiment Manager

2. Purpose
   - Orchestrate and coordinate Phase 8 experiments. Create run directories/manifests, set seeds, snapshot environment, and schedule module execution (sequential or parallel).

3. Responsibilities
   - Validate experiment configs, generate unique run IDs, record code/environment provenance, set deterministic seeds, launch and monitor evaluator/profiler/stat jobs, collect run-level artifacts into the experiment manifest.

4. Inputs
   - Experiment configuration (YAML/JSON), environment descriptor (optional), request to run a specific experiment matrix entry, optional `dry-run` flag.

5. Outputs
   - Run directory (experiments/<run-id>/), manifest.json (top-level run manifest), status codes, logs, and exit codes for downstream processing.

6. Dependencies
   - Filesystem and path utilities, Artifact Store API, optional job executor (local or cluster), environment snapshot tool (git, container image).

7. Public Interfaces
   - `create_run(config) -> run_id` (conceptual): validate and create run directory and manifest
   - `launch_run(run_id) -> status` (conceptual): start pipeline for run
   - `query_run(run_id) -> manifest/status` (conceptual)

8. Internal Responsibilities
   - Create experiment directory layout, write initial manifest (config, commit SHA, seed), create logging context, orchestrate execution order or parallel launches, handle termination and error aggregation, finalize manifest.

9. Configuration Requirements
   - Accept top-level experiment parameters: run_id prefix, seed, models to evaluate, datasets, perturbations, parallelism limits, retention policy.

10. Expected Exceptions / Error Handling
   - Invalid config -> fail fast with descriptive error
   - Resource exhaustion (disk/permission) -> log and set run state to failed
   - Downstream module failures -> capture cause, mark run as failed, still capture partial manifest and diagnostics

11. Logging Requirements
   - Log each major step and timestamps, env snapshot (git sha, python version), warnings and errors with stack traces, and a human-readable summary at run end.

12. Artifact Generation Responsibilities
   - Write `experiments/<run>/manifest.json` (includes inputs list, start/end timestamps, commit), write a `status.json` with module exit codes.

13. Unit Testing Scope
   - Validate config parsing and validation, seed propagation, manifest generation, error conditions for invalid configs.

14. Integration Testing Scope
   - Full orchestration with mock evaluators and a real Artifact Store; end-to-end dry-run and actual small dataset runs.

15. Future Extension Points
   - Plugin executor for remote cluster submission (Slurm/Kubernetes), hooks for CI, webhooks on run completion for external systems.

16. Interaction with other modules
   - Calls Dataset Manager, Evaluators, Profiler, Artifact Store; reads/writes manifests for all runs.

17. Sequence Diagram (ASCII)

```
Client -> Experiment Manager: start(config)
Experiment Manager -> Experiment Manager: validate(config)
Experiment Manager -> Artifact Store: create run dir
Experiment Manager -> Dataset Manager: prepare inputs
Experiment Manager -> Evaluators: launch KPI/DeepLog/Fusion
Evaluators -> Artifact Store: write predictions
Experiment Manager -> Profiler: capture metrics
Experiment Manager -> Statistical Engine: trigger analysis
Experiment Manager -> Artifact Store: finalize manifest
Client <- Experiment Manager: run_id/status
```

18. Lifecycle of the module
   - Loaded at Phase 8 runtime; instantiated once per controller process; persists until run completion; stateless between runs except manifest history.

---

2) Dataset Manager

1. Module Name
   - Dataset Manager

2. Purpose
   - Prepare and serve dataset artifacts required by evaluators: deterministic splits, preprocessing, windowing, and labeled ground truth.

3. Responsibilities
   - Validate raw dataset inputs, apply deterministic preprocessing, create train/val/test or hold-out windows as configured, generate canonical dataset artifacts for experiment run.

4. Inputs
   - Raw KPI and Log datasets (CSV/Parquet), labeling mapping, experiment config parameters (window size, stride, split strategy), seed from Experiment Manager.

5. Outputs
   - Preprocessed dataset files stored under `experiments/<run>/inputs/` (e.g., `kpi_test.csv`, `log_test.csv`, `labels.csv`), and dataset-level metadata (schema, row counts, checksums).

6. Dependencies
   - Filesystem, data parsing libraries (pandas or similar), time-window utilities, canonical schema definitions.

7. Public Interfaces
   - `prepare_datasets(run_id, config) -> inputs_manifest` (conceptual)
   - `get_dataset_path(run_id, name) -> Path`

8. Internal Responsibilities
   - Validate field presence and types, canonicalize timestamp formats (ISO-8601 UTC), enforce schema, compute and store checksums, record dataset provenance.

9. Configuration Requirements
   - Window size, alignment parameters, split method (time-based/stratified), sample balancing flags, allowed missingness thresholds.

10. Expected Exceptions / Error Handling
   - Missing required columns -> error and manifest entry
   - Unparseable timestamps -> record row-level errors or drop rows per config
   - Insufficient labeled data -> warning and manifest note

11. Logging Requirements
   - Log preprocessing steps, rows processed/removed, created file paths and checksums.

12. Artifact Generation Responsibilities
   - Write preprocessed CSV/Parquet files, write `inputs_manifest.json` with file paths, checksums, and sample counts.

13. Unit Testing Scope
   - Deterministic split correctness, schema validation, timestamp canonicalization, minimal dataset examples.

14. Integration Testing Scope
   - End-to-end data preparation integrated with Evaluators and Fusion Evaluator on tiny example datasets.

15. Future Extension Points
   - Support more file formats (Parquet), on-the-fly streaming windowing, connectors for remote data stores.

16. Interaction with other modules
   - Invoked by Experiment Manager; outputs consumed by Evaluators and Profiler; writes to Artifact Store.

17. Sequence Diagram (ASCII)

```
Experiment Manager -> Dataset Manager: prepare_datasets(config)
Dataset Manager -> Dataset Manager: validate and preprocess
Dataset Manager -> Artifact Store: write preprocessed files
Dataset Manager -> Experiment Manager: inputs_manifest
```

18. Lifecycle of the module
   - Per-run instance or function call; stateless between runs beyond written artifacts.

---

3) KPI Evaluator

1. Module Name
   - KPI Evaluator

2. Purpose
   - Run KPI-model inference on preprocessed KPI datasets and produce per-window scores and predictions compatible with fusion input schema.

3. Responsibilities
   - Load KPI model artifact or inference wrapper, perform deterministic inference, apply thresholds (if configured), and output predictions with metadata and checksums.

4. Inputs
   - Preprocessed KPI dataset artifact, model artifact (or inference wrapper), evaluation config (thresholds, batch sizes), seed.

5. Outputs
   - Predictions CSV: `predictions/kpi/<run>/predictions.csv` with columns: window_ts, window_end_ts, entity_id, kpi_score, kpi_available, source_record_id, source_metadata.

6. Dependencies
   - Model artifact format, data I/O, numeric libraries, Artifact Store for writing output.

7. Public Interfaces
   - `evaluate(run_id, model_artifact, input_path) -> predictions_manifest`

8. Internal Responsibilities
   - Batch inference, numeric stability checks, missing-value handling, attaching provenance to each prediction row.

9. Configuration Requirements
   - Model artifact path, threshold(s), batch size, device selection (CPU/GPU), timeouts.

10. Expected Exceptions / Error Handling
   - Model load failure -> log and signal failure to Experiment Manager
   - Numeric overflow/NaN -> handle per-row and record diagnostics

11. Logging Requirements
   - Model load time, inference throughput (rows/sec), errors per-batch, summary per-run.

12. Artifact Generation Responsibilities
   - Write predictions CSV and `predictions_manifest.json` including checksum and sample counts.

13. Unit Testing Scope
   - Prediction format validation, handling of missing scores, small-sample deterministic outputs.

14. Integration Testing Scope
   - Run KPI Evaluator end-to-end integrated with Dataset Manager, Artifact Store, and Fusion Evaluator on small dataset.

15. Future Extension Points
   - Support different model artifact formats and runtime accelerators; add confidence calibration step.

16. Interaction with other modules
   - Reads input created by Dataset Manager, writes outputs to Artifact Store, is consumed by Fusion Evaluator and Statistical Engine.

17. Sequence Diagram (ASCII)

```
Experiment Manager -> KPI Evaluator: evaluate(run_id, model, input)
KPI Evaluator -> Model: load
KPI Evaluator -> Model: infer(batch)
KPI Evaluator -> Artifact Store: write predictions
KPI Evaluator -> Experiment Manager: predictions_manifest
```

18. Lifecycle of the module
   - Invoked per-run; may be run multiple times in parallel for different models or dataset partitions.

---

4) DeepLog Evaluator

1. Module Name
   - DeepLog Evaluator

2. Purpose
   - Run DeepLog model inference on log datasets to produce per-window or per-event anomaly scores for evaluation and fusion.

3. Responsibilities
   - Load DeepLog artifact, align log events to evaluation windows, compute anomaly scores, and write standardized predictions schema.

4. Inputs
   - Preprocessed log dataset, DeepLog model artifact, windowing parameters, seed.

5. Outputs
   - Predictions CSV: `predictions/deeplog/<run>/predictions.csv` with fields: window_ts, window_end_ts, entity_id, log_score, log_available, source_record_id, source_metadata.

6. Dependencies
   - DeepLog inference runtime, event-window mapping utilities, Artifact Store.

7. Public Interfaces
   - `evaluate(run_id, model_artifact, input_path) -> predictions_manifest`

8. Internal Responsibilities
   - Map events to windows deterministically, handle sparse windows with no events, produce stable numeric outputs, store per-row metadata.

9. Configuration Requirements
   - Model artifact path, event-to-window mapping rules, batch size, GPU/CPU selection.

10. Expected Exceptions / Error Handling
   - Model load failure, unexpected event formats; module should record row-level failures and continue where possible, reporting diagnostics.

11. Logging Requirements
   - Event-to-window mapping counts, inference throughput, error counts, and sample rows for diagnostics.

12. Artifact Generation Responsibilities
   - Write predictions CSV, predictions_manifest.json, and optionally event-level debug files if enabled.

13. Unit Testing Scope
   - Window mapping correctness, empty-window behaviours, and output schema checks.

14. Integration Testing Scope
   - End-to-end evaluation with Dataset Manager and Fusion Evaluator; small dataset integration tests.

15. Future Extension Points
   - Support sequence-level outputs, online inference mode, and alternative log-model evaluators.

16. Interaction with other modules
   - Inputs from Dataset Manager; outputs consumed by Fusion Evaluator and Statistical Engine.

17. Sequence Diagram (ASCII)

```
Experiment Manager -> DeepLog Evaluator: evaluate(run_id, model, input)
DeepLog Evaluator -> DeepLog Model: load
DeepLog Evaluator -> DeepLog Model: infer
DeepLog Evaluator -> Artifact Store: write predictions
DeepLog Evaluator -> Experiment Manager: predictions_manifest
```

18. Lifecycle of the module
   - Invoked per run; optional long-running process for streaming evaluation (future extension).

---

5) Fusion Evaluator

1. Module Name
   - Fusion Evaluator

2. Purpose
   - Run the production `FusionOrchestrator` against per-model predictions to produce fused scores and decisions for evaluation.

3. Responsibilities
   - Prepare inputs in the format expected by the orchestrator, invoke `FusionOrchestrator` in evaluation mode, collect fused outputs and diagnostics, and write fused predictions and manifests.

4. Inputs
   - KPI predictions, DeepLog predictions, Fusion configuration (from Phase 7), run manifest seed for determinism.

5. Outputs
   - Fused predictions CSV: `predictions/fusion/<run>/fused_predictions.csv`; `fusion_manifest.json` with fusion diagnostics and normalization diagnostics.

6. Dependencies
   - Production `FusionOrchestrator` (Phase 7 code), Artifact Store, model prediction inputs.

7. Public Interfaces
   - `evaluate(run_id, inputs_manifest) -> fusion_manifest`

8. Internal Responsibilities
   - Validate input prediction formats, namespace outputs per-run to avoid collisions, capture normalization diagnostics and decision-engine statistics, and handle partial inputs (e.g., missing KPI or Log predictions).

9. Configuration Requirements
   - Fusion config path, normalization strategy options, thresholds, and artifact namespace options.

10. Expected Exceptions / Error Handling
   - Malformed input -> log and fail; FusionOrchestrator internal exceptions -> capture and write cause in fusion_manifest; missing input -> produce partial fused outputs with manifest note.

11. Logging Requirements
   - Log normalization diagnostics, fusion decisions count, any warnings when inputs missing; include references to per-model prediction manifests.

12. Artifact Generation Responsibilities
   - Write fused_predictions.csv, fusion_summary.json, source_coverage.json, phase7_manifest.json (namespaced under experiment) and include them in run manifest.

13. Unit Testing Scope
   - Input validation, correct invocation of `FusionOrchestrator` mock, handling of empty/partial inputs.

14. Integration Testing Scope
   - Full run with actual `FusionOrchestrator` and small input artifacts; verify produced artifacts and manifest fields.

15. Future Extension Points
   - Support alternative fusion strategies, ensemble-weight sweeps, and per-entity adaptive fusion.

16. Interaction with other modules
   - Consumes predictions from KPI and DeepLog Evaluators; writes outputs to Artifact Store; diagnostics consumed by Statistical Engine.

17. Sequence Diagram (ASCII)

```
Experiment Manager -> Fusion Evaluator: evaluate(run_id, predictions)
Fusion Evaluator -> FusionOrchestrator: run(inputs)
FusionOrchestrator -> Fusion Evaluator: fused outputs + diagnostics
Fusion Evaluator -> Artifact Store: write fused artifacts
Fusion Evaluator -> Experiment Manager: fusion_manifest
```

18. Lifecycle of the module
   - Invoked per-run; may be executed multiple times for perturbation experiments.

---

6) Robustness Runner

1. Module Name
   - Robustness Runner

2. Purpose
   - Systematically create perturbed dataset variants (missingness, corruption, time shifts, label noise) and drive re-runs to evaluate model and pipeline robustness.

3. Responsibilities
   - Parameterize perturbation levels, apply perturbations to dataset artifacts deterministically, schedule evaluator runs for each perturbation level, and aggregate delta metrics.

4. Inputs
   - Baseline input artifacts, perturbation matrix in experiment config, seed.

5. Outputs
   - For each perturbation: predictions, metrics, runs manifests, robustness summary CSV and plots.

6. Dependencies
   - Dataset Manager utilities, Evaluators, Experiment Manager orchestration, Artifact Store.

7. Public Interfaces
   - `run_perturbations(run_id, perturbation_matrix) -> robustness_summary`

8. Internal Responsibilities
   - Implement deterministic perturbation generators, apply corruption in a reversible manner (write new artifacts), and tag artifacts with perturbation metadata.

9. Configuration Requirements
   - Types and levels of perturbations, whether to overwrite or create new run namespaces, sampling strategies for missingness.

10. Expected Exceptions / Error Handling
   - If perturbation yields invalid dataset (e.g., all labels removed), log and skip/mark run as invalid; downstream evaluator failures handled per normal run semantics.

11. Logging Requirements
   - For each perturbation, log parameters, number of rows affected, and checksums of perturbed artifacts.

12. Artifact Generation Responsibilities
   - Write perturbed inputs under `experiments/<run>/perturbations/<label>/inputs/` and associated manifest fragment.

13. Unit Testing Scope
   - Perturbation generation logic correctness, deterministic behavior, basic error handling.

14. Integration Testing Scope
   - Run a small perturbation matrix through full pipeline and validate aggregated delta metrics.

15. Future Extension Points
   - Add adversarial perturbations or targeted corruption strategies.

16. Interaction with other modules
   - Calls Dataset Manager to create perturbed inputs, then invokes Experiment Manager/Evaluators for each variant, and writes results to Artifact Store.

17. Sequence Diagram (ASCII)

```
Experiment Manager -> Robustness Runner: run(run_id, perturbations)
Robustness Runner -> Dataset Manager: create perturbed inputs
Robustness Runner -> Experiment Manager: launch run for perturbed inputs
Robustness Runner -> Artifact Store: collect metrics
Robustness Runner -> Experiment Manager: robustness_summary
```

18. Lifecycle of the module
   - Invoked per robustness experiment; orchestrates multiple runs and cleans up temporary artifacts if configured.

---

7) Pipeline Profiler & Validator

1. Module Name
   - Pipeline Profiler & Validator

2. Purpose
   - Capture per-stage runtime, CPU/memory usage, I/O metrics, and validate artifact existence/format during runs.

3. Responsibilities
   - Expose hooks/wrappers to measure stage start/end times, resource snapshots, and optionally produce cProfile traces; validate outputs against schemas and record anomalies.

4. Inputs
   - Hooks into Experiment Manager and Evaluator calls, optional sampling flags for deep profiling.

5. Outputs
   - Profiling artifacts under `profiling/<run>/` including `timings.json`, `resource_usage.csv`, optional `profile.pstats` or flamegraph files, and validation reports.

6. Dependencies
   - System monitoring libraries, cProfile/time/perf utilities, Artifact Store.

7. Public Interfaces
   - `start_stage(stage_name)`, `end_stage(stage_name)` (conceptual), `snapshot_resources()`.

8. Internal Responsibilities
   - Aggregate per-stage metrics, compute throughput rates, and provide summaries for inclusion in run manifest. Validate artifact schema using canonical validators.

9. Configuration Requirements
   - Sampling rate for deep profiling, thresholds for warnings (e.g., memory > X), enable/disable cProfile collection.

10. Expected Exceptions / Error Handling
   - Profiling failures (permission or system calls) should not crash the run; profiler must log a warning and continue.

11. Logging Requirements
   - Emit per-stage start/stop events, resource peaks, and validation failures; attach sample stacks if cProfile enabled.

12. Artifact Generation Responsibilities
   - Write timing summaries, resource metrics, and validation reports to Artifact Store and include pointers in run manifest.

13. Unit Testing Scope
   - Timing wrapper semantics and validation rule correctness.

14. Integration Testing Scope
   - Integrate with a small end-to-end run to capture timings and validate artifact schema generation.

15. Future Extension Points
   - Distributed tracing (OpenTelemetry) integration and remote flamegraph aggregation.

16. Interaction with other modules
   - Hooks into Experiment Manager and Evaluators; writes profile artifacts to Artifact Store; inputs to Visualization Engine.

17. Sequence Diagram (ASCII)

```
Experiment Manager -> Profiler: start_stage("dataset.prepare")
Profiler -> Dataset Manager: (wrap)
Dataset Manager -> Profiler: end_stage("dataset.prepare")
Profiler -> Artifact Store: write timings
```

18. Lifecycle of the module
   - Instantiated for the duration of a run, providing stage-level measurement APIs.

---

8) Artifact Store

1. Module Name
   - Artifact Store

2. Purpose
   - Provide a canonical on-disk layout and APIs for writing, reading, and validating experimental artifacts (predictions, metrics, plots, manifests).

3. Responsibilities
   - Enforce directory schema, compute and write checksums, ensure permissions, and provide helper methods for canonicalized read/write operations used by other modules.

4. Inputs
   - Files and objects from Evaluators, Profiler, Statistical Engine, Visualization Engine.

5. Outputs
   - Files stored per run under `experiments/<run>/` and global indices such as `runs_index.json`.

6. Dependencies
   - Filesystem, checksum library (sha256), optional remote-storage connectors.

7. Public Interfaces
   - `write_artifact(run_id, path_relative, data) -> artifact_manifest_entry`
   - `read_artifact(run_id, path_relative) -> data`
   - `list_artifacts(run_id) -> list`

8. Internal Responsibilities
   - Ensure atomic writes (write to temp then rename), maintain artifact indices, apply retention policy, and optionally support compression.

9. Configuration Requirements
   - Root artifacts directory, retention policy, optional remote sync settings.

10. Expected Exceptions / Error Handling
   - Disk full or permissions -> bubble to Experiment Manager; write retries for transient I/O errors.

11. Logging Requirements
   - Log artifact writes with sizes and checksums, and any validation failures.

12. Artifact Generation Responsibilities
   - Not a data generator but the canonical writer: compute checksums, write metadata JSON alongside artifacts.

13. Unit Testing Scope
   - Atomic write behaviour, checksum correctness, file listing and read-back.

14. Integration Testing Scope
   - Write and read artifacts across modules in end-to-end runs, verify manifest inclusion.

15. Future Extension Points
   - Remote storage adapters (S3, GCS), DB-backed artifact indices, signed URLs for sharing.

16. Interaction with other modules
   - All modules use Artifact Store to write outputs; Experiment Manager consults Artifact Store for run artifacts.

17. Sequence Diagram (ASCII)

```
Module -> Artifact Store: write_artifact(run_id, path, data)
Artifact Store -> Artifact Store: write temp file
Artifact Store -> Artifact Store: compute checksum
Artifact Store -> Artifact Store: rename temp to final
Artifact Store -> Module: return manifest entry
```

18. Lifecycle of the module
   - Singleton service used by all per-run modules; stateless beyond filesystem artifacts.

---

9) Statistical Engine

1. Module Name
   - Statistical Engine

2. Purpose
   - Execute the statistical analysis plan: paired tests, bootstrapped confidence intervals, AUC comparisons, multiple-test correction, and produce statistical artifacts for reporting.

3. Responsibilities
   - Implement paired permutation/McNemar tests for categorical outcomes, implement bootstrap resampling for metric CIs, support DeLong or bootstrap for AUC comparisons, and generate JSON/CSV artifacts summarizing tests and p-values.

4. Inputs
   - Metrics table(s) across runs/models, per-record predictions for paired testing, pre-registered analysis plan.

5. Outputs
   - `stats/<run>/...` files including `bootstrap_cis.json`, `paired_tests.json`, and effect-size tables.

6. Dependencies
   - Numeric/statistics libraries (numpy/scipy or equivalent), Artifact Store for inputs and outputs.

7. Public Interfaces
   - `analyze(run_id, analysis_plan) -> stats_manifest`

8. Internal Responsibilities
   - Validate analysis plan, run specified tests, compute p-values and CIs, apply multiple testing correction, and log assumptions and test conditions.

9. Configuration Requirements
   - Number of bootstrap samples, significance thresholds, correction method (BH/Bonferroni), seed for resampling.

10. Expected Exceptions / Error Handling
   - If assumptions for a test are not satisfied, choose fallback test (documented) and record this in results; insufficient samples -> mark as underpowered.

11. Logging Requirements
   - Log test names, sample sizes, p-values, test durations, and warnings if assumptions violated.

12. Artifact Generation Responsibilities
   - Write test result artifacts (JSON/CSV) and a human-readable summary into Artifact Store.

13. Unit Testing Scope
   - Correctness of bootstrap implementation, permutation test reproducibility, multiple-correction logic.

14. Integration Testing Scope
   - End-to-end analysis using real predictions and metrics to confirm outputs and formats expected by Visualization Engine.

15. Future Extension Points
   - Add Bayesian analysis module or advanced causal inference tests.

16. Interaction with other modules
   - Consumes metrics/predictions from Artifact Store; produces artifacts used by Visualization Engine and Report Generator.

17. Sequence Diagram (ASCII)

```
Experiment Manager -> Statistical Engine: analyze(run_id, plan)
Stat Engine -> Artifact Store: read metrics/predictions
Stat Engine -> Stat Engine: run tests
Stat Engine -> Artifact Store: write stats artifacts
Stat Engine -> Experiment Manager: stats_manifest
```

18. Lifecycle of the module
   - Invoked as needed post-run; stateless between analyses other than output artifacts.

---

10) Visualization Engine

1. Module Name
   - Visualization Engine

2. Purpose
   - Produce high-quality, publication-ready figures and tables for the dissertation from metrics and statistical outputs.

3. Responsibilities
   - Generate consistent style plots (ROC, PR, calibration), LaTeX-ready tables, and interactive notebooks for exploration.

4. Inputs
   - Predictions, metrics, stats artifacts from Artifact Store, plotting style configuration.

5. Outputs
   - Vector and raster figures under `plots/<run>/`, table artifacts under `tables/<run>/` and figure metadata for captions.

6. Dependencies
   - Plotting libraries (matplotlib, seaborn, etc.), LaTeX generator or tabulate utilities, Artifact Store.

7. Public Interfaces
   - `render(run_id, templates) -> plots_manifest`

8. Internal Responsibilities
   - Apply canonical color/theme, ensure legibility (font sizes), compute CI ribbons where needed, embed provenance info in figure metadata.

9. Configuration Requirements
   - Figure DPI, default color palette, font sizes, output formats, figure captions templates.

10. Expected Exceptions / Error Handling
   - Missing data for requested figure -> log and skip or generate placeholder; plotting errors -> capture stack trace and continue with other plots.

11. Logging Requirements
   - Log created figure paths, time to render per figure, any warnings about insufficient data.

12. Artifact Generation Responsibilities
   - Write plot files and table files to Artifact Store and add manifest entries.

13. Unit Testing Scope
   - Plot data-preparation utilities, table formatting, and caption templating.

14. Integration Testing Scope
   - Full-run generation of primary figures from Statistical Engine outputs to verify file formats and correct captions/provenance.

15. Future Extension Points
   - Interactive dashboard generation, specialized plotting for new metrics.

16. Interaction with other modules
   - Reads metrics from Artifact Store, consumes Statistical Engine artifacts, writes visuals to Artifact Store for Report Generator.

17. Sequence Diagram (ASCII)

```
Experiment Manager -> Visualization Engine: render(run_id)
Visualization Engine -> Artifact Store: read stats
Visualization Engine -> Visualization Engine: create figures
Visualization Engine -> Artifact Store: write figure files
Visualization Engine -> Experiment Manager: plots_manifest
```

18. Lifecycle of the module
   - Stateless utility invoked post-analysis; runs as part of finalization steps for a run.

---

11) Report Generator

1. Module Name
   - Report Generator

2. Purpose
   - Aggregate figures, tables, and statistical summaries into dissertation-ready artifacts (PDF/LaTeX/Markdown) and a structured results bundle.

3. Responsibilities
   - Compose a pre-defined report skeleton incorporating canonical figures and tables, generate a compact README describing reproduction steps, and create a results ZIP.

4. Inputs
   - Figures, tables, metrics, manifests, and textual fragments (chapter skeletons) from Visualization Engine and Statistical Engine.

5. Outputs
   - `results/<run>/main_report.pdf` or LaTeX source, `results/<run>/results_bundle.zip`, README.

6. Dependencies
   - LaTeX toolchain (optional), templating engine (Jinja/Markdown templater), Artifact Store.

7. Public Interfaces
   - `generate_report(run_id, template) -> report_manifest`

8. Internal Responsibilities
   - Resolve figure/table paths into templates, ensure captions and provenance embedded, package outputs and metadata.

9. Configuration Requirements
   - Template selection, output formats, inclusion lists, copyright.

10. Expected Exceptions / Error Handling
   - Missing figure/table -> produce placeholder and log; LaTeX compile failures -> fallback to Markdown bundle and record compile logs.

11. Logging Requirements
   - Log packaging steps, compile times, and final artifact sizes.

12. Artifact Generation Responsibilities
   - Produce final PDF/LaTeX/Markdown report and zipped results for archival/sharing.

13. Unit Testing Scope
   - Template rendering correctness and manifest inclusion.

14. Integration Testing Scope
   - Full run where figures and tables exist; compile report and verify included assets.

15. Future Extension Points
   - Automated submission packaging for conferences, DOIs embedding, or manuscript metadata.

16. Interaction with other modules
   - Consumes visuals and stats; writes final reports into Artifact Store; notifies Experiment Registry.

17. Sequence Diagram (ASCII)

```
Experiment Manager -> Report Generator: generate_report(run_id)
Report Generator -> Artifact Store: read figures/tables
Report Generator -> Template Engine: render
Report Generator -> Artifact Store: write report bundle
Report Generator -> Experiment Manager: report_manifest
```

18. Lifecycle of the module
   - Invoked as a finalization step; may be run multiple times for different template variants.

---

12) Ground-Truth Auditor

1. Module Name
   - Ground-Truth Auditor

2. Purpose
   - Evaluate and quantify label quality: coverage, disagreement, temporal gaps, and per-entity label density; flag low-quality segments for exclusion or caution.

3. Responsibilities
   - Run label consistency checks, compute label coverage statistics, create annotation confidence reports, and optionally generate suggested hold-out segments.

4. Inputs
   - Label files, dataset metadata, optionally human annotation metadata.

5. Outputs
   - `audit/<run>/label_quality.json`, suggested exclusions list, summary plots of label coverage.

6. Dependencies
   - Dataset Manager outputs and Artifact Store.

7. Public Interfaces
   - `audit_labels(run_id, label_paths) -> audit_manifest`

8. Internal Responsibilities
   - Compute per-entity per-time coverage, detect contradictory labels, compute agreement rates if multiple annotators exist.

9. Configuration Requirements
   - Minimum coverage thresholds, label smoothing policies, conflict resolution policies.

10. Expected Exceptions / Error Handling
   - Missing labels -> mark audit as no-data; contradictory labels -> produce conflict entries.

11. Logging Requirements
   - Log audit steps and flagged issues with row-level references for review.

12. Artifact Generation Responsibilities
   - Write audit JSON and plots and add entries to run manifest.

13. Unit Testing Scope
   - Synthetic label sets for correctness of calculations.

14. Integration Testing Scope
   - Audit integrated with Dataset Manager and used to gate experiment runs when configured.

15. Future Extension Points
   - Human-in-the-loop annotation remediation UI integration.

16. Interaction with other modules
   - Consults Dataset Manager, writes to Artifact Store; Experiment Manager may refer to audit to skip or annotate runs.

17. Sequence Diagram (ASCII)

```
Experiment Manager -> Ground-Truth Auditor: audit_labels(run_id)
Ground-Truth Auditor -> Artifact Store: read labels
Ground-Truth Auditor -> Artifact Store: write audit report
Ground-Truth Auditor -> Experiment Manager: audit_manifest
```

18. Lifecycle of the module
   - Typically run prior to main experiments; produces artifacts for downstream experiment annotation.

---

13) Experiment Registry (lightweight dashboard)

1. Module Name
   - Experiment Registry

2. Purpose
   - Provide a browseable index of runs and artifacts to aid reviewers and developers; optional web UI (lightweight) or static HTML index generator.

3. Responsibilities
   - Index run manifests, expose search by tags/metrics, provide links to artifacts and provenance.

4. Inputs
   - Run manifests and artifact indices from Artifact Store.

5. Outputs
   - `registry/index.html` (or JSON index), API endpoints for querying run metadata.

6. Dependencies
   - Artifact Store, optional lightweight web server (Flask or static file server).

7. Public Interfaces
   - `index_runs()` static generator; optional `query_runs(params)` API.

8. Internal Responsibilities
   - Aggregate manifests, build indices, generate HTML/JSON, and optionally provide simple metrics filtering.

9. Configuration Requirements
   - Root URL, authentication (optional), retention policies.

10. Expected Exceptions / Error Handling
   - Missing manifests handled by skipping runs; index generation failure -> partial index and logged error.

11. Logging Requirements
   - Index generation times and any skipped runs with reasons.

12. Artifact Generation Responsibilities
   - Generate index artifacts (HTML/JSON) and copy referenced assets for quick browsing.

13. Unit Testing Scope
   - Index generation correctness given sample manifests.

14. Integration Testing Scope
   - Index generation from a full experiment directory tree and link verification.

15. Future Extension Points
   - Full-fledged dashboard with drill-down; integration with authentication and role-based access.

16. Interaction with other modules
   - Reads manifests from Artifact Store; optionally triggered by Experiment Manager at run finalization.

17. Sequence Diagram (ASCII)

```
Experiment Manager -> Registry: index_runs()
Registry -> Artifact Store: read manifests
Registry -> Registry: generate HTML/JSON index
Registry -> Experiment Manager: index_manifest
```

18. Lifecycle of the module
   - Periodic or on-demand; stateless, regenerates from artifacts.

---

CROSS-CUTTING CONCERNS

Overall dependency graph (module-level)

```
Experiment Manager
  -> Dataset Manager
  -> Experiment Registry
  -> Robustness Runner -> Dataset Manager
  -> KPI Evaluator -> Artifact Store
  -> DeepLog Evaluator -> Artifact Store
  -> Fusion Evaluator -> Artifact Store
  -> Pipeline Profiler -> Artifact Store
  -> Ground-Truth Auditor -> Artifact Store
  -> Statistical Engine -> Artifact Store
  -> Visualization Engine -> Artifact Store
  -> Report Generator -> Artifact Store
```

Implementation order (recommended)

1. Core infra: Artifact Store, configuration loader, shared data models
2. Experiment Manager (manifest creation, run scaffolding)
3. Dataset Manager (preprocessing and deterministic splitting)
4. KPI Evaluator and DeepLog Evaluator (per-model evaluators)
5. Fusion Evaluator (integrate Phase 7 FusionOrchestrator)
6. Pipeline Profiler & Validator
7. Ground-Truth Auditor
8. Statistical Engine
9. Visualization Engine
10. Report Generator
11. Robustness Runner & Experiment Registry

Recommended package structure

```
phase8/
  core/                # artifact store, config loader, shared models
  manager/             # Experiment Manager
  data/                # Dataset Manager, perturbation utilities
  evaluators/
    kpi/
    deeplog/
    fusion/
  profiler/
  stats/
  visuals/
  reports/
  audit/
  registry/
  configs/
  experiments/
```

Shared data models (schema overview)

- Prediction row (canonical):
  - window_ts (ISO UTC), window_end_ts (ISO UTC), entity_id, score, available (bool), source_type, source_record_id, source_metadata (dict)

- Metrics row (canonical):
  - run_id, model, window_ts, entity_id, pred_label, true_label, score, threshold, extra_metadata

- Manifest (top-level):
  - run_id, config_ref, commit_sha, env_hash, start_ts, end_ts, inputs, outputs, modules_diagnostics

Configuration hierarchy

- `configs/global.yaml` — global defaults (artifact root, retention)
- `configs/experiment_schema.yaml` — canonical experiment schema enforced by Experiment Manager
- `configs/<experiment>.yaml` — experiment-specific overrides

Artifact directory hierarchy (canonical)

```
experiments/<run-id>/
  manifest.json
  inputs/
  predictions/
    kpi/
    deeplog/
    fusion/
  metrics/
  stats/
  plots/
  profiling/
  audit/
  reports/
```

Naming conventions

- Run IDs: `YYYYMMDD-HHMMSS-<short-desc>`
- Files: `snake_case.ext` (e.g., `fusion_summary.json`, `fused_predictions.csv`)
- Manifests: `manifest.json` at run root

Coding standards (high-level)

- Follow PEP8 / PEP257 for Python code
- Strict typing and runtime validation for public interfaces
- Prefer composition over inheritance; small pure functions for logic
- Clearly separate I/O from business logic to ease testing

Testing hierarchy

- Unit tests: `tests/unit/` for module internal functions and small deterministic behaviour
- Integration tests: `tests/integration/` for end-to-end small data runs
- System tests: `tests/system/` for full-size or scaled runs (optional, may run off-CI)

Acceptance criteria for each module (summary)

- Artifact Store: atomic writes, checksum correctness, reads return same bytes
- Experiment Manager: valid run manifest created for every accepted config
- Dataset Manager: deterministic splits reproducible given seed
- KPI/DeepLog Evaluators: produce canonical prediction schema and metadata; throughput logged
- Fusion Evaluator: produces same artifacts as production Phase 7 `ArtifactWriter` contract
- Profiler: produces timings and resource usage for every stage
- Statistical Engine: produces reproducible test outputs and CIs; document assumptions
- Visualization Engine: produces required figures with captions and provenance
- Report Generator: bundles final artifacts and includes a reproduction README

---

Appendix: Implementation checklist (milestones)

- Milestone 1: Core infra + Experiment Manager + Dataset Manager
- Milestone 2: Evaluators (KPI & DeepLog) + Artifact Store integration
- Milestone 3: Fusion evaluator integration + Profiler
- Milestone 4: Statistical Engine + Visualization Engine
- Milestone 5: Report Generator, Auditor, and Registry
- Milestone 6: Robustness Runner, full experiment matrix runs, and documentation

---

DOCUMENT END
