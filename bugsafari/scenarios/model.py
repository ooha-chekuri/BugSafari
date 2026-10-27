"""Scenario data model: a run described entirely as data."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ACTIONS_REQUIRING_TARGET = frozenset(
    {"click", "fill", "change_quantity", "press", "select", "wait_visible", "read"}
)
ACTIONS_REQUIRING_VALUE = frozenset({"fill", "change_quantity", "press", "select"})
SUPPORTED_ACTIONS = frozenset({"open", *ACTIONS_REQUIRING_TARGET})
TARGET_KINDS = ("local_demo", "url")


@dataclass(frozen=True)
class Step:
    """One browser interaction, independent of any selector implementation."""

    action: str
    target: str | None = None
    value: str | None = None
    label: str | None = None

    def describe(self) -> str:
        parts = [self.action]
        if self.target:
            parts.append(self.target)
        if self.value is not None:
            parts.append(f"= {self.value}")
        return " ".join(parts)


@dataclass(frozen=True)
class InvariantSpec:
    """A named rule plus optional parameters, evaluated against a snapshot."""

    rule: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TargetSpec:
    """Where the run points: the bundled demo or an already running site."""

    kind: str = "local_demo"
    url: str | None = None


@dataclass(frozen=True)
class Scenario:
    """A validated, immutable scenario definition."""

    id: str
    name: str
    description: str
    target: TargetSpec
    steps: tuple[Step, ...]
    capture: tuple[str, ...] = ()
    invariants: tuple[InvariantSpec, ...] = ()
    source: Path | None = None

    def step_actions(self) -> list[str]:
        return [step.action for step in self.steps]
