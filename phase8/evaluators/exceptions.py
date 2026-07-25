"""Evaluator-specific exceptions for Phase 8."""
from __future__ import annotations

from typing import Optional


class EvaluatorError(RuntimeError):
    """Base class for evaluator errors."""


class KPIEvaluatorError(EvaluatorError):
    pass


class DeepLogEvaluatorError(EvaluatorError):
    pass
