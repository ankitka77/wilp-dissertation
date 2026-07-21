"""Phase 5 orchestration script.

Run with `python phase5_analysis.py` to execute the Phase 5 pipeline.
"""

from __future__ import annotations

import project_bootstrap  # noqa: F401
from pathlib import Path
from datetime import datetime, timezone
import time
import logging

import pandas as pd

from common.settings import load_settings
from infrastructure.experiment_manager import ExperimentManager
from log_processing import (
    LogDataLoader,
    LogParser,
    TemplateMiner,
    EventIdMapper,
    SequenceBuilder,
    DatasetValidator,
    SequenceProfiler,
    LogVisualizer,
    ReportGenerator,
)

logger = logging.getLogger("project")


def main() -> int:
    print(">>> Entered Phase 5 main()")

    settings = load_settings()

    # Use Phase5Settings input_dir when available, fallback to default path
    input_dir = getattr(settings, "phase5", None).input_dir if getattr(settings, "phase5", None) is not None else "data/logs/HDFS_v1"
    loader = LogDataLoader(input_dir)
    print(">> Loading raw logs...")
    logger.info("Loading raw logs...")
    t0 = time.perf_counter()
    parsed_raw = loader.load()
    fingerprint = loader.fingerprint()
    elapsed = time.perf_counter() - t0
    logger.info("Loading raw logs completed in %.1f seconds", elapsed)
    print(f">> Loading raw logs completed in {elapsed:.1f} seconds")

    parser = LogParser()
    logger.info("Parsing logs...")
    print(">> Parsing logs...")

    t0 = time.perf_counter()
    parsed = parser.parse(parsed_raw)
    elapsed = time.perf_counter() - t0
    logger.info("Parsing logs completed in %.1f seconds", elapsed)
    print(f">> Parsing logs completed in {elapsed:.1f} seconds")

    miner = TemplateMiner()
    logger.info("Mining templates...")
    print(">> Mining templates...")
    t0 = time.perf_counter()
    mined = miner.mine_templates(parsed)
    elapsed = time.perf_counter() - t0
    logger.info("Mining templates completed in %.1f seconds", elapsed)
    print(f">> Mining templates completed in {elapsed:.1f} seconds")
    print(f">> Templates after mining: {mined['template'].nunique():,}")
    print(">> Sample mined templates:")
    print(mined["template"].head(10).to_string(index=False))
    unique_templates = mined["template"].nunique()
    total_logs = len(mined)

    print(f">> Templates after mining: {unique_templates:,}")
    print(f">> Total log entries: {total_logs:,}")
    print(f">> Template uniqueness ratio: {unique_templates / total_logs:.2%}")

    mapper = EventIdMapper()
    logger.info("Building event vocabulary...")
    print(">> Building event vocabulary...")

    t0 = time.perf_counter()
    vocab_df = mapper.build_vocabulary(mined)
    elapsed = time.perf_counter() - t0
    logger.info("Building event vocabulary completed in %.1f seconds", elapsed)
    print(f">> Building event vocabulary completed in {elapsed:.1f} seconds")

    logger.info("Mapping event IDs...")
    print(">> Mapping event IDs...")
    t0 = time.perf_counter()
    mapped = mapper.map_event_ids(mined)
    elapsed = time.perf_counter() - t0
    logger.info("Mapping event IDs completed in %.1f seconds", elapsed)
    print(f">> Mapping event IDs completed in {elapsed:.1f} seconds")   

    phase5_cfg = getattr(settings, "phase5", None)
    if phase5_cfg is None:
        window_size = 10
        stride = 1
        train_ratio = 0.8
    else:
        window_size = phase5_cfg.window_size
        stride = phase5_cfg.stride
        train_ratio = phase5_cfg.train_ratio

    seq_builder = SequenceBuilder(window_size=window_size, stride=stride, train_ratio=train_ratio)
    logger.info("Building sequences...")
    print(">> Building sequences...")
    t0 = time.perf_counter()
    sequences = seq_builder.build_sequences(mapped)
    elapsed = time.perf_counter() - t0
    logger.info("Building sequences completed in %.1f seconds", elapsed)
    print(f">> Building sequences completed in {elapsed:.1f} seconds")

    validator = DatasetValidator()
    # use train+test as all
    all_seqs = sequences.get("all", pd.DataFrame())
    logger.info("Validation...")
    print(">> Validation...")
    t0 = time.perf_counter()
    validation = validator.validate(parsed=mined, vocab=vocab_df, sequences=all_seqs, config={})
    elapsed = time.perf_counter() - t0
    logger.info("Validation completed in %.1f seconds", elapsed)
    print(f">> Validation completed in {elapsed:.1f} seconds")

    profiler = SequenceProfiler()
    logger.info("Profiling...")
    print(">> Profiling...")
    t0 = time.perf_counter()
    event_stats = profiler.profile_events(mined)
    seq_stats = profiler.profile_sequences(all_seqs)
    elapsed = time.perf_counter() - t0
    logger.info("Profiling completed in %.1f seconds", elapsed)

    reports = ReportGenerator()
    logger.info("Saving artifacts...")
    print(">> Saving artifacts...")
    t0 = time.perf_counter()
    reports.save_event_table(event_stats)
    reports.save_sequence_table(pd.DataFrame([seq_stats]))
    reports.save_validation_report(validation)
    elapsed = time.perf_counter() - t0
    logger.info("Saving artifacts completed in %.1f seconds", elapsed)
    print(f">> Saving artifacts completed in {elapsed:.1f} seconds")

    # save core data outputs
    out_dir = Path("artifacts/reports/phase5")
    out_dir.mkdir(parents=True, exist_ok=True)
    parsed_path = out_dir / "parsed_log_events.csv"
    mined.to_csv(parsed_path, index=False)
    vocab_csv = out_dir / "event_vocabulary.csv"
    mapper.save_vocab_csv(vocab_csv)
    mapper.save_vocab_json(out_dir / "event_vocabulary.json")

    train_df = sequences.get("train", pd.DataFrame())
    test_df = sequences.get("test", pd.DataFrame())
    train_path = out_dir / "training_sequences.csv"
    test_path = out_dir / "test_sequences.csv"
    train_df.to_csv(train_path, index=False)
    test_df.to_csv(test_path, index=False)

    seq_meta = out_dir / "sequence_metadata.csv"
    all_seqs.to_csv(seq_meta, index=False)

    # visualizations
    viz = LogVisualizer()
    logger.info("Generating visualizations...")
    print(">> Generating visualizations...")
    t0 = time.perf_counter()
    viz_paths = []
    p = viz.plot_event_frequency(event_stats)
    if p:
        viz_paths.append(p)
    p = viz.plot_top_templates(event_stats)
    if p:
        viz_paths.append(p)
    p = viz.plot_sequence_length_histogram(all_seqs)
    if p:
        viz_paths.append(p)
    p = viz.plot_sequence_length_boxplot(all_seqs)
    if p:
        viz_paths.append(p)
    p = viz.plot_train_test_split(train_df, test_df)
    if p:
        viz_paths.append(p)
    elapsed = time.perf_counter() - t0
    logger.info("Generating visualizations completed in %.1f seconds", elapsed)
    print(f">> Generating visualizations completed in {elapsed:.1f} seconds")

    # manifest
    manifest = {
        "manifest_version": "1.0",
        "generated_on": datetime.now(timezone.utc).isoformat(),
        "dataset_name": Path(input_dir).name,
        "dataset_fingerprint": fingerprint,
        "vocabulary_size": int(len(vocab_df)),
        "vocabulary_csv": str(vocab_csv),
        "vocabulary_json": str(out_dir / "event_vocabulary.json"),
        "sequence_count": int(len(all_seqs)),
        "train_sequence_count": int(len(train_df)),
        "test_sequence_count": int(len(test_df)),
        "train_sequences_path": str(train_path),
        "test_sequences_path": str(test_path),
        "window_size": seq_builder.window_size,
        "stride": seq_builder.stride,
        "min_sequence_length": getattr(phase5_cfg, "min_sequence_length", settings.phase5.min_sequence_length if getattr(settings, "phase5", None) else 1),
        "max_sequence_length": getattr(phase5_cfg, "max_sequence_length", settings.phase5.max_sequence_length if getattr(settings, "phase5", None) else 1000000),
        "configuration_summary": (phase5_cfg.model_dump() if phase5_cfg is not None else {}),
        "config": {},
    }
    # try to add git metadata if available
    try:
        import subprocess

        branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        branch = getattr(settings.phase4, "git_branch", "local")
    try:
        commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        commit = getattr(settings.phase4, "git_commit", "unknown")
    try:
        tag = subprocess.check_output(["git", "describe", "--tags", "--exact-match"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        tag = getattr(settings.phase4, "git_tag", None)

    manifest.update({"git_branch": branch, "git_commit": commit, "git_tag": tag, "notes": ""})
    logger.info("Writing manifest...")
    print(">> Writing manifest...")
    t0 = time.perf_counter()
    reports.save_manifest(manifest)
    elapsed = time.perf_counter() - t0
    logger.info("Writing manifest completed in %.1f seconds", elapsed)
    print(f">> Writing manifest completed in {elapsed:.1f} seconds")

    # experiment manager
    logger.info("Experiment finalization...")
    print(">> Experiment finalization...")
    t0 = time.perf_counter()
    em = ExperimentManager()
    em.start_experiment(manifest)
    em.log_metrics({"vocab_size": manifest["vocabulary_size"], "sequence_count": manifest["sequence_count"]})
    for p in viz_paths:
        em.log_plot(p, Path(p).name)
    em.finalize()
    elapsed = time.perf_counter() - t0
    logger.info("Experiment finalization completed in %.1f seconds", elapsed)
    print(f">> Experiment finalization completed in {elapsed:.1f} seconds")

    print("Phase 5 completed. Artifacts written to artifacts/reports/phase5 and artifacts/plots/phase5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
