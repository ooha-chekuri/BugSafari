
"""Bounded planners for selecting scenario actions."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Protocol

from bugsafari.scenarios.model import Scenario, Step, SUPPORTED_ACTIONS


@dataclass(frozen=True)
class Observation:
    """Minimal browser state available to a planner."""
    goal: str
    completed_steps: tuple[Step, ...]
    remaining_steps: tuple[Step, ...]
    last_result: str = ""


class Planner(Protocol):
    def next_step(self, observation: Observation) -> Step | None:
        """Choose the next supported step, or None to stop."""


class ScriptedPlanner:
    """Preserve the scenario's predefined action sequence."""

    def __init__(self, scenario: Scenario):
        self.steps = scenario.steps

    def next_step(self, observation: Observation) -> Step | None:
        if not observation.remaining_steps:
            return None
        return observation.remaining_steps[0]


class SeededRandomPlanner:
    """Explore the scenario's predefined steps in a reproducible order."""

    def __init__(self, scenario: Scenario, seed: int = 0):
        self.steps = list(scenario.steps)
        self.rng = random.Random(seed)

    def plan(self) -> list[Step]:
        # Keep navigation first; shuffle only the interactions.
        opening = [s for s in self.steps if s.action == "open"]
        interactions = [s for s in self.steps if s.action != "open"]
        self.rng.shuffle(interactions)
        planned = opening[:1] + interactions

        for step in planned:
            if step.action not in SUPPORTED_ACTIONS:
                raise ValueError(f"Unsupported planner action: {step.action}")
        return planned
