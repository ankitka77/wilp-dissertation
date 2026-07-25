# Phase 7 Architecture — Fusion Engine

## 1. Purpose of the Fusion Engine

Phase 7 introduces a Fusion Engine that combines anomaly evidence from two already completed detectors:

- KPI Detector, corresponding to the detector developed in Phase 4
- Log Detector, corresponding to the detector developed in Phase 6

The purpose of the Fusion Engine is to produce one unified anomaly assessment per aligned analysis window so that heterogeneous anomaly signals can be interpreted through a single, consistent decision layer.

The Fusion Engine does not retrain upstream detectors. It consumes their frozen outputs, aligns them in time, normalizes their scores into a common scale, applies a configuration-selected fusion strategy, and emits final fused anomaly scores, labels, manifests, and reports.

Architecturally, the Fusion Engine is designed not only for dissertation evaluation but also as the foundation of a production-grade multi-source anomaly fusion service. The architecture therefore emphasizes:

- source-oriented abstractions instead of dissertation-phase abstractions
- SOLID-aligned component boundaries
- strict separation of concerns
- configuration-driven behavior
- extensibility for additional anomaly sources, strategies, and policies

## 2. Responsibilities

The Fusion Engine is responsible for:

- reading KPI Source and Log Source artifacts from their published output locations
- validating required schemas, timestamps, scores, labels, and metadata before fusion begins
- converting heterogeneous detector outputs into the canonical `FusionRecord` domain model
- aligning source records onto a shared configurable fusion window
- handling missing, sparse, delayed, or unmatched source records through explicit availability-aware policies
- normalizing source-specific anomaly scores using a configuration-selected normalization strategy
- combining normalized scores using a configuration-selected fusion strategy
- delegating final label generation to a dedicated Decision Engine
- producing reproducible experiment artifacts, manifests, reports, and diagnostics
- exposing source contributions to support explainability, debugging, and auditability

The Fusion Engine is not responsible for:

- retraining the KPI Detector
- retraining the Log Detector
- changing upstream detector internals
- embedding business rules inside orchestration
- alert routing or downstream operational response mechanisms

Configuration philosophy:

All experiment-specific behavior is configuration-driven. At minimum, configuration controls:

- fusion strategy
- `kpi_weight`
- `log_weight`
- threshold
- `window_size`
- normalization strategy

Future configuration options must be extendable without modifying business logic.

## 3. Overall architecture

The Phase 7 architecture is organized as a file-driven, experiment-oriented post-processing pipeline with strict separation of concerns.

Logical layers:

1. Source ingestion layer
2. Canonicalization and validation layer
3. Timestamp alignment layer
4. Missing-data resolution layer
5. Score normalization layer
6. Fusion score computation layer
7. Decision layer
8. Artifact, manifest, and reporting layer

Recommended Phase 7 module set:

- `fusion_config`: central configuration for source ingestion, windowing, normalization, fusion, and thresholding
- `source_manager`: source-oriented metadata and source-type definitions
- `fusion_ingest`: reads detector artifacts and metadata
- `fusion_validator`: validates schemas, score ranges, timestamps, required fields, and source compatibility
- `fusion_mapper`: converts source outputs into `FusionRecord`
- `timestamp_aligner`: groups and aligns source records into configurable windows
- `aggregation_strategy`: strategy interface for in-window source aggregation
- `score_aggregator`: delegates in-window source aggregation to the configured aggregation strategy
- `missing_data_handler`: resolves absent or incomplete source signals using explicit policies
- `normalization_strategy`: strategy interface for score normalization
- `score_normalizer`: delegates normalization to the configured normalization strategy
- `fusion_strategy`: strategy interface for fused score computation
- `decision_engine`: applies thresholding and decision policies to fused scores
- `artifact_writer`: writes experiment artifacts, manifests, and reports
- `fusion_orchestrator`: loads configuration, initializes modules, coordinates execution, and invokes artifact writing

Source-oriented abstraction:

- `SourceType`
  - `KPI`
  - `LOG`

The Fusion Engine operates on anomaly sources rather than dissertation phases. This enables new sources to be introduced in the future without redesigning the core architecture.

Experiment lifecycle:

Configuration
↓
Experiment
↓
Pipeline Execution
↓
Artifacts
↓
Metrics
↓
Manifest
↓
Reports

Phase 7 follows the same experiment-driven philosophy established in earlier phases of the dissertation while generalizing the architecture toward production-grade reproducibility and auditability.

Recommended configuration shape:

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
```

Default values:

- `kpi_weight = 0.50`
- `log_weight = 0.50`
- `threshold = 0.60`
- `window_size = 5 minutes`
- `normalization_strategy = min_max`
- `aggregation.strategy = max`

These parameters are intentionally configurable so users can experiment with different weight combinations, thresholds, and window sizes without modifying code. This supports dissertation experimentation, sensitivity analysis, ablation studies, and future production tuning.

The aggregation policy is also configurable so that in-window source summarization can be changed without modifying business logic.

## 4. Complete data flow

End-to-end flow:

1. Load configuration and initialize the experiment context.
2. Read KPI Source output artifacts.
3. Read Log Source manifest and prediction artifacts.
4. Validate presence of timestamps, anomaly scores, labels, source identifiers, and experiment metadata.
5. Convert source-specific records into `FusionRecord` instances.
6. Align `FusionRecord` instances into a shared configurable window.
7. Aggregate multiple records from the same source within the same window through the configured aggregation strategy.
8. Apply missing-data handling and set availability flags.
9. Normalize source scores through the configured normalization strategy.
10. Compute one fused anomaly score through the configured fusion strategy.
11. Pass fused scores to the Decision Engine.
12. Generate final anomaly labels, decision reasons, and decision metadata.
13. Write traceability artifacts, fused reports, metrics, manifest, and summary outputs.

Canonical fusion unit:

- one `FusionRecord` per analysis window after alignment and aggregation
- optional secondary dimensions: `entity_id`, `kpi_id`, `session_id`, or `block_id` when available

The data flow explicitly separates:

- source ingestion from canonicalization
- normalization from fusion score computation
- fusion score computation from decision making
- decision making from artifact generation

This separation supports SOLID principles, reduces coupling, and ensures that configuration changes do not require changes to core business logic.

## 5. Inputs and outputs of every module

| Module | Inputs | Outputs |
|---|---|---|
| `fusion_config` | YAML/JSON settings, runtime overrides | validated fusion configuration object |
| `source_manager` | source definitions and source metadata | managed `SourceType` values and source descriptors |
| `fusion_ingest` | KPI Source prediction/report paths, Log Source manifest path | raw KPI Source tables, raw Log Source tables, source metadata |
| `fusion_validator` | raw source tables, source descriptors, configuration | validation report, schema-normalized source tables |
| `fusion_mapper` | validated source tables | source-level `FusionRecord` instances |
| `timestamp_aligner` | source-level `FusionRecord` instances, `window_size` configuration | aligned window-level `FusionRecord` instances |
| `aggregation_strategy` | aligned source scores within a window | aggregated source score per window |
| `score_aggregator` | aligned window-level `FusionRecord` instances, aggregation configuration | aggregated window-level `FusionRecord` instances |
| `missing_data_handler` | aligned `FusionRecord` instances, missing-data policy | availability-complete `FusionRecord` instances with fallback metadata |
| `normalization_strategy` | source scores and source-specific normalization parameters | normalized source scores |
| `score_normalizer` | availability-complete `FusionRecord` instances, normalization configuration | normalized `FusionRecord` instances and normalization diagnostics |
| `fusion_strategy` | normalized `FusionRecord` instances, configured weights | fused score, `kpi_contribution`, `log_contribution`, and fusion metadata |
| `decision_engine` | fused `FusionRecord` instances, configurable threshold and decision policy | final label, decision reason, decision metadata |
| `artifact_writer` | input snapshots, `FusionRecord` outputs, config, metrics, metadata | CSV/JSON reports, plots, manifest, summary files |
| `fusion_orchestrator` | top-level configuration and artifact paths | complete Phase 7 experiment execution |

### FusionRecord

`FusionRecord` is the canonical domain object used throughout the Fusion Engine architecture after ingestion and mapping. It represents the standardized data model flowing across alignment, missing-data handling, normalization, fusion, decisioning, and artifact generation.

Important `FusionRecord` fields include:

- `window_ts`
- `window_end_ts`
- `entity_id`
- `source_type`
- `source_record_id`
- `kpi_score`
- `log_score`
- `kpi_score_normalized`
- `log_score_normalized`
- `kpi_available`
- `log_available`
- `missing_reason`
- `kpi_weight`
- `log_weight`
- `kpi_contribution`
- `log_contribution`
- `fused_score`
- `final_label`
- `decision_reason`
- `decision_metadata`
- `source_metadata`

Architectural interpretation:

- source-level `FusionRecord` instances may be partially populated before alignment
- aligned window-level `FusionRecord` instances become the canonical decision unit
- later pipeline stages enrich the same domain object with normalized scores, contributions, fused scores, and decision metadata

## 6. Integration with KPI Detector and Log Detector

### Integration with the KPI Detector

The KPI Detector is treated as the KPI Source.

Expected consumable artifacts from the KPI Source:

- experiment prediction CSV containing timestamp-aligned KPI anomaly output
- experiment metrics JSON for provenance
- experiment metadata or configuration snapshot where available

Expected KPI Source fields required by the Fusion Engine:

- `timestamp`
- `anomaly_score`
- predicted anomaly label field such as `prediction` or equivalent
- optional `KPI ID` or entity key

KPI Source adaptation rules:

- map KPI anomaly scores directly to `kpi_score`
- convert predicted anomaly labels into binary form: `0 = normal`, `1 = anomaly`
- if multiple KPI rows fall in one window, aggregate them before fusion

Recommended in-window KPI aggregation:

- aggregation strategy selected by configuration
- label aggregation: anomaly if any KPI row in the window is anomalous

Rationale:

- a single highly abnormal KPI point is operationally meaningful
- `MaxAggregation` preserves peak anomaly intensity better than `mean`

### Integration with the Log Detector

The Log Detector is treated as the Log Source.

Expected consumable artifacts from the Log Source:

- Log Detector published manifest
- `predictions.csv`
- optional training metrics and metadata for provenance only

For the current dissertation implementation, the Log Detector published manifest corresponds to `phase6_manifest.json`.

Expected Log Source fields required by the Fusion Engine:

- timestamp or timestamp-derivable event or window field
- `anomaly_score`
- `is_anomaly`
- `prediction_confidence`
- optional `id`, `session_id`, `block_id`, or sequence key

Log Source adaptation rules:

- read artifact locations from the manifest rather than hardcoding paths
- map log anomaly scores directly to `log_score`
- map `is_anomaly` to binary form
- preserve `prediction_confidence` as optional auxiliary evidence

Recommended in-window Log aggregation:

- aggregation strategy selected by configuration
- label aggregation: anomaly if any sequence in the window is anomalous
- confidence aggregation: score-weighted average when confidence is available

Source integration principle:

Although the initial architecture integrates exactly two sources, the internal design is source-oriented and extensible. Additional anomaly sources must be introducible through source management, mapping, and strategy compatibility without redesigning the core Fusion Engine.

## 7. Timestamp alignment strategy

The KPI Source and Log Source produce signals at different granularities. The Fusion Engine therefore requires a canonical alignment window.

Recommended strategy:

- convert all timestamps to UTC
- round or bucket timestamps into a configurable window size
- use one canonical window index for all sources
- align by `window_start <= timestamp < window_end`

Window configuration:

- configuration field: `window_size`
- default: `5 minutes`

The architecture must support alternative window sizes without modifying business logic.

Why a configurable window matters:

- anomaly timing noise may differ by detector
- operational workloads may require finer or coarser correlation granularity
- dissertation experiments may require sensitivity analysis across multiple window sizes
- future production environments may require tuning by workload or service domain

Alignment process:

1. parse all timestamps using one timezone policy
2. convert to UTC
3. assign each KPI Source record to a configured fusion window
4. assign each Log Source record to the same configured fusion window logic
5. group source records by window and entity scope
6. create one aligned window-level `FusionRecord`

Alignment precedence:

- primary key: `window_ts`
- secondary keys when available: `entity_id`, `kpi_id`, `session_id`, `block_id`

If cross-source entity keys are not comparable, fusion falls back to timestamp-only alignment.

## 8. Aggregation strategy

Multiple source records may map to the same fusion window. The Fusion Engine therefore uses a strategy-based aggregation design for in-window score summarization.

The architecture uses an aggregation strategy abstraction:

- `AggregationStrategy` (interface)
  - `MaxAggregation`
  - `MeanAggregation`
  - `MedianAggregation`

Configuration selects the aggregation strategy.

Example configuration:

```yaml
aggregation:
  strategy: max
```

Implementation scope for Phase 7:

- `MaxAggregation` will be implemented in Phase 7
- `MeanAggregation` and `MedianAggregation` are architecture extension points only

Recommended default aggregation policy:

- configuration field: `aggregation.strategy`
- default: `max`

Aggregation rationale:

- `MaxAggregation` preserves peak anomaly intensity within a window
- configurable aggregation supports comparative experiments without changing business logic
- future production tuning may prefer different summarization behavior for different workloads

## 9. Missing data handling strategy

Missing data can occur when one source produces no record for a fusion window.

Missing-data cases:

- KPI Source missing, Log Source present
- Log Source missing, KPI Source present
- both present
- both missing after alignment

Recommended handling:

- both present: perform normal fusion
- one source missing: use the available source score and renormalize configured source weights over available sources only
- both missing: drop the window from scored output and record it in diagnostics

Operational rules:

- add boolean fields `kpi_available` and `log_available`
- add `missing_reason` for absent source windows
- never impute anomaly scores using forward-fill or interpolation for dissertation scoring or production-grade auditability

Rationale for no score imputation:

- imputation can invent anomaly evidence not produced by either source
- research and production auditability both require preservation of original detector outputs
- availability-aware fusion is simpler, defensible, and easier to validate

## 10. Score normalization strategy

The KPI Source and Log Source may not share the same raw score semantics, even if both are numerically bounded.

Normalization goals:

- map source scores into a comparable anomaly scale
- preserve rank ordering within each source
- avoid allowing one source to dominate due to wider numeric spread
- keep normalization policy replaceable without changing fusion logic

The architecture uses a strategy-based normalization design:

- `NormalizationStrategy` (interface)
  - `MinMaxNormalization`
  - `ZScoreNormalization`
  - `IdentityNormalization`

Configuration selects the normalization strategy.

Implementation scope for Phase 7:

- `MinMaxNormalization` will be implemented in Phase 7
- `ZScoreNormalization` and `IdentityNormalization` are architecture extension points only

Recommended default normalization policy:

- configuration field: `normalization_strategy`
- default: `min_max`

Default normalization formula for `MinMaxNormalization`:

$$
s'_{src} = \frac{s_{src} - \min(s_{src})}{\max(s_{src}) - \min(s_{src}) + \epsilon}
$$

Where:

- $s_{src}$ is the raw source anomaly score
- $s'_{src}$ is the normalized source anomaly score
- $\epsilon$ prevents division by zero

Safeguards:

- clamp all normalized values to $[0,1]$
- if all scores are identical for a source, set normalized score to the raw bounded score if already in $[0,1]$, otherwise set all normalized values to `0.5`
- record normalization configuration and source-wise calibration statistics in the manifest for reproducibility

## 11. Comparison of fusion strategies

The architecture uses a strategy-based fusion design:

- `FusionStrategy` (interface)
  - `WeightedAverageStrategy`
  - `ConfidenceWeightedStrategy`
  - `ThresholdStrategy`
  - `VotingStrategy`

Configuration selects the strategy.

Implementation scope for Phase 7:

- `WeightedAverageStrategy` will be implemented in Phase 7
- `ConfidenceWeightedStrategy`, `ThresholdStrategy`, and `VotingStrategy` are architecture extension points only

### Weighted Average

Definition:

$$
S_f = w_k s'_k + w_l s'_l \quad \text{where } w_k + w_l = 1
$$

Strengths:

- simple and highly interpretable
- easy to justify in research and production settings
- stable under moderate noise
- easy to analyze through configurable weight changes

Weaknesses:

- does not automatically adapt to per-record confidence variation
- weight selection remains a calibration exercise

### Confidence Weighted

Definition:

$$
S_f = \frac{c_k s'_k + c_l s'_l}{c_k + c_l + \epsilon}
$$

Strengths:

- adapts to source confidence per record
- can down-weight weaker predictions dynamically

Weaknesses:

- requires reliable confidence estimates from both sources
- KPI confidence is often weaker or indirect
- increases methodological and operational complexity

### Threshold Based

Definition:

- trigger anomaly using hand-crafted rules such as `KPI anomalous OR log score > high threshold`

Strengths:

- easy to explain
- useful when hard safety rules are required

Weaknesses:

- produces brittle decisions
- discards score granularity
- difficult to calibrate fairly across experiments

### Voting

Definition:

- each source casts a binary anomaly vote and the final decision follows majority or tie rules

Strengths:

- extremely simple
- robust when only labels are available

Weaknesses:

- wastes anomaly score information
- two-source settings create frequent ties
- tie-breaking introduces additional policy choices

## 12. Recommended strategy for this dissertation with justification

Recommended strategy: **WeightedAverageStrategy**

Recommended default configuration:

- `kpi_weight = 0.50`
- `log_weight = 0.50`

Justification:

- Weighted-average fusion preserves continuous anomaly intensity from both sources.
- It is transparent, reproducible, and easy to analyze in ablation studies.
- It supports sensitivity analysis through configuration-only changes to weights.
- It avoids assuming strong per-record confidence calibration from the KPI Source.
- It is stronger than voting in a two-source architecture because it preserves score granularity.
- It provides a production-suitable baseline because its behavior is predictable, auditable, and tunable.

Architectural note:

The default values are intentionally balanced rather than hardcoded into business logic. Users can change source weights through configuration without changing code. This enables dissertation experimentation, future tuning, and environment-specific calibration.

Availability-aware adjustment:

- if both sources are available, use the configured weights
- if one source is missing, assign effective weight `1.0` to the available source through availability-aware renormalization

## 13. Final anomaly score calculation

Primary fused score:

$$
S_{fusion} = \frac{w_k a_k s'_k + w_l a_l s'_l}{w_k a_k + w_l a_l + \epsilon}
$$

Where:

- $s'_k$ is normalized `kpi_score`
- $s'_l$ is normalized `log_score`
- $w_k$ is configured `kpi_weight`
- $w_l$ is configured `log_weight`
- $a_k \in \{0,1\}$ is `kpi_available`
- $a_l \in \{0,1\}$ is `log_available`

Interpretation:

- if both sources are present, the score is a configured weighted combination
- if one source is absent, the denominator renormalizes to the available source only
- if both are absent, no fused score is generated

Window-level source aggregation before fusion:

- KPI window score: aggregated normalized KPI anomaly score in the window, computed by the configured aggregation strategy
- Log window score: aggregated normalized log anomaly score in the window, computed by the configured aggregation strategy

Source contribution reporting:

Every fused prediction must include:

- `kpi_weight`
- `log_weight`
- `kpi_contribution`
- `log_contribution`

Contribution interpretation:

- `kpi_contribution` represents the weighted contribution of the KPI Source to the final fused score
- `log_contribution` represents the weighted contribution of the Log Source to the final fused score

These fields improve explainability and help analysts understand how much each anomaly source influenced the final decision.

## 14. Final anomaly label generation

The architecture separates fused score computation from decision making.

Pipeline stage progression:

Fusion Strategy
↓
Decision Engine
↓
Artifact Writer

Decision Engine responsibilities:

- apply configurable threshold
- produce final anomaly label
- generate decision reason
- attach decision metadata

Threshold configuration:

- configuration field: `threshold`
- default: `0.60`

Threshold must be configurable without changing code.

Recommended decision rule:

$$
L_{fusion} =
\begin{cases}
1 & \text{if } S_{fusion} \ge \tau_f \\
0 & \text{otherwise}
\end{cases}
$$

Where $\tau_f$ is the configured threshold.

Label semantics:

- `1`: fused anomaly
- `0`: fused normal

Decision metadata to attach per fused row:

- `fused_score`
- `final_label`
- `kpi_score_normalized`
- `log_score_normalized`
- `kpi_available`
- `log_available`
- `fusion_strategy`
- `decision_threshold`
- `decision_reason`
- `decision_metadata`

Recommended `decision_reason` values:

- `weighted_fusion_threshold_exceeded`
- `weighted_fusion_below_threshold`
- `kpi_only_window`
- `log_only_window`

## 15. Experiment artifacts produced

Phase 7 should produce the following artifacts:

- `artifacts/phase7/experiments/<experiment_id>/reports/fusion_inputs.csv`
- `artifacts/phase7/experiments/<experiment_id>/reports/aligned_windows.csv`
- `artifacts/phase7/experiments/<experiment_id>/reports/normalized_scores.csv`
- `artifacts/phase7/experiments/<experiment_id>/reports/fused_predictions.csv`
- `artifacts/phase7/experiments/<experiment_id>/reports/fusion_summary.json`
- `artifacts/phase7/experiments/<experiment_id>/reports/source_coverage.json`
- `artifacts/phase7/experiments/<experiment_id>/plots/fused_score_histogram.png`
- `artifacts/phase7/experiments/<experiment_id>/plots/fused_score_timeseries.png`
- `artifacts/phase7/experiments/<experiment_id>/manifests/phase7_manifest.json`

Purpose of `fusion_inputs.csv`:

- capture complete fusion inputs before normalization and fusion
- provide a transparent handoff between ingestion and later decision stages
- improve debugging, traceability, reproducibility, and dissertation analysis
- allow auditors to verify source availability and missing-data handling independently of final fused decisions

Suggested fields for `fusion_inputs.csv`:

- `window_ts`
- `window_end_ts`
- `entity_id`
- `kpi_raw_score`
- `log_raw_score`
- `kpi_available`
- `log_available`
- `missing_reason`

Recommended content of `fused_predictions.csv`:

- `window_ts`
- `window_end_ts`
- `entity_id`
- `kpi_score`
- `log_score`
- `kpi_score_normalized`
- `log_score_normalized`
- `kpi_available`
- `log_available`
- `kpi_weight`
- `log_weight`
- `kpi_contribution`
- `log_contribution`
- `fused_score`
- `final_label`
- `decision_reason`

Recommended content of `phase7_manifest.json`:

- manifest version
- generation timestamp
- experiment id
- KPI Detector Experiment ID
- Log Detector Experiment ID
- input artifact locations
- output artifact locations
- fusion strategy
- configured weights
- configured threshold
- configured window size
- normalization strategy
- coverage statistics
- experiment summary metadata

Manifest rationale:

The expanded manifest improves experiment reproducibility and auditability by capturing the exact upstream detector lineage, configuration state, strategy selection, and artifact locations used to produce a fusion run.

## 16. ASCII UML Component Diagram

```text
+---------------------+
|    fusion_config    |
+----------+----------+
           |
           v
+---------------------+      +---------------------+
|   source_manager    |----->|    fusion_ingest    |
+----------+----------+      +----------+----------+
           |                            |
           v                            v
+---------------------+      +---------------------+
|  fusion_validator   |----->|    fusion_mapper    |
+----------+----------+      +----------+----------+
           |                            |
           v                            v
+---------------------+      +---------------------+
| timestamp_aligner   |----->|  score_aggregator   |
+----------+----------+      +----------+----------+
           v                            v
+---------------------+      +---------------------+
|aggregation_strategy |----->| missing_data_handler|
+----------+----------+      +----------+----------+
           |                            |
           +-------------+--------------+
                         |
                         v
              +--------------------------+
              |    score_normalizer      |
              | -> NormalizationStrategy |
              +------------+-------------+
                           |
                           v
              +--------------------------+
              |     fusion_strategy      |
              |    -> FusionStrategy     |
              +------------+-------------+
                           |
                           v
              +--------------------------+
              |     decision_engine      |
              +------------+-------------+
                           |
                           v
              +--------------------------+
              |     artifact_writer      |
              +------------+-------------+
                           ^
                           |
              +--------------------------+
              |   fusion_orchestrator    |
              +--------------------------+

Strategy Extension Points:
  FusionStrategy:
    - WeightedAverageStrategy
    - ConfidenceWeightedStrategy
    - ThresholdStrategy
    - VotingStrategy

  AggregationStrategy:
    - MaxAggregation
    - MeanAggregation
    - MedianAggregation

  NormalizationStrategy:
    - MinMaxNormalization
    - ZScoreNormalization
    - IdentityNormalization

External Dependencies:
  KPI Source Outputs -----> fusion_ingest
  Log Source Manifest ----> fusion_ingest
  Log Source Predictions -> fusion_ingest
```

## 17. ASCII Sequence Diagram

```text
KPI Source   Log Detector Manifest   Fusion Orchestrator   Validator   Mapper   Aligner   Aggregator   Normalizer   Fusion Strategy   Decision Engine   Writer
  |                |                    |                 |          |         |            |            |               |                 |            |
  |                |                    |                 |          |         |            |            |               |                 |            |
  |--------------->|                    |                 |          |         |            |            |               |                 |            |
  |                |------------------->|                 |          |         |            |            |               |                 |            |
  |                |                    |--load config--> |          |         |            |            |               |                 |            |
  |                |                    |--init modules------------------------------------------------------------------------------------->|
  |                |                    |--ingest source artifacts-------------------------------------------------------------------------->|
  |                |                    |----------------> |          |         |            |            |               |                 |            |
  |                |                    |<---------------validation report--------|            |            |               |                 |            |
  |                |                    |--------------------------->|            |            |            |               |                 |            |
  |                |                    |<-----------------------FusionRecord set-|            |            |               |                 |            |
  |                |                    |--------------------------------------->|            |            |               |                 |            |
  |                |                    |<----------------------aligned records---|            |            |               |                 |            |
  |                |                    |----------------------------------------------------->|            |               |                 |            |
  |                |                    |<-------------------aggregated records---------------|            |               |                 |            |
  |                |                    |----------------------------------------------------------------->|               |                 |            |
  |                |                    |<----------------------normalized records-------------------------|               |                 |            |
  |                |                    |---------------------------------------------------------------------------------->|                 |            |
  |                |                    |<-------------------------fused scores and contributions--------------------------|                 |            |
  |                |                    |---------------------------------------------------------------------------------------------------->|            |
  |                |                    |<-------------------------labels and decision metadata-------------------------------------------|            |
  |                |                    |----------------------------------------------------------------------------------------------------------------->|
  |                |                    |<--------------------------------artifact paths and manifest--------------------------------------|
```

## 18. Complete execution pipeline

1. Load Phase 7 configuration.
2. Start the Phase 7 experiment context.
3. Resolve KPI Source prediction artifact path.
4. Resolve Log Source manifest path.
5. Read the Log Detector Manifest and locate canonical prediction artifacts.
6. Load both source prediction tables.
7. Validate schemas, timestamp fields, score fields, labels, and source metadata.
8. Map source records into source-level `FusionRecord` instances.
9. Bucket records into the configured `window_size`.
10. Apply the configured aggregation strategy to summarize KPI Source records within each window.
11. Apply the configured aggregation strategy to summarize Log Source records within each window.
12. Construct one aligned window-level `FusionRecord` with source availability flags.
13. Write `fusion_inputs.csv` as the pre-normalization traceability artifact.
14. Apply missing-data policy.
15. Normalize `kpi_score` and `log_score` through the configured normalization strategy.
16. Apply the configured fusion strategy to compute `fused_score`, `kpi_contribution`, and `log_contribution`.
17. Pass fused records to the Decision Engine.
18. Apply the configured threshold to generate `final_label` and decision metadata.
19. Write fused predictions, coverage diagnostics, summary reports, plots, metrics, and manifest.
20. Finalize experiment reports.

Fusion Orchestrator responsibilities are intentionally limited to:

- load configuration
- initialize modules
- coordinate pipeline execution
- invoke each pipeline stage
- invoke artifact writing

The Fusion Orchestrator must not contain:

- normalization logic
- fusion calculations
- decision logic
- business rules

## 19. Risks and design considerations

- Timestamp granularity mismatch can create false disagreement between sources.
- If the Log Source timestamps are not directly available in prediction outputs, upstream sequence-to-time derivation must be consistent and documented.
- Score distributions may shift across experiments, making normalization sensitive to outliers.
- Aggregation strategy selection changes anomaly sensitivity within each window and must therefore remain explicit and auditable.
- If the KPI Source and Log Source cover different operational scopes, timestamp-only alignment may over-associate unrelated events.
- Missing-source windows can bias summary metrics if not reported separately.
- Strategy selection must remain configuration-driven so that experimentation and production tuning do not require architecture changes.
- Threshold calibration must be evaluated empirically and then frozen per experiment or deployment profile.
- Future additional sources may require stronger entity-correlation policies beyond timestamp alignment alone.

## 20. Assumptions

- The KPI Detector and Log Detector are frozen and are not modified by Phase 7.
- Both detectors expose machine-readable anomaly scores.
- Both detectors expose or can be mapped to timestamps.
- All timestamps can be converted to a consistent timezone.
- Log Source predictions are discoverable through the published Detector Manifest.
- KPI Source predictions are available in a stable artifact format.
- A single fused window is an acceptable evaluation unit for the dissertation and a reasonable correlation unit for the baseline production architecture.
- Configuration remains the authoritative control surface for strategy, weighting, thresholding, and windowing behavior.

## 21. Future extensibility

The Phase 7 design should support future expansion without architectural redesign.

Planned extension points include:

- additional anomaly sources
- additional aggregation strategies
- additional fusion strategies
- additional normalization strategies
- learnable fusion
- explainability modules
- richer entity-correlation policies
- multiple window-size profiles
- late-fusion benchmarking under a single orchestrator

Extensibility rationale:

- additional anomaly sources can be added through source management, source mapping, and strategy compatibility
- additional aggregation strategies can be introduced by extending `AggregationStrategy` without changing alignment, normalization, fusion, or decision components
- additional fusion strategies can be introduced by extending `FusionStrategy` without changing orchestration, ingestion, or decision components
- additional normalization strategies can be introduced by extending `NormalizationStrategy` without changing fusion logic
- learnable fusion can replace configuration-based weighting when labeled data and calibration maturity justify it
- explainability modules can consume `FusionRecord`, contribution fields, and decision metadata without requiring redesign of the execution pipeline

The architecture keeps source ingestion, alignment, normalization, fusion, decisioning, and artifact generation separate so future methods can be substituted independently while preserving experiment reproducibility, auditability, and stable artifact contracts.
