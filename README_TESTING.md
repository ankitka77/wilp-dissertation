# Testing Guide

This document describes the repository test organization after isolating Phase 7 test infrastructure from legacy Phase 1–6 tests.

## Layout

```text
tests/
  conftest.py
  unit/
  integration/
  regression/
  phase7/
    conftest.py
    helpers/
      assertion_helpers.py
      artifact_helpers.py
      fixture_builders.py
    fixtures/
      phase7_config.yaml
      minimal_config.yaml
      invalid_config.yaml
    sample_data/
      sample_kpi_predictions.csv
      sample_log_predictions.csv
      sample_manifest.json
    unit/
      test_fusion_config.py
    integration/
    regression/
```

Purpose of each area:

- `tests/conftest.py`: repository-wide bootstrap and deterministic collection ordering only
- `tests/unit/`, `tests/integration/`, `tests/regression/`: legacy repository tests for earlier phases
- `tests/phase7/conftest.py`: Phase 7-only fixtures and local helper wiring
- `tests/phase7/helpers/`: reusable Phase 7 assertions, builders, and artifact utilities
- `tests/phase7/fixtures/`: static Phase 7 configuration fixtures
- `tests/phase7/sample_data/`: realistic Phase 7 input samples for source-ingest and artifact tests
- `tests/phase7/unit/`, `tests/phase7/integration/`, `tests/phase7/regression/`: dedicated Phase 7 test suites

## Isolation Rules

Phase 7 fixtures live only under `tests/phase7/`.

This ensures:

- legacy Phase 1–6 tests do not automatically import or see Phase 7 fixtures
- Phase 7 helpers remain self-contained
- future Phase 7 tests are added only under `tests/phase7/`

## Install Test Dependencies

```powershell
pip install -r requirements-test.txt
```

`requirements-test.txt` includes the repository development requirements, including pytest and coverage support.

## Run Tests

Run the full repository suite:

```powershell
pytest
```

Run only Phase 7 tests:

```powershell
pytest tests/phase7
```

Run only Phase 9 tests:

```powershell
pytest tests/phase9
```

Run only the FusionConfig tests:

```powershell
pytest tests/phase7/unit/test_fusion_config.py
```

Run Phase 7 integration tests:

```powershell
pytest tests/phase7/integration -m integration
```

Run Phase 7 regression tests:

```powershell
pytest tests/phase7/regression -m regression
```

Collect tests without execution:

```powershell
pytest --collect-only
```

## Pytest Behavior

The shared pytest configuration provides:

- verbose output
- strict marker validation
- warnings visibility
- deterministic collection ordering
- coverage-ready defaults for `phase7`

Deterministic ordering is enforced in `tests/conftest.py` by sorting collected tests by path and node id.

## Phase 7 Fixtures

Phase 7 shared fixtures currently include:

- repository paths: `repo_root`, `phase7_tests_root`, `phase7_fixtures_root`, `phase7_sample_data_root`
- configuration paths: `phase7_config_path`, `minimal_config_path`, `invalid_config_path`
- loaded configuration dictionaries: `phase7_config_dict`, `minimal_config_dict`, `invalid_config_dict`
- loaded production configuration objects: `phase7_config`, `minimal_phase7_config`
- source data: `sample_kpi_predictions_df`, `sample_log_predictions_df`, `sample_kpi_prediction_records`, `sample_log_prediction_records`, `sample_manifest_dict`
- test scaffolding: `sample_timestamps`, `temp_artifact_root`, `experiment_dir`, `artifact_locations`, `sample_fusion_record`

These fixtures are available only to tests collected from the `tests/phase7/` subtree.

## Phase 7 Helper Usage

### Assertion Helpers

Use `tests.phase7.helpers.assertion_helpers` for:

- `assert_fusion_record_equal`: compare FusionRecord-like dictionaries, dataclasses, or objects
- `assert_artifact_exists`: validate created artifacts
- `assert_dataframe_equal`: compare DataFrames with optional stable sorting
- `assert_manifest_valid`: validate manifest structure and artifact references
- `assert_float_equal`: stable floating-point comparisons

### Fixture Builders

Use `tests.phase7.helpers.fixture_builders` for:

- representative full and minimal configuration dictionaries
- intentionally invalid configuration dictionaries
- synthetic KPI and log prediction records
- synthetic published Log Detector manifests
- reusable FusionRecord-shaped sample objects
- reusable timestamp sequences

### Artifact Helpers

Use `tests.phase7.helpers.artifact_helpers` for:

- creating deterministic experiment directory trees
- writing CSV, JSON, and YAML files into temporary locations
- materializing complete synthetic Phase 7 input bundles
- cleaning up temporary files and directories

## Adding New Phase 7 Tests

Guidelines for adding Phase 7 tests:

- place Phase 7 unit tests only in `tests/phase7/unit/`
- place Phase 7 multi-module workflow tests only in `tests/phase7/integration/`
- place Phase 7 deterministic and stability tests only in `tests/phase7/regression/`
- mark tests with the appropriate pytest marker: `unit`, `integration`, `regression`, `artifact`, or `deterministic`
- prefer shared builders and fixtures over local ad hoc test data
- prefer helper assertions over duplicating low-level comparison logic

## Artifact Validation

Artifact-producing Phase 7 tests should validate:

- expected files are created
- expected columns or top-level fields exist
- manifest references are complete
- repeated runs with identical inputs remain stable where deterministic behavior is expected

## Regression and Determinism

Phase 7 regression tests should focus on:

- stable configuration snapshots
- deterministic window assignment inputs
- stable artifact serialization contracts
- consistent manifest structures
- repeatable sample-data driven behavior