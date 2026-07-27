"""Top-level orchestrator for Phase 6.

The `Orchestrator` wires ingest, training, inference, reporting and
visualization components to run an experiment end-to-end. The class is a
coordinator and keeps its behaviour minimal and well-logged.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional, NoReturn
import logging

from phase6.config import Config
from phase6.types import ManifestInfo, JSONDict, ExperimentInfo
import shutil
from pathlib import Path
import json
from datetime import datetime

logger = logging.getLogger("project")


class OrchestrationError(RuntimeError):
    """Raised when orchestration cannot complete."""


class Orchestrator:
    """Coordinate end-to-end Phase 6 execution.

    Parameters
    ----------
    config:
        Phase 6 `Config` instance used for defaults and snapshots.
    logger:
        Optional logger; defaults to the centralized project logger.
    experiment_manager:
        Instance providing `start_experiment` and `finalize_experiment`.
    """

    def __init__(self, config: Config, logger: Optional[logging.Logger] = None, experiment_manager: Optional[Any] = None) -> None:
        if not isinstance(config, Config):
            raise OrchestrationError("Orchestrator requires a valid Config instance")
        self._config = config
        self._logger = logger or logging.getLogger("project")
        if experiment_manager is None:
            raise OrchestrationError("Orchestrator requires an ExperimentManager instance")
        self._experiment_manager = experiment_manager

    def run_phase6(self, paths: Dict[str, str], overrides: Optional[Dict[str, Any]] = None) -> str:
        """Run Phase 6 pipeline using artifacts at `paths` and return manifest path.

        Parameters
        ----------
        paths:
            Mapping of role names to filesystem paths (as expected by the
            `Ingestor`).
        overrides:
            Optional configuration overrides to influence component
            construction.

        Returns
        -------
        str
            Path to the written phase manifest (JSON).

        Raises
        ------
        OrchestrationError
            On any failure during orchestration.
        """
        try:
            # Start experiment bookkeeping
            name = overrides.get("name") if overrides else None
            exp_info: ExperimentInfo = self._experiment_manager.start_experiment(name=name)

            # Build components for the experiment
            components = self._build_components(paths, overrides or {}, exp_info)

            # Ingest inputs when available
            phase5_inputs = None
            if "ingestor" in components:
                phase5_inputs, _ = components["ingestor"].load(paths)

            # Create model spec if factory available
            model_spec = None
            if "model_spec_factory" in components:
                # Provide basic dataset metadata from ingest when possible
                overrides_spec = {}
                try:
                    if phase5_inputs is not None and getattr(phase5_inputs, "vocabulary", None) is not None:
                        overrides_spec["vocab_size"] = len(phase5_inputs.vocabulary)
                except Exception as exc:
                    self._logger.debug("Failed to infer vocab_size from phase5_inputs: %s", exc)
                # fall back to config for sequence length
                overrides_spec.setdefault("sequence_length", getattr(self._config, "sequence_length", 50))
                model_spec = components["model_spec_factory"].create_model_spec(overrides_spec)

                # Instantiate the concrete model now that a valid ModelSpec
                # (with dataset-derived metadata) is available. This ensures
                # `components['model']` exists before training/inference.
                try:
                    # Avoid overwriting an existing model if one was provided
                    # by external wiring.
                    if "model" not in components:
                        from phase6.model import DeepLogModel

                        components["model"] = DeepLogModel(model_spec, config=self._config, logger=self._logger)
                except Exception:
                    # Temporary debugging: log full exception + traceback and re-raise
                    self._logger.exception("DeepLogModel import/instantiation failed")
                    raise

            # Training (if trainer present)
            training_result = None
            model_obj = None
            if "trainer" in components:
                trainer = components["trainer"]
                model_obj = components.get("model")
                train_loader = getattr(phase5_inputs, "train_df", None)
                val_loader = getattr(phase5_inputs, "test_df", None)
                if model_obj is None:
                    self._logger.info("No model implementation available; skipping training step")
                    training_result = None
                else:
                    training_result = trainer.train(model_obj, train_loader, val_loader)

            # Write training metrics
            if "report_generator" in components and training_result is not None:
                components["report_generator"].write_training_metrics(training_result)

            # Inference and decisions
            prediction_result = None
            decision_result = None
            if "inference" in components:
                inf = components["inference"]
                if model_obj is None:
                    self._logger.info("No model available; skipping inference step")
                    prediction_result = None
                else:
                    prediction_result = inf.run(model_obj, getattr(phase5_inputs, "test_df", []), top_k=getattr(self._config, "top_k", None))
            if "decision_engine" in components and prediction_result is not None:
                decision_result = components["decision_engine"].decide(prediction_result, threshold=getattr(self._config, "threshold", None))

            # Persist predictions and manifest
            if "report_generator" in components and decision_result is not None:
                # Capture predictions CSV path so it can be advertised in the
                # final manifest for downstream phases to discover.
                try:
                    predictions_path = components["report_generator"].write_predictions(decision_result)
                except Exception:
                    self._logger.exception("Failed to write predictions CSV")
                    predictions_path = None

            # Visualizations
            if "visualizer" in components and training_result is not None:
                try:
                    components["visualizer"].plot_training_metrics(training_result)
                except Exception:
                    self._logger.exception("Visualizer failed for training metrics")
            if "visualizer" in components and decision_result is not None:
                try:
                    components["visualizer"].plot_predictions_summary(decision_result)
                except Exception:
                    self._logger.exception("Visualizer failed for prediction summary")

            # Finalize and write manifest (pass predictions_path through)
            manifest_path = self._finalize_and_write_manifest(
                exp_info, components, phase5_inputs, model_spec, training_result, predictions_path
            )

            # Finalize experiment record
            try:
                self._experiment_manager.finalize_experiment(exp_info, {"manifest_path": manifest_path})
            except Exception:
                self._logger.exception("ExperimentManager.finalize_experiment failed")

            # Publish latest artifacts (best-effort; do not make this part of
            # experiment success). Log warnings but do not fail the run.
            try:
                self._publish_latest_artifacts(exp_info)
            except Exception:
                self._logger.warning("Publishing latest Phase 6 artifacts failed; continuing")

            return manifest_path

        except Exception as exc:
            self._handle_exception(exc)

    # ---- Private helpers ----
    def _handle_exception(self, exc: Exception) -> NoReturn:
        """Centralized exception handling for orchestration failures."""
        self._logger.exception("Orchestration failed: %s", exc)
        raise OrchestrationError(f"Orchestration failed: {exc}") from exc

    def _build_components(self, paths: Dict[str, str], overrides: Dict[str, Any], experiment_info: ExperimentInfo) -> Dict[str, Any]:
        """Instantiate pipeline components using standard module factories.

        This method performs lazy imports to avoid import-time side effects.
        """
        comps: Dict[str, Any] = {}

        # Ingest
        try:
            from phase6.ingest import Ingestor

            comps["ingestor"] = Ingestor(config=self._config, logger=self._logger)
        except Exception:
            self._logger.debug("Ingestor not available; continuing without it")

        # Model spec factory
        try:
            from phase6.model_spec import ModelSpecFactory

            comps["model_spec_factory"] = ModelSpecFactory(self._config)
        except Exception:
            self._logger.debug("ModelSpecFactory not available")

        # Trainer
        try:
            from phase6.trainer import Trainer

            # Trainer may need model_spec and experiment_info depending on implementation
            comps["trainer"] = Trainer(model_spec=None, config=self._config, logger=self._logger, experiment_info=experiment_info)
        except Exception:
            self._logger.debug("Trainer not available")

        # NOTE: model instantiation is intentionally deferred until runtime
        # when dataset-derived metadata (vocab_size, sequence_length) is
        # available. Do not create the model here.

        # Inference and decision
        try:
            from phase6.inference import InferenceEngine

            comps["inference"] = InferenceEngine(model_spec=None, config=self._config, logger=self._logger)
        except Exception:
            self._logger.debug("InferenceEngine not available")
        try:
            from phase6.decision_engine import DecisionEngine

            comps["decision_engine"] = DecisionEngine(config=self._config, logger=self._logger)
        except Exception:
            self._logger.debug("DecisionEngine not available")

        # Reporting and visualization
        try:
            from phase6.report_generator import ReportGenerator

            comps["report_generator"] = ReportGenerator(experiment_info=experiment_info, logger=self._logger, config=self._config)
        except Exception:
            self._logger.debug("ReportGenerator not available")
        try:
            from phase6.visualizer import Visualizer

            comps["visualizer"] = Visualizer(experiment_info=experiment_info, logger=self._logger, config=self._config)
        except Exception:
            self._logger.debug("Visualizer not available")

        # Persistence manager
        try:
            from phase6.persistence import PersistenceManager

            comps["persistence"] = PersistenceManager(experiment_info.path if hasattr(experiment_info, "path") else experiment_info.path, config=self._config, logger=self._logger)
        except Exception:
            self._logger.debug("PersistenceManager not available")

        return comps

    def _finalize_and_write_manifest(self, experiment_info: ExperimentInfo, components: Dict[str, Any], phase5_inputs: Optional[Any], model_spec: Optional[Any], training_result: Optional[Any], predictions_path: Optional[str] = None) -> str:
        """Assemble a `ManifestInfo` object and persist it via the report generator.

        Returns the path to the written manifest JSON.
        """
        gen_time = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

        inputs_snapshot: JSONDict = {}
        if phase5_inputs is not None:
            try:
                inputs_snapshot["vocab_size"] = len(getattr(phase5_inputs, "vocabulary", {}))
                inputs_snapshot["dataset_name"] = getattr(phase5_inputs, "dataset_name", None)
            except Exception:
                inputs_snapshot = {}

        artifacts: JSONDict = {}
        # Allow report_generator to supply artifact paths by convention
        try:
            if "report_generator" in components:
                # No formal API for artifact listing; keep minimal
                artifacts["reports_path"] = getattr(experiment_info, "reports_path", None)
                artifacts["plots_path"] = getattr(experiment_info, "plots_path", None)
                # Include predictions CSV path when available (backward-compatible)
                try:
                    if predictions_path:
                        artifacts["predictions_csv"] = str(predictions_path)
                except Exception:
                    self._logger.debug("No predictions path to include in manifest")
        except Exception as exc:
            self._logger.debug("Failed to gather artifacts info: %s", exc)

        model_spec_json: JSONDict = {}
        if model_spec is not None:
            try:
                model_spec_json = asdict(model_spec)
            except Exception as exc:
                self._logger.debug("Failed to convert model_spec to dict: %s", exc)
                model_spec_json = {}

        training_summary: JSONDict = {}
        if training_result is not None:
            try:
                training_summary = asdict(training_result)
            except Exception as exc:
                self._logger.debug("Failed to convert training_result to dict: %s", exc)
                training_summary = {}

        manifest = ManifestInfo(
            manifest_version="1.0",
            generated_on=gen_time,
            phase="phase6",
            inputs=inputs_snapshot,
            artifacts=artifacts,
            model_spec=model_spec_json,
            model_metadata={},
            training_summary=training_summary,
            git={},
            config_snapshot=asdict(self._config),
            experiment_id=experiment_info.experiment_id,
        )

        if "report_generator" not in components:
            raise OrchestrationError("ReportGenerator not available to write manifest")

        manifest_path = components["report_generator"].write_manifest(manifest)
        return manifest_path

    def _publish_latest_artifacts(self, experiment_info: ExperimentInfo) -> None:
        """Publish stable copies of key Phase 6 artifacts to artifacts/phase6/latest.

        This function is best-effort: failures are logged and do not affect
        experiment success. Uses `shutil.copy2` to preserve timestamps.
        """
        self._logger.info("Publishing latest Phase 6 artifacts...")
        try:
            # Resolve repository root (two levels up from this module)
            repo_root = Path(__file__).resolve().parent.parent
            latest_dir = repo_root / "artifacts" / "phase6" / "latest"
            latest_dir.mkdir(parents=True, exist_ok=True)

            # Sources inside the experiment
            reports_dir = Path(experiment_info.reports_path)
            manifests_dir = Path(experiment_info.manifests_path)

            files_to_copy = [
                (reports_dir / "predictions.csv", latest_dir / "predictions.csv"),
                (manifests_dir / "manifest.json", latest_dir / "manifest.json"),
                (reports_dir / "training_metrics.json", latest_dir / "training_metrics.json"),
            ]

            any_copied = False
            for src, dst in files_to_copy:
                try:
                    if src.exists():
                        shutil.copy2(src, dst)
                        any_copied = True
                    else:
                        self._logger.debug("Source not found for publishing: %s", src)
                except Exception as exc:
                    self._logger.warning("Failed to copy %s to %s: %s", src, dst, exc)

            if any_copied:
                # Write a small published info file alongside the latest artifacts
                info = {
                    "published_on": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                    "source_experiment": experiment_info.experiment_id,
                    "latest_dir": str(latest_dir),
                }
                try:
                    with (latest_dir / "published_info.json").open("w", encoding="utf-8") as fh:
                        json.dump(info, fh, indent=2)
                except Exception:
                    self._logger.debug("Failed to write published_info.json in %s", latest_dir)

                self._logger.info("Latest artifacts updated.")
            else:
                self._logger.warning("No Phase 6 artifacts were found to publish for experiment %s", experiment_info.experiment_id)
        except Exception as exc:  # pragma: no cover - best-effort publishing
            self._logger.warning("Failed to publish latest Phase 6 artifacts: %s", exc)


__all__ = ["Orchestrator", "OrchestrationError"]
