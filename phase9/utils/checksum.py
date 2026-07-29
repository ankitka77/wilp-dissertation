from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Union


def sha256_file(path: Union[str, Path]) -> str:
    """Compute SHA256 checksum of a file and return hex digest."""
    h = hashlib.sha256()
    p = Path(path)
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
