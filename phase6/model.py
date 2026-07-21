"""DeepLog LSTM model implementation using PyTorch.

Provides a minimal DeepLog-style model that integrates with the existing
Trainer and InferenceEngine. The model implements `train_epoch`,
`predict_topk`, and `predict_probs` expected by the framework.
"""
from __future__ import annotations

from typing import Any, Iterable, List, Optional
import json
import re
import logging

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    import numpy as np
except Exception as exc:  # pragma: no cover - runtime dependency
    raise RuntimeError("PyTorch is required for the Phase 6 model: install torch") from exc

from dataclasses import asdict
from phase6.model_spec import ModelSpec
from phase6.config import Config

logger = logging.getLogger("project")


class DeepLogModel(nn.Module):
    """Simple DeepLog-style LSTM next-event predictor.

    Constructor accepts a `ModelSpec` instance and optional `Config`.
    """

    def __init__(self, spec: ModelSpec, config: Optional[Config] = None, logger: Optional[logging.Logger] = None) -> None:
        super().__init__()
        if not isinstance(spec, ModelSpec):
            raise TypeError("spec must be a ModelSpec instance")
        self.spec = spec
        self._config = config or Config()
        self._logger = logger or logging.getLogger("project")

        self.vocab_size = int(spec.vocab_size)
        self.embedding_dim = int(spec.embedding_dim)
        self.hidden_size = int(spec.hidden_size)
        self.num_layers = int(spec.num_layers)
        self.dropout = float(spec.dropout)
        self.pad_token = int(spec.pad_token)
        self.sequence_length = int(spec.sequence_length)

        # Layers
        self.embedding = nn.Embedding(self.vocab_size + 1, self.embedding_dim, padding_idx=self.pad_token)
        # use dropout only if num_layers > 1 as PyTorch ignores dropout otherwise
        lstm_dropout = self.dropout if self.num_layers > 1 else 0.0
        self.lstm = nn.LSTM(input_size=self.embedding_dim, hidden_size=self.hidden_size, num_layers=self.num_layers, batch_first=True, dropout=lstm_dropout)
        self.fc = nn.Linear(self.hidden_size, self.vocab_size + 1)
        # Optimizer placeholder (create lazily to allow caller to move model to device first)
        self._optim: Optional[torch.optim.Optimizer] = None

    # ---- Training API expected by Trainer ----
    def train_epoch(self, train_loader: Iterable[dict]) -> float:
        """Run one epoch of training over `train_loader`.

        Expects `train_loader` to yield batch dicts with keys `inputs` (np.ndarray),
        optional `lengths` (np.ndarray), and `targets` (iterable of ints).
        Returns average loss for the epoch.
        """
        self.train()
        # If a pandas DataFrame was passed directly as the train_loader,
        # convert it into an iterable of batch dicts with keys expected
        # by the training loop. This handles the common case where the
        # orchestrator passes a DataFrame produced by the Ingestor.
        try:
            import pandas as _pd  # type: ignore
        except Exception:
            _pd = None

        if _pd is not None and isinstance(train_loader, _pd.DataFrame):
            records = train_loader.to_dict(orient="records")

            def _iter_from_df():
                # Yield batches of examples (lists of sequences) using the
                # configured batch size so downstream training code receives
                # a proper batch-shaped input.
                batch_size = int(getattr(self._config, "batch_size", 32) or 32)
                batch_inputs = []
                batch_targets = []
                batch_lengths = []

                for rec in records:
                    # Normalize field names used by Phase5 outputs
                    if "inputs" in rec:
                        seq = rec.get("inputs")
                    elif "sequence_events" in rec:
                        seq = rec.get("sequence_events")
                    elif "input_sequence" in rec:
                        seq = rec.get("input_sequence")
                    else:
                        seq = rec

                    # targets may be explicit or be the last element
                    target = rec.get("targets") or rec.get("next_event_target")
                    if target is None:
                        try:
                            target = seq[-1] if seq else None
                        except Exception:
                            target = None

                    try:
                        length = len(seq) if seq is not None else 0
                    except Exception:
                        length = 0

                    batch_inputs.append(seq)
                    batch_targets.append(target)
                    batch_lengths.append(length)

                    if len(batch_inputs) >= batch_size:
                        yield {"inputs": list(batch_inputs), "targets": list(batch_targets), "lengths": list(batch_lengths)}
                        batch_inputs = []
                        batch_targets = []
                        batch_lengths = []

                # yield any remaining
                if batch_inputs:
                    yield {"inputs": list(batch_inputs), "targets": list(batch_targets), "lengths": list(batch_lengths)}

            train_iter = _iter_from_df()
        else:
            train_iter = train_loader
        # Create optimizer lazily so its state is preserved across epochs.
        if getattr(self, "_optim", None) is None:
            self._optim = torch.optim.Adam(self.parameters(), lr=float(getattr(self._config, "learning_rate", 0.001)))
        optim = self._optim
        criterion = nn.CrossEntropyLoss()

        total_loss = 0.0
        total_examples = 0

        for batch in train_iter:
            inputs = batch.get("inputs")
            targets = batch.get("targets")
            lengths = batch.get("lengths")

            if inputs is None or targets is None:
                # Skip malformed batch
                continue

            # Convert to tensors on the same device as model parameters.
            # Inputs may be numeric arrays or sequences of token ids; if the
            # data is string-typed (e.g. templates or numeric strings) try to
            # coerce to integer token ids. Provide clear error if conversion
            # is not possible.
            device = next(self.parameters()).device
            arr = np.asarray(inputs)
            if arr.dtype.kind in ("U", "S", "O"):
                # Inputs are string/object-typed; treat `inputs` as a batch of
                # sequences and parse each sequence into integer token ids.
                processed: List[List[int]] = []
                processed_targets: List[int] = []
                processed_lengths: List[int] = []

                # Ensure targets and lengths are list-like to zip with inputs
                if not isinstance(targets, (list, tuple, np.ndarray)):
                    targets_list = [targets] * len(inputs)
                else:
                    targets_list = list(targets)
                if not isinstance(lengths, (list, tuple, np.ndarray)):
                    lengths_list = [lengths] * len(inputs)
                else:
                    lengths_list = list(lengths)

                for seq, tar, llen in zip(inputs, targets_list, lengths_list):
                    # Normalize string-encoded sequences (JSON or comma-separated)
                    if isinstance(seq, str):
                        s = seq.strip()
                        parsed_seq = None
                        try:
                            parsed = json.loads(s)
                            if isinstance(parsed, list):
                                parsed_seq = parsed
                            else:
                                parsed_seq = [parsed]
                        except Exception:
                            if "," in s:
                                parsed_seq = [p.strip().strip("[]") for p in s.split(",")]
                            else:
                                parts = [p.strip().strip("[]") for p in s.split()]
                                parsed_seq = parts
                        seq_list = parsed_seq
                    elif isinstance(seq, (list, tuple, np.ndarray)):
                        seq_list = list(seq)
                    else:
                        seq_list = [seq]

                    # Convert elements to int token ids, skip non-numeric tokens
                    seq_ints: List[int] = []
                    for e in seq_list:
                        if isinstance(e, str):
                            s = e.strip()
                            m = re.findall(r"-?\\d+", s)
                            if m:
                                try:
                                    seq_ints.append(int(m[0]))
                                    continue
                                except Exception:
                                    pass
                            cleaned = re.sub(r"[^0-9-]", "", s)
                            if cleaned:
                                try:
                                    seq_ints.append(int(cleaned))
                                    continue
                                except Exception:
                                    pass
                            # skip non-numeric token
                            continue
                        try:
                            seq_ints.append(int(e))
                        except Exception:
                            continue

                    # If any numeric tokens parsed, keep this example
                    if seq_ints:
                        processed.append(seq_ints)
                        processed_targets.append(tar)
                        try:
                            processed_lengths.append(int(llen) if llen is not None else len(seq_ints))
                        except Exception:
                            processed_lengths.append(len(seq_ints))

                if not processed:
                    # Nothing to train on in this batch; skip
                    continue

                # Create a 2D numpy int array (may be ragged; let downstream handle shapes)
                try:
                    arr = np.array(processed, dtype=np.int64)
                except Exception:
                    arr = np.empty(len(processed), dtype=object)
                    for i, r in enumerate(processed):
                        arr[i] = np.asarray(r, dtype=np.int64)

                # Replace targets/lengths with processed versions so they align
                targets = processed_targets
                lengths = processed_lengths

            # Infer correct per-sequence lengths from the parsed data.
            # The incoming `lengths` (from DataFrame preprocessing) may be
            # computed on raw string values (character counts) and therefore
            # be incorrect. Prefer lengths derived from the parsed sequences
            # (when available) or from the array shape.
            inferred_lengths = None
            try:
                # If `arr` is an object-dtype (ragged), use the parsed `processed`
                # list where available; otherwise derive from array shape.
                if isinstance(arr, np.ndarray) and arr.dtype == object:
                    # arr contains numpy arrays per element; compute lengths per entry
                    inferred_lengths = np.array([int(a.shape[0]) if hasattr(a, 'shape') else len(a) for a in arr], dtype=np.int64)
                elif isinstance(arr, np.ndarray):
                    # Regular 2D numeric array
                    if arr.ndim == 1:
                        inferred_lengths = np.ones(len(arr), dtype=np.int64)
                    else:
                        inferred_lengths = np.full(arr.shape[0], arr.shape[1], dtype=np.int64)
            except Exception:
                inferred_lengths = None

            # Decide which lengths to use: prefer inferred_lengths when available
            if inferred_lengths is not None:
                lens = torch.tensor(inferred_lengths, dtype=torch.long, device=device)
            else:
                if lengths is not None:
                    lens = torch.tensor(np.asarray(lengths), dtype=torch.long, device=device)
                else:
                    lens = None

            # If arr is an object-dtype (ragged sequences), pad/truncate to a
            # 2D integer array of shape (batch, max_seq_len) using pad_token so
            # PyTorch can consume it. Otherwise convert directly.
            if isinstance(arr, np.ndarray) and arr.dtype == object:
                try:
                    # Build padded 2D array
                    seq_lists = [np.asarray(r, dtype=np.int64) for r in arr]
                    max_len = max((s.shape[0] for s in seq_lists), default=0)
                    if max_len == 0:
                        # nothing numeric in this batch
                        continue
                    padded = np.full((len(seq_lists), max_len), fill_value=self.pad_token, dtype=np.int64)
                    for i, s in enumerate(seq_lists):
                        length = min(s.shape[0], max_len)
                        if length > 0:
                            padded[i, :length] = s[:length]
                    arr = padded
                except Exception:
                    raise TypeError("Failed to coerce ragged sequences into numeric array for training")
            x = torch.tensor(arr, dtype=torch.long, device=device)
            y = torch.tensor(np.asarray(targets), dtype=torch.long, device=device)

            optim.zero_grad()
            logits = self._forward_logits(x, lens)
            try:
                loss = criterion(logits, y)
            except Exception as exc:
                self._logger.exception("Loss computation failed: %s", exc)
                raise
            loss.backward()
            optim.step()

            batch_size = x.shape[0]
            total_loss += float(loss.item()) * batch_size
            total_examples += batch_size

        avg_loss = float(total_loss / total_examples) if total_examples > 0 else 0.0
        return avg_loss

    # ---- Inference API expected by InferenceEngine ----
    def predict_probs(self, inputs: Any) -> List[List[float]]:
        """Return predicted probability distributions per example.

        `inputs` may be a numpy array or list of sequences (padded). Returns a
        list of lists of floats (length = vocab_size+1) per example.
        """
        self.eval()
        with torch.no_grad():
            device = next(self.parameters()).device
            x = self._prepare_inputs_for_inference(inputs, device=device)
            # no lengths available at inference; assume full
            logits = self._forward_logits(x, None)
            probs = F.softmax(logits, dim=1)
            out = [list(map(float, p.cpu().numpy().tolist())) for p in probs]
        return out

    def predict_topk(self, inputs: Any, k: int) -> List[List[int]]:
        """Return top-k predicted token ids per example."""
        self.eval()
        with torch.no_grad():
            device = next(self.parameters()).device
            x = self._prepare_inputs_for_inference(inputs, device=device)
            logits = self._forward_logits(x, None)
            topk = torch.topk(logits, k=min(int(k), logits.shape[1]), dim=1)
            inds = topk.indices.cpu().tolist()
        return inds

    def _prepare_inputs_for_inference(self, inputs: Any, device: Optional[torch.device] = None) -> torch.Tensor:
        """Normalize and pad `inputs` for inference.

        Accepts lists/arrays of sequences where each sequence may be a list
        of ints, a JSON string like "[1,2,3]", a comma-separated string,
        or whitespace-separated tokens. Non-numeric tokens are skipped. If a
        sequence yields no numeric tokens, it is replaced by a single
        `pad_token` so the model can still produce a prediction.
        """
        # Helper to parse a single sequence into list[int]
        def parse_seq(seq) -> List[int]:
            if seq is None:
                return []
            if isinstance(seq, (list, tuple, np.ndarray)):
                seq_list = list(seq)
            elif isinstance(seq, str):
                s = seq.strip()
                try:
                    parsed = json.loads(s)
                    if isinstance(parsed, list):
                        seq_list = parsed
                    else:
                        seq_list = [parsed]
                except Exception:
                    if "," in s:
                        seq_list = [p.strip().strip("[]") for p in s.split(",") if p.strip()]
                    else:
                        seq_list = [p.strip().strip("[]") for p in s.split() if p.strip()]
            else:
                seq_list = [seq]

            out: List[int] = []
            for e in seq_list:
                if isinstance(e, str):
                    s = e.strip()
                    m = re.findall(r"-?\d+", s)
                    if m:
                        try:
                            out.append(int(m[0]))
                            continue
                        except Exception:
                            pass
                    cleaned = re.sub(r"[^0-9-]", "", s)
                    if cleaned:
                        try:
                            out.append(int(cleaned))
                            continue
                        except Exception:
                            pass
                    continue
                try:
                    out.append(int(e))
                except Exception:
                    continue
            return out

        # If single sequence provided, wrap into batch
        if not isinstance(inputs, (list, tuple, np.ndarray)) or (isinstance(inputs, np.ndarray) and inputs.dtype == object):
            # treat as single example unless it's an array of sequences
            batch = [inputs]
        else:
            batch = list(inputs)

        parsed = [parse_seq(s) for s in batch]
        # Replace empty sequences with pad_token
        norm = [p if p else [self.pad_token] for p in parsed]

        # Truncate/pad using model.sequence_length if available, otherwise max length
        max_len = min(int(self.sequence_length), max((len(p) for p in norm), default=1)) if getattr(self, 'sequence_length', None) else max((len(p) for p in norm), default=1)
        padded = np.full((len(norm), max_len), fill_value=self.pad_token, dtype=np.int64)
        for i, p in enumerate(norm):
            length = min(len(p), max_len)
            if length > 0:
                padded[i, :length] = np.array(p[:length], dtype=np.int64)

        return torch.tensor(padded, dtype=torch.long, device=device)

    # ---- Helpers ----
    def _forward_logits(self, x: torch.Tensor, lengths: Optional[torch.Tensor]) -> torch.Tensor:
        """Compute logits for the next-event prediction using the last valid LSTM output."""
        # x: (batch, seq_len)
        embeds = self.embedding(x)

        if lengths is not None:
            # pack padded sequence for efficiency
            try:
                packed = nn.utils.rnn.pack_padded_sequence(embeds, lengths.cpu().numpy(), batch_first=True, enforce_sorted=False)
                packed_out, _ = self.lstm(packed)
                out, _ = nn.utils.rnn.pad_packed_sequence(packed_out, batch_first=True, total_length=embeds.size(1))
            except Exception:
                # fallback to un-packed path
                out, _ = self.lstm(embeds)
        else:
            out, _ = self.lstm(embeds)

        # select last valid output per sequence
        if lengths is not None:
            idx = (lengths - 1).clamp(min=0).to(torch.long)
            batch_idx = torch.arange(out.size(0), device=out.device)
            last = out[batch_idx, idx, :]
        else:
            last = out[:, -1, :]

        logits = self.fc(last)
        return logits


__all__ = ["DeepLogModel"]
