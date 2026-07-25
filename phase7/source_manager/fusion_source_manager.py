"""Source manager for Phase 7 fusion input datasets.

This module provides a small, focused `FusionSourceManager` responsible for
locating configured input sources, validating source configuration and
existence, loading datasets (KPI and Log), and exposing them together with
immutable source metadata.

The implementation intentionally keeps responsibilities narrow and does not
perform alignment, mapping, aggregation, normalization, fusion, scoring or
any other downstream processing.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional
import logging

import pandas as pd  # type: ignore

from phase7.config.fusion_config import FusionConfig

logger = logging.getLogger("project.phase7.source_manager")


class _ImmutableFrozenSet(frozenset):
    """frozenset subclass that raises TypeError on mutation attempts."""

    def add(self, *args, **kwargs):  # pragma: no cover - trivial
        raise TypeError("cannot modify immutable set")

    def remove(self, *args, **kwargs):  # pragma: no cover - trivial
        raise TypeError("cannot modify immutable set")


def _deep_freeze(value: Any) -> Mapping[str, Any] | Any:
    """Recursively freeze Python container types into immutable equivalents.

    - mapping -> MappingProxyType with frozen values
    - list -> tuple
    - set -> _ImmutableFrozenSet
    - tuple -> tuple (with frozen elements)
    Primitives are returned unchanged.
    """
    if isinstance(value, Mapping):
        frozen = {k: _deep_freeze(v) for k, v in value.items()}
        return MappingProxyType(frozen)
    if isinstance(value, list):
        return tuple(_deep_freeze(v) for v in value)
    if isinstance(value, set):
        return _ImmutableFrozenSet(_deep_freeze(v) for v in value)
    if isinstance(value, tuple):
        return tuple(_deep_freeze(v) for v in value)
    return value


class FusionSourceManagerError(RuntimeError):
    """Base exception for FusionSourceManager errors."""


class SourceConfigurationError(FusionSourceManagerError):
    """Raised when the configured sources are invalid or unsupported."""


class SourceLoadError(FusionSourceManagerError):
    """Raised when a configured source cannot be loaded from disk or other IO."""


class SourceValidationError(FusionSourceManagerError):
    """Raised when a loaded dataset fails validation (empty, missing columns, etc.)."""


@dataclass(slots=True)
class _SourceSpec:
    """Internal representation of a configured source."""

    name: str
    kind: str
    path: Path
    required_columns: tuple[str, ...]
    raw_config: Mapping[str, Any]


class FusionSourceManager:
    """Manage configured input sources for the Phase 7 fusion pipeline.

    Usage:
        manager = FusionSourceManager(config)
        manager.initialize()
        manager.load_sources()
        df = manager.get_source("kpi_train")
    """

    def __init__(self, config: FusionConfig, *, logger_: Optional[logging.Logger] = None) -> None:
        """Create a new `FusionSourceManager`.

        Parameters
        - config: FusionConfig instance (read-only configuration).
        - logger_: optional Logger; if omitted a module logger is used.
        """
        if config is None:
            raise SourceConfigurationError("FusionConfig instance is required")
        self._config = config
        self._logger = logger_ or logger
        self._specs: dict[str, _SourceSpec] = {}
        self._loaded: dict[str, pd.DataFrame] = {}
        self._metadata: dict[str, Mapping[str, Any]] = {}

    # Initialization and configuration parsing --------------------------------
    def initialize(self, *, section_name: str = "extensions") -> None:
        """Parse and validate the configured sources from the configuration.

        The configuration is expected to expose a mapping section (by
        default `extensions`) containing a top-level `sources` mapping. Each
        source entry must be a mapping with at least the following keys:
        - `type`: string (e.g. "KPI" or "LOG")
        - `path`: filesystem path to the dataset CSV

        Additional optional keys supported per-source:
        - `required_columns`: list of string column names that must be present

        Raises
        -----
        - SourceConfigurationError: on missing/invalid configuration
        """
        self._logger.debug("Initializing FusionSourceManager from config section '%s'", section_name)

        try:
            section = self._config.get_section(section_name)
        except Exception as exc:
            raise SourceConfigurationError(f"Configuration section '{section_name}' missing or invalid") from exc

        if not isinstance(section, Mapping):
            raise SourceConfigurationError(f"Configuration section '{section_name}' must be a mapping")

        sources = section.get("sources")
        if sources is None:
            raise SourceConfigurationError("No 'sources' mapping found in configuration extensions")
        if not isinstance(sources, Mapping):
            raise SourceConfigurationError("'sources' configuration must be a mapping of source-name -> configuration")

        # Build internal specs
        specs: dict[str, _SourceSpec] = {}
        for name, raw in sources.items():
            if not isinstance(raw, Mapping):
                raise SourceConfigurationError(f"Source '{name}' configuration must be a mapping")

            kind = raw.get("type")
            if not isinstance(kind, str) or not kind.strip():
                raise SourceConfigurationError(f"Source '{name}' missing required 'type' string")
            kind_norm = kind.strip().upper()

            path_val = raw.get("path")
            if path_val is None:
                raise SourceConfigurationError(f"Source '{name}' missing required 'path'")
            path = Path(str(path_val))

            req_cols = raw.get("required_columns") or []
            if not isinstance(req_cols, Iterable) or isinstance(req_cols, (str, bytes)):
                raise SourceConfigurationError(f"Source '{name}' has invalid 'required_columns' value; must be list of strings")
            req_tuple = tuple(str(c) for c in req_cols)

            specs[name] = _SourceSpec(name=name, kind=kind_norm, path=path, required_columns=req_tuple, raw_config=dict(raw))

        self._specs = specs
        self._logger.info("Configured %d source(s)", len(self._specs))

    # Loading -----------------------------------------------------------------
    def load_sources(self) -> None:
        """Load all configured sources into memory.

        Existing loaded sources are cleared before loading. Individual source
        load failures raise `SourceLoadError`.
        """
        self.clear()
        for name, spec in self._specs.items():
            try:
                if spec.kind == "KPI":
                    df = self.load_kpi_source(spec)
                elif spec.kind == "LOG":
                    df = self.load_log_source(spec)
                else:
                    raise SourceConfigurationError(f"Unsupported source type for '{name}': {spec.kind}")
            except FusionSourceManagerError:
                raise
            except Exception as exc:
                raise SourceLoadError(f"Failed to load source '{name}': {exc}") from exc

            # store loaded DataFrame and metadata (immutable, recursively frozen)
            self._loaded[name] = df
            meta: dict[str, Any] = dict(spec.raw_config)
            meta.update({"path": str(spec.path), "type": spec.kind})
            self._metadata[name] = _deep_freeze(meta)
            self._logger.info("Loaded source '%s' (%s) with %d rows", name, spec.kind, len(df))

    def load_kpi_source(self, spec: _SourceSpec) -> pd.DataFrame:
        """Load a KPI dataset from disk and validate its structure.

        Parameters
        - spec: parsed source specification

        Returns
        - pandas.DataFrame loaded dataset

        Raises
        - SourceLoadError: on IO/parsing issues
        - SourceValidationError: on empty dataset or missing columns
        """
        return self._load_csv_source(spec, label="KPI")

    def load_log_source(self, spec: _SourceSpec) -> pd.DataFrame:
        """Load a Log dataset from disk and validate its structure.

        Implementation intentionally mirrors `load_kpi_source` as logs are
        represented as tabular CSV inputs for Phase 7 ingestion.
        """
        return self._load_csv_source(spec, label="Log")

    def _load_csv_source(self, spec: _SourceSpec, *, label: str) -> pd.DataFrame:
        """Common CSV loading and validation helper.

        Preserves error message phrasing used by the public loader methods.
        """
        if not spec.path.exists():
            raise SourceLoadError(f"{label} source file not found: {spec.path}")
        try:
            df = pd.read_csv(spec.path)
        except Exception as exc:
            raise SourceLoadError(f"Failed to read {label} CSV '{spec.path}': {exc}") from exc

        if not isinstance(df, pd.DataFrame):
            raise SourceValidationError(f"Loaded {label} source is not a DataFrame")
        if df.empty:
            raise SourceValidationError(f"{label} dataset is empty")

        self._validate_required_columns(df, spec)
        return df

    def _validate_required_columns(self, df: pd.DataFrame, spec: _SourceSpec) -> None:
        """Ensure required columns are present in the loaded DataFrame.

        Raises SourceValidationError on missing columns.
        """
        missing = [c for c in spec.required_columns if c not in df.columns]
        if missing:
            raise SourceValidationError(f"Source '{spec.name}' is missing required columns: {missing}")

    # Accessors ----------------------------------------------------------------
    def has_source(self, name: str) -> bool:
        """Return True if the named source is configured (regardless of load state)."""
        return name in self._specs

    def list_sources(self) -> list[str]:
        """Return the list of configured source names."""
        return list(self._specs.keys())

    def get_source(self, name: str) -> pd.DataFrame:
        """Return a defensive copy of the loaded DataFrame for `name`.

        Raises KeyError if the source is unknown and SourceLoadError if not loaded.
        """
        if name not in self._specs:
            raise KeyError(f"Unknown source: {name}")
        if name not in self._loaded:
            raise SourceLoadError(f"Source not loaded: {name}")
        # defensive copy to avoid exposing internal mutable state
        return self._loaded[name].copy(deep=True)

    def get_all_sources(self) -> Mapping[str, pd.DataFrame]:
        """Return an immutable mapping of all loaded sources to defensive copies."""
        return MappingProxyType({k: v.copy(deep=True) for k, v in self._loaded.items()})

    def get_source_metadata(self, name: str) -> Mapping[str, Any]:
        """Return read-only metadata for a configured source.

        Raises KeyError if unknown.
        """
        if name not in self._specs:
            raise KeyError(f"Unknown source: {name}")
        return self._metadata.get(name, MappingProxyType({}))

    def clear(self) -> None:
        """Clear loaded sources and metadata from memory (keeps configuration)."""
        self._loaded.clear()
        self._metadata.clear()
        self._logger.debug("Cleared loaded sources and metadata")


__all__ = [
    "FusionSourceManager",
    "FusionSourceManagerError",
    "SourceConfigurationError",
    "SourceLoadError",
    "SourceValidationError",
]
