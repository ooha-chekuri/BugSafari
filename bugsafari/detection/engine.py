"""Evaluate scenario invariants against a snapshot.

A rule that cannot evaluate is reported separately from a confirmed violation:
an unevaluable rule must never be presented as a bug.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from bugsafari.detection.invariants import RuleError
from bugsafari.detection.rules import get_rule
from bugsafari.reporting.models import ActionRecord, Finding, Snapshot

if TYPE_CHECKING:
    from bugsafari.scenarios.model import InvariantSpec


@dataclass
class Evaluation:
    findings: list[Finding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def confirmed(self) -> bool:
        return bool(self.findings)


def evaluate(
    snapshot: Snapshot,
    specs: tuple[InvariantSpec, ...] | list[InvariantSpec],
    actions: list[ActionRecord],
) -> Evaluation:
    """Run every invariant in order, collecting confirmed findings and errors."""
    evaluation = Evaluation()
    for spec in specs:
        try:
            check = get_rule(spec.rule).check
            finding = check(snapshot, spec.params)
        except RuleError as exc:
            evaluation.errors.append(f"{spec.rule}: {exc}")
            continue
        if finding is not None:
            finding.reproduction_steps = list(actions)
            evaluation.findings.append(finding)
    return evaluation
