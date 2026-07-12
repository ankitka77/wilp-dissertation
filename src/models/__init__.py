"""Model implementations for anomaly detection workflows."""

from .base_model import BaseModel
from .isolation_forest_model import IsolationForestModel

__all__ = ["BaseModel", "IsolationForestModel"]
