"""Template miner: mask variable tokens to produce canonical templates."""
from __future__ import annotations

import re
from typing import Pattern
import pandas as pd


class TemplateMiner:
    """Generate templates by masking common variable tokens.

    The miner replaces numbers, IPs, UUID-like tokens, file paths and hex
    tokens with a placeholder `<*>` to produce canonical templates.
    """

    MASK_PATTERNS: dict[str, Pattern] = {
        # IPv6 (basic groups), placed before IPv4 to avoid partial matches
        "IPV6": re.compile(r"\b(?:[0-9A-Fa-f]{1,4}:){2,7}[0-9A-Fa-f]{1,4}\b"),
        # MAC addresses: aa:bb:cc:dd:ee:ff or aa-bb-cc-dd-ee-ff or aabb.ccdd.eeff
        "MAC": re.compile(r"\b(?:[0-9A-Fa-f]{2}(?::|-)){5}[0-9A-Fa-f]{2}\b|\b(?:[0-9A-Fa-f]{4}\.){2}[0-9A-Fa-f]{4}\b"),
        "IP": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
        "UUID": re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),
        "HEX": re.compile(r"\b0x[0-9a-fA-F]+\b"),
        # scientific notation (1.23e+10, -1E-5)
        "SCINUM": re.compile(r"\b[+-]?(?:\d+(?:\.\d*)?|\.\d+)[eE][+-]?\d+\b"),
        # signed floating point numbers (including .5, 1.0, -2.3)
        "SIGNED_FLOAT": re.compile(r"\b[+-]?(?:\d+\.\d*|\.\d+)\b"),
        # fallback integer matcher (unsigned)
        "HDFS_BLOCK": re.compile(r"\b(blk|block)_-?\d+\b", re.IGNORECASE,),
        "NUMBER": re.compile(r"\b\d+\b"),
        "PATH": re.compile(r"(/[^\s]+)+"),
        "QUOTED": re.compile(r'"[^\"]*"|\'[^\']*\''),
    }

    def __init__(self, placeholder: str = "<*>") -> None:
        self.placeholder = placeholder

    def mine_templates(self, df: pd.DataFrame, message_col: str = "message") -> pd.DataFrame:
        # Use a shallow copy to avoid duplicating large underlying arrays
        # while still returning a DataFrame with the same columns/structure.
        out = df.copy(deep=False)
        # tolerate being given raw loader output by falling back to 'raw_line'
        if message_col not in out.columns:
            if "raw_line" in out.columns:
                out[message_col] = out["raw_line"].fillna("")
            else:
                out[message_col] = ""
        out["template"] = out[message_col].fillna("")

        def mask(text: str) -> str:
            s = text

            # Preserve the semantic prefix while masking the numeric block ID
            s = re.sub(
                r"\b(blk|block)_-?\d+\b",
                r"\1_<*>",
                s,
                flags=re.IGNORECASE,
            )

            # Apply all remaining generic masks
            for name, patt in self.MASK_PATTERNS.items():
                if name == "HDFS_BLOCK":
                    continue
                s = patt.sub(self.placeholder, s)

            # Collapse repeated placeholders
            s = re.sub(
                rf"({re.escape(self.placeholder)})+",
                self.placeholder,
                s,
            )

            return s.strip()

        out["template"] = out["template"].apply(mask)
        return out
