from phase8.visualization.visualization_engine import (
    VisualizationEngine,
    PRECISION_PNG,
    SUMMARY_PNG,
    EXPERIMENT_COMPARISON_PNG,
)
from phase8.core.artifact_store import ArtifactStore, ArtifactStoreError
from phase8.core.experiment_manager import ExperimentManager
from phase8.visualization.exceptions import VisualizationError


def test_visualize_experiment_skips_missing_metrics(tmp_path):
    store = ArtifactStore(tmp_path / "v1")
    exp = ExperimentManager(store)
    vis = VisualizationEngine(exp, store)

    exp.create_experiment("e")
    # only precision present
    store.write_json("e", "analysis/statistics.json", {"metrics": {"precision": {"mean": 0.9}} , "raw": {"precision": [0.9]}})

    written = vis.visualize_experiment("e")
    # precision PNG exists, summary exists
    data = store.read_artifact("e", PRECISION_PNG)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    data2 = store.read_artifact("e", SUMMARY_PNG)
    assert data2[:8] == b"\x89PNG\r\n\x1a\n"


def test_visualize_experiment_no_summary_when_no_means(tmp_path):
    store = ArtifactStore(tmp_path / "v2")
    exp = ExperimentManager(store)
    vis = VisualizationEngine(exp, store)

    exp.create_experiment("e2")
    # metrics present but all means None
    store.write_json("e2", "analysis/statistics.json", {"metrics": {"precision": {}, "recall": {}, "f1": {}}, "raw": {}})

    written = vis.visualize_experiment("e2")
    assert written == []


def test_visualize_experiment_write_failure_raises(tmp_path):
    class BrokenStore(ArtifactStore):
        def write_artifact(self, run_id: str, relative_path: str, data: bytes):
            # fail only on visualization artifact writes
            if relative_path.startswith("visualization"):
                raise ArtifactStoreError("disk full")
            return super().write_artifact(run_id, relative_path, data)

    # create experiment using a normal store so metadata write succeeds
    normal = ArtifactStore(tmp_path / "v3_normal")
    exp = ExperimentManager(normal)
    exp.create_experiment("e3")
    normal.write_json("e3", "analysis/statistics.json", {"metrics": {"precision": {"mean": 0.5}}, "raw": {"precision": [0.5]}})

    # use BrokenStore pointing at the same root for visualization (will fail on write)
    broken = BrokenStore(normal._root)
    vis = VisualizationEngine(exp, broken)
    try:
        vis.visualize_experiment("e3")
    except VisualizationError:
        return
    assert False, "Expected VisualizationError when write_artifact fails"


def test_visualize_experiments_fallback_and_aggregate(tmp_path):
    store = ArtifactStore(tmp_path / "v4")
    exp = ExperimentManager(store)
    vis = VisualizationEngine(exp, store)

    exp.create_experiment("a1")
    # write only evaluation summary (fallback path)
    store.write_json("a1", "evaluation/kpi_summary.json", {"precision": 0.2, "recall": 0.3, "f1": 0.25})

    spec = vis.visualize_experiments(["a1", "missing"])
    # aggregated PNG exists
    data = store.read_artifact("aggregated", EXPERIMENT_COMPARISON_PNG)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_visualize_experiments_no_stats_raises(tmp_path):
    store = ArtifactStore(tmp_path / "v5")
    exp = ExperimentManager(store)
    vis = VisualizationEngine(exp, store)

    exp.create_experiment("z1")
    try:
        vis.visualize_experiments(["z1"])
    except VisualizationError:
        return
    assert False, "Expected VisualizationError when no statistics available to visualize"


def test_visualize_aggregated_persist_failure_raises(tmp_path):
    class BrokenAggStore(ArtifactStore):
        def write_artifact(self, run_id: str, relative_path: str, data: bytes):
            if run_id == "aggregated":
                raise ArtifactStoreError("no space")
            return super().write_artifact(run_id, relative_path, data)

    store = BrokenAggStore(tmp_path / "v6")
    exp = ExperimentManager(store)
    vis = VisualizationEngine(exp, store)

    exp.create_experiment("b1")
    exp.create_experiment("b2")
    store.write_json("b1", "analysis/statistics.json", {"metrics": {"precision": {"mean": 0.1}, "recall": {"mean": 0.2}, "f1": {"mean": 0.15}}, "raw": {"precision": [0.1]}})
    store.write_json("b2", "analysis/statistics.json", {"metrics": {"precision": {"mean": 0.3}, "recall": {"mean": 0.4}, "f1": {"mean": 0.35}}, "raw": {"precision": [0.3]}})
    try:
        vis.visualize_experiments(["b1", "b2"])
    except VisualizationError:
        return
    assert False, "Expected VisualizationError when aggregated write fails"
