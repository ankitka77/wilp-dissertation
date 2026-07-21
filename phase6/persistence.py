"""Persistent storage utilities for Phase 6.

Provides `PersistenceManager` for saving/loading model artifacts and their
metadata atomically, computing checksums, and pruning old checkpoints.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json
import logging

import pickle

from phase6.config import Config
from phase6.types import PersistenceInfo, CheckpointType, ModelMetadata

logger = logging.getLogger("project")


class ModelPersistenceError(RuntimeError):
    """Raised when model persistence operations fail."""


class InferenceError(RuntimeError):
    """Raised when loading a model for inference fails integrity checks."""


class PersistenceManager:
    """Manage saving and loading of model artifacts within an experiment.

    Parameters
    ----------
    experiment_path:
        Root path for the experiment (filesystem directory).
    config:
        Phase 6 `Config` instance providing `max_checkpoints` and related
        settings.
    logger:
        Optional logger; defaults to the centralized project logger.
    """

    def __init__(self, experiment_path: str | Path, config: Config, logger: Optional[logging.Logger] = None) -> None:
        self._experiment_path = Path(experiment_path)
        self._config = config
        self._logger = logger or logging.getLogger("project")

        # Ensure models directory exists
        self._models_dir = self._experiment_path / "models"
        try:
            self._models_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            raise ModelPersistenceError(f"Unable to create models directory: {exc}") from exc

    def save_model(self, model_obj: Any, metadata: Dict[str, Any], checkpoint_type: CheckpointType) -> PersistenceInfo:
        """Persist `model_obj` and `metadata` as an atomic checkpoint.

        Returns
        -------
        PersistenceInfo
            Information describing the stored artifact and metadata file.

        Raises
        ------
        ModelPersistenceError
            On filesystem errors or serialization failures.
        """
        created_on = datetime.now(timezone.utc).replace(microsecond=0)
        ts = created_on.isoformat().replace("+00:00", "Z")
        # filesystem-safe timestamp for filenames (no colons)
        ts_file = created_on.strftime("%Y%m%dT%H%M%SZ")
        suffix = checkpoint_type.value.lower()
        base_name = f"model_{ts_file}_{suffix}"
        model_path = self._models_dir / f"{base_name}.bin"
        meta_path = self._models_dir / f"{base_name}.json"

        # Serialize model to binary file atomically
        try:
            self._atomic_write_file(model_path, pickle.dumps(model_obj, protocol=pickle.HIGHEST_PROTOCOL), binary=True)
        except Exception as exc:
            raise ModelPersistenceError(f"Failed to write model file: {exc}") from exc

        # Compute checksum of model file
        try:
            checksum = self._compute_checksum(model_path)
        except Exception as exc:
            raise ModelPersistenceError(f"Failed to compute checksum: {exc}") from exc

        # Augment metadata (override provided checksum/artifact_path to ensure integrity)
        meta = dict(metadata)
        meta["created_on"] = meta.get("created_on", ts)
        meta["artifact_path"] = str(model_path)
        meta["checksum"] = checksum

        # Write metadata
        try:
            self._atomic_write_file(meta_path, json.dumps(meta, indent=2).encode("utf-8"), binary=True)
        except Exception as exc:
            # Attempt to remove model file if metadata write fails
            try:
                model_path.unlink(missing_ok=True)
            except Exception as exc2:
                self._logger.debug("Failed to remove model file after metadata write failure: %s", exc2)
            raise ModelPersistenceError(f"Failed to write metadata file: {exc}") from exc

        info = PersistenceInfo(path=str(model_path), metadata_path=str(meta_path), checksum=checksum, created_on=ts, checkpoint_type=checkpoint_type)

        # Prune older checkpoints according to config
        try:
            self._prune_old_checkpoints()
        except Exception:
            self._logger.exception("Pruning old checkpoints failed")

        return info

    def load_model(self, path: str | Path) -> tuple[Any, ModelMetadata]:
        """Load a persisted model and its metadata.

        Parameters
        ----------
        path:
            Path to the model binary file.

        Returns
        -------
        tuple
            `(model_obj, ModelMetadata)` loaded from disk.

        Raises
        ------
        ModelPersistenceError
            For IO or deserialization errors.
        InferenceError
            If checksum or metadata integrity checks fail.
        """
        model_path = Path(path)
        if not model_path.exists():
            raise ModelPersistenceError(f"Model file not found: {model_path}")

        meta_path = model_path.with_suffix(".json")
        if not meta_path.exists():
            raise ModelPersistenceError(f"Metadata file not found for model: {meta_path}")

        # Load metadata
        try:
            with meta_path.open("r", encoding="utf-8") as fh:
                meta = json.load(fh)
        except Exception as exc:
            raise ModelPersistenceError(f"Failed to read metadata file: {exc}") from exc

        # Verify checksum
        expected = meta.get("checksum")
        try:
            actual = self._compute_checksum(model_path)
        except Exception as exc:
            raise ModelPersistenceError(f"Failed to compute checksum: {exc}") from exc

        if expected is not None and expected != actual:
            raise InferenceError("Model checksum mismatch; file may be corrupted")

        # Load model object
        try:
            with model_path.open("rb") as fh:
                model_obj = pickle.load(fh)
        except Exception as exc:
            raise ModelPersistenceError(f"Failed to deserialize model object: {exc}") from exc

        # Convert metadata to ModelMetadata if possible
        try:
            model_meta = ModelMetadata(**meta)  # type: ignore[arg-type]
        except Exception:
            # If conversion fails, raise a descriptive error
            raise ModelPersistenceError("Metadata does not conform to ModelMetadata schema")

        return model_obj, model_meta

    def list_checkpoints(self) -> List[PersistenceInfo]:
        """List known checkpoints by reading metadata files in the models dir."""
        out: List[PersistenceInfo] = []
        for p in sorted(self._models_dir.glob("*.json")):
            try:
                with p.open("r", encoding="utf-8") as fh:
                    meta = json.load(fh)
                ck_type = CheckpointType[meta.get("checkpoint_type")] if meta.get("checkpoint_type") in CheckpointType.__members__ else CheckpointType.INTERMEDIATE
                created_on = meta.get("created_on") or datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")
                info = PersistenceInfo(path=str(Path(str(meta.get("artifact_path")) if meta.get("artifact_path") else p.with_suffix(".bin"))), metadata_path=str(p), checksum=meta.get("checksum", ""), created_on=created_on, checkpoint_type=ck_type)
                out.append(info)
            except Exception:
                self._logger.exception("Failed to read checkpoint metadata: %s", p)
        return out

    # Private helpers
    def _atomic_write_file(self, path: Path, data: bytes, binary: bool = True) -> None:
        """Write bytes to `path` atomically using a temporary file in the same dir."""
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            with tmp.open("wb") as fh:
                fh.write(data)
            # On POSIX, replace is atomic
            tmp.replace(path)
        finally:
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception as exc:
                self._logger.debug("Failed to cleanup tmp file %s: %s", tmp, exc)

    def _compute_checksum(self, path: Path) -> str:
        """Compute SHA256 checksum for a file and return hex digest."""
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _prune_old_checkpoints(self) -> None:
        """Remove old checkpoints when exceeding `config.max_checkpoints`.

        This reads metadata files and sorts by `created_on` when present.
        """
        try:
            max_ck = int(getattr(self._config, "max_checkpoints", 0) or 0)
        except (TypeError, ValueError) as exc:
            self._logger.debug("Invalid max_checkpoints value: %s", exc)
            max_ck = 0
        if max_ck <= 0:
            return

        checkpoints = self.list_checkpoints()
        if len(checkpoints) <= max_ck:
            return

        # Sort by created_on (ISO format) ascending
        def sort_key(ci: PersistenceInfo):
            try:
                return ci.created_on
            except Exception as exc:
                self._logger.debug("Failed to read created_on for %s: %s", ci, exc)
                return ""

        checkpoints_sorted = sorted(checkpoints, key=sort_key)
        to_remove = checkpoints_sorted[: max(0, len(checkpoints_sorted) - max_ck)]
        for ci in to_remove:
            try:
                Path(ci.path).unlink(missing_ok=True)
                Path(ci.metadata_path).unlink(missing_ok=True)
            except Exception:
                self._logger.exception("Failed to remove old checkpoint files for %s", ci.path)


__all__ = ["PersistenceManager", "ModelPersistenceError", "InferenceError"]


def save_checkpoint(*, experiment_info: dict, model_spec: Any, epoch: int, checkpoint_type: CheckpointType, model_obj: Any, config: Optional[Config] = None, logger: Optional[logging.Logger] = None) -> PersistenceInfo:
    """Module-level adapter used by Trainer to save a checkpoint by delegating
    to a `PersistenceManager` instance.

    This thin wrapper keeps existing callsites small while allowing the
    `PersistenceManager` instance API to remain the canonical implementation.
    """
    cfg = config or Config()
    log = logger or logging.getLogger("project")
    exp_path = experiment_info.get("experiment_path") if isinstance(experiment_info, dict) else None
    if exp_path is None:
        raise ModelPersistenceError("experiment_info must contain 'experiment_path' key")

    manager = PersistenceManager(exp_path, cfg, log)

    # Compose metadata
    metadata = {
        "experiment": experiment_info.get("name", "unnamed"),
        "epoch": int(epoch),
        "checkpoint_type": checkpoint_type.name,
        "model_spec": str(model_spec),
    }

    return manager.save_model(model_obj=model_obj, metadata=metadata, checkpoint_type=checkpoint_type)
