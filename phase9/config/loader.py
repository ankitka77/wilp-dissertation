from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Any, Optional
import yaml

from .settings import Phase9Settings
from ..utils.fs import safe_read_text
from pathlib import Path


def load_yaml(path: Path) -> Dict[str, Any]:
    text = safe_read_text(path)
    return yaml.safe_load(text) or {}


def load_config(path: Optional[Path] = None, overrides: Optional[Dict[str, Any]] = None) -> Phase9Settings:
    """Load Phase9 configuration.

    Order of precedence (highest to lowest):
      1. runtime overrides (argument `overrides`)
      2. environment variables (PHASE9_... handled by Pydantic)
      3. YAML file at `path` if provided
      4. Pydantic defaults defined in settings.py

    """
    overrides = overrides or {}
    data = {}
    if path:
        p = Path(path)
        if p.exists():
            data = load_yaml(p)
    # Merge overrides
    if overrides:
        # simple shallow merge; config structure is nested so expect dicts
        for k, v in overrides.items():
            data[k] = v

    settings = Phase9Settings(**data)
    return settings
