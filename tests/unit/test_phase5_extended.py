import json
import pandas as pd
from pathlib import Path

from log_processing import (
    LogParser,
    TemplateMiner,
    EventIdMapper,
    SequenceBuilder,
    ReportGenerator,
    LogVisualizer,
)


def test_malformed_log_lines():
    # synthetic malformed and edge lines
    lines = ["", None, "A random informational message without structured fields", "2020-01-01 00:00:00 INFO Comp: Started"]
    df = pd.DataFrame({"raw_line": lines})
    parser = LogParser()
    out = parser.parse(df)

    # empty/None lines should produce empty message rather than crash
    assert out.loc[0, "message"] == ""
    assert out.loc[1, "message"] == ""
    # unstructured line preserved
    assert out.loc[2, "message"] == lines[2]
    # structured line parsed
    assert out.loc[3, "level"] == "INFO"


def test_empty_and_invalid_datasets():
    empty = pd.DataFrame({"raw_line": []})
    parser = LogParser()
    assert parser.parse(empty).empty

    miner = TemplateMiner()
    assert miner.mine_templates(empty).empty

    mapper = EventIdMapper()
    vocab_df = mapper.build_vocabulary(pd.DataFrame({"template": []}))
    assert vocab_df.empty

    # mapping templates not in vocab -> event_id == 0
    df = pd.DataFrame({"template": ["unknown_template"]})
    mapped = mapper.map_event_ids(df)
    assert mapped.loc[0, "event_id"] == 0


def test_deterministic_vocabulary_generation():
    # Templates in different orders should produce same deterministic ids
    templates = ["b", "a", "c", "a"]
    df1 = pd.DataFrame({"template": templates})
    df2 = pd.DataFrame({"template": list(reversed(templates))})

    mapper = EventIdMapper()
    v1 = mapper.build_vocabulary(df1)
    mapper2 = EventIdMapper()
    v2 = mapper2.build_vocabulary(df2)

    # Both vocabularies should have same templates in same sorted order
    assert list(v1["template"]) == sorted(list(set(templates)))
    assert list(v1["event_id"]) == list(v2["event_id"])
    # event_id for 'a' should be 1 because sorted order ['a','b','c']
    row_a = v1[v1["template"] == "a"].iloc[0]
    assert row_a["event_id"] == 1


def test_different_window_sizes_and_sliding(tmp_path):
    # create mapped dataframe with event_id column
    df = pd.DataFrame({"event_id": [1, 2, 3, 4, 5], "source": ["ds"]*5})
    # window 2 stride 1 -> windows: [1,2],[2,3],[3,4],[4,5]
    sb = SequenceBuilder(window_size=2, stride=1, train_ratio=0.5)
    seqs = sb.build_sequences(df)["all"]
    assert len(seqs) == 4
    assert seqs.iloc[0]["sequence_events"] == [1, 2]
    assert seqs.iloc[0]["input_sequence"] == [1]
    assert seqs.iloc[0]["next_event_target"] == 2

    # window 3 stride 2 -> [1,2,3],[3,4,5]
    sb2 = SequenceBuilder(window_size=3, stride=2, train_ratio=1.0)
    seqs2 = sb2.build_sequences(df)["all"]
    assert len(seqs2) == 2
    assert seqs2.iloc[1]["sequence_events"] == [3, 4, 5]


def test_hdfs_block_grouping():
    df = pd.DataFrame({
        "event_id": [10, 11, 20, 21, 22],
        "block_id": ["A", "A", "B", "B", "B"],
        "source": ["datasetX"] * 5,
        "session_id": ["s1", "s1", "s2", "s2", "s2"],
    })
    sb = SequenceBuilder(window_size=3, stride=1, train_ratio=1.0)
    all_df = sb.build_sequences(df)["all"]
    assert len(all_df) == 2
    a = all_df[all_df["block_id"] == "A"].iloc[0]
    assert a["input_sequence"] == [10]
    assert a["next_event_target"] == 11
    b = all_df[all_df["block_id"] == "B"].iloc[0]
    assert b["input_sequence"] == [20, 21]
    assert b["next_event_target"] == 22


def test_manifest_and_report_generation(tmp_path):
    rg = ReportGenerator(reports_dir=tmp_path)
    manifest = {
        "manifest_version": "1.0",
        "generated_on": "2020-01-01T00:00:00Z",
        "dataset_name": "testset",
        "dataset_fingerprint": "abc123",
        "vocabulary_size": 3,
        "vocabulary_csv": "vocab.csv",
        "vocabulary_json": "vocab.json",
        "sequence_count": 5,
        "train_sequence_count": 3,
        "test_sequence_count": 2,
        "train_sequences_path": "train.csv",
        "test_sequences_path": "test.csv",
        "window_size": 10,
        "stride": 1,
        "min_sequence_length": 1,
        "max_sequence_length": 1000,
        "configuration_summary": {},
        "git_branch": "local",
        "git_commit": "deadbeef",
        "git_tag": None,
        "notes": "",
    }
    path = rg.save_manifest(manifest)
    assert path.exists()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    for key in [
        "manifest_version",
        "generated_on",
        "dataset_name",
        "dataset_fingerprint",
        "vocabulary_size",
        "sequence_count",
        "train_sequence_count",
        "test_sequence_count",
        "window_size",
        "stride",
        "min_sequence_length",
        "max_sequence_length",
        "git_branch",
        "git_commit",
        "notes",
    ]:
        assert key in loaded

    # event and sequence table generation
    event_table = pd.DataFrame({"template": ["t1", "t2"], "frequency": [5, 3]})
    seq_stats = pd.DataFrame([{"count": 2, "mean_length": 3.0}])
    p1 = rg.save_event_table(event_table)
    p2 = rg.save_sequence_table(seq_stats)
    assert p1.exists()
    assert p2.exists()


def test_visualization_generation(tmp_path):
    viz = LogVisualizer(output_dir=tmp_path)
    event_table = pd.DataFrame({"template": ["t1", "t2"], "frequency": [10, 5]})
    seq_df = pd.DataFrame({"sequence_length": [2, 3, 4]})
    train = pd.DataFrame({"sequence_id": ["s1"]})
    test = pd.DataFrame({"sequence_id": ["s2", "s3"]})

    p1 = viz.plot_event_frequency(event_table)
    p2 = viz.plot_top_templates(event_table)
    p3 = viz.plot_sequence_length_histogram(seq_df)
    p4 = viz.plot_sequence_length_boxplot(seq_df)
    p5 = viz.plot_train_test_split(train, test)

    for p in [p1, p2, p3, p4, p5]:
        assert Path(p).exists()
