import json
from phase8.analysis.statistical_analysis import (
    StatisticalAnalysisEngine,
    _compute_basic_stats,
    STATISTICS_PATH,
    SUMMARY_STATISTICS_PATH,
    ANALYSIS_PATH,
)
from phase8.analysis.exceptions import StatisticalAnalysisError
from phase8.core.artifact_store import ArtifactStore, ArtifactStoreError
from phase8.core.experiment_manager import ExperimentManager


def test_compute_basic_stats_even_median():
    s = _compute_basic_stats([0.0, 1.0])
    assert s.count == 2
    assert s.median == 0.5


def test_analyze_missing_experiment_raises(tmp_path):
    store = ArtifactStore(tmp_path / "s1")
    exp = ExperimentManager(store)
    engine = StatisticalAnalysisEngine(exp, store)
    try:
        engine.analyze_experiment("nope")
    except StatisticalAnalysisError:
        return
    assert False, "Expected StatisticalAnalysisError for missing experiment"


def test_analyze_no_summaries_raises(tmp_path):
    store = ArtifactStore(tmp_path / "s2")
    exp = ExperimentManager(store)
    engine = StatisticalAnalysisEngine(exp, store)
    exp.create_experiment("e1")
    try:
        engine.analyze_experiment("e1")
    except StatisticalAnalysisError:
        return
    assert False, "Expected StatisticalAnalysisError when no summaries present"


def test_analyze_malformed_summary_ignored(tmp_path):
    store = ArtifactStore(tmp_path / "s3")
    exp = ExperimentManager(store)
    engine = StatisticalAnalysisEngine(exp, store)
    exp.create_experiment("e2")
    # write a malformed summary (JSON list) that will cause .get to raise
    store.write_artifact("e2", "evaluation/kpi_summary.json", json.dumps([1, 2, 3]).encode("utf-8"))
    # write a valid deeplog summary
    store.write_json("e2", "evaluation/deeplog_summary.json", {"precision": 0.2, "recall": 0.3, "f1": 0.25})
    out = engine.analyze_experiment("e2")
    assert out["experiment_id"] == "e2"
    # malformed KPI should be ignored and deeplog metrics should be present
    assert out["raw"]["precision"] == [0.2]


def test_analyze_write_failure_raises(tmp_path):
    class BrokenStore(ArtifactStore):
        def write_json(self, run_id: str, relative_path: str, obj):
            if relative_path == STATISTICS_PATH:
                raise ArtifactStoreError("no space")
            return super().write_json(run_id, relative_path, obj)

    store = BrokenStore(tmp_path / "s4")
    exp = ExperimentManager(store)
    engine = StatisticalAnalysisEngine(exp, store)
    exp.create_experiment("e3")
    store.write_json("e3", "evaluation/kpi_summary.json", {"precision": 1.0, "recall": 1.0, "f1": 1.0})
    try:
        engine.analyze_experiment("e3")
    except StatisticalAnalysisError:
        return
    assert False, "Expected StatisticalAnalysisError when write_json fails"


def test_aggregate_no_statistics_raises(tmp_path):
    store = ArtifactStore(tmp_path / "s5")
    exp = ExperimentManager(store)
    engine = StatisticalAnalysisEngine(exp, store)
    exp.create_experiment("a1")
    exp.create_experiment("a2")
    try:
        engine.aggregate_experiments(["a1", "a2"])
    except StatisticalAnalysisError:
        return
    assert False, "Expected StatisticalAnalysisError when no stats available to aggregate"


def test_aggregate_persist_failure_raises(tmp_path):
    class BrokenAggStore(ArtifactStore):
        def write_json(self, run_id: str, relative_path: str, obj):
            if run_id == "aggregated" and relative_path == STATISTICS_PATH:
                raise ArtifactStoreError("no space")
            return super().write_json(run_id, relative_path, obj)

    store = BrokenAggStore(tmp_path / "s6")
    exp = ExperimentManager(store)
    engine = StatisticalAnalysisEngine(exp, store)
    exp.create_experiment("b1")
    exp.create_experiment("b2")
    store.write_json("b1", "evaluation/kpi_summary.json", {"precision": 0.1, "recall": 0.2, "f1": 0.15})
    store.write_json("b2", "evaluation/kpi_summary.json", {"precision": 0.3, "recall": 0.4, "f1": 0.35})
    try:
        engine.aggregate_experiments(["b1", "b2"])
    except StatisticalAnalysisError:
        return
    assert False, "Expected StatisticalAnalysisError when aggregated write fails"
