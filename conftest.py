"""Pytest bootstrap.

Ensures the project root is importable no matter which directory pytest is
started from, and registers the repository-wide test markers (declared in
``pyproject.toml``).
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
