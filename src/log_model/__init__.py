"""Log model package.

This package is reserved for Phase 6/7 model implementations (DeepLog and
other log-anomaly models). It is intentionally retained as a clear target
for model code and for backward compatibility with any imports referencing
`src.log_model`.
"""

from .model import LogAnomalyModel

__all__ = ["LogAnomalyModel"]
