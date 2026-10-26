from bugsafari.engine.explorer import run_demo_exploration


def test_seeded_quantity_bug_is_detected_with_action_history(tmp_path):
    result = run_demo_exploration(str(tmp_path / "seeded-bug.png"))
    assert result.status == "bug_detected", result.error
    assert result.finding is not None
    assert result.finding.expected == "$36.00"
    assert result.finding.actual == "$18.00"
    assert [action.action for action in result.finding.reproduction_steps] == ["open", "click", "fill"]
    assert result.screenshot is not None
