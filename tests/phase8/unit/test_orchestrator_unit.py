from dataclasses import dataclass
from typing import List

from phase8.core.artifact_store import ArtifactStore
from phase8.core.experiment_manager import ExperimentManager
from phase8.core.dataset_manager import DatasetManager
from phase8.orchestrator import ExperimentOrchestrator, ExperimentResult


class DummyEvaluator:
    def __init__(self):
        self.called: List[str] = []

    def evaluate(self, *args, **kwargs):
        self.called.append("evaluate")
        return None


class FailingEvaluator(DummyEvaluator):
    def evaluate(self, *args, **kwargs):
        self.called.append("evaluate")
        raise RuntimeError("failed")


def test_orchestrator_stops_on_kpi_failure(tmp_path):
    store = ArtifactStore(tmp_path / "o1")
    exp = ExperimentManager(store)
    ds = DatasetManager(store)

    # create experiment and dataset
    exp.create_experiment("o1_exp")
    ds.register_dataset("ds1", "test dataset", {"source": "unit"})

    kpi = FailingEvaluator()
    dl = DummyEvaluator()
    fusion = DummyEvaluator()
    stats = DummyEvaluator()
    viz = DummyEvaluator()
    report = DummyEvaluator()

    orch = ExperimentOrchestrator(exp, ds, store, kpi_evaluator=kpi, deeplog_evaluator=dl, fusion_evaluator=fusion, stats_engine=stats, viz_engine=viz, report_generator=report)

    try:
        orch.run("o1_exp", "ds1", "ds1")
    except RuntimeError:
        # KPI failed; ensure downstream not called
        assert dl.called == []
        assert fusion.called == []
        assert stats.called == []
        assert viz.called == []
        assert report.called == []
        return
    assert False, "Expected RuntimeError from failing KPI evaluator"


def test_orchestrator_successful_order(tmp_path):
    store = ArtifactStore(tmp_path / "o2")
    exp = ExperimentManager(store)
    ds = DatasetManager(store)

    exp.create_experiment("o2_exp")
    ds.register_dataset("ds2", "test dataset", {"source": "unit"})

    # Use dummy evaluators that record calls and return simple objects where needed
    class ReturningEvaluator:
        def __init__(self, name):
            self.name = name
            self.called = []

        def evaluate(self, *args, **kwargs):
            self.called.append(self.name)
            @dataclass
            class Res:
                metrics = {"precision": 1.0}
            return Res()

    class ReturningFusion:
        def __init__(self):
            self.called = []

        def evaluate(self, *args, **kwargs):
            self.called.append("fusion")
            @dataclass
            class Res:
                metrics = {"precision": 1.0}
            return Res()

    class ReturningStats:
        def __init__(self):
            self.called = []

        def analyze_experiment(self, *args, **kwargs):
            self.called.append("stats")
            return {"metrics": {"precision": {"mean": 1.0}}}

    class ReturningViz:
        def __init__(self):
            self.called = []

        def visualize_experiment(self, *args, **kwargs):
            self.called.append("viz")
            @dataclass
            class Plot:
                path: str = "visualization/x.png"
            return [Plot()]

    class ReturningReport:
        def __init__(self):
            self.called = []

        def generate_report(self, *args, **kwargs):
            self.called.append("report")
            return None

    kpi = ReturningEvaluator("kpi")
    dl = ReturningEvaluator("dl")
    fusion = ReturningFusion()
    stats = ReturningStats()
    viz = ReturningViz()
    report = ReturningReport()

    orch = ExperimentOrchestrator(exp, ds, store, kpi_evaluator=kpi, deeplog_evaluator=dl, fusion_evaluator=fusion, stats_engine=stats, viz_engine=viz, report_generator=report)
    res = orch.run("o2_exp", "ds2", "ds2")
    assert isinstance(res, ExperimentResult)
    assert res.status == "success"
    assert stats.called == ["stats"]
    assert viz.called == ["viz"]
    assert report.called == ["report"]
