from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Union


def ensure_dir(path: Union[str, Path]) -> Path:
    """Ensure a directory exists and return the Path."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_write_text(path: Union[str, Path], text: str, encoding: str = "utf-8") -> None:
    """Atomically write text to file by writing to a temp file then renaming.

    This prevents partial writes and is cross-platform.
    """
    p = Path(path)
    ensure_dir(p.parent)
    fd, tmp = tempfile.mkstemp(prefix=p.name, dir=str(p.parent))
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(text)
        os.replace(tmp, str(p))
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def safe_read_text(path: Union[str, Path], encoding: str = "utf-8") -> str:
    p = Path(path)
    with p.open("r", encoding=encoding) as f:
        return f.read()
