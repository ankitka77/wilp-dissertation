"""Report generation for Phase 8 Milestone 6.

Builds a `ReportModel` from existing artifacts and renders a simple PDF
using matplotlib. The PDF and a small metadata JSON are written through
the `ArtifactStore`.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import List, Mapping, Optional
import io
import logging
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from phase8.core.artifact_store import ArtifactStore, ArtifactStoreError
from phase8.core.experiment_manager import ExperimentManager, ExperimentNotFoundError
from phase8.reporting.report_model import ReportModel
from phase8.reporting.exceptions import ReportGenerationError

logger = logging.getLogger("phase8.reporting")


# artifact filenames
REPORT_PDF = "report/experiment_report.pdf"
REPORT_METADATA = "report/report_metadata.json"

# constants
SUPPORTED_METRICS = ("precision", "recall", "f1")
KPI_SUMMARY_PATH = "evaluation/kpi_summary.json"
DEEPLOG_SUMMARY_PATH = "evaluation/deeplog_summary.json"
FUSION_SUMMARY_PATH = "evaluation/fusion_summary.json"
STATISTICS_PATH = "analysis/statistics.json"
VISUALIZATION_PREFIX = "visualization/"


class ReportGenerator:
    """Build and render reports for experiments.

    Public API:
    - `generate_report(experiment_id)` -> writes PDF + metadata and returns ReportModel
    """

    def __init__(self, experiment_manager: ExperimentManager, artifact_store: ArtifactStore) -> None:
        self._exp = experiment_manager
        self._store = artifact_store

    def _read_json_safe(self, run_id: str, path: str) -> Mapping:
        try:
            return self._store.read_json(run_id, path)
        except ArtifactStoreError:
            return {}

    def build_report_model(self, experiment_id: str) -> ReportModel:
        try:
            meta = self._exp.get_metadata(experiment_id)
        except ExperimentNotFoundError as exc:
            logger.error("Experiment %s not found", experiment_id)
            raise ReportGenerationError("experiment not found") from exc

        eval_kpi = self._read_json_safe(experiment_id, KPI_SUMMARY_PATH)
        eval_dl = self._read_json_safe(experiment_id, DEEPLOG_SUMMARY_PATH)
        eval_fus = self._read_json_safe(experiment_id, FUSION_SUMMARY_PATH)
        stats = self._read_json_safe(experiment_id, STATISTICS_PATH)

        # collect visualization artifact paths (if any)
        visuals = [entry.path for entry in self._store.list_artifacts(experiment_id) if entry.path.startswith(VISUALIZATION_PREFIX)]

        if not any((eval_kpi, eval_dl, eval_fus, stats)):
            logger.error("No content available to build report for %s", experiment_id)
            raise ReportGenerationError("no reportable artifacts present")

        evaluation_summary = {"kpi": eval_kpi, "deeplog": eval_dl, "fusion": eval_fus}

        model = ReportModel(
            experiment_id=experiment_id,
            title=f"Experiment Report: {experiment_id}",
            generated_timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            experiment_metadata=asdict(meta),
            dataset_information={},
            evaluation_summary=evaluation_summary,
            statistical_summary=stats,
            visualizations=visuals,
            generated_artifacts={"report_pdf": REPORT_PDF, "metadata": REPORT_METADATA},
            overall_conclusions=None,
        )
        return model

    def _render_pdf_bytes(self, model: ReportModel) -> bytes:
        fig = plt.figure(figsize=(8.27, 11.69))
        fig.suptitle(model.title, fontsize=14)

        self._build_experiment_section(fig, model)
        self._build_statistics_section(fig, model)
        self._build_visualization_section(fig, model)
        self._build_generated_artifacts_section(fig, model)

        buf = io.BytesIO()
        fig.savefig(buf, format="pdf", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    def _build_experiment_section(self, fig: matplotlib.figure.Figure, model: ReportModel) -> None:
        meta_ax = fig.add_axes([0.05, 0.7, 0.9, 0.25])
        meta_ax.axis("off")
        lines = [f"Experiment ID: {model.experiment_id}", f"Generated: {model.generated_timestamp}", ""]
        lines.append("Evaluation Summary:")
        for k, v in model.evaluation_summary.items():
            lines.append(f"- {k}: {v.get('f1') if isinstance(v, dict) else v}")
        meta_ax.text(0, 1, "\n".join(lines), va="top", fontsize=8)

    def _build_statistics_section(self, fig: matplotlib.figure.Figure, model: ReportModel) -> None:
        stats_ax = fig.add_axes([0.05, 0.45, 0.9, 0.22])
        stats_ax.axis("off")
        stats = model.statistical_summary.get("metrics", {}) if isinstance(model.statistical_summary, dict) else {}
        text_lines = ["Statistical Summary:"]
        for m in SUPPORTED_METRICS:
            mm = stats.get(m, {})
            text_lines.append(f"- {m}: mean={mm.get('mean')} count={mm.get('count')}")
        stats_ax.text(0, 1, "\n".join(text_lines), va="top", fontsize=8)

    def _build_visualization_section(self, fig: matplotlib.figure.Figure, model: ReportModel) -> None:
        y = 0.42
        h = 0.12
        for idx, vpath in enumerate(model.visualizations[:3]):
            try:
                data = self._store.read_artifact(model.experiment_id, vpath)
                img = plt.imread(io.BytesIO(data), format="png")
                ax = fig.add_axes([0.05 + idx * 0.32, y, 0.3, h])
                ax.imshow(img)
                ax.axis("off")
            except (ArtifactStoreError, OSError, ValueError):
                logger.debug("Failed to embed visualization %s", vpath)

    def _build_generated_artifacts_section(self, fig: matplotlib.figure.Figure, model: ReportModel) -> None:
        ga_ax = fig.add_axes([0.05, 0.05, 0.9, 0.32])
        ga_ax.axis("off")
        ga_lines = ["Generated Artifacts:"]
        for k, v in model.generated_artifacts.items():
            ga_lines.append(f"- {k}: {v}")
        ga_ax.text(0, 1, "\n".join(ga_lines), va="top", fontsize=8)

    def generate_report(self, experiment_id: str) -> ReportModel:
        model = self.build_report_model(experiment_id)
        pdf = self._render_pdf_bytes(model)
        try:
            self._store.write_artifact(experiment_id, REPORT_PDF, pdf)
            self._store.write_json(experiment_id, REPORT_METADATA, {"generated_at": model.generated_timestamp, "report": REPORT_PDF})
        except ArtifactStoreError as exc:
            logger.exception("Failed to persist report for %s", experiment_id)
            raise ReportGenerationError("failed to persist report") from exc
        return model
