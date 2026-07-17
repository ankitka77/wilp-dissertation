"""Project configuration management for Phase 1 setup."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ProjectSettings(BaseModel):
    """Global project metadata and runtime controls."""

    name: str = "anomaly-fault-detection-wireless"
    environment: str = "development"
    random_seed: int = 42


class PathSettings(BaseModel):
    """Relative paths used by pipelines and reports."""

    data_dir: str = "data"
    logs_dir: str = "data/logs"


class LoggingSettings(BaseModel):
    """Logging setup configuration."""

    level: str = "INFO"
    config_file: str = "config/logging.yaml"


class ArtifactSettings(BaseModel):
    """Centralized runtime artifact configuration for all phases."""

    root: str = "artifacts"
    reports_root: str = "artifacts/reports"
    models_root: str = "artifacts/models"
    experiments_root: str = "artifacts/experiments"
    plots_root: str = "artifacts/plots"

    def phase_report_dir(self, phase_name: str) -> Path:
        """Return the report directory for a specific phase."""
        return Path(self.reports_root) / phase_name


class FeatureEngineeringSettings(BaseModel):
    """Configuration for KPI feature engineering."""

    lag_values: list[int] = Field(default_factory=lambda: [1, 3, 5, 10])
    rolling_windows: list[int] = Field(default_factory=lambda: [5, 10, 20])
    ema_periods: list[int] = Field(default_factory=lambda: [5, 10, 20])
    normalize: bool = False
    missing_strategy: str = "forward_fill"
    include_timestamp_features: bool = True


class Phase4Settings(BaseModel):
    """Configuration for Phase 4 anomaly detection."""

    n_estimators: int = 100
    contamination: float = 0.05
    max_samples: str | int = "auto"
    bootstrap: bool = False
    random_state: int = 42
    dataset_version: str = "phase3"
    git_branch: str = "local"
    git_commit: str = "unknown"
    git_tag: str | None = None


class Phase5Settings(BaseModel):
    """Configuration for Phase 5 log processing."""

    dataset_type: str = "hdfs"
    input_dir: str = "data/logs/HDFS_v1"
    parser_mode: str = "auto"
    sequence_mode: str = "auto"
    window_size: int = 10
    stride: int = 1
    min_sequence_length: int = 1
    max_sequence_length: int = 1000000
    train_ratio: float = 0.8
    include_dataset_fingerprint: bool = True


class AppSettings(BaseModel):
    """Top-level validated settings model."""

    project: ProjectSettings = Field(default_factory=ProjectSettings)
    paths: PathSettings = Field(default_factory=PathSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    artifacts: ArtifactSettings = Field(default_factory=ArtifactSettings)
    feature_engineering: FeatureEngineeringSettings = Field(default_factory=FeatureEngineeringSettings)
    phase4: Phase4Settings = Field(default_factory=Phase4Settings)
    phase5: Phase5Settings = Field(default_factory=Phase5Settings)


DEFAULT_CONFIG_FILE = Path("config/settings.yaml")
DEFAULT_DOTENV_FILE = Path(".env")


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected mapping in config file: {path}")
    return loaded


def _load_dotenv_file(path: Path = DEFAULT_DOTENV_FILE) -> None:
    """Load simple KEY=VALUE pairs from a local .env file if present."""

    if not path.exists():
        return

    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')

            if key and key not in os.environ:
                os.environ[key] = value


def load_settings(config_path: str | Path | None = None) -> AppSettings:
    """Load validated settings from YAML and environment overrides."""

    _load_dotenv_file()

    cfg_path = Path(config_path) if config_path else DEFAULT_CONFIG_FILE
    data = _read_yaml(cfg_path)
    settings = AppSettings.model_validate(data)

    environment = os.getenv("WILP_ENVIRONMENT")
    random_seed = os.getenv("WILP_RANDOM_SEED")
    log_level = os.getenv("WILP_LOG_LEVEL")

    if environment:
        settings.project.environment = environment
    if random_seed:
        settings.project.random_seed = int(random_seed)
    if log_level:
        settings.logging.level = log_level.upper()

    return settings
