"""Pytest bootstrap for project imports."""

from pathlib import Path
import sys

# Ensure the repository `src/` directory is on sys.path for tests
ROOT = Path(__file__).resolve().parent.parent
SRC = (ROOT / "src").resolve()
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
