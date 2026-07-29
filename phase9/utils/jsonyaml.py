from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import yaml


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, obj: Any) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def dump_yaml(path: Path, obj: Any) -> None:
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(obj, f)
