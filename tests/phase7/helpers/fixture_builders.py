"""Reusable builders for Phase 7 test fixtures and sample records."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


def build_phase7_config(overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return a representative full Phase 7 configuration dictionary."""

    config: dict[str, Any] = {
        "fusion": {
            "strategy": "weighted_average",
            "kpi_weight": 0.50,
            "log_weight": 0.50,
            "threshold": 0.60,
            "window_size": "5m",
            "normalization_strategy": "min_max",
        },
        "aggregation": {
            "strategy": "max",
        },
        "logging": {
            "level": "INFO",
            "enable_debug_artifacts": False,
        },
        "artifacts": {
            "root_dir": "artifacts/phase7",
            "retain_intermediate": True,
        },
        "validation": {
            "strict": True,
            "allow_row_drops": False,
        },
        "sources": {
            "kpi": {
                "source_type": "KPI",
                "predictions_path": "tests/phase7/sample_data/sample_kpi_predictions.csv",
                "required_fields": ["timestamp", "anomaly_score", "prediction"],
                "entity_key": "KPI ID",
            },
            "log": {
                "source_type": "LOG",
                "manifest_path": "tests/phase7/sample_data/sample_manifest.json",
                "predictions_key": "predictions",
                "required_fields": [
                    "timestamp",
                    "anomaly_score",
                    "is_anomaly",
                    "prediction_confidence",
                ],
            },
        },
        "extensions": {},
    }
    return _apply_overrides(config, overrides)


def build_minimal_config(overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return a minimal configuration that still validates through defaults."""

    config: dict[str, Any] = {
        "fusion": {
            "threshold": 0.55,
            "window_size": "1m",
        }
    }
    return _apply_overrides(config, overrides)


def build_invalid_config(overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return an intentionally invalid configuration for failure-path tests."""

    config: dict[str, Any] = {
        "fusion": {
            "strategy": "unsupported_strategy",
            "kpi_weight": -0.10,
            "log_weight": 0.00,
            "threshold": 1.50,
            "window_size": "0m",
            "normalization_strategy": "unknown",
        },
        "aggregation": {
            "strategy": "average",
        },
        "logging": {
            "level": "TRACE",
            "enable_debug_artifacts": "no",
        },
    }
    return _apply_overrides(config, overrides)


def build_kpi_prediction_records() -> list[dict[str, Any]]:
    """Return realistic KPI prediction records spanning multiple windows."""

    return [
        {
            "timestamp": "2026-01-01T00:00:30Z",
            "KPI ID": "KPI-CPU-01",
            "anomaly_score": 0.12,
            "prediction": 0,
        },
        {
            "timestamp": "2026-01-01T00:02:10Z",
            "KPI ID": "KPI-CPU-01",
            "anomaly_score": 0.88,
            "prediction": 1,
        },
        {
            "timestamp": "2026-01-01T00:04:55Z",
            "KPI ID": "KPI-MEM-01",
            "anomaly_score": 0.65,
            "prediction": 1,
        },
        {
            "timestamp": "2026-01-01T00:07:05Z",
            "KPI ID": "KPI-CPU-01",
            "anomaly_score": 0.18,
            "prediction": 0,
        },
        {
            "timestamp": "2026-01-01T00:09:40Z",
            "KPI ID": "KPI-MEM-01",
            "anomaly_score": 0.91,
            "prediction": 1,
        },
    ]


def build_log_prediction_records() -> list[dict[str, Any]]:
    """Return realistic log prediction records spanning multiple windows."""

    return [
        {
            "timestamp": "2026-01-01T00:00:45Z",
            "id": "log-001",
            "session_id": "session-A",
            "block_id": "blk-001",
            "anomaly_score": 0.15,
            "is_anomaly": 0,
            "prediction_confidence": 0.92,
        },
        {
            "timestamp": "2026-01-01T00:03:20Z",
            "id": "log-002",
            "session_id": "session-A",
            "block_id": "blk-001",
            "anomaly_score": 0.72,
            "is_anomaly": 1,
            "prediction_confidence": 0.61,
        },
        {
            "timestamp": "2026-01-01T00:04:15Z",
            "id": "log-003",
            "session_id": "session-B",
            "block_id": "blk-003",
            "anomaly_score": 0.56,
            "is_anomaly": 1,
            "prediction_confidence": 0.70,
        },
        {
            "timestamp": "2026-01-01T00:08:10Z",
            "id": "log-004",
            "session_id": "session-A",
            "block_id": "blk-002",
            "anomaly_score": 0.20,
            "is_anomaly": 0,
            "prediction_confidence": 0.89,
        },
        {
            "timestamp": "2026-01-01T00:09:50Z",
            "id": "log-005",
            "session_id": "session-C",
            "block_id": "blk-005",
            "anomaly_score": 0.94,
            "is_anomaly": 1,
            "prediction_confidence": 0.44,
        },
    ]


def build_log_manifest(
    predictions_path: str = "tests/phase7/sample_data/sample_log_predictions.csv",
) -> dict[str, Any]:
    """Return a representative published Log Detector manifest."""

    return {
        "manifest_version": "1.0",
        "generated_on": "2026-01-01T00:10:00Z",
        "experiment_id": "log-detector-exp-001",
        "detector": {
            "name": "Log Detector",
            "source_type": "LOG",
        },
        "artifacts": {
            "predictions": predictions_path,
        },
        "config_snapshot": {
            "top_k": 5,
            "threshold": 0.60,
        },
    }


def build_fusion_record(overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return a canonical FusionRecord-shaped dictionary for future tests."""

    record: dict[str, Any] = {
        "window_ts": "2026-01-01T00:00:00Z",
        "window_end_ts": "2026-01-01T00:05:00Z",
        "entity_id": "entity-001",
        "source_type": "KPI",
        "source_record_id": "src-001",
        "kpi_score": 0.88,
        "log_score": 0.72,
        "kpi_available": True,
        "log_available": True,
        "kpi_score_normalized": 0.88,
        "log_score_normalized": 0.72,
        "kpi_weight": 0.50,
        "log_weight": 0.50,
        "kpi_contribution": 0.44,
        "log_contribution": 0.36,
        "fused_score": 0.80,
        "final_label": 1,
        "decision_reason": "weighted_fusion_threshold_exceeded",
        "decision_metadata": {
            "decision_threshold": 0.60,
            "fusion_strategy": "weighted_average",
        },
        "source_metadata": {
            "lineage": "synthetic",
            "record_count": 1,
        },
    }
    return _apply_overrides(record, overrides)


def build_sample_timestamps() -> list[str]:
    """Return reusable timestamps for deterministic windowing tests."""

    return [
        "2026-01-01T00:00:00Z",
        "2026-01-01T00:01:00Z",
        "2026-01-01T00:04:59Z",
        "2026-01-01T00:05:00Z",
        "2026-01-01T00:09:59Z",
    ]


def _apply_overrides(base: dict[str, Any], overrides: Mapping[str, Any] | None) -> dict[str, Any]:
    if not overrides:
        return deepcopy(base)

    merged = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(merged.get(key), dict) and isinstance(value, Mapping):
            merged[key] = _apply_overrides(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


__all__ = [
    "build_fusion_record",
    "build_invalid_config",
    "build_kpi_prediction_records",
    "build_log_manifest",
    "build_log_prediction_records",
    "build_minimal_config",
    "build_phase7_config",
    "build_sample_timestamps",
]