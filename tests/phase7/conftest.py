"""Phase 7-local pytest fixtures and helpers."""

from __future__ import annotations

from pathlib import Path
import json

import pandas as pd
import pytest
import yaml

from phase7.config.fusion_config import FusionConfig
from tests.phase7.helpers.artifact_helpers import create_experiment_layout
from tests.phase7.helpers.fixture_builders import build_fusion_record


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Return the repository root."""

    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def phase7_tests_root(repo_root: Path) -> Path:
    """Return the root directory of the Phase 7 test subtree."""

    return repo_root / "tests" / "phase7"


@pytest.fixture(scope="session")
def phase7_fixtures_root(phase7_tests_root: Path) -> Path:
    """Return the directory containing Phase 7 file fixtures."""

    return phase7_tests_root / "fixtures"


@pytest.fixture(scope="session")
def phase7_sample_data_root(phase7_tests_root: Path) -> Path:
    """Return the directory containing Phase 7 sample data."""

    return phase7_tests_root / "sample_data"


@pytest.fixture(scope="session")
def phase7_config_path(phase7_fixtures_root: Path) -> Path:
    """Return the Phase 7 representative configuration fixture path."""

    return phase7_fixtures_root / "phase7_config.yaml"


@pytest.fixture(scope="session")
def minimal_config_path(phase7_fixtures_root: Path) -> Path:
    """Return the Phase 7 minimal configuration fixture path."""

    return phase7_fixtures_root / "minimal_config.yaml"


@pytest.fixture(scope="session")
def invalid_config_path(phase7_fixtures_root: Path) -> Path:
    """Return the Phase 7 invalid configuration fixture path."""

    return phase7_fixtures_root / "invalid_config.yaml"


@pytest.fixture(scope="session")
def phase7_config_dict(phase7_config_path: Path) -> dict[str, object]:
    """Load the representative Phase 7 YAML configuration as a dictionary."""

    with phase7_config_path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    assert isinstance(loaded, dict)
    return loaded


@pytest.fixture(scope="session")
def minimal_config_dict(minimal_config_path: Path) -> dict[str, object]:
    """Load the minimal Phase 7 YAML configuration as a dictionary."""

    with minimal_config_path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    assert isinstance(loaded, dict)
    return loaded


@pytest.fixture(scope="session")
def invalid_config_dict(invalid_config_path: Path) -> dict[str, object]:
    """Load the invalid Phase 7 YAML configuration as a dictionary."""

    with invalid_config_path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    assert isinstance(loaded, dict)
    return loaded


@pytest.fixture(scope="session")
def phase7_config(phase7_config_path: Path) -> FusionConfig:
    """Load the representative Phase 7 configuration via the production loader."""

    return FusionConfig.load(phase7_config_path)


@pytest.fixture(scope="session")
def minimal_phase7_config(minimal_config_path: Path) -> FusionConfig:
    """Load the minimal Phase 7 configuration via the production loader."""

    return FusionConfig.load(minimal_config_path)


@pytest.fixture(scope="session")
def sample_kpi_predictions_df(phase7_sample_data_root: Path) -> pd.DataFrame:
    """Load the Phase 7 sample KPI predictions CSV."""

    return pd.read_csv(phase7_sample_data_root / "sample_kpi_predictions.csv")


@pytest.fixture(scope="session")
def sample_log_predictions_df(phase7_sample_data_root: Path) -> pd.DataFrame:
    """Load the Phase 7 sample log predictions CSV."""

    return pd.read_csv(phase7_sample_data_root / "sample_log_predictions.csv")


@pytest.fixture(scope="session")
def sample_kpi_prediction_records(sample_kpi_predictions_df: pd.DataFrame) -> list[dict[str, object]]:
    """Return Phase 7 sample KPI predictions as records."""

    return sample_kpi_predictions_df.to_dict(orient="records")


@pytest.fixture(scope="session")
def sample_log_prediction_records(sample_log_predictions_df: pd.DataFrame) -> list[dict[str, object]]:
    """Return Phase 7 sample log predictions as records."""

    return sample_log_predictions_df.to_dict(orient="records")


@pytest.fixture(scope="session")
def sample_manifest_dict(phase7_sample_data_root: Path) -> dict[str, object]:
    """Load the Phase 7 sample published detector manifest."""

    with (phase7_sample_data_root / "sample_manifest.json").open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    assert isinstance(loaded, dict)
    return loaded


@pytest.fixture(scope="session")
def sample_timestamps() -> list[str]:
    """Return reusable ISO8601 timestamps spanning multiple fusion windows."""

    return [
        "2026-01-01T00:00:00Z",
        "2026-01-01T00:01:00Z",
        "2026-01-01T00:04:59Z",
        "2026-01-01T00:05:00Z",
        "2026-01-01T00:09:59Z",
    ]


@pytest.fixture
def temp_artifact_root(tmp_path: Path) -> Path:
    """Return a temporary artifact root for test-local file output."""

    path = tmp_path / "artifacts"
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def experiment_dir(temp_artifact_root: Path) -> dict[str, Path]:
    """Create a deterministic experiment directory layout for Phase 7 tests."""

    return create_experiment_layout(temp_artifact_root, experiment_id="experiment_001")


@pytest.fixture
def artifact_locations(experiment_dir: dict[str, Path]) -> dict[str, Path]:
    """Return the most commonly used artifact directories."""

    return {
        "root": experiment_dir["root"],
        "reports": experiment_dir["reports"],
        "plots": experiment_dir["plots"],
        "manifests": experiment_dir["manifests"],
    }


@pytest.fixture
def sample_fusion_record() -> dict[str, object]:
    """Return a reusable canonical FusionRecord-shaped dictionary."""

    return build_fusion_record()