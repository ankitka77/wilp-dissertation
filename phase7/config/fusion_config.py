"""Configuration management for the Phase 7 Fusion Engine.

This module implements the frozen configuration contract defined by the
Phase 7 architecture and design documents. It provides deterministic loading
from JSON or YAML, layered override merging, strict validation, immutable
section objects, and snapshot export for reproducibility.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import timedelta
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, Mapping, MutableMapping
import json
import logging
import re

logger = logging.getLogger("project")


class FusionConfigError(RuntimeError):
    """Base exception raised for Fusion Engine configuration failures."""


class FusionConfigLoadError(FusionConfigError):
    """Raised when configuration cannot be loaded from the configured source."""


class FusionConfigValidationError(FusionConfigError):
    """Raised when loaded configuration violates the frozen contract."""


class FusionStrategyName(str, Enum):
    """Supported fusion strategy identifiers."""

    WEIGHTED_AVERAGE = "weighted_average"
    CONFIDENCE_WEIGHTED = "confidence_weighted"
    THRESHOLD = "threshold"
    VOTING = "voting"


class AggregationStrategyName(str, Enum):
    """Supported aggregation strategy identifiers."""

    MAX = "max"
    MEAN = "mean"
    MEDIAN = "median"


class NormalizationStrategyName(str, Enum):
    """Supported normalization strategy identifiers."""

    MIN_MAX = "min_max"
    Z_SCORE = "z_score"
    IDENTITY = "identity"


class LogLevelName(str, Enum):
    """Supported logging level identifiers."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


_WINDOW_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>ms|s|m|h|d)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class FusionSettings:
    """Typed configuration for fusion behavior."""

    strategy: FusionStrategyName = FusionStrategyName.WEIGHTED_AVERAGE
    kpi_weight: float = 0.50
    log_weight: float = 0.50
    threshold: float = 0.60
    window_size: timedelta = timedelta(minutes=5)
    normalization_strategy: NormalizationStrategyName = NormalizationStrategyName.MIN_MAX


@dataclass(frozen=True, slots=True)
class AggregationSettings:
    """Typed configuration for in-window aggregation."""

    strategy: AggregationStrategyName = AggregationStrategyName.MAX


@dataclass(frozen=True, slots=True)
class LoggingSettings:
    """Typed configuration for module and experiment logging."""

    level: LogLevelName = LogLevelName.INFO
    enable_debug_artifacts: bool = False


@dataclass(frozen=True, slots=True)
class ArtifactSettings:
    """Typed configuration for artifact creation and retention."""

    root_dir: Path = Path("artifacts/phase7")
    retain_intermediate: bool = True


@dataclass(frozen=True, slots=True)
class ValidationSettings:
    """Typed configuration for validation strictness."""

    strict: bool = True
    allow_row_drops: bool = False


@dataclass(frozen=True, slots=True)
class FusionConfig:
    """Immutable Phase 7 configuration.

    The configuration is exposed as nested, typed, read-only sections. Any
    unmodeled top-level sections are preserved for forward compatibility and
    may be retrieved through :meth:`get_section`.
    """

    fusion: FusionSettings = FusionSettings()
    aggregation: AggregationSettings = AggregationSettings()
    logging: LoggingSettings = LoggingSettings()
    artifacts: ArtifactSettings = ArtifactSettings()
    validation: ValidationSettings = ValidationSettings()
    extensions: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    additional_sections: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    config_path: Path | None = None

    @classmethod
    def load(
        cls,
        config_path: str | Path | None = None,
        overrides: Mapping[str, Any] | None = None,
        env_overrides: Mapping[str, Any] | None = None,
    ) -> FusionConfig:
        """Load, merge, validate, and return an immutable configuration.

        Merge precedence is:

        defaults < file values < env_overrides < overrides
        """

        resolved_path = Path(config_path) if config_path is not None else None
        raw_config = cls._default_raw_config()

        if resolved_path is not None:
            file_config = cls._read_config_file(resolved_path)
            if not isinstance(file_config, Mapping):
                raise FusionConfigLoadError(
                    f"Configuration root must be a mapping in file: {resolved_path}"
                )
            raw_config = _deep_merge(raw_config, dict(file_config))

        if env_overrides:
            raw_config = _deep_merge(raw_config, dict(env_overrides))

        if overrides:
            raw_config = _deep_merge(raw_config, dict(overrides))

        config = cls._from_raw(raw_config, resolved_path)
        config.validate()
        logger.debug(
            "Loaded Phase 7 configuration",
            extra={
                "config_path": str(resolved_path) if resolved_path is not None else None,
                "fusion_strategy": config.fusion.strategy.value,
                "aggregation_strategy": config.aggregation.strategy.value,
                "normalization_strategy": config.fusion.normalization_strategy.value,
            },
        )
        return config

    def validate(self) -> None:
        """Validate the configuration against the frozen contract."""

        self._validate_weights()
        self._validate_threshold()
        self._validate_window_size()
        self._validate_validation_policy()

    def export_snapshot(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot of the effective configuration."""

        snapshot: dict[str, Any] = {
            "fusion": {
                "strategy": self.fusion.strategy.value,
                "kpi_weight": self.fusion.kpi_weight,
                "log_weight": self.fusion.log_weight,
                "threshold": self.fusion.threshold,
                "window_size": _format_timedelta(self.fusion.window_size),
                "normalization_strategy": self.fusion.normalization_strategy.value,
            },
            "aggregation": {
                "strategy": self.aggregation.strategy.value,
            },
            "logging": {
                "level": self.logging.level.value,
                "enable_debug_artifacts": self.logging.enable_debug_artifacts,
            },
            "artifacts": {
                "root_dir": str(self.artifacts.root_dir),
                "retain_intermediate": self.artifacts.retain_intermediate,
            },
            "validation": {
                "strict": self.validation.strict,
                "allow_row_drops": self.validation.allow_row_drops,
            },
            "extensions": _thaw_value(self.extensions),
        }
        if self.additional_sections:
            snapshot.update(_thaw_value(self.additional_sections))
        if self.config_path is not None:
            snapshot["config_path"] = str(self.config_path)
        return snapshot

    def get_section(self, section_name: str) -> Any:
        """Return a typed known section or a read-only additional section.

        Parameters
        ----------
        section_name:
            Name of the top-level section to retrieve.
        """

        normalized_name = section_name.strip()
        if not normalized_name:
            raise FusionConfigValidationError("Section name must not be empty")

        known_sections = {
            "fusion": self.fusion,
            "aggregation": self.aggregation,
            "logging": self.logging,
            "artifacts": self.artifacts,
            "validation": self.validation,
            "extensions": self.extensions,
        }
        if normalized_name in known_sections:
            return known_sections[normalized_name]
        if normalized_name in self.additional_sections:
            return self.additional_sections[normalized_name]
        raise KeyError(f"Unknown configuration section: {normalized_name}")

    @property
    def fusion_settings(self) -> FusionSettings:
        """Return typed fusion settings."""

        return self.fusion

    @property
    def aggregation_settings(self) -> AggregationSettings:
        """Return typed aggregation settings."""

        return self.aggregation

    @property
    def logging_settings(self) -> LoggingSettings:
        """Return typed logging settings."""

        return self.logging

    @property
    def artifact_settings(self) -> ArtifactSettings:
        """Return typed artifact settings."""

        return self.artifacts

    @property
    def validation_settings(self) -> ValidationSettings:
        """Return typed validation settings."""

        return self.validation

    @staticmethod
    def _default_raw_config() -> dict[str, Any]:
        return {
            "fusion": {
                "strategy": FusionStrategyName.WEIGHTED_AVERAGE.value,
                "kpi_weight": 0.50,
                "log_weight": 0.50,
                "threshold": 0.60,
                "window_size": "5m",
                "normalization_strategy": NormalizationStrategyName.MIN_MAX.value,
            },
            "aggregation": {
                "strategy": AggregationStrategyName.MAX.value,
            },
            "logging": {
                "level": LogLevelName.INFO.value,
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
            "extensions": {},
        }

    @classmethod
    def _from_raw(
        cls,
        raw_config: Mapping[str, Any],
        config_path: Path | None,
    ) -> FusionConfig:
        raw_top = dict(raw_config)

        fusion_raw = cls._extract_known_section(raw_top, "fusion")
        aggregation_raw = cls._extract_known_section(raw_top, "aggregation")
        logging_raw = cls._extract_known_section(raw_top, "logging")
        artifacts_raw = cls._extract_known_section(raw_top, "artifacts")
        validation_raw = cls._extract_known_section(raw_top, "validation")
        extensions_raw = cls._extract_known_section(raw_top, "extensions", required=False)

        additional_sections = {
            key: _freeze_value(value)
            for key, value in raw_top.items()
            if key
            not in {"fusion", "aggregation", "logging", "artifacts", "validation", "extensions"}
        }

        fusion_settings = cls._build_fusion_settings(fusion_raw)
        aggregation_settings = cls._build_aggregation_settings(aggregation_raw)
        logging_settings = cls._build_logging_settings(logging_raw)
        artifact_settings = cls._build_artifact_settings(artifacts_raw)
        validation_settings = cls._build_validation_settings(validation_raw)

        return cls(
            fusion=fusion_settings,
            aggregation=aggregation_settings,
            logging=logging_settings,
            artifacts=artifact_settings,
            validation=validation_settings,
            extensions=_freeze_mapping(dict(extensions_raw)),
            additional_sections=_freeze_mapping(additional_sections),
            config_path=config_path,
        )

    @staticmethod
    def _extract_known_section(
        raw_config: Mapping[str, Any],
        section_name: str,
        *,
        required: bool = True,
    ) -> Mapping[str, Any]:
        if section_name not in raw_config:
            if required:
                raise FusionConfigValidationError(
                    f"Missing required configuration section: {section_name}"
                )
            return {}

        section_value = raw_config[section_name]
        if not isinstance(section_value, Mapping):
            raise FusionConfigValidationError(
                f"Configuration section '{section_name}' must be a mapping"
            )
        return section_value

    @classmethod
    def _build_fusion_settings(cls, raw_section: Mapping[str, Any]) -> FusionSettings:
        cls._validate_allowed_keys(
            raw_section,
            "fusion",
            {
                "strategy",
                "kpi_weight",
                "log_weight",
                "threshold",
                "window_size",
                "normalization_strategy",
            },
        )
        strategy = cls._parse_enum(
            raw_section.get("strategy"),
            FusionStrategyName,
            "fusion.strategy",
        )
        normalization_strategy = cls._parse_enum(
            raw_section.get("normalization_strategy"),
            NormalizationStrategyName,
            "fusion.normalization_strategy",
        )
        kpi_weight = cls._parse_float(raw_section.get("kpi_weight"), "fusion.kpi_weight")
        log_weight = cls._parse_float(raw_section.get("log_weight"), "fusion.log_weight")
        threshold = cls._parse_float(raw_section.get("threshold"), "fusion.threshold")
        window_size = cls._parse_window_size(raw_section.get("window_size"))

        return FusionSettings(
            strategy=strategy,
            kpi_weight=kpi_weight,
            log_weight=log_weight,
            threshold=threshold,
            window_size=window_size,
            normalization_strategy=normalization_strategy,
        )

    @classmethod
    def _build_aggregation_settings(
        cls, raw_section: Mapping[str, Any]
    ) -> AggregationSettings:
        cls._validate_allowed_keys(raw_section, "aggregation", {"strategy"})
        return AggregationSettings(
            strategy=cls._parse_enum(
                raw_section.get("strategy"),
                AggregationStrategyName,
                "aggregation.strategy",
            )
        )

    @classmethod
    def _build_logging_settings(cls, raw_section: Mapping[str, Any]) -> LoggingSettings:
        cls._validate_allowed_keys(
            raw_section,
            "logging",
            {"level", "enable_debug_artifacts"},
        )
        return LoggingSettings(
            level=cls._parse_enum(raw_section.get("level"), LogLevelName, "logging.level"),
            enable_debug_artifacts=cls._parse_bool(
                raw_section.get("enable_debug_artifacts"),
                "logging.enable_debug_artifacts",
            ),
        )

    @classmethod
    def _build_artifact_settings(cls, raw_section: Mapping[str, Any]) -> ArtifactSettings:
        cls._validate_allowed_keys(
            raw_section,
            "artifacts",
            {"root_dir", "retain_intermediate"},
        )
        root_dir_value = raw_section.get("root_dir")
        if root_dir_value is None:
            raise FusionConfigValidationError("Missing required configuration field: artifacts.root_dir")
        root_dir = Path(str(root_dir_value))
        if not str(root_dir).strip():
            raise FusionConfigValidationError(
                "Configuration field 'artifacts.root_dir' must not be empty"
            )
        return ArtifactSettings(
            root_dir=root_dir,
            retain_intermediate=cls._parse_bool(
                raw_section.get("retain_intermediate"),
                "artifacts.retain_intermediate",
            ),
        )

    @classmethod
    def _build_validation_settings(
        cls, raw_section: Mapping[str, Any]
    ) -> ValidationSettings:
        cls._validate_allowed_keys(
            raw_section,
            "validation",
            {"strict", "allow_row_drops"},
        )
        return ValidationSettings(
            strict=cls._parse_bool(raw_section.get("strict"), "validation.strict"),
            allow_row_drops=cls._parse_bool(
                raw_section.get("allow_row_drops"),
                "validation.allow_row_drops",
            ),
        )

    @staticmethod
    def _validate_allowed_keys(
        raw_section: Mapping[str, Any], section_name: str, allowed_keys: set[str]
    ) -> None:
        unknown_keys = sorted(set(raw_section) - allowed_keys)
        if unknown_keys:
            unknown_display = ", ".join(unknown_keys)
            raise FusionConfigValidationError(
                f"Unknown configuration field(s) in section '{section_name}': {unknown_display}"
            )

    @staticmethod
    def _parse_enum(value: Any, enum_type: type[Enum], field_name: str) -> Any:
        if value is None:
            raise FusionConfigValidationError(f"Missing required configuration field: {field_name}")
        try:
            return enum_type(str(value))
        except ValueError as exc:
            allowed_values = ", ".join(member.value for member in enum_type)
            raise FusionConfigValidationError(
                f"Invalid value for '{field_name}': {value!r}. Allowed values: {allowed_values}"
            ) from exc

    @staticmethod
    def _parse_float(value: Any, field_name: str) -> float:
        if value is None:
            raise FusionConfigValidationError(f"Missing required configuration field: {field_name}")
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise FusionConfigValidationError(
                f"Configuration field '{field_name}' must be numeric"
            ) from exc

    @staticmethod
    def _parse_bool(value: Any, field_name: str) -> bool:
        if value is None:
            raise FusionConfigValidationError(f"Missing required configuration field: {field_name}")
        if isinstance(value, bool):
            return value
        raise FusionConfigValidationError(
            f"Configuration field '{field_name}' must be a boolean"
        )

    @staticmethod
    def _parse_window_size(value: Any) -> timedelta:
        if value is None:
            raise FusionConfigValidationError(
                "Missing required configuration field: fusion.window_size"
            )
        if isinstance(value, timedelta):
            return value
        if not isinstance(value, str):
            raise FusionConfigValidationError(
                "Configuration field 'fusion.window_size' must be a duration string such as '5m'"
            )

        match = _WINDOW_PATTERN.match(value)
        if match is None:
            raise FusionConfigValidationError(
                "Configuration field 'fusion.window_size' must be a positive duration string using one of: ms, s, m, h, d"
            )

        numeric_value = float(match.group("value"))
        unit = match.group("unit").lower()
        if numeric_value <= 0.0:
            raise FusionConfigValidationError(
                "Configuration field 'fusion.window_size' must be greater than zero"
            )

        if unit == "ms":
            return timedelta(milliseconds=numeric_value)
        if unit == "s":
            return timedelta(seconds=numeric_value)
        if unit == "m":
            return timedelta(minutes=numeric_value)
        if unit == "h":
            return timedelta(hours=numeric_value)
        if unit == "d":
            return timedelta(days=numeric_value)

        raise FusionConfigValidationError(
            f"Unsupported duration unit for 'fusion.window_size': {unit}"
        )

    @staticmethod
    def _read_config_file(config_path: Path) -> Mapping[str, Any]:
        if not config_path.exists():
            raise FusionConfigLoadError(f"Configuration file not found: {config_path}")
        if not config_path.is_file():
            raise FusionConfigLoadError(f"Configuration path is not a file: {config_path}")

        suffix = config_path.suffix.lower()
        try:
            if suffix == ".json":
                with config_path.open("r", encoding="utf-8") as handle:
                    return json.load(handle)
            if suffix in {".yml", ".yaml"}:
                try:
                    import yaml  # type: ignore
                except ImportError as exc:
                    raise FusionConfigLoadError(
                        "YAML configuration requires PyYAML to be installed"
                    ) from exc
                with config_path.open("r", encoding="utf-8") as handle:
                    loaded = yaml.safe_load(handle)
                    return {} if loaded is None else loaded
        except FusionConfigLoadError:
            raise
        except (OSError, json.JSONDecodeError) as exc:
            raise FusionConfigLoadError(
                f"Failed to read configuration file '{config_path}': {exc}"
            ) from exc
        except Exception as exc:
            raise FusionConfigLoadError(
                f"Failed to parse configuration file '{config_path}': {exc}"
            ) from exc

        raise FusionConfigLoadError(
            f"Unsupported configuration file type for '{config_path}'. Supported extensions are .json, .yml, and .yaml"
        )

    def _validate_weights(self) -> None:
        if self.fusion.kpi_weight < 0.0:
            raise FusionConfigValidationError("Configuration field 'fusion.kpi_weight' must be non-negative")
        if self.fusion.log_weight < 0.0:
            raise FusionConfigValidationError("Configuration field 'fusion.log_weight' must be non-negative")
        if self.fusion.kpi_weight == 0.0 and self.fusion.log_weight == 0.0:
            raise FusionConfigValidationError(
                "Configuration fields 'fusion.kpi_weight' and 'fusion.log_weight' cannot both be zero"
            )

    def _validate_threshold(self) -> None:
        if not 0.0 <= self.fusion.threshold <= 1.0:
            raise FusionConfigValidationError(
                "Configuration field 'fusion.threshold' must be within [0.0, 1.0]"
            )

    def _validate_window_size(self) -> None:
        if self.fusion.window_size <= timedelta(0):
            raise FusionConfigValidationError(
                "Configuration field 'fusion.window_size' must be greater than zero"
            )

    def _validate_validation_policy(self) -> None:
        if self.validation.allow_row_drops and not self.validation.strict:
            return
        if not self.validation.strict and not self.validation.allow_row_drops:
            logger.debug(
                "Validation is configured as non-strict without row dropping; downstream modules should treat warnings as non-fatal"
            )


def _deep_merge(base: MutableMapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge nested mappings without mutating caller inputs."""

    merged = deepcopy(dict(base))
    for key, override_value in override.items():
        current_value = merged.get(key)
        if isinstance(current_value, MutableMapping) and isinstance(override_value, Mapping):
            merged[key] = _deep_merge(current_value, override_value)
        else:
            merged[key] = deepcopy(override_value)
    return merged


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze_value(item) for item in value)
    return value


def _thaw_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_value(item) for item in value]
    if isinstance(value, frozenset):
        return [_thaw_value(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, timedelta):
        return _format_timedelta(value)
    if is_dataclass(value):
        return _thaw_value(asdict(value))
    return deepcopy(value)


def _format_timedelta(value: timedelta) -> str:
    total_seconds = value.total_seconds()
    if total_seconds.is_integer():
        seconds_int = int(total_seconds)
        if seconds_int % 86400 == 0:
            return f"{seconds_int // 86400}d"
        if seconds_int % 3600 == 0:
            return f"{seconds_int // 3600}h"
        if seconds_int % 60 == 0:
            return f"{seconds_int // 60}m"
        return f"{seconds_int}s"
    milliseconds = int(total_seconds * 1000)
    return f"{milliseconds}ms"


__all__ = [
    "AggregationSettings",
    "AggregationStrategyName",
    "ArtifactSettings",
    "FusionConfig",
    "FusionConfigError",
    "FusionConfigLoadError",
    "FusionConfigValidationError",
    "FusionSettings",
    "FusionStrategyName",
    "LogLevelName",
    "LoggingSettings",
    "NormalizationStrategyName",
    "ValidationSettings",
]