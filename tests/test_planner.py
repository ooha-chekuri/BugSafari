
from bugsafari.config import load_settings
from bugsafari.scenarios.loader import load_scenario_by_id
from bugsafari.engine.planner import SeededRandomPlanner

def test_seeded_random_planner_is_reproducible():
    settings = load_settings()
    scenario = load_scenario_by_id(
        "cart-total-quantity",
        settings.scenarios_dir,
    )

    first = SeededRandomPlanner(scenario, seed=42).plan()
    second = SeededRandomPlanner(scenario, seed=42).plan()

    assert first == second
    assert first[0].action == "open"
