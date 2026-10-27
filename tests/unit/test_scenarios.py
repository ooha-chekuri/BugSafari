"""Scenario loading and validation."""

import json
from pathlib import Path

import pytest

from bugsafari.scenarios.loader import (
    ScenarioError,
    list_scenario_files,
    load_scenario,
    load_scenario_by_id,
    parse_scenario,
)

pytestmark = pytest.mark.unit

SCENARIO_DIR = Path(__file__).resolve().parents[2] / "scenarios"


def _valid_payload() -> dict:
    return {
        "id": "sample-check",
        "name": "Sample check",
        "description": "A minimal valid scenario.",
        "target": {"kind": "local_demo"},
        "steps": [
            {"action": "open"},
            {"action": "click", "target": "add-trail-mug"},
            {"action": "change_quantity", "target": "quantity-trail-mug", "value": "2"},
        ],
        "capture": ["total"],
        "invariants": [{"rule": "cart_total_matches_quantities"}],
    }


def test_bundled_scenarios_are_valid_and_unique():
    files = list_scenario_files(SCENARIO_DIR)
    assert files, "expected bundled scenario files"
    scenarios = [load_scenario(path) for path in files]
    ids = [scenario.id for scenario in scenarios]
    assert len(ids) == len(set(ids))
    assert "cart-total-quantity" in ids
    assert "cart-remove-total" in ids


def test_cart_scenario_describes_the_expected_run():
    scenario = load_scenario_by_id("cart-total-quantity", SCENARIO_DIR)
    assert scenario.step_actions() == ["open", "click", "change_quantity"]
    assert scenario.steps[2].target == "quantity-trail-mug"
    assert scenario.steps[2].value == "2"
    assert scenario.capture == ("total", "subtotal", "checkout-total")
    assert [spec.rule for spec in scenario.invariants] == [
        "total_equals_sum_of_line_totals",
        "cart_total_matches_quantities",
    ]
    assert scenario.source is not None


def test_cart_remove_scenario_describes_the_expected_run():
    scenario = load_scenario_by_id("cart-remove-total", SCENARIO_DIR)
    assert scenario.step_actions() == ["open", "click", "click", "click"]
    assert scenario.steps[3].target == "remove-trail-mug"
    assert scenario.capture == ("total", "subtotal", "checkout-total")
    assert [spec.rule for spec in scenario.invariants] == [
        "total_equals_sum_of_line_totals",
        "cart_total_matches_quantities",
        "checkout_total_equals_total",
    ]
    assert scenario.source is not None


def test_valid_payload_round_trips():
    scenario = parse_scenario(_valid_payload())
    assert scenario.id == "sample-check"
    assert scenario.target.kind == "local_demo"
    assert scenario.steps[1].label is None


def test_numeric_step_value_is_stringified():
    payload = _valid_payload()
    payload["steps"][2]["value"] = 2
    assert parse_scenario(payload).steps[2].value == "2"


@pytest.mark.parametrize(
    ("mutate", "needle"),
    [
        (lambda p: p.pop("name"), "name"),
        (lambda p: p.update({"id": "Not Valid"}), "must match"),
        (lambda p: p.update({"surprise": 1}), "unknown field"),
        (lambda p: p.update({"steps": []}), "non-empty array"),
        (lambda p: p["steps"][1].pop("target"), "target is required"),
        (lambda p: p["steps"][0].update({"action": "teleport"}), "not supported"),
        (lambda p: p["steps"][2].update({"value": ""}), "value is required"),
        (lambda p: p["invariants"][0].update({"rule": "unknown_rule"}), "unknown"),
        (lambda p: p.update({"target": {"kind": "url"}}), "target.url"),
        (lambda p: p.update({"capture": "total"}), "array"),
    ],
)
def test_invalid_scenarios_fail_with_the_offending_field(mutate, needle):
    payload = _valid_payload()
    mutate(payload)
    with pytest.raises(ScenarioError, match=needle):
        parse_scenario(payload)


def test_malformed_json_names_the_position(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text('{"id": "broken", }', encoding="utf-8")
    with pytest.raises(ScenarioError, match="invalid JSON at line 1"):
        load_scenario(path)


def test_unknown_scenario_lists_available_ids():
    with pytest.raises(ScenarioError, match="available: .*cart-total-quantity"):
        load_scenario_by_id("does-not-exist", SCENARIO_DIR)


def test_scenario_files_are_loadable_json():
    for path in list_scenario_files(SCENARIO_DIR):
        json.loads(path.read_text(encoding="utf-8"))
