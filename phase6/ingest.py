"""Phase 6 ingest module.

Reads Phase 5 outputs (vocabulary and sequences), validates schemas, coerces
sequence fields into canonical Python lists, and returns `Phase5Inputs` along
with a lightweight `ValidationResult` describing any warnings or errors.

This implementation follows the frozen Phase 6 blueprint and does not change
other modules or interfaces.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import logging

from phase6.config import Config
from phase6.types import Phase5Inputs


logger = logging.getLogger("project")


@dataclass
class ValidationResult:
    """Result of validation performed by the `Ingestor`.

    Attributes
    ----------
    ok:
        True when no errors were encountered (warnings may still be present).
    warnings:
        Ordered list of warning messages.
    errors:
        Ordered list of error messages.
    fingerprint:
        Lightweight statistics computed from the inputs to aid downstream
        bookkeeping (may be empty if inputs could not be loaded).
    """

    ok: bool = True
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    fingerprint: Dict[str, Any] = field(default_factory=dict)


class Ingestor:
    """Load Phase 5 outputs and validate basic schemas.

    Parameters
    ----------
    config:
        Phase 6 `Config` instance used for configuration values (e.g.,
        `sequence_length` and `batch_size`).
    logger:
        Logger to use for informational and diagnostic messages. If omitted,
        the centralized project logger is used.
    """

    def __init__(self, config: Config, logger: Optional[logging.Logger] = None) -> None:
        if not isinstance(config, Config):
            raise TypeError("Ingestor requires a Config instance")
        self._config = config
        self._logger = logger or logging.getLogger("project")

    def load(self, paths: Dict[str, str]) -> Tuple[Phase5Inputs, ValidationResult]:
        """Load artefacts produced by Phase 5.

        Parameters
        ----------
        paths:
            Mapping of artifact role to filesystem path. Expected keys include
            at minimum `vocabulary` and `sequences`. `train` and `test` are
            optional but recommended.

        Returns
        -------
        tuple
            `(Phase5Inputs, ValidationResult)` where `Phase5Inputs` contains
            the loaded artifacts and `ValidationResult` lists any warnings or
            errors observed during ingest.
        """
        result = ValidationResult()

        # Load vocabulary
        vocab_path = paths.get("vocabulary")
        vocabulary: Dict[str, int] = {}
        event_id_map: Dict[int, str] = {}

        if not vocab_path:
            result.ok = False
            result.errors.append("Missing 'vocabulary' path")
            self._logger.error("Missing 'vocabulary' path")
        else:
            try:
                vocabulary = self._load_vocabulary(Path(vocab_path))
                event_id_map = {int(v): k for k, v in vocabulary.items()}
            except Exception as exc:
                result.ok = False
                msg = f"Failed to load vocabulary: {exc}"
                result.errors.append(msg)
                self._logger.exception(msg)

        # Load sequences (expects a file with a column 'sequence_events')
        sequences_path = paths.get("sequences")
        train_df = None
        test_df = None
        if sequences_path:
            try:
                df = self._load_csv(Path(sequences_path))
                # Accept common alternate column names produced by Phase5 pipelines.
                # If 'sequence' is missing but an alternative exists, copy it in.
                # if "sequence" not in getattr(df, "columns", []):
                #     for alt in ("sequence_events", "input_sequence", "sequence_list"):
                #         if alt in getattr(df, "columns", []):
                #             df["sequence"] = df[alt]
                #             msg = f"Added missing 'sequence' column from '{alt}'"
                #             result.warnings.append(msg)
                #             self._logger.info(msg)
                #             break
                vr = self.validate_schema(df, required_cols=["sequence_events"])
                result.warnings.extend(vr.warnings)
                result.errors.extend(vr.errors)
                if vr.errors:
                    result.ok = False
                else:
                    # Coerce sequence_events column
                    df = df.copy()
                    df["sequence_events"] = df["sequence_events"].apply(self._coerce_sequence_field)
                    # Split into train/test if requested by paths
                    train_path = paths.get("train")
                    test_path = paths.get("test")
                    if train_path and test_path:
                        # If separate train/test files provided, prefer them
                        train_df = self._load_csv(Path(train_path))
                        test_df = self._load_csv(Path(test_path))
                    else:
                        # Otherwise use the supplied sequences file as train
                        train_df = df
            except Exception as exc:
                result.ok = False
                msg = f"Failed to load sequences: {exc}"
                result.errors.append(msg)
                self._logger.exception(msg)
        else:
            # No sequences file is a warning but not necessarily fatal
            result.warnings.append("No 'sequences' path provided; train/test will be empty")

        # Compute fingerprint if possible
        try:
            fingerprint = self._compute_fingerprint(vocabulary, train_df)
            result.fingerprint = fingerprint
        except Exception as exc:
            result.warnings.append(f"Failed to compute fingerprint: {exc}")
            self._logger.exception("Failed to compute fingerprint")

        # Build Phase5Inputs (train_df/test_df may be None)
        inputs = Phase5Inputs(
            vocabulary=vocabulary,
            event_id_map=event_id_map,
            train_df=train_df,
            test_df=test_df,
            dataset_name=paths.get("dataset_name"),
        )

        return inputs, result

    def validate_schema(self, df: Any, required_cols: List[str]) -> ValidationResult:
        """Validate that required columns exist in a DataFrame-like object.

        Parameters
        ----------
        df:
            A pandas DataFrame or similar mapping supporting `columns`.
        required_cols:
            List of column names that must be present.

        Returns
        -------
        ValidationResult
            Result containing warnings and errors describing schema issues.
        """
        vr = ValidationResult()
        try:
            cols = list(df.columns)
        except Exception as exc:
            vr.ok = False
            vr.errors.append(f"Provided object is not a DataFrame-like: {exc}")
            return vr

        missing = [c for c in required_cols if c not in cols]
        if missing:
            vr.ok = False
            vr.errors.append(f"Missing required columns: {missing}")
            self._logger.error("Missing required columns: %s", missing)
        return vr

    def _load_csv(self, path: Path):
        """Load a CSV into a pandas DataFrame.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        ValueError
            If pandas cannot parse the file.
        """
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {path}")
        import pandas as pd  # type: ignore[import]

        try:
            df = pd.read_csv(path)
        except Exception as exc:
            raise ValueError(f"Unable to read CSV {path}: {exc}") from exc
        return df

    def _load_vocabulary(self, path: Path) -> Dict[str, int]:
        """Load a vocabulary mapping from JSON or a two-column CSV.

        Returns
        -------
        Dict[str,int]
            Mapping from template string to integer id.
        """
        if not path.exists():
            raise FileNotFoundError(f"Vocabulary file not found: {path}")

        suffix = path.suffix.lower()
        if suffix == ".json":
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                raise ValueError("Vocabulary JSON must be an object mapping template->id")
            # Allow two JSON shapes:
            # 1) direct mapping: {"template": 1, ...}
            # 2) wrapped mapping: {"vocabulary": {"template": 1, ...}}
            if "vocabulary" in data and isinstance(data["vocabulary"], dict):
                data = data["vocabulary"]
            elif "vocab" in data and isinstance(data["vocab"], dict):
                data = data["vocab"]
            return {str(k): int(v) for k, v in data.items()}

        # Attempt CSV: expect columns 'template' and 'event_id' or first two cols
        import pandas as pd  # type: ignore[import]

        df = pd.read_csv(path)
        if "template" in df.columns and "event_id" in df.columns:
            return {str(r.template): int(r.event_id) for r in df.itertuples()}
        # Fallback: if two columns, use them
        if len(df.columns) >= 2:
            a, b = df.columns[:2]
            return {str(r[1]): int(r[2]) for r in df.itertuples(index=False, name=None)}

        raise ValueError("Unrecognized vocabulary CSV format; expected 'template,event_id'")

    def _coerce_sequence_field(self, value: Any) -> List[Any]:
        """Coerce a sequence field into a Python list.

        Accepts lists, JSON strings, and simple delimiter-separated strings.
        """
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, (int, float)):
            return [value]
        if isinstance(value, str):
            v = value.strip()
            # Try JSON list
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, ValueError) as exc:
                logger.debug("_coerce_sequence_field: JSON parse failed: %s", exc)
            # Try comma-separated
            if "," in v:
                parts = [p.strip() for p in v.split(",") if p.strip()]
                return parts
            # Try whitespace-separated
            parts = [p for p in v.split() if p]
            return parts
        # Fallback: wrap in list
        return [value]

    def _compute_fingerprint(self, vocabulary: Dict[str, int], train_df: Optional[Any]) -> Dict[str, Any]:
        """Compute simple statistics to fingerprint inputs.

        Returns a mapping with at least `num_examples`, `vocab_size`, and
        `max_seq_len` when possible.
        """
        fp: Dict[str, Any] = {}
        try:
            fp["vocab_size"] = len(vocabulary)
        except TypeError as exc:
            logger.debug("_compute_fingerprint: invalid vocabulary for len(): %s", exc)
            fp["vocab_size"] = 0

        num_examples = 0
        max_seq_len = 0
        if train_df is not None:
            try:
                num_examples = int(len(train_df))
                # Expect a 'sequence_events' column of list-like
                seqs = train_df.get("sequence_events") if hasattr(train_df, "get") else train_df["sequence_events"]
                for s in seqs:
                    if s is None:
                        continue
                    try:
                        seq_len = len(s)
                    except Exception as exc:
                        logger.debug("_compute_fingerprint: failed to compute length of sequence element: %s", exc)
                        seq_len = 1
                    if seq_len > max_seq_len:
                        max_seq_len = seq_len
            except Exception as exc:
                logger.debug("_compute_fingerprint: failed to compute num_examples/max_seq_len: %s", exc)
                num_examples = 0
                max_seq_len = 0

        fp["num_examples"] = num_examples
        fp["max_seq_len"] = max_seq_len
        # Include computed number of batches if batch_size available
        try:
            batch = int(getattr(self._config, "batch_size", 0) or 0)
            fp["num_batches"] = (num_examples + batch - 1) // batch if batch > 0 else 0
        except Exception:
            fp["num_batches"] = 0

        return fp


__all__ = ["Ingestor", "ValidationResult"]
