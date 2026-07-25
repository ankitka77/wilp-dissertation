"""Helpers for creating, validating, and cleaning up test artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence
import csv
import json
import shutil

import yaml

from tests.helpers.fixture_builders import (
    build_kpi_prediction_records,
    build_log_manifest,
    build_log_prediction_records,
)


def ensure_directory(path: str | Path) -> Path:
    """Create a directory if needed and return it."""

    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def create_experiment_layout(
    root_dir: str | Path,
    *,
    experiment_id: str = "experiment_001",
) -> dict[str, Path]:
    """Create a deterministic experiment artifact layout for tests."""

    root = ensure_directory(root_dir) / experiment_id
    reports = ensure_directory(root / "reports")
    plots = ensure_directory(root / "plots")
    manifests = ensure_directory(root / "manifests")
    return {
        "root": root,
        "reports": reports,
        "plots": plots,
        "manifests": manifests,
    }


def write_csv_records(path: str | Path, records: Sequence[Mapping[str, Any]]) -> Path:
    """Write records to CSV and return the path."""

    csv_path = Path(path)
    ensure_directory(csv_path.parent)
    if not records:
        raise ValueError("CSV record set must not be empty")
    fieldnames = list(records[0].keys())
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(dict(record))
    return csv_path


def write_json_file(path: str | Path, payload: Mapping[str, Any]) -> Path:
    """Write a JSON artifact and return the path."""

    json_path = Path(path)
    ensure_directory(json_path.parent)
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return json_path


def write_yaml_file(path: str | Path, payload: Mapping[str, Any]) -> Path:
    """Write a YAML artifact and return the path."""

    yaml_path = Path(path)
    ensure_directory(yaml_path.parent)
    with yaml_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(dict(payload), handle, sort_keys=False)
    return yaml_path


def create_phase7_sample_bundle(base_dir: str | Path) -> dict[str, Path]:
    """Create a complete synthetic bundle of Phase 7 input artifacts."""

    base_path = ensure_directory(base_dir)
    kpi_path = write_csv_records(base_path / "sample_kpi_predictions.csv", build_kpi_prediction_records())
    log_path = write_csv_records(base_path / "sample_log_predictions.csv", build_log_prediction_records())
    manifest_payload = build_log_manifest(predictions_path=str(log_path).replace("\\", "/"))
    manifest_path = write_json_file(base_path / "sample_manifest.json", manifest_payload)
    return {
        "kpi_predictions": kpi_path,
        "log_predictions": log_path,
        "manifest": manifest_path,
    }


def cleanup_path(path: str | Path) -> None:
    """Remove a file or directory tree if it exists."""

    target = Path(path)
    if not target.exists():
        return
    if target.is_dir():
        shutil.rmtree(target)
        return
    target.unlink()


__all__ = [
    "cleanup_path",
    "create_experiment_layout",
    "create_phase7_sample_bundle",
    "ensure_directory",
    "write_csv_records",
    "write_json_file",
    "write_yaml_file",
]