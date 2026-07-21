"""Centralized configuration loader for Phase 6.

This module implements the `Config` dataclass and `ConfigLoader` described in
the frozen Phase 6 blueprint. It provides deterministic loading of a JSON or
YAML configuration file, optional overrides, and strict validation of values.

Only the public classes and methods declared in the blueprint are exposed.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
import json
import logging

logger = logging.getLogger("project")


class ConfigurationError(RuntimeError):
    """Raised when configuration is missing, invalid, or cannot be loaded.

    This is a domain-specific exception matching the Phase 6 blueprint.
    """


@dataclass(frozen=True)
class Config:
    """Runtime configuration for Phase 6.

    All fields have blueprint-defined defaults. Implementations must obtain
    configuration only via instances of this dataclass.
    """

    learning_rate: float = 0.001
    batch_size: int = 256
    epochs: int = 10
    optimizer: str = "adam"
    scheduler: Optional[str] = None
    dropout: float = 0.2
    hidden_size: int = 128
    embedding_dim: int = 128
    sequence_length: int = 50
    top_k: int = 5
    threshold: Optional[float] = None
    random_seed: int = 42
    artifact_root: str = "artifacts/phase6"
    experiment_root: str = "artifacts/phase6/experiments"
    logging_level: str = "INFO"
    device: str = "cpu"
    pad_token: int = 0
    vocab_unknown_token: int = 0
    num_workers: int = 4
    checkpoint_interval_epochs: int = 1
    max_checkpoints: int = 5
    save_format: str = "bin"
    git_info_source: Optional[str] = None
    notes: Optional[str] = None


class ConfigLoader:
    """Load and validate a Phase 6 configuration.

    Parameters
    ----------
    config_path:
        Path to a JSON or YAML configuration file. If ``None``, defaults are
        used and any provided ``overrides`` are applied.
    overrides:
        Optional mapping of configuration keys to override values. These
        values take precedence over file values.
    """

    def __init__(self, config_path: Optional[str | Path] = None, overrides: Optional[Dict[str, Any]] = None) -> None:
        self.config_path: Optional[Path] = Path(config_path) if config_path is not None else None
        self.overrides: Dict[str, Any] = dict(overrides) if overrides else {}

    def load(self) -> Config:
        """Load, merge, validate, and return a `Config` instance.

        The precedence is: defaults < file values < `overrides`.

        Returns
        -------
        Config
            Validated configuration dataclass.

        Raises
        ------
        ConfigurationError
            If parsing fails or validation constraints are violated.
        """
        # Start with blueprint defaults by creating a Config instance
        base = Config()
        config_data: Dict[str, Any] = {k: getattr(base, k) for k in base.__dataclass_fields__}

        # Load file values if a path was provided
        if self.config_path is not None:
            if not self.config_path.exists():
                msg = f"Configuration file not found: {self.config_path}"
                logger.error(msg)
                raise ConfigurationError(msg)
            try:
                file_values = self._read_config_file(self.config_path)
            except Exception as exc:  # narrow below but keep to report parsing errors
                logger.exception("Failed to read configuration file")
                raise ConfigurationError(f"Failed to read configuration file: {exc}") from exc
            # Merge
            config_data.update(file_values)

        # Apply overrides (highest precedence)
        if self.overrides:
            config_data.update(self.overrides)

        # Validate and coerce types where appropriate
        validated = self._validate_and_coerce(config_data)

        # Create Config dataclass (frozen)
        return Config(**validated)

    def _read_config_file(self, path: Path) -> Dict[str, Any]:
        """Read JSON or YAML config file and return mapping of values.

        Supports JSON natively. YAML is supported when `yaml` is importable; if
        not available a ConfigurationError is raised for YAML files.
        """
        suffix = path.suffix.lower()
        if suffix in {".json"}:
            with path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        if suffix in {".yml", ".yaml"}:
            try:
                import yaml  # type: ignore
            except Exception as exc:
                msg = (
                    "PyYAML is required to load YAML configuration files. "
                    "Install with `pip install pyyaml` or provide JSON config."
                )
                logger.error(msg)
                raise ConfigurationError(msg) from exc
            with path.open("r", encoding="utf-8") as fh:
                return yaml.safe_load(fh) or {}
        raise ConfigurationError(f"Unsupported configuration file type: {suffix}")

    def _validate_and_coerce(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Validate configuration keys and coerce to proper types.

        Performs bounds checks and returns a mapping ready to pass into the
        `Config` dataclass.
        """
        validated: Dict[str, Any] = {}

        def get(key: str, expected_type: type, default: Any = None):
            value = raw.get(key, default)
            if value is None:
                return None
            if not isinstance(value, expected_type):
                # Allow ints where floats are expected
                if expected_type is float and isinstance(value, int):
                    return float(value)
                try:
                    return expected_type(value)
                except Exception:
                    raise ConfigurationError(f"Invalid type for '{key}': expected {expected_type.__name__}, got {type(value).__name__}")
            return value

        # Numeric and simple fields
        validated["learning_rate"] = get("learning_rate", float, 0.001)
        validated["batch_size"] = get("batch_size", int, 256)
        validated["epochs"] = get("epochs", int, 10)
        validated["optimizer"] = get("optimizer", str, "adam")
        validated["scheduler"] = raw.get("scheduler", None)
        validated["dropout"] = get("dropout", float, 0.2)
        validated["hidden_size"] = get("hidden_size", int, 128)
        validated["embedding_dim"] = get("embedding_dim", int, 128)
        validated["sequence_length"] = get("sequence_length", int, 50)
        validated["top_k"] = get("top_k", int, 5)
        validated["threshold"] = raw.get("threshold", None)
        validated["random_seed"] = get("random_seed", int, 42)

        # Paths and environment-related fields
        validated["artifact_root"] = str(raw.get("artifact_root", "artifacts/phase6"))
        validated["experiment_root"] = str(raw.get("experiment_root", f"{validated['artifact_root']}/experiments"))
        validated["logging_level"] = str(raw.get("logging_level", "INFO"))
        validated["device"] = str(raw.get("device", "cpu"))

        validated["pad_token"] = get("pad_token", int, 0)
        validated["vocab_unknown_token"] = get("vocab_unknown_token", int, 0)
        validated["num_workers"] = get("num_workers", int, 4)
        validated["checkpoint_interval_epochs"] = get("checkpoint_interval_epochs", int, 1)
        validated["max_checkpoints"] = get("max_checkpoints", int, 5)
        validated["save_format"] = str(raw.get("save_format", "bin"))
        validated["git_info_source"] = raw.get("git_info_source", None)
        validated["notes"] = raw.get("notes", None)

        # Sanity checks
        if validated["learning_rate"] <= 0.0:
            raise ConfigurationError("learning_rate must be > 0")
        if validated["batch_size"] <= 0:
            raise ConfigurationError("batch_size must be > 0")
        if validated["epochs"] <= 0:
            raise ConfigurationError("epochs must be > 0")
        if not (0.0 <= validated["dropout"] < 1.0):
            raise ConfigurationError("dropout must be in [0.0, 1.0)")
        if validated["sequence_length"] <= 0:
            raise ConfigurationError("sequence_length must be > 0")
        if validated["top_k"] <= 0:
            raise ConfigurationError("top_k must be > 0")
        if validated["num_workers"] < 0:
            raise ConfigurationError("num_workers must be >= 0")
        if validated["checkpoint_interval_epochs"] <= 0:
            raise ConfigurationError("checkpoint_interval_epochs must be > 0")
        if validated["max_checkpoints"] < 0:
            raise ConfigurationError("max_checkpoints must be >= 0")

        # If threshold provided, ensure it is between 0 and 1
        if validated["threshold"] is not None:
            try:
                tval = float(validated["threshold"])
            except Exception:
                raise ConfigurationError("threshold must be numeric between 0 and 1")
            if not (0.0 <= tval <= 1.0):
                raise ConfigurationError("threshold must be in [0.0, 1.0]")
            validated["threshold"] = tval

        # Ensure save_format is a non-empty string
        if not isinstance(validated["save_format"], str) or not validated["save_format"].strip():
            raise ConfigurationError("save_format must be a non-empty string")

        # Finalize artifact and experiment roots as strings
        validated["artifact_root"] = str(validated["artifact_root"])
        validated["experiment_root"] = str(validated["experiment_root"])

        return validated

    __all__ = ["ConfigurationError", "Config", "ConfigLoader"]
