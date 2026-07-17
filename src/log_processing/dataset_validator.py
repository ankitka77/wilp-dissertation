"""Validate datasets, vocabularies and sequences."""
from __future__ import annotations

from typing import Any, Dict
import pandas as pd


class DatasetValidator:
    """Run validation checks and produce a report object."""

    def validate(self, parsed: pd.DataFrame, vocab: pd.DataFrame, sequences: pd.DataFrame, config: Dict[str, Any] | None = None) -> Dict[str, Any]:
        issues = []
        if parsed.empty:
            issues.append("No parsed events found")

        if vocab.empty:
            issues.append("Vocabulary is empty")

        if sequences.empty:
            issues.append("No sequences generated")

        # sequence length checks
        if not sequences.empty and "sequence_length" in sequences.columns:
            min_len = int(config.get("min_sequence_length", 1)) if config else 1
            max_len = int(config.get("max_sequence_length", 1000000)) if config else 1000000
            if sequences["sequence_length"].lt(min_len).any():
                issues.append("Some sequences shorter than min_sequence_length")
            if sequences["sequence_length"].gt(max_len).any():
                issues.append("Some sequences longer than max_sequence_length")

        result = {"is_valid": not bool(issues), "issues": issues, "summary": {"parsed_count": len(parsed), "vocab_size": len(vocab), "sequence_count": len(sequences)}}
        return result
