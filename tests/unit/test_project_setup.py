"""Phase 1 smoke tests for setup components."""

from __future__ import annotations

import project_bootstrap  # noqa: F401
from pathlib import Path

from common.logging_utils import configure_logging
from common.settings import AppSettings, load_settings
from fusion.fusion_engine import WeightedFusionEngine

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def test_load_settings_returns_app_settings() -> None:
    settings = load_settings(Path("config/settings.yaml"))
    assert isinstance(settings, AppSettings)
    assert settings.project.random_seed == 42


def test_logging_configuration_returns_named_logger() -> None:
    logger = configure_logging(Path("config/logging.yaml"))
    assert logger.name == "project"


def test_fusion_engine_scoring_and_classification() -> None:
    engine = WeightedFusionEngine(kpi_weight=0.5, log_weight=0.5)
    score = engine.fuse(0.8, 0.6)
    assert score == 0.7
    assert engine.classify(score) == "Anomaly"
