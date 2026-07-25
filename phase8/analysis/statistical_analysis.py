"""Statistical Analysis Engine for Phase 8 Milestone 4.

Consumes evaluator-produced summary artifacts and computes higher-level
statistics (mean, median, variance, std, min, max, confidence intervals).

Design constraints:
- Does not re-compute evaluator metrics (precision/recall/f1).
- Uses ExperimentManager and ArtifactStore for discovery and storage.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Mapping, Optional, Dict
import logging
import math

from phase8.core.artifact_store import ArtifactStore, ArtifactStoreError
from phase8.core.experiment_manager import ExperimentManager, ExperimentNotFoundError
from .exceptions import StatisticalAnalysisError

logger = logging.getLogger("phase8.analysis.stats")


# module-level artifact names
KPI_SUMMARY = "evaluation/kpi_summary.json"
DEEPLOG_SUMMARY = "evaluation/deeplog_summary.json"
FUSION_SUMMARY = "evaluation/fusion_summary.json"

STATISTICS_PATH = "analysis/statistics.json"
SUMMARY_STATISTICS_PATH = "analysis/summary_statistics.json"
ANALYSIS_PATH = "analysis/analysis.json"


@dataclass(frozen=True)
class MetricStats:
    count: int
    mean: Optional[float]
    median: Optional[float]
    variance: Optional[float]
    std: Optional[float]
    minimum: Optional[float]
    maximum: Optional[float]
    ci_low: Optional[float]
    ci_high: Optional[float]


def _compute_basic_stats(values: List[float]) -> MetricStats:
    n = len(values)
    if n == 0:
        return MetricStats(0, None, None, None, None, None, None, None, None)
    mean = sum(values) / n
    sorted_v = sorted(values)
    mid = n // 2
    if n % 2 == 1:
        median = sorted_v[mid]
    else:
        median = 0.5 * (sorted_v[mid - 1] + sorted_v[mid])
    minimum = sorted_v[0]
    maximum = sorted_v[-1]
    # sample variance (ddof=1) when n>1 else 0.0
    if n > 1:
        var = sum((x - mean) ** 2 for x in values) / (n - 1)
        std = math.sqrt(var)
        # approximate 95% CI using normal approximation (large-sample); note: limitation documented
        se = std / math.sqrt(n)
        ci_low = mean - 1.96 * se
        ci_high = mean + 1.96 * se
    else:
        var = 0.0
        std = 0.0
        ci_low = None
        ci_high = None
    return MetricStats(count=n, mean=mean, median=median, variance=var, std=std, minimum=minimum, maximum=maximum, ci_low=ci_low, ci_high=ci_high)


class StatisticalAnalysisEngine:
    """Compute statistical summaries from evaluator outputs.

    The engine reads evaluator summaries that are written under an
    experiment id by the evaluators and writes statistical artifacts
    back under the same experiment id.
    """

    def __init__(self, experiment_manager: ExperimentManager, artifact_store: ArtifactStore) -> None:
        self._exp = experiment_manager
        self._store = artifact_store

    def _read_summary_safe(self, experiment_id: str, path: str) -> Optional[Mapping]:
        try:
            return self._store.read_json(experiment_id, path)
        except ArtifactStoreError:
            logger.debug("Summary %s missing for %s", path, experiment_id)
            return None

    def analyze_experiment(self, experiment_id: str) -> Mapping:
        """Analyze a single experiment and persist statistics under the experiment id.

        Returns a mapping with detailed statistics.
        """
        try:
            self._exp.get_metadata(experiment_id)
        except ExperimentNotFoundError as exc:
            logger.error("Experiment %s not found", experiment_id)
            raise StatisticalAnalysisError("experiment not found") from exc

        # collect available summaries
        kpi = self._read_summary_safe(experiment_id, KPI_SUMMARY)
        dl = self._read_summary_safe(experiment_id, DEEPLOG_SUMMARY)
        fus = self._read_summary_safe(experiment_id, FUSION_SUMMARY)

        if not any((kpi, dl, fus)):
            logger.error("No evaluator summaries found for %s", experiment_id)
            raise StatisticalAnalysisError("no evaluator summaries present")

        # gather metrics lists per metric name
        by_metric: Dict[str, List[float]] = {"precision": [], "recall": [], "f1": []}

        for doc in (kpi, dl, fus):
            if not doc:
                continue
            for m in ("precision", "recall", "f1"):
                try:
                    v = doc.get(m)
                    if isinstance(v, (int, float)):
                        by_metric[m].append(float(v))
                except Exception:
                    # ignore malformed entries for now
                    logger.debug("Malformed metric %s in doc %s", m, doc)

        # compute stats per metric
        stats = {m: _compute_basic_stats(vals) for m, vals in by_metric.items()}

        # prepare serializable output
        out = {
            "experiment_id": experiment_id,
            "metrics": {
                m: {
                    "count": s.count,
                    "mean": s.mean,
                    "median": s.median,
                    "variance": s.variance,
                    "std": s.std,
                    "min": s.minimum,
                    "max": s.maximum,
                    "ci_low": s.ci_low,
                    "ci_high": s.ci_high,
                }
                for m, s in stats.items()
            },
            "raw": by_metric,
        }

        # persist artifacts
        try:
            self._store.write_json(experiment_id, STATISTICS_PATH, out)
            # summary artifact contains only means
            summary = {m: {"mean": stats[m].mean, "count": stats[m].count} for m in stats}
            self._store.write_json(experiment_id, SUMMARY_STATISTICS_PATH, summary)
            # lightweight analysis metadata
            analysis = {"experiment_id": experiment_id, "has_kpi": bool(kpi), "has_deeplog": bool(dl), "has_fusion": bool(fus)}
            self._store.write_json(experiment_id, ANALYSIS_PATH, analysis)
        except ArtifactStoreError as exc:
            logger.exception("Failed to write statistical artifacts for %s", experiment_id)
            raise StatisticalAnalysisError("failed to persist statistics") from exc

        return out

    def aggregate_experiments(self, experiment_ids: List[str]) -> Mapping:
        """Aggregate statistics across multiple experiments.

        Reads per-experiment `analysis/statistics.json` (if present) and
        computes global summaries which are written to the artifact store
        under a synthetic run id `aggregated`.
        """
        collected: Dict[str, List[float]] = {"precision": [], "recall": [], "f1": []}

        for eid in experiment_ids:
            # Prefer pre-computed per-experiment statistics if available
            try:
                stats = self._store.read_json(eid, STATISTICS_PATH)
                raw = stats.get("raw", {})
            except ArtifactStoreError:
                # Fallback: try to read evaluator summaries directly
                logger.debug("No statistics for %s, falling back to evaluator summaries", eid)
                kpi = self._read_summary_safe(eid, KPI_SUMMARY) or {}
                dl = self._read_summary_safe(eid, DEEPLOG_SUMMARY) or {}
                fus = self._read_summary_safe(eid, FUSION_SUMMARY) or {}
                raw = {"precision": [], "recall": [], "f1": []}
                for doc in (kpi, dl, fus):
                    if not doc:
                        continue
                    for m in ("precision", "recall", "f1"):
                        v = doc.get(m)
                        if isinstance(v, (int, float)):
                            raw[m].append(float(v))
            # extend collected lists from the raw mapping
            for m in collected:
                vals = raw.get(m) or []
                collected[m].extend([float(x) for x in vals])
        
        if not any(collected.values()):
            raise StatisticalAnalysisError("no statistics available to aggregate")

        aggregated = {m: _compute_basic_stats(vals) for m, vals in collected.items()}

        serialized = {
            "experiment_ids": experiment_ids,
            "aggregated": {
                m: {
                    "count": s.count,
                    "mean": s.mean,
                    "median": s.median,
                    "variance": s.variance,
                    "std": s.std,
                    "min": s.minimum,
                    "max": s.maximum,
                    "ci_low": s.ci_low,
                    "ci_high": s.ci_high,
                }
                for m, s in aggregated.items()
            },
        }

        # persist under a synthetic aggregate run id
        try:
            self._store.write_json("aggregated", STATISTICS_PATH, serialized)
            self._store.write_json("aggregated", SUMMARY_STATISTICS_PATH, {m: {"mean": aggregated[m].mean, "count": aggregated[m].count} for m in aggregated})
        except ArtifactStoreError as exc:
            logger.exception("Failed to persist aggregated statistics")
            raise StatisticalAnalysisError("failed to persist aggregated statistics") from exc

        return serialized
