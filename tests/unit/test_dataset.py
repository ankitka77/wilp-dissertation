import numpy as np

from phase6.config import Config
from phase6.dataset import SequenceDataset, make_dataloader, default_collate_fn


def test_sequence_dataset_len_and_getitem():
    seqs = [[1, 2, 3], [4, 5]]
    cfg = Config()
    ds = SequenceDataset(sequences=seqs, config=cfg)
    assert len(ds) == 2
    item = ds[0]
    assert item["sequence"] == [1, 2, 3]


def test_dataloader_and_collate():
    seqs = [[1, 2, 3], [4, 5]]
    targets = [0, 1]
    cfg = Config()
    ds = SequenceDataset(sequences=seqs, config=cfg, targets=targets, sequence_ids=["a", "b"])
    dl = make_dataloader(ds, batch_size=2, shuffle=False, num_workers=0)
    batches = list(dl)
    assert len(batches) == 1
    batch = batches[0]
    assert "inputs" in batch and "masks" in batch and "lengths" in batch
    assert batch["inputs"].shape[0] == 2
    assert isinstance(batch["lengths"], np.ndarray)
    assert batch["sequence_ids"] == ["a", "b"]


def test_default_collate_fn_padding_and_masks():
    batch = [{"sequence": [1, 2], "target": 0, "id": "x"}, {"sequence": [3], "target": 1, "id": "y"}]
    out = default_collate_fn(batch)
    assert out["inputs"].shape[1] == max(len(s["sequence"]) for s in batch)
    assert out["masks"].sum() == sum(len(s["sequence"]) for s in batch)
