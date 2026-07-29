from __future__ import annotations

from pathlib import Path
from typing import List
import csv


def read_csv_headers(path: Path) -> List[str]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration:
            return []
    return headers
