from __future__ import annotations

from pathlib import Path
import json
from jsonschema import validate, ValidationError

# Load schema relative to this module to avoid CWD issues during imports
_SCHEMA_PATH = Path(__file__).parent / "manifest.schema.json"
_SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_manifest_schema(data: dict) -> None:
    try:
        validate(instance=data, schema=_SCHEMA)
    except ValidationError as e:
        raise
