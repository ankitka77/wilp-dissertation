"""Sequence encoder for Phase 6.

Provides encoding/decoding between template strings and integer ids,
padding/truncation utilities, and state serialization using
`EncoderState` defined in `phase6.types`.
"""
from __future__ import annotations

from typing import Dict, List
import logging

from phase6.types import EncoderState


logger = logging.getLogger("project")


class SequenceEncoder:
    """Encode and decode event template sequences.

    Parameters
    ----------
    vocabulary:
        Mapping from template string to integer id.
    pad_token:
        Integer id used for padding sequences.
    unknown_token:
        Integer id used for unknown templates.
    max_length:
        Maximum sequence length for `pad`/`truncate` operations.
    """

    def __init__(self, vocabulary: Dict[str, int], pad_token: int, unknown_token: int, max_length: int) -> None:
        if not isinstance(vocabulary, dict):
            raise TypeError("vocabulary must be a dict[str,int]")
        if not isinstance(pad_token, int) or not isinstance(unknown_token, int):
            raise TypeError("pad_token and unknown_token must be integers")
        if not isinstance(max_length, int) or max_length <= 0:
            raise ValueError("max_length must be a positive integer")

        self.vocabulary: Dict[str, int] = dict(vocabulary)
        self.pad_token: int = pad_token
        self.unknown_token: int = unknown_token
        self.max_length: int = max_length
        # Build reverse map for decoding
        self._id_to_template: Dict[int, str] = {v: k for k, v in self.vocabulary.items()}

    def encode(self, templates: List[str]) -> List[int]:
        """Encode a list of template strings to integer ids.

        Unknown templates are mapped to `unknown_token`.
        """
        if not isinstance(templates, list):
            raise TypeError("templates must be a list of strings")
        ids: List[int] = [self._map_template_to_id(t) for t in templates]
        return ids

    def decode(self, ids: List[int]) -> List[str]:
        """Decode a list of integer ids back to template strings.

        Unknown ids are represented as the string "<UNKNOWN>".
        """
        if not isinstance(ids, list):
            raise TypeError("ids must be a list of integers")
        templates: List[str] = [self._map_id_to_template(i) for i in ids]
        return templates

    def pad(self, ids: List[int]) -> List[int]:
        """Pad or truncate `ids` so its length equals `max_length`.

        Shorter sequences are right-padded with `pad_token`. Longer
        sequences are truncated to `max_length`.
        """
        if not isinstance(ids, list):
            raise TypeError("ids must be a list of integers")
        truncated = self.truncate(ids)
        if len(truncated) < self.max_length:
            padded = truncated + [self.pad_token] * (self.max_length - len(truncated))
            return padded
        return truncated

    def truncate(self, ids: List[int]) -> List[int]:
        """Truncate `ids` to at most `max_length` elements.

        Returns a new list.
        """
        if not isinstance(ids, list):
            raise TypeError("ids must be a list of integers")
        return ids[: self.max_length]

    def serialize(self) -> EncoderState:
        """Return the encoder state as an `EncoderState` dataclass."""
        return EncoderState(vocabulary=self.vocabulary, pad_token=self.pad_token, unknown_token=self.unknown_token, max_length=self.max_length)

    @classmethod
    def deserialize(cls, state: EncoderState) -> "SequenceEncoder":
        """Recreate a `SequenceEncoder` from an `EncoderState` instance."""
        if not isinstance(state, EncoderState):
            raise TypeError("state must be an EncoderState instance")
        return cls(vocabulary=dict(state.vocabulary), pad_token=state.pad_token, unknown_token=state.unknown_token, max_length=state.max_length)

    # Private helpers
    def _map_template_to_id(self, template: str) -> int:
        if not isinstance(template, str):
            raise TypeError("template must be a string")
        return self.vocabulary.get(template, self.unknown_token)

    def _map_id_to_template(self, id_: int) -> str:
        if not isinstance(id_, int):
            raise TypeError("id must be an integer")
        return self._id_to_template.get(id_, "<UNKNOWN>")


__all__ = ["SequenceEncoder"]
