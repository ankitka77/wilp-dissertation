# Phase 5 Implementation Plan

## Project

Anomaly and Fault Detection in Wireless Systems

## Phase

Phase 5 – Log Dataset Analysis & Sequence Preparation

## Objective

Prepare HDFS/BGL-style system log data for DeepLog-style sequence modeling in Phase 6.

This phase does not implement LSTM, DeepLog, or any anomaly model training. Its purpose is to produce clean, validated, and statistically rich log sequences, event vocabularies, and reports that can be consumed directly by Phase 6.

---

## 1. Design Principles

The Phase 5 architecture is intentionally constrained to preserve the already-frozen project structure.

### Invariants

- Do not redesign the KPI pipeline from Phases 2–4.
- Do not modify existing model or evaluation logic.
- Do not introduce LSTM or DeepLog implementation in this phase.
- Reuse the existing project conventions for settings, logging, artifact storage, and experiment tracking.
- Keep the design modular and testable for future Phase 6 integration.

---

## 2. Proposed Folder Structure

```text
wilp-dissertation/
├── data/
│   └── logs/
│       └── HDFS_v1/
├── src/
│   ├── common/
│   │   └── settings.py
│   ├── infrastructure/
│   │   └── experiment_manager.py
│   ├── log_processing/
│   │   ├── __init__.py
│   │   ├── model.py                 # Existing scaffold retained for compatibility
│   │   ├── log_loader.py           # NEW
│   │   ├── log_parser.py           # NEW (structural parsing)
│   │   ├── template_miner.py       # NEW (template extraction / mining)
│   │   ├── event_id_mapper.py      # NEW
│   │   ├── sequence_builder.py     # NEW
│   │   ├── dataset_validator.py    # NEW
│   │   ├── report_generator.py     # NEW
│   │   └── visualizer.py           # NEW
│   └── visualization/
│       └── plotter.py               # Extended only if needed for log plots
├── artifacts/
│   ├── experiments/
│   ├── models/
│   ├── plots/
│   │   └── phase5/
│   └── reports/
│       └── phase5/
├── tests/
│   └── unit/
│       └── test_phase5_log_sequence_preparation.py
└── phase5_analysis.py                # NEW orchestration entry point
```

### Notes

- The new Phase 5 logic is added under `src/log_processing` to emphasize preprocessing responsibilities.
- The existing Phase 4 experiment artifact structure remains the integration point.
- All reports are written only under `artifacts/reports/phase5` (no mirrored `reports/phase5`).

---

## 3. Proposed Classes

### 3.1 LogDataLoader

Purpose:
- Load HDFS/BGL-style log files from the configured input directory.
- Normalize raw log lines into a tabular format for downstream parsing.

Responsibilities:
- Validate input file existence.
- Read raw log lines.
- Attach source metadata such as file name, dataset type, and load timestamp.
- Return a structured record collection.

### 3.2 LogParser

Purpose:
- Perform structural parsing of raw log lines into normalized fields (timestamp, host, severity, message, ids).

Responsibilities:
- Apply line-level parsing rules and extract structured columns.
- Preserve raw message text for traceability.
- Emit a cleaned `message` field suitable for template mining.

### 3.3 TemplateMiner

Purpose:
- Extract event templates from normalized message strings and produce candidate templates.

Responsibilities:
- Apply tokenisation and variable masking to produce canonical template strings.
- Support configurable masking rules (numbers, IPs, paths, UUIDs, hex tokens, quoted strings).
- Produce a template frequency table for vocabulary construction and downstream mapping.
- Output a DataFrame augmented with a `template` column used by the EventIdMapper.

### 3.4 EventIdMapper

Purpose:
- Assign deterministic event IDs to templates.
- Build an event vocabulary for Phase 6 consumption.

Responsibilities:
- Create a vocabulary table of template, event_id, and frequency.
- Ensure event IDs are stable across repeated runs for the same dataset.
- Support optional manual override for known template mappings.

### 3.5 SequenceBuilder

Purpose:
- Transform parsed event streams into training and test sequences.
- Prepare the exact format needed for DeepLog-style modeling in Phase 6.

Responsibilities:
- Group events by sequence key such as block ID, session ID, or time-windowed context.
- Create sliding windows over event IDs.
- Produce fixed-length input sequences and next-event labels.
- Generate training and test sequence splits.

### 3.6 DatasetValidator

Purpose:
- Validate the integrity of parsed logs, event mappings, and generated sequences.

Responsibilities:
- Ensure no empty sequences are produced.
- Verify event IDs are present and non-negative.
- Check sequence lengths against configured minimum and maximum thresholds.
- Validate split coverage for train/test data.
- Produce a human-readable validation report.

### 3.7 SequenceProfiler

Purpose:
- Create statistical summaries for event and sequence distributions.

Responsibilities:
- Compute event frequency counts.
- Compute sequence length distribution.
- Compute average, median, and maximum sequence length.
- Report top frequent events and rare event coverage.
- Produce CSV and JSON report outputs.

### 3.8 LogVisualizer

Purpose:
- Produce visualizations that help assess sequence quality and event diversity.

Responsibilities:
- Plot event frequency histograms.
- Plot sequence-length distribution.
- Plot top-N event templates.
- Plot train/test sequence distribution.
- Save output images into the phase-specific plot directory.

### 3.9 Phase5Pipeline

Purpose:
- Orchestrate the full Phase 5 workflow end to end.

Responsibilities:
- Read configuration.
- Load logs.
- Parse templates.
- Build event vocabulary.
- Generate sequences.
- Validate data.
- Produce reports and visualizations.
- Register artifacts with the experiment manager.

---

## 4. Interfaces and Contracts

The design should follow clear interfaces so Phase 6 can consume outputs without ambiguity.

### 4.1 Loader Interface

- Input: configured input path and optional dataset type.
- Output: parsed log rows with normalized columns.

Suggested contract:
- load() -> pd.DataFrame
- validate_input() -> bool

### 4.2 Parser Interface

- Input: raw log rows.
- Output: parsed event records with template and raw message fields.

Suggested contract:
- parse() -> pd.DataFrame
- extract_templates() -> list[str]

### 4.3 Sequence Interface

- Input: parsed event stream and configuration.
- Output: one or more sequence tables for training and testing.

Suggested contract:
- build_sequences() -> dict[str, pd.DataFrame]
- build_windows() -> pd.DataFrame

### 4.4 Validation Interface

- Input: parsed logs, vocabularies, and sequences.
- Output: validation result object containing warnings, errors, and summary metrics.

Suggested contract:
- validate() -> dict[str, Any]

### 4.5 Reporting Interface

- Input: validated datasets and sequence statistics.
- Output: CSV/JSON/TXT artifacts.

Suggested contract:
- generate_reports() -> dict[str, Path]

---

## 5. Responsibilities by Layer

### Data Layer

- Load raw log files.
- Normalize metadata and line-level fields.
- Keep parsing logic independent from modeling logic.

### Parsing Layer

- Convert raw event strings to canonical templates.
- Produce event IDs for each template.
- Maintain deterministic vocabulary mappings.

### Sequence Layer

- Create ordered event sequences.
- Split into training and testing subsets.
- Ensure sequences are suitable for Phase 6.

### Reporting Layer

- Generate validation and statistics artifacts.
- Produce plots and summary reports.
- Preserve traceability for experiment runs.

---

## 6. Data Flow

The Phase 5 pipeline should flow as follows:

1. Configuration is loaded from the existing settings model.
2. The log loader reads the raw HDFS/BGL log files.
3. Each log line is parsed into structured fields.
4. Templates are extracted and mapped to event IDs.
5. Event streams are grouped into logical sequences.
6. Sliding windows are generated to form sequence examples.
7. Validation checks confirm data quality and sequence integrity.
8. Reports and plots are generated.
9. All outputs are persisted to the artifact directories.
10. The experiment manager records the run metadata and artifacts.

### Conceptual Flow Diagram

```text
Raw logs
  ↓
LogDataLoader
  ↓
LogParser
  ↓
TemplateMiner
  ↓
EventIdMapper
  ↓
SequenceBuilder
  ↓
DatasetValidator
  ↓
SequenceProfiler + LogVisualizer
  ↓
Artifacts + Experiment Metadata
```

---

## 7. Configuration Strategy

Phase 5 should use the existing settings architecture and extend it with a dedicated Phase 5 configuration block.

### Proposed Configuration Fields

- dataset_type: hdfs | bgl | auto
- input_dir: data/logs/HDFS_v1
- input_files: list of log files
- parser_mode: regex | template | auto
- sequence_mode: block | sliding_window | auto
- window_size: int
- stride: int
- min_sequence_length: int
- max_sequence_length: int
- train_ratio: float
- random_seed: int
- output_prefix: phase5
  - include_dataset_fingerprint: bool

### Configuration Placement

The new settings should be added in the existing settings model structure, preserving the current configuration pattern already used by Phases 2–4.

---

## 8. Log Parsing Strategy

### 8.1 Supported Log Types

The architecture should support:
- HDFS logs, where block-based sequences are natural.
- BGL logs, where chronological event streams can be segmented using a configurable sliding window.

### 8.2 Parsing Approach

The parser should follow a two-stage strategy:

1. Structural parsing
   - Extract fields such as timestamp, hostname, severity, message, and identifier if present.
   - Preserve the original raw message for traceability.

2. Template extraction
   - Replace variable values with placeholders.
   - Produce a canonical template string such as:
     - "Received block <*>"
     - "Packet <*> sent to <*>"

### 8.3 Event ID Strategy

- Each unique template becomes one event type.
- A deterministic vocabulary is built using sorted template order or frequency order.
- Event IDs should be stable between runs to allow consistent downstream training in Phase 6.

### 8.4 Parsing Rules

- Ignore malformed or empty lines without breaking the full pipeline.
- Log warnings for skipped lines.
- Keep both the template and the raw message in the parsed output.

---

## 9. Sequence Generation Strategy

The sequence generation strategy must support both block-oriented and window-oriented data.

### 9.1 HDFS Strategy

For HDFS-style logs:
- Group events by block ID or session identifier.
- Each group becomes one logical sequence.
- Keep sequence length as the number of events in that block.
- Optionally truncate or filter sequences outside configured length bounds.

### 9.2 BGL Strategy

For BGL-style logs:
- Use a time-ordered event stream.
- Create sliding windows of fixed size with configurable stride.
- Each window becomes one sequence.
- The next event can be stored as an auxiliary label for later model training if needed by Phase 6.

### 9.3 Sequence Output Format

Each generated sequence should contain at least:
- sequence_id
- split (train/test)
- source (dataset file or source ID)
- sequence_events (list or serialized representation)
- sequence_length
- label or auxiliary target if available

This format should remain simple and serializable for the downstream Phase 6 consumer.

---

## 10. Dataset Validation

Validation should be explicit and report-driven.

### Validation Checks

- Raw log file presence.
- At least one parsed event.
- Template extraction produced non-empty vocabulary.
- No empty sequences.
- Sequence lengths satisfy configured minimum/maximum bounds.
- Event IDs are unique and non-negative.
- Train and test splits are non-empty.

### Validation Output

The validator should emit:
- a summary object,
- a text report,
- and a structured validation table if needed.

The validation result should clearly distinguish:
- errors (blocking issues),
- warnings (non-blocking issues),
- and passed checks.

---

## 11. Statistical Reports

The following reports should be generated:

### Event Statistics
- total events parsed
- unique templates discovered
- event frequency table
- top-N most frequent events

### Sequence Statistics
- total sequences generated
- train/test sequence counts
- average sequence length
- median sequence length
- max sequence length
- min sequence length
- length distribution summary

### Dataset Statistics
- number of raw log lines processed
- number of invalid or skipped lines
- number of templates found
- vocabulary size

### Output Locations

- artifacts/reports/phase5/event_statistics.csv
- artifacts/reports/phase5/sequence_statistics.csv
- artifacts/reports/phase5/validation_report.txt

All reports are written only under `artifacts/reports/phase5` (no mirrored `reports/phase5`).

---

## 12. Visualizations

The visualization layer should produce a small but informative set of plots.

### Proposed Plots

1. Event frequency distribution
2. Top-N template frequency bar chart
3. Sequence length histogram
4. Sequence length boxplot (per-sequence length distribution summary)
5. Train/test sequence count comparison
6. Optional template coverage plot for rare events

### Output Location

- artifacts/plots/phase5/

These plots are saved under `artifacts/plots/phase5` and copied into the experiment `plots/` directory when the run is recorded.

These plots should be generated using the existing visualization style convention already used by prior phases: high-resolution images with descriptive titles and labels.

---

## 13. Output Artifacts

The phase should produce the following artifact set:

### Core Data Outputs

- parsed_log_events.csv
- event_vocabulary.csv
- event_vocabulary.json
- training_sequences.csv
- test_sequences.csv
- sequence_metadata.csv

### Report Outputs

- event_statistics.csv
- sequence_statistics.csv
- validation_report.txt
- dataset_summary.json
- phase5_manifest.json  # manifest with metadata for Phase 6

### Visualization Outputs

- 01_event_frequency.png
- 02_top_templates.png
- 03_sequence_length_distribution.png
- 03b_sequence_length_boxplot.png
- 04_train_test_split.png

### Experiment Outputs

- config.json
- metrics.json
- README.txt
- phase5_manifest.json (copied into experiment dir)
- plots/ (copied visuals)

Experiment metadata saved via `ExperimentManager` should include the dataset fingerprint (SHA-256) and a reference to the `phase5_manifest.json` produced by the run.

All outputs should remain under the project’s established artifact hierarchy.

---

## 14. Integration with Experiment Manager

Phase 5 should integrate with the existing ExperimentManager rather than creating a separate tracking system.

### Integration Plan

- Start a new experiment for each Phase 5 run.
- Store run configuration in config.json.
- Persist generated metrics in metrics.json.
- Copy generated plots into the experiment’s plots directory.
- Record the generated sequence and report file paths.
- Preserve metadata such as dataset type, window size, stride, and split ratio.

Additional metadata saved with the experiment's record:

- `dataset_name`: human-friendly dataset identifier
- `dataset_fingerprint`: SHA-256 hex digest of the raw dataset input used to generate sequences
- `vocabulary_size`: integer count of unique templates
- `sequence_count`: integer total of generated sequences
- `manifest_path`: relative path to `phase5_manifest.json`

This keeps Phase 5 consistent with the experiment-driven workflow used by Phase 4.

---

## 15. Unit Testing Strategy

The unit tests should focus on the core logic only and follow the same testing style used in the current repository.

### Proposed Test Modules

- test_parse_hdfs_template_extraction
- test_parse_bgl_template_extraction
- test_event_id_mapping_is_stable
- test_sequence_generation_from_block_ids
- test_sequence_generation_from_sliding_window
- test_validation_reports_errors_for_empty_sequences
- test_statistics_generation_for_sequences
- test_visualization_artifacts_are_created

- test_deterministic_vocabulary_across_runs  # verifies identical vocabulary ordering and IDs across repeated runs

### Testing Approach

- Use small synthetic log samples rather than the full dataset for fast unit tests.
- Cover both HDFS-like and BGL-like input patterns.
- Validate deterministic outputs for repeated runs.
- Assert that report files and plot files are created when expected.

---

## 16. Integration with Phase 6

Phase 5 should produce outputs that are immediately usable for Phase 6.

### Phase 6 Input Contract

Phase 6 should consume:
- event vocabulary
- training/test sequence files
- sequence length statistics
- validation reports

### Phase 6 Compatibility Requirements

- Event IDs must be stable and deterministic.
- Sequence files should be easy to load as DataFrames or arrays.
- Sequence records should preserve the original ordering of events.
- Vocabulary size and event mapping should be explicitly stored.

### Phase 6 Handoff

- The Phase 5 pipeline should expose a clean handoff artifact package such as:
- event_vocabulary.csv
- train_sequences.csv
- test_sequences.csv
- phase5_manifest.json

This manifest should contain the key metadata required by Phase 6 to load and use the generated data. Suggested manifest fields:

- `manifest_version`: "1.0" (manifest schema version)
- `generated_on`: ISO timestamp
- `dataset_name`: string identifier (e.g., "HDFS_v1")
- `dataset_fingerprint`: SHA-256 hex digest of the raw input used to generate this manifest
- `vocabulary_size`: integer
- `vocabulary_csv`: relative path to `event_vocabulary.csv`
- `vocabulary_json`: relative path to `event_vocabulary.json`
- `sequence_count`: integer (total sequences)
- `train_sequence_count`: integer
- `test_sequence_count`: integer
- `train_sequences_path`: relative path to `training_sequences.csv`
- `test_sequences_path`: relative path to `test_sequences.csv`
- `window_size`: configured window size used to generate sequences
- `stride`: configured stride used for sliding windows
- `min_sequence_length`: configured minimum
- `max_sequence_length`: configured maximum
- `config`: summary of key configuration values used for the run
- `git_branch`, `git_commit`, `git_tag`: VCS metadata if available
- `notes`: optional human-readable notes or warnings

Phase 6 should read `phase5_manifest.json` first to understand dataset layout and metadata before loading sequence files.

---

## 17. Implementation Sequence

The implementation should proceed in the following order:

1. Add Phase 5 configuration entries to the settings model.
2. Create new log-processing modules under src/log_processing.
3. Create a Phase 5 orchestration script at the repository root.
4. Implement template parsing and vocabulary generation.
5. Implement sequence construction for both HDFS and BGL strategies.
6. Implement validation and reporting.
7. Implement visualization generation.
8. Add unit tests for each processing stage.
9. Execute the pipeline and verify artifact generation.

---

## 18. Expected Deliverables

At the end of Phase 5, the project should provide:

- a reusable log preprocessing architecture,
- a deterministic event vocabulary,
- validated training and test sequences,
- statistical and validation reports,
- visualizations suitable for dissertation reporting,
- and a clear handoff package for Phase 6.

No LSTM or DeepLog model is implemented in this phase.
