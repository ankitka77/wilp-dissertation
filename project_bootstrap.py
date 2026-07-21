
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure `src` is on sys.path for legacy analysis scripts and tests that rely
# on project-local imports. Importing this module is a no-op if the path is
# already present.
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Set matplotlib backend via environment variable so modules that import
# matplotlib.pyplot use a headless backend in CI/test environments.
os.environ.setdefault("MPLBACKEND", "Agg")

__all__ = ["ROOT", "SRC"]
