from __future__ import annotations

from datetime import datetime, timezone


def now_iso() -> str:
    """Return current UTC time as ISO 8601 string with Z suffix."""
    return datetime.now(timezone.utc).isoformat()
