# Phase 7 Design — Fusion Engine

Document Metadata:

- Version: 1.0
- Status: Frozen
- Last Updated: 2026-07-21
- Document Owner: Phase 7 Fusion Engine

This design document is frozen for Phase 7 implementation. Any future design changes that affect architecture must first be reflected in the architecture document.

## 1. Purpose

This document defines the detailed software design for the Phase 7 Fusion Engine.

Its purpose is to translate the frozen architecture in `docs/PHASE7_ARCHITECTURE.md` into an implementation-ready design specification without changing the architecture, module boundaries, data flow, strategies, or responsibilities.

Relationship to the frozen architecture:

- the architecture document remains the single source of truth
- this design document explains how the architecture will be realized in software
- all implementation must remain consistent with the architecture and this design
- if ambiguity exists, the architecture takes precedence and this design must be updated rather than bypassed

Implementation policy:

- implementation must follow this design
- implementation must not introduce conflicting module responsibilities
- implementation must preserve the configuration-driven and experiment-oriented behavior defined by the architecture

## 2. Assumptions

The design assumes the following conditions are true before execution begins:

- upstream KPI detector outputs are already generated and validated
- upstream Log detector outputs are already generated and validated
- detector outputs are immutable inputs to the Fusion Engine
- input artifacts follow the schemas defined by the architecture
- timestamps are convertible to UTC
- window size is globally configured for the run
- exactly two anomaly sources are supported in Phase 7
- required experiment artifacts are available before execution begins

These assumptions clarify the expected operating context and remain consistent with the frozen architecture.

## 3. Non-Goals

The Fusion Engine does not perform the following functions:

- train machine learning models
- retrain upstream detectors
- modify detector outputs
- tune detector thresholds
- perform KPI feature engineering
- perform log sequence learning
- execute evaluation metrics
- generate dashboards or visualization analytics beyond architecture-defined artifacts
- replace upstream anomaly detectors

This section clarifies scope boundaries only and does not alter module responsibilities.

## 4. Design Principles

The design of the Fusion Engine follows the principles below.

### SOLID Principles

Single Responsibility Principle:

- each module owns one clear processing concern
- orchestration, validation, mapping, alignment, aggregation, normalization, fusion, decisioning, and artifact generation are separated

Open/Closed Principle:

- strategy interfaces allow new behaviors to be added without modifying stable calling code
- future anomaly sources, aggregation strategies, normalization strategies, and fusion strategies extend existing abstractions

Liskov Substitution Principle:

- every concrete strategy must satisfy the contract of its interface without requiring special handling in calling modules

Interface Segregation Principle:

- each interface is narrow and purpose-specific
- aggregation, normalization, and fusion contracts are independent so callers depend only on the capability they require

Dependency Inversion Principle:

- orchestration depends on abstractions rather than concrete strategies
- configurable policies are selected by configuration and exposed through interface-conforming components

### Separation of Concerns

- source discovery is separated from source ingestion
- ingestion is separated from validation
- validation is separated from canonical mapping
- alignment is separated from aggregation
- aggregation is separated from missing-data handling
- normalization is separated from fusion score computation
- fusion score computation is separated from decision making
- artifact creation is separated from core business logic

### Dependency Inversion

- `fusion_orchestrator` depends on module contracts and configured strategy abstractions
- `score_aggregator` depends on `AggregationStrategy`
- `score_normalizer` depends on `NormalizationStrategy`
- `fusion_strategy` is consumed through the `FusionStrategy` contract
- concrete strategy selection is resolved from configuration rather than embedded in processing logic

### Strategy Pattern

The design uses the Strategy pattern in exactly the areas established by the architecture:

- aggregation
- normalization
- fusion

This keeps behavior replaceable while preserving the overall pipeline.

### Configuration-Driven Behavior

All experiment-specific behavior is controlled through configuration, especially:

- detector artifact paths and source definitions
- window size
- aggregation strategy
- normalization strategy
- fusion strategy
- source weights
- decision threshold
- validation strictness
- artifact output locations
- logging behavior

### Immutable Experiment Artifacts

- once a run writes an artifact, it is treated as immutable output for that experiment
- rewritten outputs are avoided because they weaken traceability
- manifests must reference the exact artifacts produced by the run

### Reproducibility

- configuration snapshots must be persisted
- manifest metadata must preserve upstream detector lineage
- derived statistics used for normalization or validation must be reproducible
- processing order must be deterministic where ordering affects outputs

### Traceability

- every fused prediction must be explainable back to its input window and source contributions
- `fusion_inputs.csv` preserves pre-normalization inputs
- manifest data preserves experiment lineage and output locations
- logging preserves run-time reasoning for warnings and failures

## 5. Package Structure

The recommended package hierarchy keeps the architecture intact while organizing modules by concern.

```text
phase7/
  __init__.py
  config/
    fusion_config.py
  sources/
    source_manager.py
    fusion_ingest.py
    fusion_validator.py
    fusion_mapper.py
  processing/
    timestamp_aligner.py
    aggregation_strategy.py
    score_aggregator.py
    missing_data_handler.py
    normalization_strategy.py
    score_normalizer.py
    fusion_strategy.py
    decision_engine.py
  output/
    artifact_writer.py
  orchestration/
    fusion_orchestrator.py
```

This hierarchy is a packaging recommendation only. It does not change the module names defined by the architecture.

### `phase7/config`

Purpose:

- centralize configuration loading, normalization, and validation

Responsibilities:

- define the configuration schema expected by the Fusion Engine
- provide typed access to configuration sections
- expose validated configuration to all modules

Contained modules:

- `fusion_config`

### `phase7/sources`

Purpose:

- manage source metadata and convert external detector artifacts into validated canonical inputs

Responsibilities:

- describe anomaly sources
- ingest source artifacts
- validate source schemas and values
- map source records into `FusionRecord`

Contained modules:

- `source_manager`
- `fusion_ingest`
- `fusion_validator`
- `fusion_mapper`

### `phase7/processing`

Purpose:

- perform pipeline transformations after ingestion and mapping

Responsibilities:

- align records into windows
- aggregate in-window source values
- resolve missing data
- normalize scores
- compute fused scores
- generate final decisions

Contained modules:

- `timestamp_aligner`
- `aggregation_strategy`
- `score_aggregator`
- `missing_data_handler`
- `normalization_strategy`
- `score_normalizer`
- `fusion_strategy`
- `decision_engine`

### `phase7/output`

Purpose:

- manage all durable experiment outputs

Responsibilities:

- write reports, plots, summaries, and manifest files
- validate output structures before persisting them
- ensure artifact lineage is preserved

Contained modules:

- `artifact_writer`

### `phase7/orchestration`

Purpose:

- coordinate the end-to-end execution of the pipeline

Responsibilities:

- load configuration
- initialize modules
- invoke pipeline stages
- coordinate output writing

Contained modules:

- `fusion_orchestrator`

## 6. Module Design

The sections below describe the detailed design of each architectural module.

### 4.1 `fusion_config`

Purpose:

- provide the authoritative configuration object for the entire Fusion Engine

Responsibilities:

- load configuration from file and runtime overrides
- validate required sections and default values
- expose normalized configuration values to downstream modules
- persist a configuration snapshot for manifest and traceability use

Inputs:

- configuration file path
- optional environment overrides
- optional runtime override map

Outputs:

- validated configuration object
- configuration snapshot for artifact and manifest use

Dependencies:

- none at the business-logic level
- may depend on generic parsing and validation utilities

Configuration owned:

- fusion
- aggregation
- normalization
- logging
- artifacts
- validation

Internal workflow:

1. load raw configuration data
2. merge override sources according to precedence rules
3. apply defaults defined by the architecture
4. validate required fields and allowed values
5. normalize types and units
6. return an immutable or read-only configuration view to callers

Public interfaces:

- load configuration
- validate configuration
- export configuration snapshot
- resolve typed sub-sections for modules

Error handling:

- invalid or missing required fields are non-recoverable
- unknown strategy values are non-recoverable
- ambiguous unit values are non-recoverable unless coercion rules are explicit

Logging responsibilities:

- log configuration source locations
- log effective strategy selections
- log default application events at debug level
- never log secrets if future configuration adds them

Validation responsibilities:

- ensure `fusion.strategy` is valid
- ensure `aggregation.strategy` is valid
- ensure normalization strategy is valid
- ensure `kpi_weight` and `log_weight` are numeric and non-negative
- ensure threshold is numeric and within allowed bounds
- ensure `window_size` is parseable and positive

Future extensibility:

- new strategy names can be added through validation table updates
- new configuration sections can be added without breaking existing consumers if defaults are supplied

Class Design:

- Primary class name: `FusionConfig`
- Purpose: represent the validated, read-only configuration surface for the Fusion Engine
- Constructor dependencies: raw configuration source, optional override inputs, optional validation helpers
- Major public methods: `load`, `validate`, `export_snapshot`, `get_section`
- Important private or helper responsibilities: merge precedence resolution, default application, type normalization, strategy-name validation

### 4.2 `source_manager`

Purpose:

- manage source-oriented metadata and authoritative source descriptors

Responsibilities:

- define supported `SourceType` values
- maintain detector source descriptors for KPI and LOG sources
- expose source-level metadata such as required artifacts, expected score semantics, and supported join keys
- provide a stable source contract to ingest and validation modules

Inputs:

- configuration
- source definitions

Outputs:

- source descriptors
- source lookup results by source type

Dependencies:

- `fusion_config`

Configuration owned:

- source artifact locations or references
- source-specific metadata and expected field names

Internal workflow:

1. build source descriptors from configuration
2. validate that required source definitions exist
3. expose descriptor retrieval functions to downstream modules

Public interfaces:

- get descriptor for a source type
- list supported sources
- return expected artifact references
- return expected join-key preferences and schema expectations

Error handling:

- missing required source descriptor is non-recoverable
- incomplete optional source metadata may downgrade to warning if defaults exist

Logging responsibilities:

- log active sources and resolved artifact references

Validation responsibilities:

- ensure required source types for Phase 7 are present
- ensure source descriptors are internally consistent

Future extensibility:

- additional anomaly sources can be added by extending source descriptors without changing orchestration flow

Class Design:

- Primary class name: `SourceManager`
- Purpose: manage authoritative source descriptors for KPI and LOG anomaly sources
- Constructor dependencies: validated configuration, source-definition metadata
- Major public methods: `get_source`, `list_sources`, `get_artifact_refs`, `get_schema_expectations`
- Important private or helper responsibilities: descriptor construction, source-type consistency checks, join-key preference resolution

### 4.3 `fusion_ingest`

Purpose:

- read raw detector artifacts and source metadata into in-memory representations for validation

Responsibilities:

- read KPI Source prediction artifacts
- read Log Detector Manifest and resolve Log Source prediction artifacts
- load raw tabular source data and associated metadata
- preserve source lineage information for later manifest writing

Inputs:

- source descriptors from `source_manager`
- configuration

Outputs:

- raw KPI Source tables
- raw Log Source tables
- source metadata bundles

Dependencies:

- `fusion_config`
- `source_manager`

Configuration owned:

- input artifact locations
- path resolution policy

Internal workflow:

1. resolve KPI Source artifact path
2. resolve Log Detector Manifest path
3. load the published detector manifest
4. resolve the Log Source predictions artifact from the manifest
5. load raw source tables
6. attach source metadata and lineage references

Public interfaces:

- ingest all configured sources
- ingest a specific source by descriptor

Error handling:

- missing required source artifact is non-recoverable
- unreadable optional provenance artifact may produce a warning if core prediction data remains available

Logging responsibilities:

- log resolved file locations
- log row counts and basic source coverage statistics

Validation responsibilities:

- only lightweight existence and readability checks
- semantic validation is delegated to `fusion_validator`

Future extensibility:

- support additional source artifact types by extending source descriptor resolution logic

Class Design:

- Primary class name: `FusionIngest`
- Purpose: load external detector artifacts and associated source metadata for downstream validation
- Constructor dependencies: validated configuration, `SourceManager`
- Major public methods: `ingest_all`, `ingest_source`
- Important private or helper responsibilities: manifest loading, artifact path resolution, raw table loading, lineage attachment

### 4.4 `fusion_validator`

Purpose:

- enforce schema, timestamp, score, field, and source compatibility rules before canonical mapping begins

Responsibilities:

- validate raw source schemas
- validate required fields and field types
- validate timestamps and score fields
- validate manifest-to-artifact consistency for the Log Source
- produce a structured validation report with errors and warnings

Inputs:

- raw source tables
- source metadata
- configuration

Outputs:

- validation report
- schema-normalized source tables suitable for mapping

Dependencies:

- `fusion_config`
- `source_manager`

Configuration owned:

- validation strictness
- required field mappings
- score-range expectations

Internal workflow:

1. validate artifact presence against source descriptors
2. validate required columns
3. normalize column names where the source descriptor allows aliases
4. validate timestamp parseability
5. validate score field presence and numeric type
6. validate label fields and supported values
7. validate source metadata linkage
8. emit structured report and normalized tables

Public interfaces:

- validate all sources
- validate one source table against one descriptor
- produce validation summary

Error handling:

- missing required columns are non-recoverable
- invalid timestamps are non-recoverable unless the validation policy explicitly allows dropping rows
- non-critical provenance mismatches may produce warnings

Logging responsibilities:

- log validation summary by source
- log warning counts and critical error details

Validation responsibilities:

- own all pre-mapping semantic validation of source artifacts

Future extensibility:

- new per-source validation rules can be added without changing downstream modules

Class Design:

- Primary class name: `FusionValidator`
- Purpose: perform pre-mapping semantic validation and schema normalization for source artifacts
- Constructor dependencies: validated configuration, `SourceManager`
- Major public methods: `validate_all`, `validate_source`, `build_report`
- Important private or helper responsibilities: field alias normalization, timestamp checks, score checks, label checks, manifest-to-artifact consistency checks

### 4.5 `fusion_mapper`

Purpose:

- transform validated source-specific rows into source-level `FusionRecord` instances

Responsibilities:

- map KPI Source rows into `FusionRecord`
- map Log Source rows into `FusionRecord`
- populate canonical fields and source metadata references
- preserve source-specific lineage at row level where available

Inputs:

- validated source tables
- source descriptors

Outputs:

- source-level `FusionRecord` collections

Dependencies:

- `source_manager`

Configuration owned:

- field mapping rules
- alias handling rules

Internal workflow:

1. iterate over each validated source row
2. identify its `SourceType`
3. map required canonical fields
4. populate source-specific score field into the canonical source slot
5. attach source metadata and row identifiers
6. emit source-level `FusionRecord`

Public interfaces:

- map KPI Source rows
- map Log Source rows
- map all validated sources

Error handling:

- missing fields after validation indicates an internal contract breach and is non-recoverable

Logging responsibilities:

- log row-to-record mapping counts by source

Validation responsibilities:

- enforce domain-level field completeness needed for `FusionRecord` creation

Future extensibility:

- additional sources can be mapped by adding source-specific mapping adapters while preserving `FusionRecord`

Class Design:

- Primary class name: `FusionMapper`
- Purpose: create source-level `FusionRecord` instances from validated detector rows
- Constructor dependencies: `SourceManager`, mapping configuration or field-alias metadata
- Major public methods: `map_all`, `map_kpi_source`, `map_log_source`
- Important private or helper responsibilities: source-type resolution, canonical field population, source metadata attachment, source record id extraction

### 4.6 `timestamp_aligner`

Purpose:

- assign source-level `FusionRecord` instances to a common time window and create aligned window-level records

Responsibilities:

- parse and normalize timestamps to UTC
- derive `window_ts` and `window_end_ts`
- group source-level records into configured windows
- prepare the aligned record collections consumed by aggregation

Inputs:

- source-level `FusionRecord` instances
- `window_size`
- optional entity-key preferences

Outputs:

- aligned window-level `FusionRecord` collections

Dependencies:

- `fusion_config`

Configuration owned:

- `window_size`
- timestamp parsing policy
- timezone policy

Internal workflow:

1. normalize timestamps to UTC
2. compute window boundaries
3. partition records into windows
4. group by window and optional entity scope
5. construct aligned groupings for downstream aggregation

Public interfaces:

- align records into windows
- compute window key for a timestamp

Error handling:

- unparseable timestamps after validation are treated as internal contract failures
- missing timestamp for a mapped record is non-recoverable

Logging responsibilities:

- log number of input records and resulting aligned windows
- log dropped or rejected timestamp records if policy allows row-level filtering

Validation responsibilities:

- verify consistent timestamp normalization behavior across all sources

Future extensibility:

- alternate alignment scopes can be supported without changing downstream interfaces

Class Design:

- Primary class name: `TimestampAligner`
- Purpose: convert mapped records into aligned window-level records using the configured window policy
- Constructor dependencies: validated configuration, timestamp parsing policy, timezone policy
- Major public methods: `align`, `compute_window_key`
- Important private or helper responsibilities: UTC normalization, window boundary derivation, entity-scoped grouping, deterministic ordering

### 4.7 `aggregation_strategy`

Purpose:

- define the abstraction for configurable in-window source score aggregation

Responsibilities:

- define the aggregation contract
- encapsulate strategy-specific aggregation behavior
- hide concrete aggregation logic from `score_aggregator`

Inputs:

- source score collections within one window
- optional aggregation context

Outputs:

- one aggregated source score for the window

Dependencies:

- none on business modules

Configuration owned:

- selected strategy name only through `fusion_config`

Internal workflow:

- strategy-specific

Public interfaces:

- aggregate one set of source scores
- return strategy identity for metadata

Error handling:

- empty input handling must follow a clearly documented contract
- invalid numeric inputs must fail explicitly

Logging responsibilities:

- no direct logging requirement beyond exceptional conditions

Validation responsibilities:

- ensure inputs are numeric and belong to one source within one window

Future extensibility:

- supports `MaxAggregation`, `MeanAggregation`, and `MedianAggregation` without changing caller behavior

Class Design:

- Primary class name: `AggregationStrategy` with `MaxAggregation` as the Phase 7 concrete implementation
- Purpose: define and encapsulate in-window source score aggregation behavior
- Constructor dependencies: optional strategy-specific policy inputs from configuration
- Major public methods: `aggregate`, `get_name`
- Important private or helper responsibilities: numeric input checks, empty-input handling, strategy metadata preparation

### 4.8 `score_aggregator`

Purpose:

- apply the configured aggregation strategy to aligned window-level records

Responsibilities:

- separate KPI Source window scores from Log Source window scores
- invoke `AggregationStrategy` for each source within each window
- preserve label and confidence aggregation rules defined by the architecture
- emit aggregated window-level `FusionRecord` instances

Inputs:

- aligned window-level `FusionRecord` collections
- configured aggregation strategy

Outputs:

- aggregated window-level `FusionRecord` instances

Dependencies:

- `aggregation_strategy`
- `fusion_config`

Configuration owned:

- `aggregation.strategy`

Internal workflow:

1. iterate over aligned windows
2. separate KPI and LOG source values
3. aggregate source scores using the configured strategy
4. apply architecture-defined label rollup rules
5. apply confidence rollup rules for Log Source if available
6. emit one aggregated `FusionRecord` per window

Public interfaces:

- aggregate aligned records

Error handling:

- strategy failures are non-recoverable for the current window unless row-level isolation is explicitly configured

Logging responsibilities:

- log aggregation strategy in use
- log aggregated window counts and source coverage

Validation responsibilities:

- ensure aggregation only occurs on aligned windows

Future extensibility:

- new aggregation strategies plug in without changing window orchestration

Class Design:

- Primary class name: `ScoreAggregator`
- Purpose: apply the configured aggregation strategy to aligned window-level records
- Constructor dependencies: validated configuration, `AggregationStrategy`
- Major public methods: `aggregate_windows`
- Important private or helper responsibilities: per-source score extraction, label rollup, confidence rollup, aggregated record assembly

### 4.9 `missing_data_handler`

Purpose:

- apply the architecture-defined availability-aware handling policy to aggregated window-level records

Responsibilities:

- set `kpi_available` and `log_available`
- set `missing_reason`
- enforce the policy for one-source-present and both-missing windows
- prepare records for downstream normalization and fusion

Inputs:

- aggregated window-level `FusionRecord` instances
- missing-data policy from configuration

Outputs:

- availability-complete `FusionRecord` instances

Dependencies:

- `fusion_config`

Configuration owned:

- missing-data strictness and drop policy

Internal workflow:

1. inspect source presence by window
2. set availability flags
3. annotate missing reason when applicable
4. drop or retain windows according to the architecture
5. pass surviving records downstream

Public interfaces:

- resolve missing data for aggregated records

Error handling:

- missing-source windows are recoverable and expected
- both-missing windows are not failures; they are diagnostic outcomes

Logging responsibilities:

- log counts of full, partial, and empty windows

Validation responsibilities:

- ensure availability flags are consistent with score presence

Future extensibility:

- alternate availability policies can be introduced without altering normalization or fusion interfaces

Class Design:

- Primary class name: `MissingDataHandler`
- Purpose: enforce availability-aware missing-source handling on aggregated window-level records
- Constructor dependencies: validated configuration, missing-data policy settings
- Major public methods: `resolve`
- Important private or helper responsibilities: availability flag derivation, missing-reason classification, empty-window filtering

### 4.10 `normalization_strategy`

Purpose:

- define the abstraction for configurable score normalization

Responsibilities:

- define the normalization contract
- compute normalized values from raw source score inputs and normalization context

Inputs:

- source score collections
- optional calibration statistics or normalization context

Outputs:

- normalized source score collections
- optional normalization metadata

Dependencies:

- none on business modules

Configuration owned:

- selected normalization strategy through `fusion_config`

Internal workflow:

- strategy-specific

Public interfaces:

- normalize a collection of scores
- return normalization metadata needed for reproducibility

Error handling:

- invalid numeric values or impossible calibration state are non-recoverable unless identity fallback is explicitly configured

Logging responsibilities:

- no routine logging beyond diagnostic metadata exposure

Validation responsibilities:

- ensure the strategy produces values consistent with its documented contract

Future extensibility:

- supports `MinMaxNormalization`, `ZScoreNormalization`, and `IdentityNormalization` without caller changes

Class Design:

- Primary class name: `NormalizationStrategy` with `MinMaxNormalization` as the Phase 7 concrete implementation
- Purpose: define and encapsulate source-score normalization behavior
- Constructor dependencies: optional strategy-specific calibration or policy inputs from configuration
- Major public methods: `normalize`, `get_name`, `get_metadata`
- Important private or helper responsibilities: statistic derivation, range handling, metadata preparation, invalid-state detection

### 4.11 `score_normalizer`

Purpose:

- apply the configured normalization strategy to `kpi_score` and `log_score`

Responsibilities:

- prepare source score collections for normalization
- invoke `NormalizationStrategy`
- populate normalized fields on `FusionRecord`
- emit normalization diagnostics for artifact and manifest use

Inputs:

- availability-complete `FusionRecord` instances
- configured normalization strategy

Outputs:

- normalized `FusionRecord` instances
- normalization diagnostics

Dependencies:

- `normalization_strategy`
- `fusion_config`

Configuration owned:

- normalization strategy selection
- source-specific normalization options if configured

Internal workflow:

1. collect KPI Source scores from eligible records
2. collect Log Source scores from eligible records
3. compute normalization statistics
4. normalize each source independently
5. populate `kpi_score_normalized` and `log_score_normalized`
6. emit normalization metadata for the manifest

Public interfaces:

- normalize records
- export normalization diagnostics

Error handling:

- invalid normalization state is non-recoverable because fusion depends on normalized scores

Logging responsibilities:

- log selected normalization strategy and derived statistics summary

Validation responsibilities:

- ensure normalized values satisfy expected range guarantees when applicable

Future extensibility:

- strategy replacement does not require changes to fusion or decision modules

Class Design:

- Primary class name: `ScoreNormalizer`
- Purpose: apply the configured normalization strategy to KPI and LOG source scores and emit diagnostics
- Constructor dependencies: validated configuration, `NormalizationStrategy`
- Major public methods: `normalize_records`, `export_diagnostics`
- Important private or helper responsibilities: per-source score collection, normalization-context preparation, normalized-field assignment, diagnostic summary assembly

### 4.12 `fusion_strategy`

Purpose:

- define and apply configurable fused score computation

Responsibilities:

- encapsulate weighted combination behavior behind the `FusionStrategy` abstraction
- compute `fused_score`
- compute `kpi_contribution` and `log_contribution`
- preserve strategy metadata for downstream traceability

Inputs:

- normalized `FusionRecord` instances
- configured `kpi_weight`
- configured `log_weight`

Outputs:

- fused `FusionRecord` instances with contributions and strategy metadata

Dependencies:

- `fusion_config`

Configuration owned:

- fusion strategy name
- source weights

Internal workflow:

1. read normalized source scores and availability flags
2. derive effective weights according to availability-aware rules
3. compute source contributions
4. compute `fused_score`
5. attach strategy metadata to the record

Public interfaces:

- compute fused score for one record or batch of records
- return strategy identity and metadata

Error handling:

- invalid weights are non-recoverable
- missing normalized score for an available source is a contract breach

Logging responsibilities:

- log active fusion strategy and configured weights

Validation responsibilities:

- ensure effective weights are valid before score computation

Future extensibility:

- future fusion strategies plug into the same contract

Class Design:

- Primary class name: `FusionStrategy` with `WeightedAverageStrategy` as the Phase 7 concrete implementation
- Purpose: define and apply fused score computation over normalized source scores
- Constructor dependencies: validated configuration, configured source weights
- Major public methods: `compute`, `get_name`, `get_metadata`
- Important private or helper responsibilities: effective-weight derivation, contribution calculation, fused-score calculation, strategy-metadata preparation

### 4.13 `decision_engine`

Purpose:

- convert `fused_score` into a final anomaly decision using configuration-driven thresholding and decision metadata

Responsibilities:

- apply threshold
- set `final_label`
- set `decision_reason`
- attach `decision_metadata`

Inputs:

- fused `FusionRecord` instances
- configured threshold

Outputs:

- decision-complete `FusionRecord` instances

Dependencies:

- `fusion_config`

Configuration owned:

- decision threshold
- decision metadata policy

Internal workflow:

1. validate that each input record has `fused_score`
2. apply configured threshold
3. populate label
4. determine decision reason
5. attach threshold and any auxiliary decision metadata

Public interfaces:

- decide one record
- decide a collection of records

Error handling:

- missing fused score is non-recoverable
- invalid threshold is non-recoverable and should have been blocked earlier by configuration validation

Logging responsibilities:

- log threshold and label distribution summary

Validation responsibilities:

- ensure decision outputs are consistent with the threshold contract

Future extensibility:

- future decision policies can expand within the same module without changing upstream fusion behavior

Class Design:

- Primary class name: `DecisionEngine`
- Purpose: convert fused scores into final labels and decision metadata using configuration-driven thresholding
- Constructor dependencies: validated configuration, threshold policy settings
- Major public methods: `decide_record`, `decide_batch`
- Important private or helper responsibilities: threshold application, decision-reason derivation, decision-metadata assembly

### 4.14 `artifact_writer`

Purpose:

- produce all durable outputs defined by the architecture

Responsibilities:

- write `fusion_inputs.csv`
- write `aligned_windows.csv`
- write `normalized_scores.csv`
- write `fused_predictions.csv`
- write summary JSON artifacts
- write plots if enabled by the implementation plan
- write `phase7_manifest.json`

Inputs:

- pre-normalization records
- normalized records
- decision-complete records
- configuration snapshot
- validation summaries
- normalization diagnostics
- experiment lineage metadata

Outputs:

- all Phase 7 artifacts
- artifact reference metadata

Dependencies:

- `fusion_config`

Configuration owned:

- artifact root paths
- retention and naming policy
- output enablement flags if later required

Internal workflow:

1. create experiment output structure
2. serialize records into report artifacts in the correct order
3. write summary artifacts and coverage metrics
4. write manifest last, after artifact paths are known
5. return artifact reference map to orchestrator

Public interfaces:

- write all artifacts for an experiment
- write manifest
- return artifact path summary

Error handling:

- failure to write required artifacts is non-recoverable
- failure to write optional visual artifacts may be downgraded if policy allows

Logging responsibilities:

- log artifact creation order and final paths
- log row counts written per artifact

Validation responsibilities:

- validate required output fields before persistence
- validate manifest completeness before final write

Future extensibility:

- new artifact types can be added without changing the core processing modules

Class Design:

- Primary class name: `ArtifactWriter`
- Purpose: persist all required experiment artifacts and the final Phase 7 manifest
- Constructor dependencies: validated configuration, artifact path settings, optional serialization helpers
- Major public methods: `write_all`, `write_manifest`, `get_artifact_summary`
- Important private or helper responsibilities: experiment-path creation, tabular serialization, summary serialization, manifest assembly, output validation before persistence

### 4.15 `fusion_orchestrator`

Purpose:

- coordinate the full Phase 7 pipeline while remaining free of business logic

Responsibilities:

- load configuration
- initialize modules
- invoke pipeline stages in architectural order
- hand off data between stages
- invoke artifact writing and finalize run status

Inputs:

- configuration path
- runtime override inputs

Outputs:

- completed experiment execution
- artifact reference summary

Dependencies:

- all architectural modules by their contracts

Configuration owned:

- none beyond receiving the validated configuration object

Internal workflow:

1. load and validate configuration through `fusion_config`
2. initialize source descriptors through `source_manager`
3. ingest source artifacts through `fusion_ingest`
4. validate ingested data through `fusion_validator`
5. map validated rows through `fusion_mapper`
6. align records through `timestamp_aligner`
7. aggregate aligned records through `score_aggregator`
8. resolve missing data through `missing_data_handler`
9. normalize scores through `score_normalizer`
10. compute fused scores through `fusion_strategy`
11. generate final decisions through `decision_engine`
12. write artifacts through `artifact_writer`
13. finalize experiment status and emit run summary

Public interfaces:

- run full experiment
- return run status and artifact references

Error handling:

- orchestrator does not suppress non-recoverable business failures
- orchestrator may translate low-level exceptions into run-level failures with contextual metadata

Logging responsibilities:

- log stage boundaries and duration summaries
- log final run status

Validation responsibilities:

- ensure stage preconditions are satisfied before invocation

Future extensibility:

- new strategy implementations and source definitions do not require orchestrator redesign if contracts remain stable

Class Design:

- Primary class name: `FusionOrchestrator`
- Purpose: coordinate the end-to-end pipeline without owning business logic
- Constructor dependencies: configuration path or configuration object, module collaborators resolved from configuration
- Major public methods: `run`, `get_run_summary`
- Important private or helper responsibilities: stage sequencing, precondition checks, run-context initialization, failure-context propagation

## 7. FusionRecord Design

### Purpose

`FusionRecord` is the canonical domain object used throughout the Fusion Engine after ingestion and mapping. It provides a stable, source-oriented representation of the data flowing through the pipeline.

### Lifecycle

`FusionRecord` exists in progressively enriched states:

1. source-level mapped state
2. aligned state
3. aggregated state
4. missing-data-resolved state
5. normalized state
6. fused state
7. decision-complete state
8. artifact-serialized state

### Ownership

- created by `fusion_mapper`
- aligned by `timestamp_aligner`
- enriched by `score_aggregator`
- annotated by `missing_data_handler`
- normalized by `score_normalizer`
- fused by `fusion_strategy`
- finalized by `decision_engine`
- serialized by `artifact_writer`

No stage may mutate fields owned by a downstream stage before that stage executes.

Field ownership matrix:

| Field | Created By | Read By | Mutable Until | Immutable After |
|---|---|---|---|---|
| `source_type` | `fusion_mapper` | all downstream modules | end of mapping | `fusion_mapper` |
| `source_record_id` | `fusion_mapper` | `timestamp_aligner`, `artifact_writer`, diagnostics consumers | end of mapping | `fusion_mapper` |
| `window_ts` | `timestamp_aligner` | all downstream processing and output modules | end of alignment | `timestamp_aligner` |
| `window_end_ts` | `timestamp_aligner` | all downstream processing and output modules | end of alignment | `timestamp_aligner` |
| `kpi_score` | `fusion_mapper`, then summarized by `score_aggregator` | `missing_data_handler`, `score_normalizer`, `artifact_writer` | end of aggregation | `score_aggregator` |
| `log_score` | `fusion_mapper`, then summarized by `score_aggregator` | `missing_data_handler`, `score_normalizer`, `artifact_writer` | end of aggregation | `score_aggregator` |
| `kpi_available` | `missing_data_handler` | `score_normalizer`, `fusion_strategy`, `decision_engine`, `artifact_writer` | end of missing-data handling | `missing_data_handler` |
| `log_available` | `missing_data_handler` | `score_normalizer`, `fusion_strategy`, `decision_engine`, `artifact_writer` | end of missing-data handling | `missing_data_handler` |
| `kpi_score_normalized` | `score_normalizer` | `fusion_strategy`, `decision_engine`, `artifact_writer` | end of normalization | `score_normalizer` |
| `log_score_normalized` | `score_normalizer` | `fusion_strategy`, `decision_engine`, `artifact_writer` | end of normalization | `score_normalizer` |
| `kpi_weight` | `fusion_strategy` | `decision_engine`, `artifact_writer`, explainability consumers | end of fusion | `fusion_strategy` |
| `log_weight` | `fusion_strategy` | `decision_engine`, `artifact_writer`, explainability consumers | end of fusion | `fusion_strategy` |
| `kpi_contribution` | `fusion_strategy` | `decision_engine`, `artifact_writer`, explainability consumers | end of fusion | `fusion_strategy` |
| `log_contribution` | `fusion_strategy` | `decision_engine`, `artifact_writer`, explainability consumers | end of fusion | `fusion_strategy` |
| `fused_score` | `fusion_strategy` | `decision_engine`, `artifact_writer` | end of fusion | `fusion_strategy` |
| `final_label` | `decision_engine` | `artifact_writer`, downstream evaluation consumers | end of decision | `decision_engine` |
| `decision_reason` | `decision_engine` | `artifact_writer`, downstream evaluation consumers | end of decision | `decision_engine` |
| `decision_metadata` | `decision_engine` | `artifact_writer`, diagnostics consumers | end of decision | `decision_engine` |
| `source_metadata` | `fusion_mapper` | all downstream modules, especially `artifact_writer` and diagnostics consumers | end of mapping unless enriched with non-conflicting lineage details before artifact generation | `fusion_mapper` and approved upstream-enrichment stages |

### Creation

`FusionRecord` is first created from validated source rows. At creation time it must contain enough information to identify source provenance, window assignment inputs, and the source score relevant to that row.

### Mutation Policy

The design uses controlled enrichment rather than unrestricted mutation.

Rules:

- mapped source fields are write-once after `fusion_mapper`
- alignment fields are populated only by `timestamp_aligner`
- aggregated source fields are populated only by `score_aggregator`
- availability fields are populated only by `missing_data_handler`
- normalized fields are populated only by `score_normalizer`
- fused fields are populated only by `fusion_strategy`
- decision fields are populated only by `decision_engine`

If a field must be revised due to an earlier-stage correction, the stage must fail and restart rather than silently overwrite downstream-enriched state.

### Validation Rules

Required domain invariants:

- every record must have a valid `source_type`
- source-level records must have a source score in the source-appropriate slot
- aligned and later records must have `window_ts` and `window_end_ts`
- normalized records must not have normalized scores without corresponding raw scores unless the source is unavailable
- fused records must include effective weights or sufficient metadata to derive them
- decision-complete records must include `final_label` and `decision_reason`

### Required Fields

- `source_type`
- `source_record_id`
- source timestamp field or equivalent input to alignment
- source score field relevant to the record
- `source_metadata`

Required after alignment:

- `window_ts`
- `window_end_ts`

Required after missing-data handling:

- `kpi_available`
- `log_available`

Required after fusion:

- `fused_score`
- `kpi_contribution`
- `log_contribution`

Required after decision:

- `final_label`
- `decision_reason`
- `decision_metadata`

### Optional Fields

- `entity_id`
- `kpi_id`
- `session_id`
- `block_id`
- `prediction_confidence`-derived metadata
- source-specific provenance extensions

### Metadata

Metadata should preserve:

- upstream detector lineage
- source row identity
- window derivation context
- strategy selections
- decision threshold used

### State Transitions Through the Pipeline

Ingestion:

- raw source rows exist outside `FusionRecord`
- no `FusionRecord` yet

Mapping:

- `fusion_mapper` creates source-level `FusionRecord`
- source type, record identity, source score, raw label reference, and source metadata are attached

Alignment:

- `timestamp_aligner` assigns `window_ts` and `window_end_ts`
- record becomes eligible for in-window grouping

Aggregation:

- `score_aggregator` collapses multiple records per source per window
- aggregated score fields become authoritative for downstream stages

Missing-data handling:

- `missing_data_handler` sets availability flags and missing reasons
- empty windows may be excluded from scoring outputs while remaining visible in diagnostics

Normalization:

- `score_normalizer` sets `kpi_score_normalized` and `log_score_normalized`
- normalization metadata is retained for reproducibility

Fusion:

- `fusion_strategy` computes `fused_score`, `kpi_weight`, `log_weight`, `kpi_contribution`, and `log_contribution`

Decision:

- `decision_engine` computes `final_label`, `decision_reason`, and `decision_metadata`

Artifact generation:

- `artifact_writer` serializes different views of the record depending on artifact purpose
- serialization must not alter domain state

## 8. Interface Design

This section defines the design contracts for the strategy abstractions. No implementation code is prescribed here.

### `AggregationStrategy`

Purpose:

- aggregate multiple source scores within one window into one representative source score

Required methods:

- method to return strategy identity
- method to aggregate a non-empty collection of numeric source scores
- method to expose minimal metadata needed for traceability if the implementation chooses to provide it

Expected inputs:

- source score collection for one source within one window
- optional window context or source metadata

Expected outputs:

- one aggregated numeric score
- optional aggregation metadata

Error behavior:

- empty score collection must raise a clear strategy contract error unless caller precludes empty input
- non-numeric score inputs must raise a validation or domain error

Extension guidelines:

- new strategies must preserve the one-input-collection to one-score contract
- new strategies must not require caller-specific branching in `score_aggregator`

### `NormalizationStrategy`

Purpose:

- convert raw source scores into normalized source scores according to the selected normalization policy

Required methods:

- method to return strategy identity
- method to normalize a collection of source scores
- method to expose normalization metadata required for reproducibility

Expected inputs:

- collection of raw numeric scores for one source
- optional precomputed statistics or normalization context

Expected outputs:

- normalized scores aligned to the input order
- metadata including any derived statistics needed for reporting and manifest writing

Error behavior:

- invalid numeric inputs must raise a clear normalization error
- impossible normalization state must raise a non-recoverable error

Extension guidelines:

- new normalization strategies must preserve input ordering
- strategy output metadata must remain serializable for artifact and manifest use

### `FusionStrategy`

Purpose:

- compute fused anomaly scores from normalized source scores and configured weights

Required methods:

- method to return strategy identity
- method to compute fused result for one `FusionRecord` or a compatible batch abstraction
- method to expose strategy metadata needed for downstream traceability

Expected inputs:

- normalized source scores
- source availability flags
- configured source weights
- optional source confidence metadata if a future strategy needs it

Expected outputs:

- `fused_score`
- effective source weights
- `kpi_contribution`
- `log_contribution`
- strategy metadata

Error behavior:

- invalid weights or missing normalized inputs for available sources must raise clear fusion errors

Extension guidelines:

- new strategies must preserve the contract that downstream decisioning receives one fused score per `FusionRecord`
- strategies must not take over decisioning responsibilities

## 9. Configuration Design

The configuration hierarchy must preserve the frozen architectural fields while providing operational sections needed for implementation.

Recommended hierarchy:

```yaml
fusion:
  strategy: weighted_average
  kpi_weight: 0.50
  log_weight: 0.50
  threshold: 0.60
  window_size: 5m
  normalization_strategy: min_max

aggregation:
  strategy: max

logging:
  level: INFO
  enable_debug_artifacts: false

artifacts:
  root_dir: artifacts/phase7
  retain_intermediate: true

validation:
  strict: true
  allow_row_drops: false

extensions: {}
```

### `fusion`

Fields:

- `strategy`
  - default: `weighted_average`
  - allowed values: architecture-supported fusion strategies
  - validation: must be one of the supported strategy identifiers

- `kpi_weight`
  - default: `0.50`
  - validation: numeric and non-negative

- `log_weight`
  - default: `0.50`
  - validation: numeric and non-negative

- `threshold`
  - default: `0.60`
  - validation: numeric, bounded according to score semantics, and not null

- `window_size`
  - default: `5m`
  - validation: parseable duration greater than zero

### `aggregation`

Fields:

- `strategy`
  - default: `max`
  - allowed values: `max`, plus architecture extension points
  - validation: must resolve to a supported aggregation strategy

### Normalization Configuration

Normalization remains governed by the frozen architectural field below the `fusion` section:

- `fusion.normalization_strategy`
  - default: `min_max`
  - allowed values: architecture-supported normalization strategies
  - validation: must resolve to a supported normalization strategy

### `window`

The architecture places window behavior under `fusion.window_size`. The design therefore does not create a separate authoritative module-level window strategy section. Window semantics are documented here for implementation clarity only.

Window behavior derived from `fusion.window_size`:

- tumbling window semantics
- UTC normalization
- deterministic boundary assignment

### `logging`

Fields:

- `level`
  - default: `INFO`
  - validation: must be a supported logging level

- `enable_debug_artifacts`
  - default: `false`
  - validation: boolean

Purpose:

- control verbosity and optional diagnostic outputs without changing business logic

### `artifacts`

Fields:

- `root_dir`
  - default: architecture-aligned Phase 7 artifact root
  - validation: writable location or creatable path

- `retain_intermediate`
  - default: `true`
  - validation: boolean

Purpose:

- control artifact output location and retention behavior

### `validation`

Fields:

- `strict`
  - default: `true`
  - validation: boolean

- `allow_row_drops`
  - default: `false`
  - validation: boolean

Purpose:

- control how validation errors are treated when a recoverable row-level policy is permitted

### Future Extension Points

The `extensions` section is reserved for forward-compatible configuration additions that do not alter current architecture semantics.

Rules:

- future additions must not redefine the meaning of frozen architectural fields
- unknown extension keys should be ignored or warned on according to validation policy

## 10. Execution Flow

Runtime execution must follow the architecture exactly.

### Startup

1. `fusion_orchestrator` receives a configuration path and optional overrides.
2. `fusion_config` loads, merges, defaults, and validates configuration.
3. `source_manager` resolves active source descriptors.
4. logging context is initialized for the experiment.

### Main Processing Flow

1. `fusion_ingest` reads KPI Source artifacts.
2. `fusion_ingest` reads the Log Detector Manifest and resolves Log Source prediction artifacts.
3. `fusion_validator` validates raw source tables and metadata.
4. `fusion_mapper` creates source-level `FusionRecord` instances.
5. `timestamp_aligner` assigns window boundaries and aligned groupings.
6. `score_aggregator` summarizes source scores within each window.
7. `missing_data_handler` sets availability flags and missing reasons.
8. `score_normalizer` computes normalized source scores and diagnostics.
9. `fusion_strategy` computes `fused_score` and source contributions.
10. `decision_engine` computes labels and decision metadata.
11. `artifact_writer` writes artifacts in the architecture-defined output order.

### Artifact Generation Order

Recommended write order:

1. `fusion_inputs.csv`
2. `aligned_windows.csv`
3. `normalized_scores.csv`
4. `fused_predictions.csv`
5. summary JSON artifacts
6. plots
7. `phase7_manifest.json`

Rationale:

- pre-fusion traceability artifacts should exist even if a later stage fails
- the manifest must be written last because it references finalized artifact paths

### Shutdown

1. orchestrator collects artifact references and run summary
2. final status is logged
3. any unrecoverable failure exits with a run-level error after available diagnostics are preserved

## 11. Module Interaction Design

Dependency direction must remain inward toward stable contracts and outward toward infrastructure only for artifact and logging concerns.

### Call Direction

```text
fusion_orchestrator
  -> fusion_config
  -> source_manager
  -> fusion_ingest
  -> fusion_validator
  -> fusion_mapper
  -> timestamp_aligner
  -> score_aggregator
       -> AggregationStrategy
  -> missing_data_handler
  -> score_normalizer
       -> NormalizationStrategy
  -> fusion_strategy
  -> decision_engine
  -> artifact_writer
```

### Ownership Boundaries

- `fusion_orchestrator` owns control flow only
- `fusion_config` owns configuration semantics
- `source_manager` owns source descriptors
- `fusion_validator` owns source validation rules
- `fusion_mapper` owns canonical record creation
- `timestamp_aligner` owns window assignment
- `score_aggregator` owns in-window summarization coordination
- `missing_data_handler` owns availability and missingness policy
- `score_normalizer` owns normalization application and diagnostics
- `fusion_strategy` owns fused score computation and contribution metadata
- `decision_engine` owns label generation and decision explanation metadata
- `artifact_writer` owns persistence of outputs

### Communication Flow

- communication is direct, synchronous, and data-driven
- modules exchange typed configuration, source descriptors, and `FusionRecord` collections
- no module should reach backward into a prior stage to reinterpret raw source artifacts

### Interaction Constraints

- `artifact_writer` must not compute business results
- `decision_engine` must not recalculate fused scores
- `score_normalizer` must not decide final labels
- `fusion_orchestrator` must not implement strategy logic

### Dependency Rules

These rules are implementation constraints and must be preserved.

Allowed dependencies:

- `fusion_orchestrator` may depend on all architectural modules for coordination only
- `fusion_ingest` may depend on `source_manager` and configuration to resolve external detector artifacts
- `fusion_validator` may depend on `source_manager` and configuration to evaluate source-specific schemas and rules
- `fusion_mapper` may depend on `source_manager` to convert validated rows into `FusionRecord`
- `score_aggregator` may depend on `AggregationStrategy`
- `score_normalizer` may depend on `NormalizationStrategy`
- `fusion_strategy` may depend on configuration-controlled weights and normalized `FusionRecord` inputs
- `artifact_writer` may depend on finalized records, diagnostics, and configuration snapshots

Forbidden dependencies:

- `fusion_orchestrator` must never implement business logic
- `score_normalizer` must never invoke `fusion_strategy`
- `decision_engine` must never depend on `artifact_writer`
- `artifact_writer` must never compute business results
- processing modules must never read raw detector artifacts directly
- only `fusion_ingest` reads external detector outputs
- only `fusion_mapper` creates `FusionRecord` instances
- `fusion_strategy` must never decide final labels
- `fusion_validator` must never write artifacts as part of validation

Examples of correct dependency behavior:

- `fusion_orchestrator` coordinates but never implements business logic
- `score_aggregator` invokes `AggregationStrategy` but does not embed strategy-specific math in orchestration
- `decision_engine` consumes `fused_score` and emits label metadata without recomputing normalized or fused scores
- `artifact_writer` serializes results but never derives them

Examples of prohibited behavior:

- `timestamp_aligner` opening detector CSV files directly
- `score_normalizer` calling decision logic after normalization
- `artifact_writer` recalculating weights or contributions before writing `fused_predictions.csv`
- `fusion_orchestrator` bypassing `fusion_validator` and mapping raw source rows directly

## 12. Validation Design

Validation occurs at several layers.

### Configuration Validation

Performed by `fusion_config`:

- required section presence
- field type validation
- strategy name validation
- weight and threshold validation
- duration parsing for `window_size`

### Source Artifact Validation

Performed by `fusion_validator`:

- artifact presence validation
- schema validation
- required field validation
- label validation
- score field validation
- source metadata consistency validation

### Timestamp Validation

Performed primarily by `fusion_validator`, with alignment invariants checked by `timestamp_aligner`:

- parseability
- timezone normalization readiness
- absence of null required timestamps
- consistency of window assignment inputs

### Score Validation

Performed by `fusion_validator`, `score_aggregator`, `score_normalizer`, and `fusion_strategy` at their respective boundaries:

- raw numeric type validation
- aggregation input validation
- normalization input validation
- fused score prerequisite validation

### FusionRecord Validation

Performed incrementally at stage boundaries:

- creation-time required field presence
- post-alignment window field presence
- post-missingness availability consistency
- post-normalization source score coherence
- post-fusion contribution coherence
- post-decision decision-field completeness

### Artifact Validation

Performed by `artifact_writer` before write completion:

- required columns and fields
- expected row counts where applicable
- manifest reference completeness
- configuration snapshot presence

## 13. Error Handling Design

### Recoverable Errors

- source windows with only one available source
- both-missing windows treated as diagnostic outcomes
- optional provenance artifact absence when core prediction artifacts remain readable, if policy allows

### Non-Recoverable Errors

- invalid configuration
- unreadable required source artifacts
- missing required columns
- invalid threshold or unsupported strategy selection
- impossible normalization or fusion preconditions

### Logging Strategy for Errors

- warnings for recoverable anomalies in data quality or optional provenance
- errors for stage failures that prevent progression
- exception stack traces only at error or debug levels appropriate to the environment

### Warning Handling

- warnings must be structured enough to support later diagnosis
- warning counts should appear in run summaries and, where relevant, manifest metadata

### Exception Propagation

- module-level exceptions propagate upward with contextual metadata
- `fusion_orchestrator` may wrap stage failures in run-level context but should not erase causal information

### Configuration Errors

- fail fast before source ingestion begins

### Artifact Errors

- fail the run if required Phase 7 artifacts cannot be created
- optional artifacts may be downgraded only if the architecture does not require them

### Timestamp Errors

- fail validation unless an explicit row-drop policy exists and is enabled

### Missing Source Handling

- handled through `missing_data_handler` as data-state outcomes, not as exceptions

## 14. Logging Design

Logging must support experiment traceability, debugging, and operational observability.

### Logging Levels

- `DEBUG`: configuration defaults, stage-level diagnostics, derived statistics, sample counts
- `INFO`: run start, strategy selections, artifact paths, stage completion summaries
- `WARNING`: recoverable schema drift, optional provenance gaps, partial source availability summaries
- `ERROR`: non-recoverable stage failures

### Module Responsibilities

- `fusion_config`: log effective configuration summary
- `source_manager`: log active source descriptors
- `fusion_ingest`: log artifact locations and row counts
- `fusion_validator`: log validation summaries and critical issues
- `fusion_mapper`: log mapping counts
- `timestamp_aligner`: log window counts and timestamp normalization summary
- `score_aggregator`: log aggregation strategy and window coverage
- `missing_data_handler`: log availability distributions
- `score_normalizer`: log normalization strategy and diagnostics summary
- `fusion_strategy`: log configured weights and score computation summary
- `decision_engine`: log threshold and label distribution
- `artifact_writer`: log artifact creation and manifest finalization
- `fusion_orchestrator`: log stage boundaries and final run status

### Experiment Logging

- every run should have one experiment-scoped logging context
- logs should include experiment id where available

### Artifact Logging

- each required artifact write should emit location and row-count metadata

### Warning Logging

- warnings should include source type, stage, and impact summary

### Error Logging

- errors should include stage, artifact or record context where possible, and failure classification

### Debug Logging

- debug output must remain optional and configuration-controlled to avoid excessive volume in normal runs

## 15. Artifact Design

The artifact set must remain consistent with the architecture.

| Artifact | Purpose | Producer | Consumer | Creation timing | Required fields or content | Validation | Retention |
|---|---|---|---|---|---|---|---|
| `fusion_inputs.csv` | Preserve pre-normalization inputs and availability state | `artifact_writer` | analysts, diagnostics, reproducibility workflows | after alignment and before normalization | `window_ts`, `window_end_ts`, `entity_id`, `kpi_raw_score`, `log_raw_score`, `kpi_available`, `log_available`, `missing_reason` | field presence, row count consistency | retain |
| `aligned_windows.csv` | Preserve aligned and grouped window view | `artifact_writer` | diagnostics, audit workflows | after aggregation or aligned-window finalization according to implementation detail | window identifiers, source counts, source association context | alignment completeness | retain |
| `normalized_scores.csv` | Preserve normalized source score state | `artifact_writer` | diagnostics, comparison workflows | after normalization | raw and normalized score columns, availability flags | normalized-field presence and range checks | retain |
| `fused_predictions.csv` | Canonical final fused output | `artifact_writer` | downstream evaluation, reporting | after decisioning | `window_ts`, `window_end_ts`, `entity_id`, normalized scores, weights, contributions, `fused_score`, `final_label`, `decision_reason` | field completeness and type checks | retain |
| `fusion_summary.json` | Aggregate experiment summary | `artifact_writer` | reports, manifest support | after decisioning | counts, distributions, strategy summary | JSON completeness | retain |
| `source_coverage.json` | Describe source presence and missingness | `artifact_writer` | diagnostics, reporting | after missing-data handling or finalization | availability counts, missing reasons | consistency with record counts | retain |
| plots | Visualize fused score distributions and time behavior | `artifact_writer` | reports | after decisioning | plot-specific visual content | file existence and linkage | retain if enabled |
| `phase7_manifest.json` | Canonical experiment manifest | `artifact_writer` | downstream reproducibility, audit workflows | last | lineage, configuration snapshot, artifact references, strategy metadata | manifest completeness | retain |

## 16. Manifest Design

The manifest is the canonical reproducibility and audit artifact for a Phase 7 run.

### Mandatory Fields

- manifest version
- generation timestamp
- experiment id
- KPI Detector Experiment ID
- Log Detector Experiment ID
- input artifact references
- output artifact references
- fusion strategy
- configured weights
- configured threshold
- configured window size
- normalization strategy
- aggregation strategy
- coverage statistics
- configuration snapshot

### Optional Fields

- warning summary
- optional provenance references
- plot references if generated

### Metadata

Manifest metadata should include:

- run status
- source lineage
- strategy identities
- normalization diagnostics summary
- artifact counts and locations

### Configuration Snapshot

- must capture the effective configuration after defaults and overrides
- should be serialized in a stable form suitable for comparison across experiments

### Experiment Lineage

- must preserve the link to the KPI Detector Experiment ID
- must preserve the link to the Log Detector Experiment ID
- must preserve the identity of the published detector manifest used for Log Source ingestion

### Artifact References

- each artifact reference should be explicit, stable, and scoped to the current experiment output directory

### Reproducibility Information

- window size
- aggregation strategy
- normalization strategy
- fusion strategy
- source weights
- threshold
- validation strictness if it influenced row retention

## 17. Sequence Design

This section expands the full runtime sequence in operational detail.

### Stage 1: Configuration Initialization

- `fusion_orchestrator` invokes `fusion_config`
- configuration is loaded, defaulted, validated, and frozen for the run

### Stage 2: Source Definition Initialization

- `source_manager` resolves descriptors for KPI and LOG sources
- source expectations become available to ingestion and validation

### Stage 3: Source Ingestion

- `fusion_ingest` loads KPI Source artifacts
- `fusion_ingest` loads the Log Detector Manifest
- `fusion_ingest` resolves and loads Log Source prediction data

### Stage 4: Source Validation

- `fusion_validator` validates schemas, timestamps, scores, labels, and metadata consistency
- normalized source tables are returned

### Stage 5: Canonical Mapping

- `fusion_mapper` creates source-level `FusionRecord`
- source-specific fields are translated into canonical fields

### Stage 6: Timestamp Alignment

- `timestamp_aligner` assigns window boundaries
- records are grouped into aligned windows

### Stage 7: In-Window Aggregation

- `score_aggregator` invokes `AggregationStrategy`
- one source score per source per window is produced

### Stage 8: Missing-Data Resolution

- `missing_data_handler` sets availability flags and missing reasons
- both-missing windows are handled according to architecture policy

### Stage 9: Score Normalization

- `score_normalizer` invokes `NormalizationStrategy`
- normalized source scores and diagnostics are produced

### Stage 10: Fused Score Computation

- `fusion_strategy` computes `fused_score` and source contributions

### Stage 11: Decisioning

- `decision_engine` applies the configured threshold
- final labels and decision reasons are attached

### Stage 12: Artifact Generation

- `artifact_writer` writes intermediate and final artifacts
- manifest is written last

## 18. Design Patterns

### Strategy

Used for:

- aggregation
- normalization
- fusion

Why chosen:

- frozen architecture requires behavior variation without pipeline redesign
- callers remain stable while strategies vary by configuration

### Factory

Applicable conceptually inside configuration or orchestration when resolving configured strategies.

Why chosen:

- concrete strategy selection must remain centralized and configuration-driven
- no dedicated factory module is required by the architecture

Constraint:

- factory behavior must remain internal to existing modules and must not introduce new architecture-level modules

### Dependency Injection

Used conceptually by passing configured strategies and configuration objects into consuming modules.

Why chosen:

- improves testability
- reduces coupling to concrete implementations

### Orchestrator

Used by `fusion_orchestrator`.

Why chosen:

- architecture requires one coordination module with no embedded business rules

### Builder

Applicable conceptually for constructing complex output structures such as manifest payloads or configuration snapshots.

Why chosen:

- improves clarity when assembling multi-field immutable artifacts

Constraint:

- builder behavior must stay inside existing modules such as `artifact_writer` and `fusion_config`

### Composition Over Inheritance

Why chosen:

- modules compose strategies rather than inherit behavior trees
- easier to extend and test without fragile class hierarchies

## 19. Testability Design

Every architectural module should be testable in isolation and in integration. The test matrix below defines the minimum recommended coverage structure.

| Module | Unit tests | Integration tests | Contract or interface tests | Configuration tests | Failure-path tests | Artifact validation tests |
|---|---|---|---|---|---|---|
| `fusion_config` | Yes | Yes | No | Yes | Yes | No |
| `source_manager` | Yes | Yes | No | Yes | Yes | No |
| `fusion_ingest` | Yes | Yes | No | Yes | Yes | No |
| `fusion_validator` | Yes | Yes | No | Yes | Yes | No |
| `fusion_mapper` | Yes | Yes | No | Yes | Yes | No |
| `timestamp_aligner` | Yes | Yes | No | Yes | Yes | No |
| `aggregation_strategy` | Yes | Yes | Yes | Yes | Yes | No |
| `score_aggregator` | Yes | Yes | Yes | Yes | Yes | No |
| `missing_data_handler` | Yes | Yes | No | Yes | Yes | No |
| `normalization_strategy` | Yes | Yes | Yes | Yes | Yes | No |
| `score_normalizer` | Yes | Yes | Yes | Yes | Yes | No |
| `fusion_strategy` | Yes | Yes | Yes | Yes | Yes | No |
| `decision_engine` | Yes | Yes | No | Yes | Yes | No |
| `artifact_writer` | Yes | Yes | No | Yes | Yes | Yes |
| `fusion_orchestrator` | Yes | Yes | No | Yes | Yes | Yes |

### Test Matrix Guidance

`fusion_config`

- unit tests should cover defaults, override precedence, and field validation
- integration tests should verify that downstream modules receive stable configuration views
- configuration tests should cover invalid strategy names, threshold ranges, and malformed `window_size`
- failure-path tests should verify fail-fast behavior on invalid configuration

`source_manager`

- unit tests should cover descriptor construction and source lookup
- integration tests should verify compatibility with ingestion and validation
- configuration tests should cover missing or incomplete source descriptors
- failure-path tests should verify behavior when required sources are absent

`fusion_ingest`

- unit tests should cover path resolution, detector-manifest resolution, and raw table loading
- integration tests should verify end-to-end artifact resolution for both sources
- configuration tests should cover artifact path overrides
- failure-path tests should cover missing files, unreadable manifests, and invalid references

`fusion_validator`

- unit tests should cover schema, timestamp, score, and label validation rules
- integration tests should verify that normalized source tables are accepted by `fusion_mapper`
- configuration tests should cover strict versus permissive validation settings
- failure-path tests should cover missing fields, invalid timestamps, and incompatible score types

`fusion_mapper`

- unit tests should cover canonical field mapping and source-specific field translation
- integration tests should verify `FusionRecord` compatibility with alignment
- configuration tests should cover field-alias behavior where applicable
- failure-path tests should cover contract breaches after validation

`timestamp_aligner`

- unit tests should cover UTC conversion, window assignment, and deterministic ordering
- integration tests should verify compatibility with aggregation input expectations
- configuration tests should cover multiple `window_size` values
- failure-path tests should cover invalid or missing timestamp fields that escape earlier validation

`aggregation_strategy`

- unit tests should cover each supported strategy contract
- integration tests should verify compatibility with `score_aggregator`
- contract tests should assert the one-collection-to-one-score behavior for all strategy implementations
- configuration tests should verify strategy selection
- failure-path tests should cover empty inputs and non-numeric values

`score_aggregator`

- unit tests should cover score extraction, label rollup, and confidence rollup
- integration tests should verify output readiness for missing-data handling
- contract tests should verify correct invocation of `AggregationStrategy`
- configuration tests should cover strategy selection behavior
- failure-path tests should cover malformed aligned windows and strategy errors

`missing_data_handler`

- unit tests should cover full, partial, and empty window handling
- integration tests should verify downstream readiness for normalization
- configuration tests should cover drop-policy and strictness behavior if configured
- failure-path tests should verify detection of inconsistent availability states

`normalization_strategy`

- unit tests should cover supported normalization contracts and metadata outputs
- integration tests should verify compatibility with `score_normalizer`
- contract tests should assert output ordering and metadata serializability
- configuration tests should verify strategy selection
- failure-path tests should cover zero-range, invalid numeric, and impossible state scenarios

`score_normalizer`

- unit tests should cover source-wise score collection, normalization assignment, and diagnostics emission
- integration tests should verify output readiness for fusion
- contract tests should verify correct invocation of `NormalizationStrategy`
- configuration tests should cover normalization strategy selection
- failure-path tests should cover inconsistent availability or normalization failures

`fusion_strategy`

- unit tests should cover weight handling, availability-aware renormalization, contributions, and `fused_score`
- integration tests should verify output readiness for decisioning
- contract tests should assert that strategy outputs always include the fused-score contract fields
- configuration tests should cover weight and strategy configuration
- failure-path tests should cover invalid weights and missing normalized score inputs

`decision_engine`

- unit tests should cover threshold application, label generation, and decision reason assignment
- integration tests should verify compatibility with `artifact_writer`
- configuration tests should cover threshold changes
- failure-path tests should cover missing `fused_score` and invalid threshold state

`artifact_writer`

- unit tests should cover field-set generation, serialization order, and manifest assembly
- integration tests should verify complete artifact sets from finalized records
- configuration tests should cover output path and retention settings
- failure-path tests should cover write failures and incomplete manifest state
- artifact validation tests should verify column sets, manifest completeness, and artifact linkage

`fusion_orchestrator`

- unit tests should cover stage ordering, collaborator invocation, and failure propagation
- integration tests should cover end-to-end execution from ingestion to manifest generation
- configuration tests should verify startup behavior under alternate configurations
- failure-path tests should cover stage interruption and run-summary integrity
- artifact validation tests should verify that final runs expose a complete artifact reference set

## 20. Computational Complexity

This section summarizes the expected conceptual complexity of each major pipeline stage. The notation assumes:

- $N_k$ is the number of KPI Source records
- $N_l$ is the number of Log Source records
- $N = N_k + N_l$
- $W$ is the number of aligned windows
- $A$ is the average number of source records per populated window

Source ingestion:

- approximate complexity: $O(N)$
- rationale: each detector record is read once from its published artifact source

Validation:

- approximate complexity: $O(N)$
- rationale: schema, timestamp, score, and required-field validation are performed per row, plus constant-time schema checks per artifact

Mapping:

- approximate complexity: $O(N)$
- rationale: each validated source row is converted into one `FusionRecord`

Timestamp alignment:

- approximate complexity: $O(N)$ for deterministic bucket assignment and grouping, assuming direct window-key computation
- rationale: each record is assigned to one configured window and inserted into one grouped collection

Aggregation:

- approximate complexity: $O(N)$ overall, or equivalently $O(W \cdot A)$
- rationale: each grouped score participates in exactly one in-window aggregation operation

Missing-data handling:

- approximate complexity: $O(W)$
- rationale: one pass is made over aggregated window-level records to set availability flags and missing reasons

Normalization:

- approximate complexity: $O(W)$
- rationale: source score collections are traversed to derive normalization context and assign normalized values

Fusion:

- approximate complexity: $O(W)$
- rationale: one fused-score computation is performed per aggregated and normalized window-level record

Decision generation:

- approximate complexity: $O(W)$
- rationale: threshold evaluation and decision metadata assignment occur once per fused record

Artifact writing:

- approximate complexity: $O(W)$ for record-oriented outputs, plus linear cost in the size of summary and manifest payloads
- rationale: each output artifact is serialized from already prepared in-memory structures

Overall pipeline complexity:

- approximate total complexity: $O(N + W)$
- in the common case where $W \le N$, the dominant behavior is effectively linear in input size

This complexity discussion is conceptual and is intended only to set implementation expectations for scale and stage cost.

## 21. Performance Considerations

### Memory Usage

- the baseline architecture is batch-oriented and file-driven
- large source tables may require chunk-aware internal processing even if artifacts remain whole-file outputs

### Streaming vs Batch Processing

- the current architecture is best implemented as batch processing
- internal iterator-based processing may be used to reduce memory pressure without changing artifact semantics

### Large Dataset Handling

- alignment and aggregation stages are most likely to grow with input size
- implementations should avoid unnecessary duplication of record collections

### Configuration Loading

- configuration loading cost is negligible relative to data processing and should happen once per run

### Artifact Writing

- artifact writing should be staged so early diagnostic artifacts can survive downstream failure
- writing large CSV outputs should prefer sequential serialization patterns

### Future Scalability

- source-oriented design supports more sources
- strategy abstractions support scalable behavior variation
- packaging by concern supports future refactoring without redesigning the architecture

## 22. Thread Safety

The Phase 7 design assumes a single-process execution model for the baseline implementation.

Thread-safety guidance:

- individual processing modules should remain as stateless as practical
- mutable state should be minimized
- the design intentionally avoids shared mutable state across processing stages
- per-run context should be passed explicitly rather than stored globally
- artifact generation should operate on finalized inputs rather than shared live state

This guidance preserves the frozen architecture while allowing future implementations to introduce controlled parallel execution without changing module responsibilities.

## 23. Deterministic Execution

Deterministic processing is required for experiment reproducibility.

The design requires that identical:

- configuration
- detector artifacts
- source data
- processing order
- supported strategy implementations

must produce identical outputs.

Deterministic execution guarantees are supported by the following design constraints:

- configuration is loaded once and snapshotted for the run
- detector artifacts are treated as immutable inputs
- `FusionRecord` state transitions are stage-owned and controlled
- processing order is fixed by the orchestrated pipeline
- manifest contents capture sufficient metadata to reproduce the run
- artifacts should be reproducible across repeated executions using identical inputs

This requirement applies to traceability artifacts, fused predictions, summaries, and manifests.

## 24. Future Extensibility

The design supports future enhancements without changing the frozen architecture.

### Additional Anomaly Sources

- extend `source_manager` descriptors
- extend ingestion, validation, and mapping logic while preserving `FusionRecord`

### Additional Aggregation Strategies

- add new `AggregationStrategy` implementations
- no orchestrator or downstream redesign required

### Additional Normalization Strategies

- add new `NormalizationStrategy` implementations
- preserve existing normalization contract

### Additional Fusion Strategies

- add new `FusionStrategy` implementations
- preserve the fused-score output contract

### Learnable Fusion

- can replace fixed weighted fusion in a future implementation while still producing the same downstream fused score contract

### Additional Explainability

- consume existing contribution and decision metadata
- add new artifacts without altering the main processing flow

### New Artifact Types

- new output artifacts can be added in `artifact_writer` so long as manifest references remain consistent

### New Validation Rules

- extend `fusion_validator` and `FusionRecord` invariants without changing caller module order

## 25. Implementation Guidance

This section provides implementation planning guidance without source code.

### Recommended Implementation Order

1. `fusion_config`
2. `source_manager`
3. `fusion_validator`
4. `fusion_ingest`
5. `fusion_mapper`
6. `FusionRecord`
7. `timestamp_aligner`
8. `aggregation_strategy`
9. `score_aggregator`
10. `missing_data_handler`
11. `normalization_strategy`
12. `score_normalizer`
13. `fusion_strategy`
14. `decision_engine`
15. `artifact_writer`
16. `fusion_orchestrator`

### Module Dependency Order

- configuration and source descriptors first
- validation and domain mapping second
- core processing stages third
- output and orchestration last

### Integration Milestones

1. configuration and source resolution complete
2. raw ingestion and validation complete
3. `FusionRecord` mapping complete
4. alignment and aggregation complete
5. normalization and fusion complete
6. decisioning complete
7. artifact generation and manifest complete
8. end-to-end experiment run complete

### Testing Milestones

1. configuration tests
2. source validation and mapping tests
3. alignment and aggregation tests
4. normalization and fusion tests
5. decisioning tests
6. artifact and manifest tests
7. end-to-end pipeline tests

### Risk Areas

- timestamp normalization and window assignment
- manifest-to-artifact resolution for the Log Source
- source score normalization stability
- preserving deterministic ordering in aggregated outputs
- ensuring `FusionRecord` invariants across stage transitions

### Recommended Implementation Sequence

- implement stable inputs first
- implement domain model and validation next
- implement pure processing stages before orchestration
- implement artifact writing before full end-to-end orchestration
- add orchestrator once module contracts are stable

This sequence minimizes rework, improves testability, and keeps early implementation aligned with the frozen architecture.

## 26. Recommended Implementation Order

The recommended development sequence below is intended to reduce coupling risk, stabilize contracts early, and make integration incremental.

1. Configuration
Reason: all later modules depend on validated strategy, threshold, and path configuration.

2. Source Manager
Reason: source descriptors define the authoritative expectations for ingestion and validation.

3. FusionRecord
Reason: the canonical record contract must be stable before mapping, alignment, and downstream enrichment are implemented.

4. Validator
Reason: source validation rules prevent invalid upstream data from contaminating downstream modules.

5. Mapper
Reason: canonical mapping establishes the stable data handoff into the processing pipeline.

6. Timestamp Aligner
Reason: window assignment is a prerequisite for aggregation and subsequent availability handling.

7. Aggregation Strategy
Reason: the strategy contract should be stabilized before the coordinating aggregator is implemented.

8. Score Aggregator
Reason: aggregation produces the per-window per-source scores used by all later business stages.

9. Missing Data Handler
Reason: availability flags and missingness annotations must be established before normalization and fusion.

10. Normalization Strategy
Reason: the normalization contract should be stabilized before normalized fields are written onto `FusionRecord`.

11. Score Normalizer
Reason: normalized scores are required inputs for fusion and should be validated in isolation before score combination is added.

12. Fusion Strategy
Reason: fused-score and contribution logic depends on complete normalized and availability-aware records.

13. Decision Engine
Reason: label generation should be added only after fused-score semantics are stable.

14. Artifact Writer
Reason: outputs should be built after upstream contracts are stable so field definitions do not churn.

15. Fusion Orchestrator
Reason: orchestration should be assembled only after module contracts and stage boundaries are known and testable.

16. End-to-End Integration
Reason: final integration validates the complete experiment lifecycle, artifact lineage, and frozen architecture conformance.