"""Load raw log files into a normalized DataFrame."""
from __future__ import annotations

from pathlib import Path
from typing import List
import hashlib
import logging
import pandas as pd

logger = logging.getLogger("project")


class LogDataLoader:
    """Load raw log lines from a directory of log files.

    This loader reads all text files in the input directory and returns a
    DataFrame with columns: `source`, `raw_line`.
    """

    def __init__(self, input_dir: str | Path = "data/logs/HDFS_v1") -> None:
        self.input_dir = Path(input_dir)

    def list_files(self) -> List[Path]:
        if not self.input_dir.exists():
            return []
        
        all_files = [p for p in sorted(self.input_dir.iterdir()) if p.is_file()]
        log_files = [p for p in all_files if p.suffix.lower() == ".log"]
        return log_files if log_files else all_files

    def load(self) -> pd.DataFrame:
        rows = []
        for path in self.list_files():
            logger.info("Reading %s", path.name)
            lineno = 0
            try:
                with path.open("r", encoding="utf-8", errors="ignore") as fh:
                    for lineno, line in enumerate(fh, start=1):
                        if not line.strip():
                            continue
                        try:
                            rows.append({"source": path.name, "raw_line": line.rstrip("\n")})
                        except Exception as e:
                            logger.warning(
                                "Skipping malformed line in %s at line %d: %s",
                                path.name,
                                lineno,
                                str(e),
                            )
                        if lineno % 100_000 == 0:
                            logger.info("%s: %d lines loaded", path.name, lineno)
            except Exception as e:
                logger.warning("Failed to read log file %s: %s", path, str(e))
                continue

            logger.info("Finished %s (%d lines)", path.name, lineno)

        return pd.DataFrame(rows)

    def fingerprint(self) -> str:
        """Return SHA-256 fingerprint of concatenated raw files (stable order)."""
        m = hashlib.sha256()
        for path in self.list_files():
            try:
                data = path.read_bytes()
            except Exception as e:
                logger.warning("Failed to read bytes for fingerprinting %s: %s", path, str(e))
                data = b""
            m.update(path.name.encode("utf-8") + b"\n")
            m.update(data)
            m.update(b"\n")
        return m.hexdigest()
