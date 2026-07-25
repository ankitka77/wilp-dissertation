"""Normalization strategy abstractions for Phase 7.

This module implements the `NormalizationStrategy` abstraction used by the
ScoreNormalizer. Implementations must be pure, deterministic, and must not
mutate caller-provided collections. Concrete strategies provide `normalize()`
and metadata accessors. Minimal runtime logging is used only for exceptional
conditions; routine operational logging belongs to the ScoreNormalizer.

Do NOT perform orchestration, FusionRecord mutation, or fusion logic here.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from types import MappingProxyType
from typing import Mapping, Tuple, List
import logging
import math

logger = logging.getLogger("project.phase7.normalization")


# Exceptions -------------------------------------------------------------


class NormalizationStrategyError(RuntimeError):
    """Base exception for normalization strategy failures."""


class NormalizationValidationError(NormalizationStrategyError):
    """Raised when input values violate strategy validation rules."""


class NormalizationConfigurationError(NormalizationStrategyError):
    """Raised when a strategy is misconfigured."""


# Constants --------------------------------------------------------------

_DEFAULT_EPSILON: float = 1e-8


# Abstract Strategy -----------------------------------------------------


class NormalizationStrategy(ABC):
    """Abstract base class for normalization strategies.

    Concrete strategies must implement `normalize`, `get_name`, and
    `get_metadata`. Implementations must not mutate input collections and
    must return immutable tuples of floats.
    """

    @abstractmethod
    def normalize(self, values: Tuple[float, ...]) -> Tuple[float, ...]:
        """Normalize the provided tuple of floats.

        Parameters
        ----------
        values:
            Tuple of numeric values to normalize. Implementations must validate
            input and raise `NormalizationValidationError` on invalid data.

        Returns
        -------
        Tuple[float, ...]
            Immutable tuple of normalized floats.
        """

    @abstractmethod
    def get_name(self) -> str:
        """Return a short, deterministic name identifying the strategy."""

    @abstractmethod
    def get_metadata(self) -> Mapping[str, object]:
        """Return read-only metadata describing the last or configured behavior.

        Implementations should return a mapping with deterministic keys and
        values and must not expose mutable containers.
        """

    # Protected helper for common validation shared by strategies
    def _validate_values(self, values: Tuple[float, ...]) -> Tuple[float, ...]:
        """Validate common value constraints and return a tuple of floats.

        Raises `NormalizationValidationError` for invalid input.
        """
        if values is None:
            raise NormalizationValidationError("values must not be None")
        if not isinstance(values, tuple):
            raise NormalizationValidationError("values must be a tuple of numbers")
        if len(values) == 0:
            raise NormalizationValidationError("values must not be empty")
        nums: Tuple[float, ...] = tuple()
        # Build a tuple of floats while validating each element
        converted: List[float] = []
        for idx, v in enumerate(values):
            if v is None:
                raise NormalizationValidationError(f"value at index {idx} is None")
            try:
                f = float(v)
            except (TypeError, ValueError) as exc:
                raise NormalizationValidationError(f"value at index {idx} is not numeric: {v}") from exc
            if not math.isfinite(f):
                raise NormalizationValidationError(f"value at index {idx} is not finite: {v}")
            converted.append(f)
        return tuple(converted)


# Concrete Strategies ---------------------------------------------------


class MinMaxNormalization(NormalizationStrategy):
    """Min-max normalization strategy.

    Formula used:

        normalized = (raw - minimum) / (maximum - minimum + epsilon)

    Safeguards and semantics:
    - Output is clamped to [0, 1].
    - `epsilon` prevents divide-by-zero.
    - If all values are identical:
        - if each value already lies within [0, 1] -> preserve original values
        - otherwise -> return all values as 0.5
    """

    _STRATEGY: str = "min_max"

    def __init__(self, *, epsilon: float = _DEFAULT_EPSILON) -> None:
        if epsilon <= 0.0:
            raise NormalizationConfigurationError("epsilon must be positive")
        self._epsilon: float = float(epsilon)
        # metadata is immutable mapping describing latest normalization; start with configured values
        initial = {"strategy": self._STRATEGY, "epsilon": float(self._epsilon)}
        # deterministic ordering: insert keys in sorted order of keys
        ordered = {k: initial[k] for k in sorted(initial.keys())}
        self._metadata: Mapping[str, object] = MappingProxyType(ordered)

    def normalize(self, values: Tuple[float, ...]) -> Tuple[float, ...]:
        nums = self._validate_values(values)

        # Deterministic calculations
        minimum = min(nums)
        maximum = max(nums)

        # All-identical handling
        if math.isclose(maximum, minimum, rel_tol=0.0, abs_tol=0.0):
            # values identical
            # if values already lie within [0, 1], preserve originals
            if all(0.0 <= v <= 1.0 for v in nums):
                result = tuple(nums)
            else:
                # otherwise normalize all to 0.5
                result = tuple(0.5 for _ in nums)
        else:
            denom = (maximum - minimum) + self._epsilon
            result = tuple(self._clamp((v - minimum) / denom) for v in nums)

        # update metadata to reflect this normalization (deterministic key ordering)
        meta_src = {
            "strategy": self._STRATEGY,
            "epsilon": float(self._epsilon),
            "minimum": float(minimum),
            "maximum": float(maximum),
            "input_count": int(len(nums)),
        }
        ordered_meta = {k: meta_src[k] for k in sorted(meta_src.keys())}
        self._metadata = MappingProxyType(ordered_meta)
        return result

    def get_name(self) -> str:
        return self._STRATEGY

    def get_metadata(self) -> Mapping[str, object]:
        return self._metadata

    # Helpers ------------------------------------------------------------
    def _clamp(self, v: float) -> float:
        # clamp to [0, 1]
        if v < 0.0:
            return 0.0
        if v > 1.0:
            return 1.0
        return float(v)
    


class ZScoreNormalization(NormalizationStrategy):
    """Z-score normalization placeholder.

    This class is provided as an extension point and currently not implemented
    in the frozen architecture. Calling `normalize` will raise
    `NotImplementedError`.
    """

    _STRATEGY: str = "z_score"

    def normalize(self, values: Tuple[float, ...]) -> Tuple[float, ...]:
        raise NotImplementedError("ZScoreNormalization is not implemented in this release")

    def get_name(self) -> str:
        return self._STRATEGY

    def get_metadata(self) -> Mapping[str, object]:
        return MappingProxyType({"strategy": self._STRATEGY})


class IdentityNormalization(NormalizationStrategy):
    """Identity normalization: return values unchanged after validation.

    This strategy is primarily useful for testing and pipeline passthroughs.
    """

    _STRATEGY: str = "identity"

    def normalize(self, values: Tuple[float, ...]) -> Tuple[float, ...]:
        nums = self._validate_values(values)
        # Return a new tuple of floats to ensure immutability
        # update metadata to reflect this normalization
        meta_src = {"strategy": self.get_name(), "input_count": int(len(nums))}
        ordered_meta = {k: meta_src[k] for k in sorted(meta_src.keys())}
        self._metadata = MappingProxyType(ordered_meta)
        return tuple(float(v) for v in nums)

    def get_name(self) -> str:
        return self._STRATEGY

    def get_metadata(self) -> Mapping[str, object]:
        return self._metadata if hasattr(self, "_metadata") else MappingProxyType({"strategy": self._STRATEGY})


__all__ = [
    "NormalizationStrategy",
    "MinMaxNormalization",
    "ZScoreNormalization",
    "IdentityNormalization",
    "NormalizationStrategyError",
    "NormalizationValidationError",
    "NormalizationConfigurationError",
]
