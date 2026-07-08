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
    reports_dir: str = "reports"
    logs_dir: str = "data/logs"


class LoggingSettings(BaseModel):
    """Logging setup configuration."""

    level: str = "INFO"
    config_file: str = "config/logging.yaml"


class AppSettings(BaseModel):
    """Top-level validated settings model."""

    project: ProjectSettings = Field(default_factory=ProjectSettings)
    paths: PathSettings = Field(default_factory=PathSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)


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
    """Load simple KEY=VALUE pairs from a local .env file if present.

    This keeps the project dependency-free while still allowing a convenient
    local override file for environment settings.
    """

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
    """Load validated settings from YAML and environment overrides.

    Environment variables are optional and follow:
    - WILP_ENVIRONMENT
    - WILP_RANDOM_SEED
    - WILP_LOG_LEVEL
    """

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
