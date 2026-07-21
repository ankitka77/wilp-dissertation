Module: dataset.py

1. Purpose
- Build dataset objects and batching/collation logic for training and inference.

2. Public Classes
- `SequenceDataset` (holds encoded sequences and targets)
- `DataLoader` (interface description for batch iteration)

3. Dataclasses
- `DatasetMetadata` (`num_examples`, `vocab_size`, `max_seq_len`, `pad_token`, `num_batches`)

4. Enumerations
- None

5. Public Methods
- `SequenceDataset.__len__()`, `__getitem__(idx)`
- `make_dataloader(dataset, batch_size, shuffle, num_workers, collate_fn) -> DataLoader`
- `default_collate_fn(batch) -> dict` (returns `inputs`, `lengths`, `masks`, `targets`, `sequence_ids`)

6. Private Methods
- `_pad_batch`, `_compute_masks`

7. Module Inputs
- Encoded sequences and `Config`.

8. Module Outputs
- `SequenceDataset`, `DataLoader`, `DatasetMetadata`.

9. Dependencies
- sequence_encoder.py, types.py, config.py, numpy
