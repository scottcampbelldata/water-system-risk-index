"""Shared test setup.

Pipeline modules use top-level imports (e.g. ``from utils import ...`` inside
``src/score_risk.py``), so ``src/`` must be importable directly. We add it to
``sys.path`` here; ``pyproject.toml`` separately sets ``pythonpath = ["."]`` so
the ``from src.module import ...`` style used in the test files also resolves.
"""

import sys
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))
