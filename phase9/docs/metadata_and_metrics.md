# Phase 9 — Metadata Aggregation and Metrics

This document describes the `MetadataAggregator` and `MetricsCollector` modules implemented for Phase 9.

Metadata Aggregator
- Module: `phase9.aggregator.aggregator.MetadataAggregator`
- Purpose: consume `ArtifactRegistry` (authoritative registry) and produce `metadata_summary.json` containing project metadata, phase summaries, lineage and completeness statistics.
- Output: `artifacts/phase9/latest/metadata_summary.json`

Metrics & Statistics Collector
- Module: `phase9.metrics.collector.MetricsCollector`
- Purpose: compute project-wide metrics (artifact counts, per-phase counts, type distributions, validation statistics, file size statistics) and write `metrics_summary.json` and `project_statistics.json`.
- Output: `artifacts/phase9/latest/metrics_summary.json`, `project_statistics.json`

Integration
- Both modules are invoked by `Phase9Pipeline` after `ArtifactRegistry.persist()` and are exercised via the `aggregate` CLI command on `phase9_runner.py`.

Design notes
- The modules are read-only with respect to upstream artifact directories and only write outputs to the Phase 9 output directory.
- Data models use Pydantic for strong typing and validation.
