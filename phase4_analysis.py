
"""Phase 4 analysis pipeline for KPI anomaly detection with Isolation Forest."""

from __future__ import annotations

import project_bootstrap  # noqa: F401
import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from common.logging_utils import configure_logging
from common.settings import load_settings
from infrastructure.experiment_manager import ExperimentManager
from infrastructure.model_factory import ModelFactory
from preprocessing.pipeline import KPIFeatureEngineer
from visualization.plotter import VisualizationService

ROOT = Path(__file__).resolve().parent

logger = logging.getLogger("project")


def _publish_latest_artifacts(report_dir: Path, artifacts_base: Path) -> None:
    """Publish latest Phase 4 artifacts to a stable `artifacts/phase4/latest`.

    This is best-effort: failures are logged as warnings and do not raise.
    """
    logger.info("Publishing latest Phase 4 artifacts...")
    try:
        latest_dir = artifacts_base / "phase4" / "latest"
        latest_dir.mkdir(parents=True, exist_ok=True)

        # Copy anomaly_predictions.csv from report_dir when present
        src_preds = report_dir / "anomaly_predictions.csv"
        dst_preds = latest_dir / "anomaly_predictions.csv"
        if src_preds.exists():
            shutil.copy2(src_preds, dst_preds)
        else:
            logger.warning("Source predictions file not found for publishing: %s", src_preds)

        # Try several plausible manifest locations under the experiment layout
        # 1) manifests/manifest.json under the experiment directory
        # 2) manifest.json in report_dir
        manifest_copied = False
        possible_manifests = [
            report_dir.parent / "manifests" / "manifest.json",
            report_dir / "manifest.json",
            report_dir.parent / "manifest.json",
        ]
        for pm in possible_manifests:
            if pm.exists():
                try:
                    shutil.copy2(pm, latest_dir / "manifest.json")
                    manifest_copied = True
                    break
                except Exception as exc:
                    logger.warning("Failed to copy manifest %s: %s", pm, exc)

        if not manifest_copied:
            logger.warning("No manifest.json found to publish to latest Phase 4 artifacts")

        logger.info("Latest artifacts updated.")
    except Exception as exc:  # pragma: no cover - best-effort publishing
        logger.warning("Failed to publish latest Phase 4 artifacts: %s", exc)


def _resolve_feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Prepare a feature frame by selecting numeric columns with memory-efficient conversion."""
    engineer = KPIFeatureEngineer()
    feature_columns = engineer.get_numeric_feature_columns(frame)
    if not feature_columns:
        raise ValueError("No numeric feature columns are available for anomaly detection")

    prepared_columns: dict[str, pd.Series] = {}
    for column in feature_columns:
        numeric_values = pd.to_numeric(frame[column], errors="coerce")
        prepared_columns[column] = numeric_values.astype(np.float32).fillna(0.0)

    return pd.DataFrame(prepared_columns, index=frame.index)


def _build_artifact_paths(settings: Any) -> dict[str, Path]:
    """Build artifact directories for models, reports, experiments and plots."""
    base = ROOT / "artifacts"
    return {
        "base": base,
        "models": base / "models",
        "reports": base / "reports" / "phase4",
        "experiments": base / "experiments",
        "plots": base / "plots",
    }


def main() -> bool:
    """Run the Phase 4 end-to-end analysis pipeline."""
    logger = configure_logging("config/logging.yaml")
    logger.info("=" * 70)
    logger.info("PHASE 4 – KPI ANOMALY DETECTION WITH ISOLATION FOREST")
    logger.info("=" * 70)

    try:
        settings = load_settings(Path("config/settings.yaml"))
        artifact_paths = _build_artifact_paths(settings)
        for path in artifact_paths.values():
            path.mkdir(parents=True, exist_ok=True)

        report_dir = Path(settings.artifacts.reports_root) / "phase4"
        report_dir.mkdir(parents=True, exist_ok=True)

        train_path = ROOT / "data" / "processed" / "kpi_features_train.csv"
        test_path = ROOT / "data" / "processed" / "kpi_features_test.csv"
        if not train_path.exists() or not test_path.exists():
            raise FileNotFoundError("Phase 3 feature files not found. Run phase3_feature_engineering.py first.")

        train_frame = pd.read_csv(train_path)
        test_frame = pd.read_csv(test_path)

        train_features = _resolve_feature_frame(train_frame)
        _ = _resolve_feature_frame(test_frame)

        config = {
            "n_estimators": 100,
            "contamination": 0.05,
            "max_samples": "auto",
            "bootstrap": False,
            "random_state": settings.project.random_seed,
            "dataset_version": "phase3",
            "git_branch": "local",
            "git_commit": "unknown",
            "git_tag": None,
            "metadata": {"source": "phase3_feature_engineering"},
        }

        factory = ModelFactory()
        model = factory.create_model("isolation_forest", config={
            "n_estimators": config["n_estimators"],
            "contamination": config["contamination"],
            "max_samples": config["max_samples"],
            "bootstrap": config["bootstrap"],
            "random_state": config["random_state"],
        })
        model.train(train_features)

        train_predictions = model.predict(train_features)
        train_scores = model.predict_scores(train_features)
        metrics = model.evaluate(train_features, train_frame["label"].to_numpy(), train_predictions, y_scores=train_scores)

        predictions_frame = pd.DataFrame(
            {
                "timestamp": train_frame["timestamp"],
                "KPI ID": train_frame["KPI ID"],
                "prediction": train_predictions.reset_index(drop=True),
                "anomaly_score": train_scores.reset_index(drop=True),
            }
        )

        experiment_manager = ExperimentManager(output_dir=artifact_paths["experiments"])
        experiment_id = experiment_manager.start_experiment(config)
        experiment_manager.log_metrics(metrics)
        experiment_manager.log_predictions(predictions_frame)

        model_path = artifact_paths["models"] / f"{experiment_id}_model.pkl"
        model.save(model_path)
        experiment_manager.log_model(model_path)

        visualization_service = VisualizationService(artifact_paths["plots"])
        visualization_service.plot_anomaly_distribution(predictions_frame.assign(label=train_frame.get("label", 0)))
        visualization_service.plot_kpi_series(predictions_frame, value_col="anomaly_score")

        report_dir = artifact_paths["reports"]
        report_dir.mkdir(parents=True, exist_ok=True)
        metrics_path = report_dir / "phase4_metrics.json"
        with metrics_path.open("w", encoding="utf-8") as handle:
            json.dump(metrics, handle, indent=2)

        summary_path = report_dir / "phase4_summary.csv"
        pd.DataFrame([metrics]).to_csv(summary_path, index=False)

        predictions_path = report_dir / "anomaly_predictions.csv"
        predictions_frame.to_csv(predictions_path, index=False)

        classification_report_path = report_dir / "classification_report.txt"
        with classification_report_path.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(metrics.get("classification_report", {}), indent=2))

        experiment_manager.finalize()
        logger.info("Phase 4 analysis completed successfully")

        # Publish latest artifacts for downstream phases (best-effort)
        try:
            _publish_latest_artifacts(report_dir, artifact_paths["base"])
        except Exception:
            # _publish_latest_artifacts logs its own warnings; do not fail the run
            logger.warning("Publishing latest Phase 4 artifacts encountered errors; continuing")
        return True
    except Exception as exc:  # pragma: no cover - runtime guard
        logger.error("Phase 4 analysis failed: %s", exc, exc_info=True)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
