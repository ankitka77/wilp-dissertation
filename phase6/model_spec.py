"""Model specification utilities for Phase 6.

Contains `ModelSpec` and `ModelMetadata` dataclasses and the
`ModelSpecFactory` responsible for creating validated `ModelSpec` objects
from configuration and overrides.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import logging

from phase6.config import Config, ConfigurationError

logger = logging.getLogger("project")


@dataclass(frozen=True)
class ModelSpec:
    """Serializable model architecture specification.

    Fields are small primitives to keep the object JSON-serializable for
    inclusion in manifests and model metadata.
    """

    vocab_size: int
    embedding_dim: int
    hidden_size: int
    num_layers: int
    dropout: float
    rnn_type: str
    output_type: str
    sequence_length: int
    top_k: int
    pad_token: int


@dataclass(frozen=True)
class ModelMetadata:
    """Metadata accompanying a persisted model artifact.

    This structure mirrors the blueprint and is persisted alongside the
    binary model artifact to enable reproducible loading.
    """

    model_name: str
    version: str
    created_on: str
    model_spec: Dict[str, Any]
    training_summary_ref: str
    artifact_path: str
    git: Dict[str, Any]
    config_snapshot: Dict[str, Any]
    checksum: str
    notes: Optional[str]


class ModelSpecFactory:
    """Factory for creating validated ModelSpec instances.

    The factory uses values from ``config`` as defaults and accepts an
    optional ``overrides`` mapping. Per the Phase 6 blueprint the caller is
    responsible for providing dataset metadata (``vocab_size`` and
    ``sequence_length``) via the overrides mapping.
    """

    _ALLOWED_RNN_TYPES = {"LSTM"}

    def __init__(self, config: Config) -> None:
        if not isinstance(config, Config):
            raise ConfigurationError("ModelSpecFactory requires a Config instance")
        self.config = config

    def create_model_spec(self, overrides: Optional[Dict[str, Any]] = None) -> ModelSpec:
        """Create and validate a `ModelSpec`.

        Parameters
        ----------
        overrides:
            Optional mapping overriding defaults. Must include `vocab_size`
            and `sequence_length` (dataset metadata) as integers.

        Returns
        -------
        ModelSpec

        Raises
        ------
        ConfigurationError
            If required dataset metadata is missing or values are invalid.
        """
        overrides = dict(overrides or {})

        # Dataset metadata (required)
        if "vocab_size" not in overrides:
            raise ConfigurationError("'vocab_size' must be provided in overrides")
        if "sequence_length" not in overrides:
            raise ConfigurationError("'sequence_length' must be provided in overrides")

        try:
            vocab_size = int(overrides["vocab_size"])
            sequence_length = int(overrides["sequence_length"])
        except Exception as exc:
            raise ConfigurationError("vocab_size and sequence_length must be integers") from exc

        embedding_dim = int(overrides.get("embedding_dim", self.config.embedding_dim))
        hidden_size = int(overrides.get("hidden_size", self.config.hidden_size))
        num_layers = int(overrides.get("num_layers", 1))
        dropout = float(overrides.get("dropout", self.config.dropout))
        rnn_type = str(overrides.get("rnn_type", "LSTM"))
        output_type = str(overrides.get("output_type", "softmax"))
        top_k = int(overrides.get("top_k", self.config.top_k))
        pad_token = int(overrides.get("pad_token", self.config.pad_token))

        # Basic validations
        if vocab_size <= 0:
            raise ConfigurationError("vocab_size must be > 0")
        if sequence_length <= 0:
            raise ConfigurationError("sequence_length must be > 0")
        if embedding_dim <= 0:
            raise ConfigurationError("embedding_dim must be > 0")
        if hidden_size <= 0:
            raise ConfigurationError("hidden_size must be > 0")
        if num_layers <= 0:
            raise ConfigurationError("num_layers must be >= 1")
        if not (0.0 <= dropout < 1.0):
            raise ConfigurationError("dropout must be in [0.0, 1.0)")
        if top_k <= 0:
            raise ConfigurationError("top_k must be > 0")

        # rnn_type validation
        if rnn_type not in self._ALLOWED_RNN_TYPES:
            raise ConfigurationError(f"Unsupported rnn_type: {rnn_type}. Allowed: {sorted(self._ALLOWED_RNN_TYPES)}")

        spec = ModelSpec(
            vocab_size=vocab_size,
            embedding_dim=embedding_dim,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout,
            rnn_type=rnn_type,
            output_type=output_type,
            sequence_length=sequence_length,
            top_k=top_k,
            pad_token=pad_token,
        )

        logger.debug("Created ModelSpec: %s", spec)
        return spec
