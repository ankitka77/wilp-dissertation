from phase8.analysis.statistical_analysis import StatisticalAnalysisEngine, STATISTICS_PATH, SUMMARY_STATISTICS_PATH
from phase8.core.artifact_store import ArtifactStore
from phase8.core.experiment_manager import ExperimentManager


def test_analyze_single_experiment(tmp_path):
    root = tmp_path / "st"
    store = ArtifactStore(root)
    exp = ExperimentManager(store)
    engine = StatisticalAnalysisEngine(exp, store)

    exp.create_experiment("exp1")
    # write KPI and DeepLog summaries as evaluators would
    store.write_json("exp1", "evaluation/kpi_summary.json", {"precision": 1.0, "recall": 0.5, "f1": 0.66})
    store.write_json("exp1", "evaluation/deeplog_summary.json", {"precision": 0.0, "recall": 0.2, "f1": 0.0})

    out = engine.analyze_experiment("exp1")
    assert out["experiment_id"] == "exp1"
    # statistics artifact written
    stats = store.read_json("exp1", STATISTICS_PATH)
    assert "metrics" in stats
    summary = store.read_json("exp1", SUMMARY_STATISTICS_PATH)
    assert "precision" in summary


def test_aggregate_multiple_experiments(tmp_path):
    root = tmp_path / "ag"
    store = ArtifactStore(root)
    exp = ExperimentManager(store)
    engine = StatisticalAnalysisEngine(exp, store)

    exp.create_experiment("e1")
    exp.create_experiment("e2")
    store.write_json("e1", "evaluation/kpi_summary.json", {"precision": 1.0, "recall": 1.0, "f1": 1.0})
    store.write_json("e1", "evaluation/deeplog_summary.json", {"precision": 0.0, "recall": 0.0, "f1": 0.0})
    store.write_json("e2", "evaluation/kpi_summary.json", {"precision": 0.5, "recall": 0.5, "f1": 0.5})

    agg = engine.aggregate_experiments(["e1", "e2"])  # writes aggregated/statistics.json
    assert "aggregated" in agg
    # persisted under synthetic run id
    agg_stats = store.read_json("aggregated", STATISTICS_PATH)
    assert "aggregated" in agg_stats
