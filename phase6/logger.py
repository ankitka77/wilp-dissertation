"""Central logger factory for Phase 6.

This module exposes `LoggerFactory` which creates named loggers that write
to both console and an experiment-scoped log file. Handlers are added only
once per logger name to avoid duplicate records on repeated calls.

The implementation follows the frozen Phase 6 blueprint and uses the
project-wide logger name prefix `project`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
import logging
from logging import Logger
from logging.handlers import RotatingFileHandler

from phase6.config import Config, ConfigurationError

PROJECT_LOGGER_NAME = "project"


class LoggerFactory:
    """Factory that produces configured loggers for an experiment.

    Parameters
    ----------
    config:
        Phase 6 `Config` instance. Used to derive logging level and default
        experiment root if `experiment_path` is not provided.
    experiment_path:
        Optional path to an experiment directory. If provided, logs are written
        to `<experiment_path>/logs/<name>.log`. Otherwise `config.experiment_root`
        is used.
    """

    def __init__(self, config: Config, experiment_path: Optional[str] = None) -> None:
        if not isinstance(config, Config):
            raise ConfigurationError("LoggerFactory requires a valid Config instance")
        self._config = config
        self._experiment_path = Path(experiment_path) if experiment_path is not None else Path(self._config.experiment_root)

    def get_logger(self, name: str) -> Logger:
        """Return a configured logger for `name`.

        The logger writes to console and to a file at
        `<experiment_path>/logs/{name}.log`. Handlers are idempotent: calling
        this method multiple times for the same `name` will not add duplicate
        handlers.

        Parameters
        ----------
        name:
            Short, filesystem-safe logger name (used for the file name).

        Returns
        -------
        logging.Logger
            Configured logger instance.
        """
        if not name or not isinstance(name, str):
            raise ValueError("`name` must be a non-empty string")

        logger_name = f"{PROJECT_LOGGER_NAME}.{name}"
        logger = logging.getLogger(logger_name)

        # Determine desired level from config
        level_name = (self._config.logging_level or "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)
        logger.setLevel(level)

        # Ensure log directory exists
        logs_dir = self._experiment_path / "logs"
        try:
            logs_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            raise ConfigurationError(f"Unable to create logs directory: {logs_dir}: {exc}") from exc

        file_path = logs_dir / f"{name}.log"

        # Idempotent handler creation: check existing handler names
        existing_names = {getattr(h, "name", None) for h in logger.handlers}

        file_handler_name = f"{name}_file"
        console_handler_name = f"{name}_console"

        formatter = logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s")

        if file_handler_name not in existing_names:
            # RotatingFileHandler to limit file size; small default values
            # are chosen to keep behavior safe in unit tests and CI.
            file_handler = RotatingFileHandler(filename=str(file_path), maxBytes=10 * 1024 * 1024, backupCount=5)
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            file_handler.name = file_handler_name
            logger.addHandler(file_handler)

        if console_handler_name not in existing_names:
            console = logging.StreamHandler()
            console.setLevel(level)
            console.setFormatter(formatter)
            console.name = console_handler_name
            logger.addHandler(console)

        return logger

    __all__ = ["PROJECT_LOGGER_NAME", "LoggerFactory"]
