"""Load and validate scenario JSON files.

Validation happens at load time so a typo fails immediately with the field name,
never halfway through a browser run.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from bugsafari.detection.rules import available_rule_ids
from bugsafari.scenarios.model import (
    ACTIONS_REQUIRING_TARGET,
    ACTIONS_REQUIRING_VALUE,
    SUPPORTED_ACTIONS,
    TARGET_KINDS,
    InvariantSpec,
    Scenario,
    Step,
    TargetSpec,
)

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_TOP_LEVEL_KEYS = {"id", "name", "description", "target", "steps", "capture", "invariants"}
_STEP_KEYS = {"action", "target", "value", "label"}
_INVARIANT_KEYS = {"rule", "params"}
_TARGET_KEYS = {"kind", "url"}


class ScenarioError(ValueError):
    """A scenario file is missing, unreadable, or invalid."""


def load_scenario(path: str | Path) -> Scenario:
    """Read and validate a single scenario file."""
    source = Path(path)
    try:
        raw = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise ScenarioError(f"{source}: cannot read scenario ({exc})") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ScenarioError(
            f"{source}: invalid JSON at line {exc.lineno} column {exc.colno}: {exc.msg}"
        ) from exc
    return parse_scenario(data, source=source)


def parse_scenario(data: Any, source: Path | None = None) -> Scenario:
    """Validate an already decoded scenario document."""
    origin = str(source) if source is not None else "<scenario>"
    if not isinstance(data, dict):
        _fail(origin, "top level must be a JSON object")

    _reject_unknown(origin, data, _TOP_LEVEL_KEYS, "top level")

    scenario_id = _required_text(origin, data, "id")
    if not ID_PATTERN.match(scenario_id):
        _fail(origin, f"'id' must match {ID_PATTERN.pattern}; got {scenario_id!r}")
    name = _required_text(origin, data, "name")
    description = _optional_text(origin, data, "description", "")

    target = _parse_target(origin, data.get("target"))
    steps = _parse_steps(origin, data.get("steps"))
    capture = _parse_capture(origin, data.get("capture"))
    invariants = _parse_invariants(origin, data.get("invariants"))

    return Scenario(
        id=scenario_id,
        name=name,
        description=description,
        target=target,
        steps=steps,
        capture=capture,
        invariants=invariants,
        source=source,
    )


def list_scenario_files(scenarios_dir: str | Path) -> list[Path]:
    """Return every ``*.json`` scenario path, sorted for stable output."""
    directory = Path(scenarios_dir)
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.glob("*.json") if path.is_file())


def load_scenario_by_id(scenario_id: str, scenarios_dir: str | Path) -> Scenario:
    """Resolve a scenario id to a file inside ``scenarios_dir``."""
    path = Path(scenarios_dir) / f"{scenario_id}.json"
    if not path.is_file():
        available = ", ".join(path.stem for path in list_scenario_files(scenarios_dir)) or "none"
        raise ScenarioError(f"unknown scenario {scenario_id!r}; available: {available}")
    return load_scenario(path)


def list_scenarios(scenarios_dir: str | Path) -> list[Scenario]:
    """Load every scenario, surfacing the first invalid file as an error."""
    return [load_scenario(path) for path in list_scenario_files(scenarios_dir)]


def _parse_target(origin: str, raw: Any) -> TargetSpec:
    if raw is None:
        return TargetSpec()
    if not isinstance(raw, dict):
        _fail(origin, "'target' must be an object")
    _reject_unknown(origin, raw, _TARGET_KEYS, "'target'")
    kind = _optional_text(origin, raw, "kind", "local_demo")
    if kind not in TARGET_KINDS:
        _fail(origin, f"'target.kind' must be one of {', '.join(TARGET_KINDS)}; got {kind!r}")
    url = _optional_text(origin, raw, "url", "") or None
    if kind == "url" and not url:
        _fail(origin, "'target.url' is required when 'target.kind' is 'url'")
    return TargetSpec(kind=kind, url=url)


def _parse_steps(origin: str, raw: Any) -> tuple[Step, ...]:
    if not isinstance(raw, list) or not raw:
        _fail(origin, "'steps' must be a non-empty array")
    steps: list[Step] = []
    for index, item in enumerate(raw):
        where = f"'steps[{index}]'"
        if not isinstance(item, dict):
            _fail(origin, f"{where} must be an object")
        _reject_unknown(origin, item, _STEP_KEYS, where)
        action = _required_text(origin, item, "action", where)
        if action not in SUPPORTED_ACTIONS:
            supported = ", ".join(sorted(SUPPORTED_ACTIONS))
            _fail(origin, f"{where}.action {action!r} is not supported; use one of: {supported}")

        target = _optional_text(origin, item, "target", "") or None
        if action in ACTIONS_REQUIRING_TARGET and not target:
            _fail(origin, f"{where}.target is required for action {action!r}")

        value = item.get("value")
        if value is not None and not isinstance(value, (str, int, float)):
            _fail(origin, f"{where}.value must be a string or number")
        value_text = None if value is None else str(value)
        if action in ACTIONS_REQUIRING_VALUE and not value_text:
            _fail(origin, f"{where}.value is required for action {action!r}")

        steps.append(
            Step(
                action=action,
                target=target,
                value=value_text,
                label=_optional_text(origin, item, "label", "") or None,
            )
        )
    return tuple(steps)


def _parse_capture(origin: str, raw: Any) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        _fail(origin, "'capture' must be an array of test ids")
    captured: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, str) or not item.strip():
            _fail(origin, f"'capture[{index}]' must be a non-empty string")
        captured.append(item.strip())
    return tuple(dict.fromkeys(captured))


def _parse_invariants(origin: str, raw: Any) -> tuple[InvariantSpec, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        _fail(origin, "'invariants' must be an array")
    known = available_rule_ids()
    specs: list[InvariantSpec] = []
    for index, item in enumerate(raw):
        where = f"'invariants[{index}]'"
        if not isinstance(item, dict):
            _fail(origin, f"{where} must be an object")
        _reject_unknown(origin, item, _INVARIANT_KEYS, where)
        rule_id = _required_text(origin, item, "rule", where)
        if rule_id not in known:
            _fail(origin, f"{where}.rule {rule_id!r} is unknown; available: {', '.join(known)}")
        params = item.get("params", {})
        if not isinstance(params, dict):
            _fail(origin, f"{where}.params must be an object")
        specs.append(InvariantSpec(rule=rule_id, params=dict(params)))
    return tuple(specs)


def _required_text(origin: str, data: dict[str, Any], key: str, where: str = "") -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        location = f"{where}." if where else ""
        _fail(origin, f"'{location}{key}' is required and must be a non-empty string")
    return value.strip()


def _optional_text(
    origin: str, data: dict[str, Any], key: str, default: str, where: str = ""
) -> str:
    value = data.get(key)
    if value is None:
        return default
    if not isinstance(value, str):
        location = f"{where}." if where else ""
        _fail(origin, f"'{location}{key}' must be a string")
    return value.strip() or default


def _reject_unknown(
    origin: str, data: dict[str, Any], allowed: set[str], where: str
) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        _fail(origin, f"{where} has unknown field(s): {', '.join(unknown)}")


def _fail(origin: str, message: str) -> None:
    raise ScenarioError(f"{origin}: {message}")
