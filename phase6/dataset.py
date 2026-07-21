"""Dataset and dataloader utilities for Phase 6.

Provides `SequenceDataset`, a minimal `DataLoader` for batch iteration, a
`make_dataloader` factory, and `default_collate_fn` which pads/truncates and
computes masks for batches.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional
import logging

import numpy as np

from phase6.config import Config
from phase6.types import DatasetMetadata

logger = logging.getLogger("project")


class SequenceDataset:
    """Dataset holding encoded sequences and optional targets.

    Parameters
    ----------
    sequences:
        Iterable of sequences where each sequence is a list of integer ids.
    config:
        Phase 6 `Config` instance providing `pad_token` and `sequence_length`.
    targets:
        Optional iterable of target values aligned with `sequences`.
    sequence_ids:
        Optional iterable of identifiers for each sequence.
    """

    def __init__(self, sequences: Iterable[List[int]], config: Config, targets: Optional[Iterable[Any]] = None, sequence_ids: Optional[Iterable[str]] = None) -> None:
        if not isinstance(config, Config):
            raise TypeError("SequenceDataset requires a Config instance")
        self._config = config
        self._pad = int(config.pad_token)
        self._max_len = int(getattr(config, "sequence_length", 0))

        self._sequences: List[List[int]] = [list(s) for s in sequences]
        self._targets: Optional[List[Any]] = list(targets) if targets is not None else None
        self._ids: Optional[List[str]] = list(sequence_ids) if sequence_ids is not None else None

        if self._targets is not None and len(self._targets) != len(self._sequences):
            raise ValueError("targets length must match sequences length")
        if self._ids is not None and len(self._ids) != len(self._sequences):
            raise ValueError("sequence_ids length must match sequences length")

    def __len__(self) -> int:
        """Return number of examples in the dataset."""
        return len(self._sequences)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        """Return a single example as a dict with `sequence`, `target`, and `id`."""
        seq = self._sequences[idx]
        target = self._targets[idx] if self._targets is not None else None
        sid = self._ids[idx] if self._ids is not None else None
        return {"sequence": seq, "target": target, "id": sid}

    def metadata(self) -> DatasetMetadata:
        """Compute and return dataset metadata as `DatasetMetadata`."""
        num_examples = len(self)
        vocab_size = 0
        try:
            # infer vocab_size from sequences
            vocab_size = len({token for seq in self._sequences for token in seq})
        except Exception:
            vocab_size = 0
        max_seq_len = max((len(s) for s in self._sequences), default=0)
        num_batches = 0
        try:
            batch = int(getattr(self._config, "batch_size", 0) or 0)
            num_batches = (num_examples + batch - 1) // batch if batch > 0 else 0
        except Exception:
            num_batches = 0

        return DatasetMetadata(num_examples=num_examples, vocab_size=vocab_size, max_seq_len=max_seq_len, pad_token=self._pad, num_batches=num_batches)


class DataLoader:
    """Simple DataLoader that yields batches from a `SequenceDataset`.

    Parameters
    ----------
    dataset:
        `SequenceDataset` instance.
    batch_size:
        Number of examples per batch.
    shuffle:
        Whether to shuffle indices each epoch.
    num_workers:
        Ignored in this single-process implementation but accepted for API
        compatibility.
    collate_fn:
        Function that converts a list of examples into a batch mapping.
    """

    def __init__(self, dataset: SequenceDataset, batch_size: int, shuffle: bool, num_workers: int, collate_fn: Callable[[List[Dict[str, Any]]], Dict[str, Any]]) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be > 0")
        self._dataset = dataset
        self._batch_size = int(batch_size)
        self._shuffle = bool(shuffle)
        self._num_workers = int(num_workers)
        self._collate_fn = collate_fn

    def __iter__(self):
        n = len(self._dataset)
        indices = np.arange(n)
        if self._shuffle:
            np.random.shuffle(indices)
        for start in range(0, n, self._batch_size):
            batch_idx = indices[start: start + self._batch_size]
            batch = [self._dataset[int(i)] for i in batch_idx]
            yield self._collate_fn(batch)


def make_dataloader(dataset: SequenceDataset, batch_size: int, shuffle: bool, num_workers: int, collate_fn: Optional[Callable[[List[Dict[str, Any]]], Dict[str, Any]]] = None) -> DataLoader:
    """Factory to create a `DataLoader` for a given `SequenceDataset`."""
    if collate_fn is None:
        collate_fn = default_collate_fn
    return DataLoader(dataset=dataset, batch_size=batch_size, shuffle=shuffle, num_workers=num_workers, collate_fn=collate_fn)


def default_collate_fn(batch: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Default collate function producing padded arrays and masks.

    Returns a mapping with keys: `inputs` (np.ndarray), `lengths` (np.ndarray),
    `masks` (np.ndarray), `targets` (np.ndarray or None), `sequence_ids` (list).
    """
    sequences = [item["sequence"] for item in batch]
    targets = [item.get("target") for item in batch]
    seq_ids = [item.get("id") for item in batch]

    max_len = max((len(s) for s in sequences), default=0)
    # Determine pad token from first item's dataset? Assume pad token 0 if unknown
    pad = 0
    # Try to discover pad token by inspecting masks later; keep 0 as safe default

    inputs = _pad_batch(sequences, pad=pad, max_len=max_len)
    lengths = np.array([len(s) for s in sequences], dtype=np.int64)
    masks = _compute_masks(lengths, max_len)

    # Targets to numpy if not None
    if any(t is not None for t in targets):
        targets_arr = np.array([t for t in targets], dtype=object)
    else:
        targets_arr = None

    return {"inputs": inputs, "lengths": lengths, "masks": masks, "targets": targets_arr, "sequence_ids": seq_ids}


def _pad_batch(sequences: List[List[int]], pad: int, max_len: int) -> np.ndarray:
    arr = np.full((len(sequences), max_len), pad, dtype=np.int64)
    for i, seq in enumerate(sequences):
        trunc = seq[:max_len]
        arr[i, : len(trunc)] = np.array(trunc, dtype=np.int64)
    return arr


def _compute_masks(lengths: np.ndarray, max_len: int) -> np.ndarray:
    # mask: 1 for valid positions, 0 for padding
    batch_size = int(len(lengths))
    masks = np.zeros((batch_size, max_len), dtype=np.int8)
    for i, length in enumerate(lengths):
        masks[i, : int(length)] = 1
    return masks


__all__ = ["SequenceDataset", "DataLoader", "make_dataloader", "default_collate_fn"]
