
from bugsafari.config import load_settings
from bugsafari.engine.runner import run_scenario
from bugsafari.scenarios.loader import load_scenario_by_id
from demo_app.app import create_app


def test_seeded_remove_bug_is_detected_with_action_history(tmp_path):
    settings = load_settings()
    scenario = load_scenario_by_id("cart-remove-total", settings.scenarios_dir)
    result = run_scenario(
        scenario,
        settings,
        app_factory=create_app,
        screenshot_path=str(tmp_path / "remove-bug.png"),
    )

    assert result.status == "bug_detected", result.error
    assert result.finding is not None
    assert result.finding.expected == "$12.50"
    assert result.finding.actual == "$30.50"

    assert [
        action.action
        for action in result.finding.reproduction_steps
    ] == [
        "open",
        "click",
        "click",
        "click",
    ]

    assert result.screenshot is not None
