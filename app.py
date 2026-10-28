"""Root entry point for running the existing Streamlit dashboard."""

import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).parent / "app" / "dashboard.py"), run_name="__main__")
