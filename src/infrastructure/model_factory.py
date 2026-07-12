"""Placeholder model factory for future extensibility."""

from __future__ import annotations

from typing import Any

from models.base_model import BaseModel
from models.isolation_forest_model import IsolationForestModel


class ModelFactory:
    """Create model instances by name for future model expansion."""

    def __init__(self) -> None:
        self._registry: dict[str, type[BaseModel]] = {
            "isolation_forest": IsolationForestModel,
        }

    def create_model(self, model_name: str, config: dict[str, Any] | None = None) -> BaseModel:
        """Create a model instance based on a registered model name."""
        registry_name = model_name.lower()
        if registry_name not in self._registry:
            raise ValueError(f"Unsupported model: {model_name}")

        model_cls = self._registry[registry_name]
        if config is None:
            return model_cls()
        return model_cls(**config)
