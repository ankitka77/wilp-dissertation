import pandas as pd
from log_processing.sequence_builder import SequenceBuilder


def test_sliding_window_sequences_and_targets():
    # create simple event stream without block_id
    df = pd.DataFrame({
        "event_id": [1, 2, 3, 4],
        "source": ["test"] * 4,
    })

    sb = SequenceBuilder(window_size=3, stride=1, train_ratio=0.5)
    seqs = sb.build_sequences(df)
    all_df = seqs["all"]

    # expecting two windows: [1,2,3] and [2,3,4]
    assert len(all_df) == 2

    first = all_df.iloc[0]
    assert first["sequence_events"] == [1, 2, 3]
    assert first["input_sequence"] == [1, 2]
    assert first["next_event_target"] == 3
    assert first["sequence_length"] == 3
    assert first["dataset"] == "test"
    assert first["block_id"] is None
    assert first["session_id"] is None
    assert first["split"] in ("train", "test")

    second = all_df.iloc[1]
    assert second["sequence_events"] == [2, 3, 4]
    assert second["input_sequence"] == [2, 3]
    assert second["next_event_target"] == 4


def test_block_grouping_sequences_and_targets():
    # create grouped events with block_id
    df = pd.DataFrame({
        "event_id": [10, 11, 20, 21, 22],
        "block_id": ["A", "A", "B", "B", "B"],
        "source": ["datasetX"] * 5,
        "session_id": ["s1", "s1", "s2", "s2", "s2"],
    })

    sb = SequenceBuilder(window_size=3, stride=1, train_ratio=1.0)
    seqs = sb.build_sequences(df)
    all_df = seqs["all"]

    # two blocks -> two sequences
    assert len(all_df) == 2

    a = all_df.loc[all_df["block_id"] == "A"].iloc[0]
    assert a["sequence_events"] == [10, 11]
    assert a["input_sequence"] == [10]
    assert a["next_event_target"] == 11
    assert a["sequence_id"].startswith("block_")
    assert a["dataset"] == "datasetX"
    assert a["session_id"] == "s1"

    b = all_df.loc[all_df["block_id"] == "B"].iloc[0]
    assert b["sequence_events"] == [20, 21, 22]
    assert b["input_sequence"] == [20, 21]
    assert b["next_event_target"] == 22
    assert b["session_id"] == "s2"
