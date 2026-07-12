"""Reusable experiment manager for model runs and artifact tracking."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


class ExperimentManager:
    """Create structured experiment directories and persist associated artifacts."""

    def __init__(self, output_dir: str | Path | None = None) -> None:
        self.output_dir = Path(output_dir or "artifacts/experiments")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.experiments_dir = self.output_dir / "experiments" if self.output_dir.name != "experiments" else self.output_dir
        self.experiments_dir.mkdir(parents=True, exist_ok=True)
        self._experiment_count = 0
        self._current_experiment: dict[str, Any] | None = None

    def _next_experiment_id(self) -> str:
        existing_ids = [path.name for path in self.experiments_dir.iterdir() if path.is_dir() and path.name.startswith("experiment_")]
        if existing_ids:
            numeric_ids = sorted(int(item.split("_")[-1]) for item in existing_ids if item.split("_")[-1].isdigit())
            next_number = max(numeric_ids, default=0) + 1
        else:
            next_number = 1
        return f"experiment_{next_number:03d}"

    def start_experiment(self, config: dict[str, Any]) -> str:
        """Create a new experiment directory and initialize the experiment record."""
        experiment_id = self._next_experiment_id()
        experiment_dir = self.experiments_dir / experiment_id
        experiment_dir.mkdir(parents=True, exist_ok=True)
        (experiment_dir / "plots").mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).isoformat()
        self._current_experiment = {
            "experiment_id": experiment_id,
            "timestamp": timestamp,
            "configuration": config,
            "metrics": {},
            "predictions": None,
            "model_path": None,
            "plots": [],
            "git_tag": None,
            "dataset_version": config.get("dataset_version"),
            "git_branch": config.get("git_branch"),
            "git_commit": config.get("git_commit"),
            "metadata": config.get("metadata", {}),
        }

        with (experiment_dir / "config.json").open("w", encoding="utf-8") as handle:
            json.dump(self._current_experiment["configuration"], handle, indent=2, sort_keys=True)

        with (experiment_dir / "README.txt").open("w", encoding="utf-8") as handle:
            handle.write(f"Experiment {experiment_id}\n")
            handle.write(f"Timestamp: {timestamp}\n")

        return experiment_id

    def log_metrics(self, metrics: dict[str, Any]) -> None:
        """Store evaluation metrics for the current experiment."""
        if self._current_experiment is None:
            raise ValueError("No active experiment")
        self._current_experiment["metrics"] = metrics
        experiment_dir = self.experiments_dir / self._current_experiment["experiment_id"]
        with (experiment_dir / "metrics.json").open("w", encoding="utf-8") as handle:
            json.dump(metrics, handle, indent=2, sort_keys=True)

    def log_predictions(self, predictions: pd.DataFrame) -> None:
        """Persist predictions for the current experiment."""
        if self._current_experiment is None:
            raise ValueError("No active experiment")
        self._current_experiment["predictions"] = predictions.to_dict(orient="records")
        experiment_dir = self.experiments_dir / self._current_experiment["experiment_id"]
        predictions.to_csv(experiment_dir / "predictions.csv", index=False)

    def log_model(self, model_path: str | Path) -> None:
        """Register a trained model artifact for the current experiment."""
        if self._current_experiment is None:
            raise ValueError("No active experiment")
        self._current_experiment["model_path"] = str(model_path)
        experiment_dir = self.experiments_dir / self._current_experiment["experiment_id"]
        if Path(model_path).exists():
            shutil.copy2(model_path, experiment_dir / "model.pkl")

    def log_plot(self, plot_path: str | Path, name: str) -> None:
        """Copy a plot artifact into the current experiment directory."""
        if self._current_experiment is None:
            raise ValueError("No active experiment")
        source = Path(plot_path)
        if source.exists():
            target = self.experiments_dir / self._current_experiment["experiment_id"] / "plots" / source.name
            shutil.copy2(source, target)
            self._current_experiment["plots"].append(target.name)

    def finalize(self) -> dict[str, Any]:
        """Finalize the current experiment and return its record."""
        if self._current_experiment is None:
            raise ValueError("No active experiment")
        experiment_dir = self.experiments_dir / self._current_experiment["experiment_id"]
        with (experiment_dir / "README.txt").open("a", encoding="utf-8") as handle:
            handle.write(f"Metrics: {json.dumps(self._current_experiment['metrics'])}\n")
            handle.write(f"Plots: {', '.join(self._current_experiment['plots'])}\n")
        return self._current_experiment
