"""Entry point to execute the Phase 7 Fusion pipeline.

This launcher instantiates the existing Phase 7 `FusionOrchestrator` and
invokes its public `run` API. It performs minimal orchestration only and
does not implement any business logic.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import logging
import sys

from phase7.config.fusion_config import FusionConfig, FusionConfigLoadError
from phase7.fusion.fusion_orchestrator import FusionOrchestrator, FusionOrchestratorError
from phase7.normalization.normalization_strategy import (
    MinMaxNormalization,
    IdentityNormalization,
    ZScoreNormalization,
    NormalizationStrategy,
    NormalizationStrategyError,
)


def _configure_project_logger(level_name: str | None = None) -> logging.Logger:
    logger = logging.getLogger("project")
    level = getattr(logging, (level_name or "INFO").upper(), logging.INFO)
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)
        fmt = logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s")
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    return logger


def _pick_normalization_strategy(cfg: FusionConfig) -> NormalizationStrategy:
    # Choose concrete normalization strategy instance based on config value
    name = getattr(cfg.fusion, "normalization_strategy", None)
    if name is None:
        return IdentityNormalization()
    try:
        # Compare by name string to tolerate Enum or str
        n = str(name).lower()
        if n.endswith("min_max") or n == "min_max":
            return MinMaxNormalization()
        if n.endswith("z_score") or n == "z_score":
            return ZScoreNormalization()
        return IdentityNormalization()
    except Exception as exc:  # pragma: no cover - defensive
        raise NormalizationStrategyError("Failed to construct normalization strategy") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase 7 Fusion pipeline")
    parser.add_argument("--experiment-id", required=True, help="Experiment id for artifact output")
    parser.add_argument("--kpi-experiment-id", required=False, help="Optional KPI detector experiment id")
    parser.add_argument("--log-experiment-id", required=False, help="Optional log detector experiment id")
    parser.add_argument("--config", required=False, help="Optional path to Phase 7 config YAML/JSON")
    args = parser.parse_args(argv)

    project_root = Path(__file__).resolve().parent

    # Load Phase 7 configuration
    cfg_path = Path(args.config) if args.config else project_root / "phase7" / "config" / "settings.yaml"
    try:
        cfg = FusionConfig.load(cfg_path) if cfg_path.exists() else FusionConfig.load(None)
    except Exception as exc:
        print(f"Warning: failed to load Phase 7 config ({cfg_path}): {exc}; using defaults")
        cfg = FusionConfig()

    logger = _configure_project_logger(getattr(cfg.logging, "level", None).value if hasattr(cfg, "logging") else None)

    try:
        norm_strategy = _pick_normalization_strategy(cfg)
        orchestrator = FusionOrchestrator(cfg, normalization_strategy=norm_strategy, logger_=logger)

        logger.info("Starting Phase 7 Fusion orchestrator: experiment=%s", args.experiment_id)
        summary = orchestrator.run(
            experiment_id=args.experiment_id,
            kpi_detector_experiment_id=args.kpi_experiment_id,
            log_detector_experiment_id=args.log_experiment_id,
        )

        # Print concise result to stdout
        print("Phase 7 completed successfully.")
        print("Execution summary:")
        for k, v in summary.items():
            print(f"  {k}: {v}")
        return 0
    except FusionOrchestratorError as oe:
        print(f"Phase 7 orchestration failed: {oe}")
        return 1
    except Exception:
        logger.exception("Unhandled exception during Phase 7 execution")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
