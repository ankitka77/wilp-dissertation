from __future__ import annotations

import logging
import json
from logging.handlers import RotatingFileHandler
from typing import Any, Dict
from pathlib import Path


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        payload: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(config) -> None:
    """Configure root logging based on configuration object.

    `config` is expected to have a `.logging` attribute with fields: level, console, file, file_path, max_bytes, backup_count
    """
    root = logging.getLogger()
    # Clear existing handlers and close them to release file descriptors
    for h in list(root.handlers):
        try:
            h.close()
        except Exception:
            pass
        root.removeHandler(h)

    level = getattr(logging, config.logging.level.upper(), logging.INFO)
    root.setLevel(level)

    formatter = JsonFormatter()

    if config.logging.console:
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(formatter)
        root.addHandler(ch)

    if config.logging.file:
        # Ensure the log directory exists before creating the file handler.
        log_path = Path(config.logging.file_path)
        log_dir = log_path.parent
        if str(log_dir) != "":
            # Create parent directories if they don't exist. Let exceptions propagate (e.g., permissions).
            log_dir.mkdir(parents=True, exist_ok=True)

        fh = RotatingFileHandler(str(log_path), maxBytes=config.logging.max_bytes, backupCount=config.logging.backup_count)
        fh.setLevel(level)
        fh.setFormatter(formatter)
        root.addHandler(fh)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
