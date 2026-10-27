"""Legacy entry point kept for compatibility (ADR-009).

New code should call :func:`bugsafari.engine.runner.run_scenario` directly. This
module is one of the two composition points allowed to know about the bundled
demo application.
"""

from __future__ import annotations

from contextlib import AbstractContextManager

from bugsafari.config import Settings, load_settings
from bugsafari.engine.runner import run_scenario
from bugsafari.engine.target import managed_server
from bugsafari.reporting.models import RunResult
from bugsafari.scenarios.loader import load_scenario_by_id
from demo_app.app import create_app

SCENARIO_ID = "cart-total-quantity"


def local_demo_server() -> AbstractContextManager[str]:
    """Compatibility wrapper around the managed demo server."""
    return managed_server(create_app)


def run_demo_exploration(
    screenshot_path: str | None = None,
    settings: Settings | None = None,
) -> RunResult:
    """Run the bundled quantity scenario and return a dashboard-friendly result."""
    settings = settings or load_settings()
    scenario = load_scenario_by_id(SCENARIO_ID, settings.scenarios_dir)
    return run_scenario(
        scenario, settings, app_factory=create_app, screenshot_path=screenshot_path
    )


__all__ = ["local_demo_server", "run_demo_exploration"]
