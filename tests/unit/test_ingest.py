import json

import pandas as pd

from phase6.config import Config
from phase6.ingest import Ingestor, ValidationResult


def test_ingest_loads_vocabulary_and_sequences(tmp_path):
    # Prepare vocabulary JSON
    vocab = {"A": 1, "B": 2, "C": 3}
    vocab_path = tmp_path / "vocab.json"
    vocab_path.write_text(json.dumps(vocab), encoding="utf-8")

    # Prepare sequences CSV with a 'sequence' column (JSON strings)
    seqs = [json.dumps([1, 2, 3]), json.dumps([2, 3]), "4 5 6"]
    df = pd.DataFrame({"sequence_events": seqs})
    seq_path = tmp_path / "seqs.csv"
    df.to_csv(seq_path, index=False)

    cfg = Config()
    ing = Ingestor(cfg)
    inputs, vr = ing.load({"vocabulary": str(vocab_path), "sequences": str(seq_path)})

    assert isinstance(vr, ValidationResult)
    assert vr.ok
    assert inputs.vocabulary == {"A": 1, "B": 2, "C": 3}
    assert inputs.train_df is not None
    assert len(inputs.train_df) == 3
    # Sequence coercion: first two rows should be lists
    assert isinstance(inputs.train_df.iloc[0]["sequence_events"], list)


def test_ingest_missing_vocabulary_reports_error(tmp_path):
    cfg = Config()
    ing = Ingestor(cfg)
    inputs, vr = ing.load({"sequences": str(tmp_path / "no_such.csv")})
    assert not vr.ok
    assert any("Missing 'vocabulary' path" in e or "Failed to load vocabulary" in e for e in vr.errors + vr.warnings)
