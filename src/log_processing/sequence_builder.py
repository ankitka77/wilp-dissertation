"""Build sequences from event streams using block grouping or sliding windows."""
from __future__ import annotations

from typing import List, Dict
import pandas as pd
from pathlib import Path


class SequenceBuilder:
    """Create training and test sequences from event streams.

    Default behaviour: if 'block_id' column exists, group by it to form sequences.
    Otherwise use sliding windows over `event_id` with configured window_size and stride.
    """

    def __init__(self, window_size: int = 10, stride: int = 1, train_ratio: float = 0.8) -> None:
        self.window_size = int(window_size)
        self.stride = int(stride)
        self.train_ratio = float(train_ratio)

    def build_sequences(self, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        if "block_id" in df.columns:
            seqs = self._from_blocks(df)
        else:
            seqs = self._from_sliding_windows(df)

        # split and annotate split label so downstream consumers know train/test
        total = len(seqs)
        train_cut = int(total * self.train_ratio)
        for i, s in enumerate(seqs):
            s["split"] = "train" if i < train_cut else "test"

        train = seqs[:train_cut]
        test = seqs[train_cut:]

        train_df = pd.DataFrame(train)
        test_df = pd.DataFrame(test)
        all_df = pd.DataFrame(seqs)
        return {"train": train_df, "test": test_df, "all": all_df}

    def _from_blocks(self, df: pd.DataFrame) -> List[Dict]:
        sequences = []
        for block, group in df.groupby("block_id", sort=False):
            events = group["event_id"].tolist()
            if not events:
                continue
            seq = {
                "sequence_id": f"block_{block}",
                "sequence_events": events,
                "sequence_length": len(events),
                "source": group["source"].iloc[0],
                "dataset": group["source"].iloc[0],
                "block_id": block,
                "session_id": group["session_id"].iloc[0] if "session_id" in group.columns else None,
            }
            # next-event style target for DeepLog: input is all events except last, target is last
            if len(events) >= 2:
                seq["input_sequence"] = events[:-1]
                seq["next_event_target"] = events[-1]
            else:
                seq["input_sequence"] = []
                seq["next_event_target"] = None

            sequences.append(seq)
        return sequences

    def _from_sliding_windows(self, df: pd.DataFrame) -> List[Dict]:
        events = df["event_id"].tolist()
        sequences = []
        n = len(events)
        for start in range(0, max(0, n - self.window_size + 1), self.stride):
            window = events[start : start + self.window_size]
            seq = {
                "sequence_id": f"win_{start}",
                "sequence_events": window,
                "sequence_length": len(window),
                "source": df["source"].iloc[0] if not df.empty else "",
                "dataset": df["source"].iloc[0] if not df.empty else "",
                "block_id": None,
                "session_id": df["session_id"].iloc[start] if "session_id" in df.columns and len(df["session_id"])>start else None,
            }
            # for sliding windows, define input as all but last, target as last
            if len(window) >= 2:
                seq["input_sequence"] = window[:-1]
                seq["next_event_target"] = window[-1]
            else:
                seq["input_sequence"] = []
                seq["next_event_target"] = None

            sequences.append(seq)
        return sequences
