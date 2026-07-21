Module: sequence_encoder.py

1. Purpose
- Convert between event-level vocabulary and numeric sequences, provide padding/truncation rules and encoder state serialization.

2. Public Classes
- `SequenceEncoder`
  - Responsibilities: encode/decode sequences, provide `pad`/`truncate`, persist encoder state.
  - Attributes: `vocabulary`, `pad_token`, `unknown_token`, `max_length`.

3. Dataclasses
- `EncoderState` (`vocabulary`, `pad_token`, `unknown_token`, `max_length`)

4. Enumerations
- None

5. Public Methods
- `encode(self, templates: list[str]) -> list[int]`
- `decode(self, ids: list[int]) -> list[str]`
- `pad(self, ids: list[int]) -> list[int]`
- `truncate(self, ids: list[int]) -> list[int]`
- `serialize(self) -> EncoderState`
- `deserialize(state: EncoderState) -> SequenceEncoder` (classmethod)

6. Private Methods
- `_map_template_to_id`, `_map_id_to_template`

7. Module Inputs
- `vocabulary` dict from Phase 5 and `Config`.

8. Module Outputs
- Encoded sequences and `EncoderState`.

9. Dependencies
- types.py, config.py
