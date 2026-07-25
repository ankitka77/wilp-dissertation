from phase8.core.artifact_store import ArtifactStore
from phase8.core.experiment_manager import ExperimentManager
from phase8.visualization.visualization_engine import VisualizationEngine, EXPERIMENT_COMPARISON_PNG, PRECISION_PNG
from phase8.analysis.statistical_analysis import StatisticalAnalysisEngine
import io


def test_visualize_single_experiment(tmp_path):
    root = tmp_path / "vis"
    store = ArtifactStore(root)
    exp = ExperimentManager(store)
    vis = VisualizationEngine(exp, store)

    exp.create_experiment("v1")
    # write analysis/statistics.json with simple metrics
    store.write_json("v1", "analysis/statistics.json", {
        "experiment_id": "v1",
        "metrics": {
            "precision": {"mean": 0.7, "ci_low": 0.6, "ci_high": 0.8},
            "recall": {"mean": 0.5, "ci_low": 0.4, "ci_high": 0.6},
            "f1": {"mean": 0.6, "ci_low": 0.5, "ci_high": 0.7},
        },
        "raw": {"precision": [0.7], "recall": [0.5], "f1": [0.6]},
    })

    written = vis.visualize_experiment("v1")
    # verify artifacts exist and are PNGs
    data = store.read_artifact("v1", PRECISION_PNG)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_visualize_aggregate_experiments(tmp_path):
    root = tmp_path / "vis2"
    store = ArtifactStore(root)
    exp = ExperimentManager(store)
    vis = VisualizationEngine(exp, store)

    exp.create_experiment("a1")
    exp.create_experiment("a2")
    store.write_json("a1", "analysis/statistics.json", {"metrics": {"precision": {"mean": 0.2}, "recall": {"mean": 0.3}, "f1": {"mean": 0.25}}, "raw": {"precision": [0.2], "recall": [0.3], "f1": [0.25]}})
    store.write_json("a2", "analysis/statistics.json", {"metrics": {"precision": {"mean": 0.8}, "recall": {"mean": 0.7}, "f1": {"mean": 0.75}}, "raw": {"precision": [0.8], "recall": [0.7], "f1": [0.75]}})

    spec = vis.visualize_experiments(["a1", "a2"])
    data = store.read_artifact("aggregated", EXPERIMENT_COMPARISON_PNG)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_visualize_missing_stats_raises(tmp_path):
    root = tmp_path / "vis3"
    store = ArtifactStore(root)
    exp = ExperimentManager(store)
    vis = VisualizationEngine(exp, store)
    exp.create_experiment("m1")
    try:
        vis.visualize_experiment("m1")
    except Exception:
        return
    assert False, "Expected exception for missing statistics"
