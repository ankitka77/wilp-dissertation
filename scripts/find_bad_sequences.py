#!/usr/bin/env python3
"""
Diagnostic script to find problematic `sequence_events` rows in Phase5 CSVs.

Usage:
    python scripts/find_bad_sequences.py \
        --csv artifacts/reports/phase5/training_sequences.csv \
        --limit 20

The script prints the number of problematic rows and a sample of raw values
and parsed tokens that do not contain any integer substrings.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, List

import pandas as pd  # type: ignore


def coerce(v: Any) -> List[str]:
    if pd.isna(v):
        return []
    s = str(v).strip()
    # try json
    try:
        parsed = json.loads(s)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
        return [str(parsed)]
    except Exception:
        pass
    # comma separated
    if "," in s:
        parts = [p.strip().strip("[]") for p in s.split(",")]
        return [p for p in parts]
    # whitespace separated
    parts = [p.strip().strip("[]") for p in s.split()]
    if parts:
        return [p for p in parts]
    return [s]


def find_bad_rows(csv_path: Path, col: str = "sequence_events", limit: int = 20):
    if not csv_path.exists():
        raise SystemExit(f"CSV file not found: {csv_path}")

    df = pd.read_csv(csv_path)

    bad = []
    for i, row in df.iterrows():
        raw = row.get(col, "")
        seq = coerce(raw)
        # If any token has a digit substring, consider it OK
        ok = False
        for token in seq:
            if re.search(r"-?\d+", str(token)):
                ok = True
                break
        if not ok:
            bad.append((i, raw, seq))

    print(f"Checked {len(df)} rows. Found {len(bad)} problematic rows where no integer token was detected.")
    if not bad:
        return

    print(f"Showing up to {limit} examples:\n")
    for i, raw, seq in bad[:limit]:
        print(f"Row index: {i}")
        print(" Raw value:", repr(raw))
        print(" Parsed tokens:", seq)
        print("---")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=False, default="artifacts/reports/phase5/training_sequences.csv", help="Path to sequences CSV")
    p.add_argument("--col", required=False, default="sequence_events", help="Column name to inspect")
    p.add_argument("--limit", required=False, type=int, default=20, help="How many examples to show")
    args = p.parse_args()

    csv_path = Path(args.csv)
    try:
        find_bad_rows(csv_path, col=args.col, limit=args.limit)
    except Exception as exc:
        print("Error:", exc)
        raise


if __name__ == "__main__":
    main()
