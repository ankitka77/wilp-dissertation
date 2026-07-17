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
        templates = sorted(df[template_col].dropna().unique())
        self.vocab = {t: i + 1 for i, t in enumerate(templates)}
        rows = [{"template": t, "event_id": self.vocab[t], "frequency": int((df[template_col] == t).sum())} for t in templates]
        return pd.DataFrame(rows)

    def map_event_ids(self, df: pd.DataFrame, template_col: str = "template") -> pd.DataFrame:
        out = df.copy()
        out["event_id"] = out[template_col].map(self.vocab).fillna(0).astype(int)
        return out

    def save_vocab_csv(self, path: str | Path) -> None:
        df = pd.DataFrame([{"template": t, "event_id": i} for t, i in self.vocab.items()])
        df.to_csv(path, index=False)

    def save_vocab_json(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"vocabulary": self.vocab}, handle, indent=2, ensure_ascii=False)
