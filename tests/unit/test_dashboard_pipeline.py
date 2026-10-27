"""Tests for dashboard scenario execution pipeline.

The Streamlit dashboard cannot be imported in a test process because ``st.*``
calls run at module level and require a live Streamlit runtime.  Instead these
tests exercise every function the dashboard calls:

- ``list_scenarios``  — populates the selector drop-down
- ``load_scenario_by_id``  — resolves the user's selection
- ``run_scenario``  — executes the selected scenario end-to-end
- ``ScenarioError``  — raised on a bad scenario directory / ID

The integration tests (run_scenario tests) are marked ``integration`` so they
run with the rest of the browser-backed suite.  The unit tests run immediately
without a browser.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bugsafari.config import load_settings
from bugsafari.engine.runner import run_scenario
from bugsafari.scenarios.loader import ScenarioError, list_scenarios, load_scenario_by_id
from demo_app.app import create_app

pytestmark = pytest.mark.unit

SCENARIO_DIR = Path(__file__).resolve().parents[2] / "scenarios"


# ---------------------------------------------------------------------------
# Unit tests — no browser required
# ---------------------------------------------------------------------------


def test_list_scenarios_returns_both_bundled_scenarios():
    """The selector drop-down must include every bundled scenario."""
    scenarios = list_scenarios(SCENARIO_DIR)
    ids = [s.id for s in scenarios]
    assert "cart-total-quantity" in ids
    assert "cart-remove-total" in ids


def test_list_scenarios_returns_scenario_objects_with_names():
    """Each entry has a human-readable name that the label formatter uses."""
    scenarios = list_scenarios(SCENARIO_DIR)
    for scenario in scenarios:
        assert scenario.name, f"scenario {scenario.id!r} has no name"
        assert scenario.description, f"scenario {scenario.id!r} has no description"


def test_load_scenario_by_id_resolves_quantity_scenario():
    scenario = load_scenario_by_id("cart-total-quantity", SCENARIO_DIR)
    assert scenario.id == "cart-total-quantity"
    assert scenario.step_actions() == ["open", "click", "change_quantity"]


def test_load_scenario_by_id_resolves_remove_scenario():
    scenario = load_scenario_by_id("cart-remove-total", SCENARIO_DIR)
    assert scenario.id == "cart-remove-total"
    assert scenario.step_actions() == ["open", "click", "click", "click"]


def test_load_scenario_by_id_raises_scenario_error_for_unknown_id():
    """The dashboard catches ScenarioError and shows an error message."""
    with pytest.raises(ScenarioError, match="unknown scenario"):
        load_scenario_by_id("does-not-exist", SCENARIO_DIR)


def test_list_scenarios_empty_dir_returns_empty_list(tmp_path):
    """A missing or empty directory must not crash; the dashboard handles it."""
    assert list_scenarios(tmp_path) == []


def test_list_scenarios_nonexistent_dir_returns_empty_list(tmp_path):
    assert list_scenarios(tmp_path / "nonexistent") == []


# ---------------------------------------------------------------------------
# Integration tests — launch a real browser
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_dashboard_pipeline_quantity_scenario_detects_bug(tmp_path):
    """End-to-end: quantity scenario produces expected=$36.00, actual=$18.00."""
    settings = load_settings()
    scenario = load_scenario_by_id("cart-total-quantity", settings.scenarios_dir)
    result = run_scenario(
        scenario,
        settings,
        app_factory=create_app,
        screenshot_path=str(tmp_path / "qty.png"),
        minimize=False,
    )

    assert result.status == "bug_detected", result.error
    assert result.finding is not None
    assert result.finding.expected == "$36.00"
    assert result.finding.actual == "$18.00"
    assert result.screenshot is not None


@pytest.mark.integration
def test_dashboard_pipeline_remove_scenario_detects_bug(tmp_path):
    """End-to-end: remove scenario produces expected=$12.50, actual=$30.50."""
    settings = load_settings()
    scenario = load_scenario_by_id("cart-remove-total", settings.scenarios_dir)
    result = run_scenario(
        scenario,
        settings,
        app_factory=create_app,
        screenshot_path=str(tmp_path / "remove.png"),
        minimize=False,
    )

    assert result.status == "bug_detected", result.error
    assert result.finding is not None
    assert result.finding.expected == "$12.50"
    assert result.finding.actual == "$30.50"
    assert result.screenshot is not None


@pytest.mark.integration
def test_dashboard_pipeline_run_scenario_records_action_history(tmp_path):
    """The action log the dashboard displays must match the scenario steps."""
    settings = load_settings()
    scenario = load_scenario_by_id("cart-remove-total", settings.scenarios_dir)
    result = run_scenario(
        scenario,
        settings,
        app_factory=create_app,
        minimize=False,
    )

    action_types = [a.action for a in result.actions]
    assert action_types == ["open", "click", "click", "click"]


@pytest.mark.integration
def test_dashboard_pipeline_replay_produces_same_finding(tmp_path):
    """The dashboard's replay verification must confirm the same signature."""
    settings = load_settings()
    scenario = load_scenario_by_id("cart-total-quantity", settings.scenarios_dir)

    first = run_scenario(scenario, settings, app_factory=create_app, minimize=False)
    replay = run_scenario(scenario, settings, app_factory=create_app, minimize=False)

    assert first.finding is not None
    assert replay.finding is not None
    assert first.finding.signature() == replay.finding.signature()
