"""Produce statistical summaries for event and sequence distributions."""
from __future__ import annotations

from typing import Dict
import pandas as pd


class SequenceProfiler:
    def profile_events(self, parsed: pd.DataFrame) -> pd.DataFrame:
        df = parsed.copy()
        table = df["template"].value_counts().reset_index()
        table.columns = ["template", "frequency"]
        return table

    def profile_sequences(self, sequences: pd.DataFrame) -> Dict[str, float]:
        if sequences.empty:
            return {"count": 0, "mean_length": 0.0, "median_length": 0.0, "max_length": 0, "min_length": 0}
        lengths = sequences["sequence_length"].astype(float)
        return {
            "count": len(sequences),
            "mean_length": float(lengths.mean()),
            "median_length": float(lengths.median()),
            "max_length": int(lengths.max()),
            "min_length": int(lengths.min()),
        }
