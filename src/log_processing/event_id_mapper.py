"""Map templates to deterministic event IDs and produce vocabulary outputs."""
from __future__ import annotations

from typing import Dict
import pandas as pd
import json
from pathlib import Path


class EventIdMapper:
    """Create deterministic event IDs from template strings.

    The mapper sorts unique templates and assigns incremental IDs starting at 1.
    """

    def __init__(self) -> None:
        self.vocab: Dict[str, int] = {}

    def build_vocabulary(self, df: pd.DataFrame, template_col: str = "template") -> pd.DataFrame:
        # compute frequencies once using value_counts (vectorized)
        counts = df[template_col].dropna()
        value_counts = counts.value_counts()
        print(f">> Unique templates discovered: {len(value_counts):,}")

        # create deterministic template list by sorting template strings
        templates = sorted(value_counts.index.tolist())
        # assign deterministic event ids starting at 1
        self.vocab = {t: i + 1 for i, t in enumerate(templates)}
        rows = [
            {"template": t, "event_id": self.vocab[t], "frequency": int(value_counts[t])}
            for t in templates
        ]
        print(f">> Event vocabulary size: {len(self.vocab):,}")
        return pd.DataFrame(rows)

    def map_event_ids(self, df: pd.DataFrame, template_col: str = "template") -> pd.DataFrame:
        # Shallow copy to avoid duplicating millions of rows.
        # We only add one new column, so a deep copy is unnecessary.
        out = df.copy(deep=False)

        out["event_id"] = (
            out[template_col]
            .map(self.vocab)
            .fillna(0)
            .astype("int32")
        )

        return out

    def save_vocab_csv(self, path: str | Path) -> None:
        df = pd.DataFrame([{"template": t, "event_id": i} for t, i in self.vocab.items()])
        df.to_csv(path, index=False)

    def save_vocab_json(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"vocabulary": self.vocab}, handle, indent=2, ensure_ascii=False)
