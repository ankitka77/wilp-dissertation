from phase6.sequence_encoder import SequenceEncoder
from phase6.types import EncoderState


def test_encode_decode_and_pad_truncate():
    vocab = {"A": 1, "B": 2}
    pad_token = 0
    unk = 99
    max_len = 4

    enc = SequenceEncoder(vocabulary=vocab, pad_token=pad_token, unknown_token=unk, max_length=max_len)

    ids = enc.encode(["A", "B", "C"])  # C is unknown
    assert ids == [1, 2, unk]

    decoded = enc.decode(ids)
    assert decoded == ["A", "B", "<UNKNOWN>"]

    padded = enc.pad(ids)
    assert len(padded) == max_len
    assert padded[-1] == pad_token

    truncated = enc.truncate([1, 2, 3, 4, 5])
    assert len(truncated) == max_len


def test_serialize_deserialize():
    vocab = {"X": 10}
    state = EncoderState(vocabulary=vocab, pad_token=0, unknown_token=1, max_length=3)
    enc = SequenceEncoder.deserialize(state)
    assert enc.serialize().vocabulary == vocab
    assert enc.max_length == 3
