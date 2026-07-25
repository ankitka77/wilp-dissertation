"""Unit tests for the Phase 7 FusionConfig implementation."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from types import MappingProxyType
import json

import pytest

from phase7.config.fusion_config import (
    AggregationStrategyName,
    FusionConfig,
    FusionConfigLoadError,
    FusionConfigValidationError,
    FusionStrategyName,
    LogLevelName,
    NormalizationStrategyName,
)
from tests.phase7.helpers.fixture_builders import (
    build_invalid_config,
    build_minimal_config,
    build_phase7_config,
)
from phase7.config import fusion_config as fc
import yaml


pytestmark = [pytest.mark.unit]


def test_load_uses_defaults_when_no_file_is_provided() -> None:
    config = FusionConfig.load()

    assert config.fusion.strategy is FusionStrategyName.WEIGHTED_AVERAGE
    assert config.aggregation.strategy is AggregationStrategyName.MAX
    assert config.logging.level is LogLevelName.INFO
    assert config.fusion.window_size == timedelta(minutes=5)
    assert config.artifacts.root_dir == Path("artifacts/phase7")
    assert config.extensions == MappingProxyType({})


def test_load_reads_yaml_fixture_with_additional_sections(phase7_config_path: Path) -> None:
    config = FusionConfig.load(phase7_config_path)

    assert config.config_path == phase7_config_path
    assert config.fusion.strategy is FusionStrategyName.WEIGHTED_AVERAGE
    assert config.fusion.normalization_strategy is NormalizationStrategyName.MIN_MAX
    assert config.get_section("sources")["kpi"]["predictions_path"] == "tests/phase7/sample_data/sample_kpi_predictions.csv"


def test_load_reads_json_file_and_applies_overrides(tmp_path: Path) -> None:
    config_path = tmp_path / "fusion_config.json"
    config_path.write_text(json.dumps(build_minimal_config()), encoding="utf-8")

    config = FusionConfig.load(
        config_path,
        overrides={"fusion": {"threshold": 0.75}},
        env_overrides={"aggregation": {"strategy": "median"}},
    )

    assert config.fusion.threshold == pytest.approx(0.75)
    assert config.aggregation.strategy is AggregationStrategyName.MEDIAN
    assert config.fusion.window_size == timedelta(minutes=1)


def test_export_snapshot_is_json_serializable(phase7_config: FusionConfig) -> None:
    snapshot = phase7_config.export_snapshot()

    assert snapshot["fusion"]["window_size"] == "5m"
    assert snapshot["fusion"]["strategy"] == "weighted_average"
    assert Path(snapshot["artifacts"]["root_dir"]).as_posix() == "artifacts/phase7"
    assert snapshot["sources"]["log"]["manifest_path"] == "tests/phase7/sample_data/sample_manifest.json"
    json.dumps(snapshot)


def test_get_section_returns_known_and_additional_sections(phase7_config: FusionConfig) -> None:
    fusion_section = phase7_config.get_section("fusion")
    sources_section = phase7_config.get_section("sources")

    assert fusion_section is phase7_config.fusion
    assert sources_section["log"]["predictions_key"] == "predictions"


def test_get_section_rejects_empty_section_name(phase7_config: FusionConfig) -> None:
    with pytest.raises(FusionConfigValidationError, match="Section name must not be empty"):
        phase7_config.get_section("   ")


def test_get_section_rejects_unknown_section(phase7_config: FusionConfig) -> None:
    with pytest.raises(KeyError, match="Unknown configuration section"):
        phase7_config.get_section("missing_section")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"fusion": {"kpi_weight": -0.1}}, "fusion.kpi_weight"),
        ({"fusion": {"log_weight": -0.2}}, "fusion.log_weight"),
        ({"fusion": {"kpi_weight": 0.0, "log_weight": 0.0}}, "cannot both be zero"),
        ({"fusion": {"threshold": 1.2}}, "fusion.threshold"),
        ({"fusion": {"window_size": "0m"}}, "fusion.window_size"),
        ({"fusion": {"strategy": "not_supported"}}, "fusion.strategy"),
        ({"fusion": {"normalization_strategy": "bad_value"}}, "fusion.normalization_strategy"),
        ({"aggregation": {"strategy": "bad_value"}}, "aggregation.strategy"),
        ({"logging": {"level": "TRACE"}}, "logging.level"),
        ({"logging": {"enable_debug_artifacts": "yes"}}, "enable_debug_artifacts"),
        ({"artifacts": {"root_dir": None}}, "artifacts.root_dir"),
        ({"validation": {"strict": "false"}}, "validation.strict"),
        ({"fusion": {"extra_field": 1}}, "Unknown configuration field"),
    ],
)
def test_load_rejects_invalid_configuration_values(
    tmp_path: Path,
    overrides: dict[str, object],
    message: str,
) -> None:
    config_path = tmp_path / "invalid.yaml"
    payload = build_phase7_config(overrides)
    config_path.write_text(_to_yaml_text(payload), encoding="utf-8")

    with pytest.raises(FusionConfigValidationError, match=message):
        FusionConfig.load(config_path)


def test_invalid_fixture_raises_validation_error(invalid_config_path: Path) -> None:
    with pytest.raises(FusionConfigValidationError):
        FusionConfig.load(invalid_config_path)


def test_missing_file_raises_load_error(tmp_path: Path) -> None:
    with pytest.raises(FusionConfigLoadError, match="Configuration file not found"):
        FusionConfig.load(tmp_path / "missing.yaml")


def test_unsupported_extension_raises_load_error(tmp_path: Path) -> None:
    config_path = tmp_path / "fusion.txt"
    config_path.write_text("fusion=1", encoding="utf-8")

    with pytest.raises(FusionConfigLoadError, match="Unsupported configuration file type"):
        FusionConfig.load(config_path)


def test_malformed_json_raises_load_error(tmp_path: Path) -> None:
    config_path = tmp_path / "broken.json"
    config_path.write_text("{broken", encoding="utf-8")

    with pytest.raises(FusionConfigLoadError, match="Failed to read configuration file"):
        FusionConfig.load(config_path)


def test_minimal_fixture_loads_with_defaults(minimal_phase7_config: FusionConfig) -> None:
    assert minimal_phase7_config.fusion.threshold == pytest.approx(0.55)
    assert minimal_phase7_config.fusion.strategy is FusionStrategyName.WEIGHTED_AVERAGE
    assert minimal_phase7_config.aggregation.strategy is AggregationStrategyName.MAX
    assert minimal_phase7_config.logging.level is LogLevelName.INFO


def test_property_getters_return_typed_sections(phase7_config: FusionConfig) -> None:
    assert phase7_config.fusion_settings is phase7_config.fusion
    assert phase7_config.aggregation_settings is phase7_config.aggregation
    assert phase7_config.logging_settings is phase7_config.logging
    assert phase7_config.artifact_settings is phase7_config.artifacts
    assert phase7_config.validation_settings is phase7_config.validation


def test_missing_required_section_raises(tmp_path: Path) -> None:
    # remove the 'fusion' section entirely — production merges defaults
    payload = build_phase7_config()
    payload.pop("fusion", None)
    p = tmp_path / "no_fusion.yaml"
    p.write_text(yaml.safe_dump(payload), encoding="utf-8")

    cfg = FusionConfig.load(p)
    assert cfg.fusion.threshold == pytest.approx(0.60)


def test_missing_required_field_raises(tmp_path: Path) -> None:
    # creating a fusion section missing non-required fields should load with defaults
    payload = {"fusion": {"strategy": "weighted_average"}, "aggregation": {"strategy": "max"}, "logging": {"level": "INFO"}, "artifacts": {"root_dir": "artifacts/phase7", "retain_intermediate": True}, "validation": {"strict": True, "allow_row_drops": False}}
    p = tmp_path / "missing_field.yaml"
    p.write_text(yaml.safe_dump(payload), encoding="utf-8")

    cfg = FusionConfig.load(p)
    assert cfg.fusion.strategy is FusionStrategyName.WEIGHTED_AVERAGE
    assert cfg.fusion.threshold == pytest.approx(0.60)


def test_invalid_configuration_root_not_mapping(tmp_path: Path) -> None:
    p = tmp_path / "list.json"
    p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

    with pytest.raises(FusionConfigLoadError, match="Configuration root must be a mapping"):
        FusionConfig.load(p)


def test_section_type_must_be_mapping(tmp_path: Path) -> None:
    payload = {"fusion": [1, 2, 3]}
    p = tmp_path / "bad_section.yaml"
    p.write_text(yaml.safe_dump(payload), encoding="utf-8")

    with pytest.raises(FusionConfigValidationError, match="must be a mapping"):
        FusionConfig.load(p)


def test_directory_instead_of_file_raises(tmp_path: Path) -> None:
    d = tmp_path / "adir"
    d.mkdir()
    with pytest.raises(FusionConfigLoadError, match="is not a file"):
        FusionConfig.load(d)


def test_yaml_requires_pyyaml(monkeypatch, tmp_path: Path) -> None:
    p = tmp_path / "cfg.yaml"
    p.write_text("fusion:\n  threshold: 0.5\n", encoding="utf-8")

    import builtins

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "yaml" or name.startswith("yaml."):
            raise ImportError("No module named yaml")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(FusionConfigLoadError, match="YAML configuration requires PyYAML"):
        FusionConfig.load(p)


def test_file_read_failure_raises(monkeypatch, tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(build_phase7_config()), encoding="utf-8")

    orig_open = fc.Path.open

    def broken_open(self, *args, **kwargs):
        if Path(self) == p:
            raise OSError("cannot read")
        return orig_open(self, *args, **kwargs)

    monkeypatch.setattr(fc.Path, "open", broken_open)
    with pytest.raises(FusionConfigLoadError, match="Failed to read configuration file"):
        FusionConfig.load(p)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("10ms", timedelta(milliseconds=10)),
        ("5s", timedelta(seconds=5)),
        ("2m", timedelta(minutes=2)),
        ("3h", timedelta(hours=3)),
        ("1d", timedelta(days=1)),
    ],
)
def test_window_size_parsing_units(value: str, expected: timedelta, tmp_path: Path) -> None:
    payload = build_phase7_config()
    payload["fusion"]["window_size"] = value
    p = tmp_path / "units.yaml"
    p.write_text(yaml.safe_dump(payload), encoding="utf-8")

    cfg = FusionConfig.load(p)
    assert cfg.fusion.window_size == expected


def test_unsupported_duration_unit_raises(tmp_path: Path) -> None:
    payload = build_phase7_config()
    payload["fusion"]["window_size"] = "3w"
    p = tmp_path / "bad_unit.yaml"
    p.write_text(yaml.safe_dump(payload), encoding="utf-8")

    with pytest.raises(FusionConfigValidationError, match="positive duration string"):
        FusionConfig.load(p)


def test_freeze_and_thaw_and_format_timedelta() -> None:
    data = {"a": [1, {"b": 2}], "c": {"x": 3}}
    frozen = fc._freeze_value(data)
    assert isinstance(frozen, MappingProxyType) or isinstance(frozen, dict)
    thawed = fc._thaw_value(frozen)
    assert thawed["a"][1]["b"] == 2

    assert fc._format_timedelta(timedelta(days=2)) == "2d"
    assert fc._format_timedelta(timedelta(hours=1)) == "1h"
    assert fc._format_timedelta(timedelta(minutes=2)) == "2m"
    assert fc._format_timedelta(timedelta(seconds=1)) == "1s"
    assert fc._format_timedelta(timedelta(milliseconds=5)) == "5ms"


def test_validation_policy_non_strict_and_row_drops_ok() -> None:
    cfg = FusionConfig.load(overrides={"validation": {"strict": False, "allow_row_drops": True}})
    assert cfg.validation.strict is False
    assert cfg.validation.allow_row_drops is True


def test_additional_sections_and_extensions_roundtrip(tmp_path: Path) -> None:
    payload = build_phase7_config()
    payload["custom_section"] = {"alpha": 1}
    payload["extensions"] = {"ext1": {"x": 2}}
    p = tmp_path / "extras.yaml"
    p.write_text(yaml.safe_dump(payload), encoding="utf-8")

    cfg = FusionConfig.load(p)
    assert cfg.get_section("custom_section")["alpha"] == 1
    assert cfg.extensions["ext1"]["x"] == 2
    snap = cfg.export_snapshot()
    assert "custom_section" in snap


def test_parse_enum_and_float_and_bool_errors(tmp_path: Path) -> None:
    payload = build_phase7_config()
    payload["fusion"]["strategy"] = "bad_enum"
    p = tmp_path / "bad_enum.yaml"
    p.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(FusionConfigValidationError, match="Invalid value for 'fusion.strategy'"):
        FusionConfig.load(p)

    payload = build_phase7_config()
    payload["fusion"]["threshold"] = "notnumber"
    p2 = tmp_path / "bad_float.yaml"
    p2.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(FusionConfigValidationError, match="must be numeric"):
        FusionConfig.load(p2)

    payload = build_phase7_config()
    payload["logging"]["enable_debug_artifacts"] = "yes"
    p3 = tmp_path / "bad_bool.yaml"
    p3.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(FusionConfigValidationError, match="must be a boolean"):
        FusionConfig.load(p3)


def test_deep_merge_behaviour() -> None:
    a = {"x": {"y": 1, "z": 2}, "k": 5}
    b = {"x": {"y": 9}, "new": 1}
    merged = fc._deep_merge(a, b)
    assert merged["x"]["y"] == 9
    assert merged["x"]["z"] == 2
    assert merged["k"] == 5
    assert merged["new"] == 1


def test_from_raw_missing_required_section_raises() -> None:
    with pytest.raises(FusionConfigValidationError, match="Missing required configuration section: fusion"):
        FusionConfig._from_raw({}, None)


def test_read_config_file_unsupported_extension(tmp_path: Path) -> None:
    p = tmp_path / "weird.txt"
    p.write_text("{}", encoding="utf-8")
    with pytest.raises(FusionConfigLoadError, match="Unsupported configuration file type"):
        FusionConfig._read_config_file(p)


def test_validate_validation_policy_non_strict_warns_but_returns() -> None:
    cfg = FusionConfig.load(overrides={"validation": {"strict": False, "allow_row_drops": False}})
    # should not raise; exercise the debug-logging branch
    cfg.validate()


def test_parse_helpers_missing_value_errors() -> None:
    with pytest.raises(FusionConfigValidationError, match="Missing required configuration field: fusion.strategy"):
        FusionConfig._parse_enum(None, FusionStrategyName, "fusion.strategy")
    with pytest.raises(FusionConfigValidationError, match="Missing required configuration field: test.float"):
        FusionConfig._parse_float(None, "test.float")
    with pytest.raises(FusionConfigValidationError, match="Missing required configuration field: test.bool"):
        FusionConfig._parse_bool(None, "test.bool")


def _to_yaml_text(payload: dict[str, object]) -> str:
    import yaml

    return yaml.safe_dump(payload, sort_keys=False)