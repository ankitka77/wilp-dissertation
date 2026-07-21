"""Structural parser for raw log lines."""
from __future__ import annotations

import re
import pandas as pd


class LogParser:
    """Parse raw log lines into structured fields.

    The parser uses a set of simple regex rules to extract an ISO-like
    timestamp (if present) and a message body. Other fields are preserved
    in `raw_line`.
    """
    TIMESTAMP_RE = re.compile(r"^(?P<timestamp>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:,\d+)?)\s+(?P<message>.*)$")

    # Limit severity tokens to common log levels to avoid false positives
    LEVEL_TOKENS = r"(?:INFO|WARN|WARNING|ERROR|DEBUG|TRACE|FATAL|CRITICAL)"

    # HDFS-like lines: known level then Java class/logger then message
    HDFS_CLASS_RE = re.compile(rf"^(?P<level>{LEVEL_TOKENS})\s+(?P<component>[\w\.-]+):?\s*(?P<message>.*)$")

    # Host + component + optional pid + required level + message
    HOST_COMP_PID_LEVEL_RE = re.compile(rf"^(?P<host>\S+)\s+(?P<component>[^\s\[]+)(?:\[(?P<pid>\d+)\])?\s+(?P<level>{LEVEL_TOKENS})\s*:?\s*(?P<message>.*)$")

    # Component + optional pid + required level + message
    COMP_PID_LEVEL_RE = re.compile(rf"^(?P<component>[^\s\[]+)(?:\[(?P<pid>\d+)\])?\s+(?P<level>{LEVEL_TOKENS})\s*:?\s*(?P<message>.*)$")

    THREAD_RE = re.compile(r"\b(Thread[-_ ]?\d+|tid[:=]?\d+|thread[:=]?\w+)\b", re.IGNORECASE)
    BLOCK_RE = re.compile(r"\b(blk_[0-9_]+|block_[0-9_]+)\b", re.IGNORECASE)
    SESSION_RE = re.compile(r"\b(session[_-]?[A-Za-z0-9-]+|sessionId[:=][A-Za-z0-9-]+)\b", re.IGNORECASE)

    def __init__(self) -> None:
        pass

    def parse(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        out = df.copy()
        # Preserve raw line and create structured fields; keep compatibility
        out["timestamp"] = None
        out["hostname"] = None
        out["level"] = None
        out["component"] = None
        out["pid"] = None
        out["thread_id"] = None
        out["block_id"] = None
        out["session_id"] = None
        # start with the raw line as the baseline message
        out["message"] = out["raw_line"].fillna("")

        # Step 1: extract timestamp and message remainder using vectorized extract
        ts_extract = out["raw_line"].str.extract(self.TIMESTAMP_RE)
        if "timestamp" in ts_extract.columns:
            out.loc[ts_extract["timestamp"].notna(), "timestamp"] = ts_extract.loc[ts_extract["timestamp"].notna(), "timestamp"]
        if "message" in ts_extract.columns:
            # where timestamp matched, replace message with remainder
            mask_ts = ts_extract["message"].notna()
            out.loc[mask_ts, "message"] = ts_extract.loc[mask_ts, "message"].str.strip()

        # Work on the remainder message
        remainder = out["message"].fillna("")

        # Step 2: known severity tokens at start
        known_levels = {"INFO", "WARN", "WARNING", "ERROR", "DEBUG", "TRACE", "FATAL", "CRITICAL"}

        # For very large inputs, perform partitioning in chunks to avoid
        # creating huge intermediate arrays that may cause MemoryError.
        def _partition_series(s: pd.Series) -> pd.DataFrame:
            # use partition which is more memory-friendly than split
            return s.str.partition(" ")

        total = len(remainder)
        if total > 500_000:
            parts_first = []
            # only need the first token for all rows
            for start in range(0, total, 100_000):
                chunk = remainder.iloc[start : start + 100_000]
                p = _partition_series(chunk)
                parts_first.append(p.iloc[:, 0].fillna(""))
            first_token = pd.concat(parts_first)
        else:
            first_token = _partition_series(remainder).iloc[:, 0].fillna("")

        mask_known = first_token.isin(known_levels)
        if mask_known.any():
            out.loc[mask_known, "level"] = first_token[mask_known]

            # compute the rest (text after the first token) only for known rows
            known_idx = mask_known[mask_known].index
            if len(known_idx) > 0:
                # process known rows in chunks
                rest_parts = []
                for start in range(0, len(known_idx), 100_000):
                    sub_idx = known_idx[start : start + 100_000]
                    chunk = remainder.loc[sub_idx]
                    rest_parts.append(_partition_series(chunk).iloc[:, 2].fillna(""))
                rest = pd.concat(rest_parts)
            else:
                rest = pd.Series([], dtype=object)

            has_colon = rest.str.contains(":")
            if has_colon.any():
                colon_idx = has_colon[has_colon].index
                comps = rest.loc[colon_idx].str.split(":", n=1)
                out.loc[colon_idx, "component"] = comps.str[0].str.strip()
                out.loc[colon_idx, "message"] = comps.str[1].str.strip()
            # rows without colon: first token after level is component
            no_colon_idx = has_colon[~has_colon].index
            if len(no_colon_idx) > 0:
                toks = rest.loc[no_colon_idx].str.split(n=1)
                out.loc[no_colon_idx, "component"] = toks.str[0]
                out.loc[no_colon_idx, "message"] = toks.str[1].fillna("").str.strip()

        # Step 3: host/component/pid/level style for remaining rows
        mask_unhandled = out["level"].isna()
        if mask_unhandled.any():
            host_comp = remainder[mask_unhandled].str.extract(self.HOST_COMP_PID_LEVEL_RE)
            # host_comp columns correspond to our named groups if available
            if not host_comp.empty:
                # only assign for rows where any group matched
                matched = host_comp.dropna(how="all").index
                if len(matched) > 0:
                    if "host" in host_comp.columns:
                        out.loc[matched, "hostname"] = host_comp.loc[matched, "host"].values
                    if "component" in host_comp.columns:
                        out.loc[matched, "component"] = host_comp.loc[matched, "component"].values
                    if "pid" in host_comp.columns:
                        out.loc[matched, "pid"] = host_comp.loc[matched, "pid"].values
                    if "level" in host_comp.columns:
                        out.loc[matched, "level"] = host_comp.loc[matched, "level"].values
                    if "message" in host_comp.columns:
                        out.loc[matched, "message"] = host_comp.loc[matched, "message"].fillna("").str.strip().values

        # Step 4: component-level style for any still-unhandled rows
        mask_unhandled = out["level"].isna()
        if mask_unhandled.any():
            comp_pid = remainder[mask_unhandled].str.extract(self.COMP_PID_LEVEL_RE)
            if not comp_pid.empty:
                matched = comp_pid.dropna(how="all").index
                if len(matched) > 0:
                    if "component" in comp_pid.columns:
                        out.loc[matched, "component"] = comp_pid.loc[matched, "component"].values
                    if "pid" in comp_pid.columns:
                        out.loc[matched, "pid"] = comp_pid.loc[matched, "pid"].values
                    if "level" in comp_pid.columns:
                        out.loc[matched, "level"] = comp_pid.loc[matched, "level"].values
                    if "message" in comp_pid.columns:
                        out.loc[matched, "message"] = comp_pid.loc[matched, "message"].fillna("").str.strip().values

        # Step 5: extract thread, block, session ids from the message body using vectorized extract
        out.loc[:, "thread_id"] = out["message"].str.extract(self.THREAD_RE).fillna("").iloc[:, 0].replace({"": None})
        out.loc[:, "block_id"] = out["message"].str.extract(self.BLOCK_RE).fillna("").iloc[:, 0].replace({"": None})
        out.loc[:, "session_id"] = out["message"].str.extract(self.SESSION_RE).fillna("").iloc[:, 0].replace({"": None})

        return out
