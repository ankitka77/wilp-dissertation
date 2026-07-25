"""Experiment Orchestrator for Phase 8 Milestone 7.

Coordinates execution of existing evaluators, analysis, visualization,
and report generation components. Does not implement any domain logic;
it only invokes public APIs of the composed components.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from phase8.core.artifact_store import ArtifactStore
from phase8.core.experiment_manager import ExperimentManager
from phase8.core.dataset_manager import DatasetManager
from phase8.evaluators.kpi_evaluator import KPIEvaluator
from phase8.evaluators.deep_log_evaluator import DeepLogEvaluator
from phase8.evaluators.fusion_evaluator import FusionEvaluator
from phase8.analysis.statistical_analysis import StatisticalAnalysisEngine
from phase8.visualization.visualization_engine import VisualizationEngine
from phase8.reporting.report_generator import ReportGenerator, REPORT_PDF


@dataclass(frozen=True)
class ExperimentResult:
    experiment_id: str
    kpi_dataset_id: str
    deeplog_dataset_id: str
    status: str
    started_at: str
    completed_at: Optional[str]
    generated_artifacts: Dict[str, str]
    summary: Dict[str, object]


class ExperimentOrchestrator:
    """Coordinate a Phase 8 experiment run.

    The orchestrator invokes the following stages in order:
    - KPIEvaluator.evaluate
    - DeepLogEvaluator.evaluate
    - FusionEvaluator.evaluate
    - StatisticalAnalysisEngine.analyze_experiment
    - VisualizationEngine.visualize_experiment
    - ReportGenerator.generate_report

    It accepts either instantiated components or will construct them from
    provided managers/store when necessary.
    """

    def __init__(
        self,
        experiment_manager: ExperimentManager,
        dataset_manager: DatasetManager,
        artifact_store: ArtifactStore,
        kpi_evaluator: Optional[KPIEvaluator] = None,
        deeplog_evaluator: Optional[DeepLogEvaluator] = None,
        fusion_evaluator: Optional[FusionEvaluator] = None,
        stats_engine: Optional[StatisticalAnalysisEngine] = None,
        viz_engine: Optional[VisualizationEngine] = None,
        report_generator: Optional[ReportGenerator] = None,
    ) -> None:
        self._exp = experiment_manager
        self._ds = dataset_manager
        self._store = artifact_store

        # compose with provided components or construct defaults
        self._kpi = kpi_evaluator or KPIEvaluator(self._exp, self._ds, self._store)
        self._dl = deeplog_evaluator or DeepLogEvaluator(self._exp, self._ds, self._store)
        self._fusion = fusion_evaluator or FusionEvaluator(self._exp, self._ds, self._store)
        self._stats = stats_engine or StatisticalAnalysisEngine(self._exp, self._store)
        self._viz = viz_engine or VisualizationEngine(self._exp, self._store)
        self._report = report_generator or ReportGenerator(self._exp, self._store)

    def run(self, experiment_id: str, kpi_dataset_id: str, deeplog_dataset_id: str) -> ExperimentResult:
        started = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        result = ExperimentResult(
            experiment_id=experiment_id,
            kpi_dataset_id=kpi_dataset_id,
            deeplog_dataset_id=deeplog_dataset_id,
            status="running",
            started_at=started,
            completed_at=None,
            generated_artifacts={},
            summary={},
        )

        # Execute stages sequentially; propagate exceptions to caller.
        # KPI
        kpi_res = self._kpi.evaluate(experiment_id, kpi_dataset_id)

        # DeepLog
        dl_res = self._dl.evaluate(experiment_id, deeplog_dataset_id)

        # Fusion (ensure underlying evaluators' artifacts are available)
        fusion_res = self._fusion.evaluate(experiment_id, kpi_dataset_id, deeplog_dataset_id)

        # Statistical analysis
        stats = self._stats.analyze_experiment(experiment_id)

        # Visualization
        plots = self._viz.visualize_experiment(experiment_id)

        # Report generation
        report_model = self._report.generate_report(experiment_id)

        completed = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        generated = {"report_pdf": REPORT_PDF}
        summary = {
            "kpi": getattr(kpi_res, "metrics", None),
            "deeplog": getattr(dl_res, "metrics", None),
            "fusion": getattr(fusion_res, "metrics", None),
            "statistics": stats,
            "plots": [p.path for p in plots],
        }

        return ExperimentResult(
            experiment_id=experiment_id,
            kpi_dataset_id=kpi_dataset_id,
            deeplog_dataset_id=deeplog_dataset_id,
            status="success",
            started_at=started,
            completed_at=completed,
            generated_artifacts=generated,
            summary=summary,
        )
