"""KPI Evaluator for Phase 8 Milestone 2.

Computes simple binary classification metrics (precision, recall, f1)
for KPI predictions and writes metric artifacts using the ArtifactStore.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Mapping
import logging
from pathlib import Path

from phase8.core.artifact_store import ArtifactStore, ArtifactStoreError
from phase8.core.experiment_manager import ExperimentManager, ExperimentNotFoundError
from phase8.core.dataset_manager import DatasetManager, DatasetNotFoundError
from .exceptions import KPIEvaluatorError

logger = logging.getLogger("phase8.evaluators.kpi")

# Module-level filename constants
GROUND_TRUTH_FILENAME = "ground_truth.csv"
PREDICTIONS_FILENAME = "predictions.csv"
SUMMARY_PATH = "evaluation/kpi_summary.json"

# Phase 4 stabilized published artifact location (run id + filename)
PHASE4_RUN_ID = "phase4/latest"
PHASE4_PREDICTIONS = "anomaly_predictions.csv"

@dataclass(frozen=True)
class KPIMetrics:
    precision: float
    recall: float
    f1: float


@dataclass(frozen=True)
class KPIResult:
    experiment_id: str
    dataset_id: str
    metrics: KPIMetrics
    summary_path: str


class KPIEvaluator:
    """Evaluator for KPI binary predictions.
    The evaluator reads Phase 4's published prediction artifact and joins
    it with KPI ground-truth labels provided to Phase 8. The join and
    evaluation occur entirely inside this component. Legacy single-column
    ground-truth files are still supported for backward compatibility.
    """

    def __init__(self, experiment_manager: ExperimentManager, dataset_manager: DatasetManager, artifact_store: ArtifactStore) -> None:
        self._exp = experiment_manager
        self._ds = dataset_manager
        self._store = artifact_store

    def _read_series(self, dataset_id: str, relative: str) -> List[int]:
        data = self._store.read_artifact(dataset_id, relative)
        # deterministic parsing
        text = data.decode("utf-8").strip()
        if text == "":
            return []
        return [int(line.strip().split(",")[0]) for line in text.splitlines()]

    def _read_phase4_predictions(self, run_id: str | None = None) -> List[int]:
        # kept signature for backwards compatibility; support optional run_id via attribute
        """Read predictions from the stabilized Phase 4 published artifact.

        The artifact is expected at run id `phase4/latest` with filename
        `anomaly_predictions.csv`. The CSV is parsed using a header-aware
        reader; the evaluator will try to find a `prediction` column (case
        insensitive) and fall back to the third column if no header is
        present.
        """
        run = run_id or PHASE4_RUN_ID
        data = self._store.read_artifact(run, PHASE4_PREDICTIONS)
        text = data.decode("utf-8")
        # parse CSV robustly
        import io, csv as _csv

        fh = io.StringIO(text)
        # sniff for header
        try:
            # use DictReader when header present. Only accept explicit prediction
            # columns (avoid treating anomaly_score/probability as a binary label).
            reader = _csv.DictReader(fh)
            if reader.fieldnames:
                pred_cols = [fn for fn in reader.fieldnames if fn and fn.strip().lower() in {"prediction", "pred", "label", "final_label"}]
                if pred_cols:
                    preds = []
                    pred_col = pred_cols[0]
                    for row in reader:
                        val = row.get(pred_col)
                        if val is None:
                            logger.warning("Missing prediction value in row while reading %s; treating as 0", PHASE4_PREDICTIONS)
                            val = "0"
                        try:
                            preds.append(int(str(val).strip()))
                        except ValueError as exc:
                            logger.warning("Unable to parse prediction value '%s' as int: %s", val, exc)
                            raise
                    return preds
        except Exception as exc:
            logger.warning("Header parsing of %s failed, falling back to positional parsing: %s", PHASE4_PREDICTIONS, exc)
            fh.seek(0)

        # positional parsing: take third column (index 2) if available,
        # otherwise use first column
        fh.seek(0)
        reader2 = _csv.reader(fh)
        preds = []
        for parts in reader2:
            if not parts:
                continue
            if len(parts) >= 3:
                try:
                    preds.append(int(parts[2].strip()))
                except ValueError as exc:
                    logger.warning("Unable to parse positional prediction '%s' as int: %s", parts[2], exc)
                    raise
            else:
                try:
                    preds.append(int(parts[0].strip()))
                except ValueError as exc:
                    logger.warning("Unable to parse positional prediction '%s' as int: %s", parts[0], exc)
                    raise
        return preds

    def _read_phase4_predictions_map(self, run_id: str | None = None) -> dict:
        """Read Phase 4 predictions and return a mapping from a composite
        key (timestamp|kpi_id) -> prediction (int). Returns empty dict on
        parse failure.
        """
        run = run_id or PHASE4_RUN_ID
        data = self._store.read_artifact(run, PHASE4_PREDICTIONS)
        text = data.decode("utf-8")
        import io, csv as _csv

        fh = io.StringIO(text)
        try:
            reader = _csv.DictReader(fh)
            if reader.fieldnames:
                # normalize fieldnames
                fns = [fn for fn in reader.fieldnames]
                def _norm(s: str) -> str:
                    return s.lower().replace(" ", "").replace("_", "").replace("-", "") if s else ""

                ts_candidates = {"timestamp", "time", "ts"}
                kpi_candidates = {"kpiid", "kpi", "kpiid"}
                # restrict prediction candidates to explicit binary labels
                pred_candidates = {"prediction", "pred", "label", "final_label"}

                ts_col = None
                kpi_col = None
                pred_col = None
                for fn in fns:
                    n = _norm(fn)
                    if not ts_col and n in ts_candidates:
                        ts_col = fn
                    if not kpi_col and n in kpi_candidates:
                        kpi_col = fn
                    if not pred_col and n in pred_candidates:
                        pred_col = fn

                mapping = {}
                if pred_col and (ts_col or kpi_col):
                    for row in reader:
                        ts = row.get(ts_col, "") if ts_col else ""
                        kpi = row.get(kpi_col, "") if kpi_col else ""
                        key = f"{str(ts).strip()}|{str(kpi).strip()}"
                        val = row.get(pred_col)
                        try:
                            mapping[key] = int(str(val).strip())
                        except Exception as exc:
                            logger.warning("Unable to parse prediction value '%s' in %s: %s", val, PHASE4_PREDICTIONS, exc)
                            raise
                    return mapping
        except Exception as exc:
            logger.warning("Header parsing of %s failed, falling back to positional parsing: %s", PHASE4_PREDICTIONS, exc)
            fh.seek(0)

        # positional fallback
        fh.seek(0)
        reader2 = _csv.reader(fh)
        mapping = {}
        for parts in reader2:
            if not parts:
                continue
            if len(parts) >= 3:
                ts = parts[0].strip()
                kpi = parts[1].strip()
                try:
                    pred = int(parts[2].strip())
                except Exception as exc:
                    logger.warning("Unable to parse positional prediction '%s' as int: %s", parts[2], exc)
                    raise
                mapping[f"{ts}|{kpi}"] = pred
        return mapping

    def _resolve_phase4_run(self, dataset_manifest) -> str:
        """Resolve the Phase 4 run id to read published artifacts from.

        Preference order:
        - explicit override in dataset manifest `source` mapping (keys like
          `phase4_run` or values containing `phase4/latest`)
        - default to module-level `PHASE4_RUN_ID`
        """
        if dataset_manifest and getattr(dataset_manifest, "source", None):
            try:
                src = dataset_manifest.source
                # explicit key
                for k in ("phase4_run", "phase4_run_id", "run_id", "artifact_run"):
                    if k in src and isinstance(src[k], str) and src[k].strip():
                        return src[k].strip()
                # scan values for a phase4/latest hint
                for v in src.values():
                    if isinstance(v, str) and "phase4" in v and "latest" in v:
                        return "phase4/latest"
            except Exception:
                pass
        return PHASE4_RUN_ID

    def _read_ground_truth_map(self, dataset_id: str) -> dict | None:
        """Read ground truth CSV and return mapping (timestamp|kpi_id)->label.

        Returns None when the ground truth file is a simple single-column
        series (legacy format) so callers can fallback to positional parsing.
        """
        data = self._store.read_artifact(dataset_id, GROUND_TRUTH_FILENAME)
        text = data.decode("utf-8")
        import io, csv as _csv

        fh = io.StringIO(text)
        try:
            reader = _csv.DictReader(fh)
            if reader.fieldnames:
                fns = [fn for fn in reader.fieldnames]
                def _norm(s: str) -> str:
                    return s.lower().replace(" ", "").replace("_", "").replace("-", "") if s else ""

                ts_candidates = {"timestamp", "time", "ts"}
                kpi_candidates = {"kpiid", "kpi", "kpiid"}
                label_candidates = {"label", "groundtruth", "ground_truth", "y", "target"}

                ts_col = None
                kpi_col = None
                label_col = None
                for fn in fns:
                    n = _norm(fn)
                    if not ts_col and n in ts_candidates:
                        ts_col = fn
                    if not kpi_col and n in kpi_candidates:
                        kpi_col = fn
                    if not label_col and n in label_candidates:
                        label_col = fn

                mapping = {}
                if label_col and (ts_col or kpi_col):
                    for row in reader:
                        ts = row.get(ts_col, "") if ts_col else ""
                        kpi = row.get(kpi_col, "") if kpi_col else ""
                        key = f"{str(ts).strip()}|{str(kpi).strip()}"
                        val = row.get(label_col)
                        mapping[key] = int(str(val).strip())
                    return mapping
                # if header exists but not keyable, fall through to positional
        except Exception:
            fh.seek(0)

        # positional fallback: if rows have >=3 columns, build mapping
        fh.seek(0)
        reader2 = _csv.reader(fh)
        mapping = {}
        row_count = 0
        max_cols = 0
        rows = []
        for parts in reader2:
            row_count += 1
            max_cols = max(max_cols, len(parts))
            rows.append(parts)
        if max_cols >= 3:
            for parts in rows:
                if not parts:
                    continue
                if len(parts) >= 3:
                    ts = parts[0].strip()
                    kpi = parts[1].strip()
                    label = int(parts[2].strip())
                    mapping[f"{ts}|{kpi}"] = label
            return mapping

        # single-column ground truth -> return None to trigger legacy path
        return None

    def _compute_metrics(self, y_true: List[int], y_pred: List[int]) -> KPIMetrics:
        if len(y_true) != len(y_pred):
            logger.error("Length mismatch: true=%d pred=%d", len(y_true), len(y_pred))
            raise KPIEvaluatorError("ground truth and predictions length mismatch")
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        return KPIMetrics(precision=precision, recall=recall, f1=f1)

    def evaluate(self, experiment_id: str, dataset_id: str) -> KPIResult:
        """Run evaluation for `experiment_id` using dataset `dataset_id`.

        The result is written as JSON to `evaluation/kpi_summary.json` under the
        experiment artifact root and the `KPIResult` is returned.
        """
        # validate experiment exists and retrieve metadata
        try:
            _meta = self._exp.get_metadata(experiment_id)
        except ExperimentNotFoundError as exc:
            logger.error("Experiment %s not found", experiment_id)
            raise KPIEvaluatorError("experiment not found") from exc

        # validate dataset exists (manifest optional for inter-phase published outputs)
        # Attempt to retrieve manifest; if missing, continue (Phase 4 published
        # artifacts intentionally may not provide a manifest).
        try:
            dataset_manifest = self._ds.get_manifest(dataset_id)
        except DatasetNotFoundError:
            dataset_manifest = None
            logger.info("Dataset manifest for %s not found; continuing (may be inter-phase published artifact)", dataset_id)

        # read, join, compute and persist
        try:
            # Attempt to read ground-truth as a keyed CSV (timestamp+kpi) -> label
            labels_map = None
            try:
                labels_map = self._read_ground_truth_map(dataset_id)
            except Exception as exc:
                labels_map = None
                logger.warning("Failed to parse ground truth map for %s: %s", dataset_id, exc)

            # resolve where to read Phase 4 published artifact from
            phase4_run = self._resolve_phase4_run(dataset_manifest)

            preds_map = None
            try:
                preds_map = self._read_phase4_predictions_map(run_id=phase4_run)
            except Exception as exc:
                preds_map = None
                logger.warning("Failed to parse Phase 4 predictions map from %s (%s): %s", phase4_run, PHASE4_PREDICTIONS, exc)

            y_true: List[int]
            y_pred: List[int]

            if labels_map and preds_map:
                # join on intersection of keys
                label_keys = set(labels_map.keys())
                pred_keys = set(preds_map.keys())
                keys = sorted(k for k in label_keys & pred_keys)

                total_preds = len(pred_keys)
                total_labels = len(label_keys)
                matched = len(keys)
                unmatched_preds = total_preds - matched
                unmatched_labels = total_labels - matched

                logger.info(
                    "Join summary: total_preds=%d total_labels=%d matched=%d unmatched_preds=%d unmatched_labels=%d",
                    total_preds,
                    total_labels,
                    matched,
                    unmatched_preds,
                    unmatched_labels,
                )

                if matched == 0:
                    logger.error("No matching prediction-label pairs found for dataset %s (phase4_run=%s)", dataset_id, phase4_run)
                    raise KPIEvaluatorError("no matching prediction-label pairs found")

                y_true = [labels_map[k] for k in keys]
                y_pred = [preds_map[k] for k in keys]
            else:
                logger.warning("Falling back to legacy positional parsing for dataset %s and Phase 4 predictions (phase4_run=%s)", dataset_id, phase4_run)
                # fall back to legacy behaviour: positional ground truth + positional predictions
                y_true = self._read_series(dataset_id, GROUND_TRUTH_FILENAME)
                y_pred = self._read_phase4_predictions(run_id=phase4_run)

            metrics = self._compute_metrics(y_true, y_pred)

            summary = {
                "experiment_id": experiment_id,
                "dataset_id": dataset_id,
                "precision": metrics.precision,
                "recall": metrics.recall,
                "f1": metrics.f1,
            }
            self._store.write_json(experiment_id, SUMMARY_PATH, summary)
            logger.info("KPI evaluation complete for %s/%s", experiment_id, dataset_id)
            return KPIResult(experiment_id=experiment_id, dataset_id=dataset_id, metrics=metrics, summary_path=SUMMARY_PATH)
        except (ArtifactStoreError, ValueError, KPIEvaluatorError) as exc:
            # ArtifactStoreError -> IO problems; ValueError -> parse issues
            logger.exception("KPI evaluation failed for %s/%s", experiment_id, dataset_id)
            raise KPIEvaluatorError("evaluation failed") from exc
