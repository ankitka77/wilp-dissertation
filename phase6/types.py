"""Phase 6 shared types and enums.

This module provides the canonical dataclasses and enums used across Phase 6
modules. It is implementation of the `phase6/docs/types.md` blueprint and
must not introduce additional public APIs.

Design notes
- Dataclasses intended as immutable are declared with ``frozen=True``.
- Types that reference heavy libraries (e.g. pandas.DataFrame) are annotated
  using ``typing.Any`` at runtime and conditional imports under ``TYPE_CHECKING``
  to avoid importing heavy dependencies during module import.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import logging

# Centralized logger (shared across modules). Other modules provide richer
# configuration; this module uses the project's logger name but does not
# configure handlers itself.
logger = logging.getLogger("project")


JSONDict = Dict[str, Any]


class TrainingStatus(Enum):
    """Execution status for a training run."""

    NOT_STARTED = "NOT_STARTED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CheckpointType(Enum):
    """Types of checkpoints persisted by the training pipeline."""

    INTERMEDIATE = "INTERMEDIATE"
    FINAL = "FINAL"
    BEST = "BEST"


class DecisionReason(Enum):
    """Canonical reasons assigned by the DecisionEngine."""

    SCORE_THRESHOLD = "SCORE_THRESHOLD"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass
class Phase5Inputs:
    """Canonical container for Phase 5 outputs consumed by Phase 6.

    Attributes
    ----------
    vocabulary:
        Mapping from template (str) to event id (int). Must be deterministic.
    event_id_map:
        Reverse mapping from event id (int) to template (str).
    train_df:
        Training DataFrame produced by Phase 5. Runtime type is library
        specific (pandas.DataFrame) but annotated as ``Any`` here to avoid
        importing pandas at module import time.
    test_df:
        Test DataFrame (may be empty).
    dataset_name:
        Optional human-readable dataset name.
    """

    vocabulary: Dict[str, int]
    event_id_map: Dict[int, str]
    train_df: Any
    test_df: Any
    dataset_name: Optional[str] = None


@dataclass(frozen=True)
class DatasetMetadata:
    """Statistics describing a dataset used for training or inference.

    Fields are simple primitives to make metadata JSON-serializable.
    """

    num_examples: int
    vocab_size: int
    max_seq_len: int
    pad_token: int
    num_batches: int


@dataclass(frozen=True)
class ModelSpec:
    """Serializable model architecture specification.

    This dataclass is included (by value) into persisted model metadata and
    manifests.
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

    All fields are primitives or small JSON-serializable structures to
    facilitate manifest generation and integrity checking.
    """

    model_name: str
    version: str
    created_on: str
    model_spec: JSONDict
    training_summary_ref: str
    artifact_path: str
    git: JSONDict
    config_snapshot: JSONDict
    checksum: str
    notes: Optional[str] = None


@dataclass
class TrainingResult:
    """Container for training run outputs and per-epoch metrics.

    The structure is intentionally mutable because metrics are accumulated
    during training.
    """

    status: TrainingStatus
    epoch_metrics: List[JSONDict]
    final_checkpoint: Optional[JSONDict]
    best_checkpoint: Optional[JSONDict]
    num_epochs_run: int


@dataclass
class ValidationResult:
    """Result of running validation over a held-out set.

    Fields follow the blueprint: numeric summaries and a time-series for
    plotting or further analysis.
    """

    val_loss: Optional[float]
    topk_accuracy: Optional[float]
    metrics_time_series: List[JSONDict]
    should_early_stop: bool
    best_checkpoint_candidate: Optional[JSONDict]


@dataclass
class PredictionResult:
    """In-memory representation of inference outputs.

    `predictions` is a list of per-event dictionaries containing the
    required fields described in the blueprint.
    """

    predictions: List[JSONDict]
    meta: JSONDict = field(default_factory=dict)


@dataclass
class DecisionResult:
    """Canonical decision outputs produced by the DecisionEngine.

    `decisions` is a list of dicts; each dict contains the keys described in
    the implementation blueprint.
    """

    predictions_ref: str
    decisions: List[JSONDict]


@dataclass(frozen=True)
class ExperimentInfo:
    """Paths and identifiers for an experiment run.

    All paths are workspace-relative strings.
    """

    experiment_id: str
    path: str
    models_path: str
    reports_path: str
    plots_path: str
    manifests_path: str
    created_on: str


@dataclass(frozen=True)
class ManifestInfo:
    """Final manifest structure for Phase 6 runs.

    This dataclass mirrors the JSON structure written by the
    `ReportGenerator`.
    """

    manifest_version: str
    generated_on: str
    phase: str
    inputs: JSONDict
    artifacts: JSONDict
    model_spec: JSONDict
    model_metadata: JSONDict
    training_summary: JSONDict
    git: JSONDict
    config_snapshot: JSONDict
    experiment_id: str
    notes: Optional[str] = None
    status: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class PredictionConfidence:
    """Standardized prediction confidence structure.

    `confidence_score` is in the range [0.0, 1.0].
    """

    confidence_score: float
    method: str


@dataclass(frozen=True)
class EncoderState:
    """Persisted encoder state: vocabulary and tokens."""

    vocabulary: Dict[str, int]
    pad_token: int
    unknown_token: int
    max_length: int


@dataclass(frozen=True)
class PersistenceInfo:
    """Reference to a persisted artifact on disk."""

    path: str
    metadata_path: str
    checksum: str
    created_on: str
    checkpoint_type: CheckpointType


# Expose a concise public API for imports
__all__ = [
    "TrainingStatus",
    "CheckpointType",
    "DecisionReason",
    "Phase5Inputs",
    "DatasetMetadata",
    "ModelSpec",
    "ModelMetadata",
    "TrainingResult",
    "ValidationResult",
    "PredictionResult",
    "DecisionResult",
    "ExperimentInfo",
    "ManifestInfo",
    "PredictionConfidence",
    "EncoderState",
    "PersistenceInfo",
    "JSONDict",
]
