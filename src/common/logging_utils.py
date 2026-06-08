"""Logging bootstrap utilities for the project."""

from __future__ import annotations

import logging
import logging.config
from pathlib import Path
from typing import Any

import yaml

DEFAULT_LOGGER_NAME = "project"


def _load_logging_dict(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    if not isinstance(config, dict):
        raise ValueError(f"Invalid logging configuration in {config_path}")
    return config


def configure_logging(config_path: str | Path = "config/logging.yaml") -> logging.Logger:
    """Configure process logging and return the project logger."""

    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Logging config file not found: {path}")

    config = _load_logging_dict(path)

    # Ensure file-based handlers can be created before dictConfig runs.
    handlers = config.get("handlers", {})
    file_handler = handlers.get("file", {})
    file_name = file_handler.get("filename")
    if isinstance(file_name, str):
        Path(file_name).parent.mkdir(parents=True, exist_ok=True)

    logging.config.dictConfig(config)
    return logging.getLogger(DEFAULT_LOGGER_NAME)
