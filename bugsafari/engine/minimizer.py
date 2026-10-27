"""Greedy delta debugging: shrink a failing step list to a 1-minimal one.

The algorithm repeatedly tries to remove a single step, keeping the removal only
when the exact same finding (rule, expected, actual) still reproduces. It is
deliberately simple and bounded; every candidate is a real browser attempt, so
the budget matters more than asymptotics.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from time import monotonic

from bugsafari.reporting.models import Finding
from bugsafari.scenarios.model import Step

Reproducer = Callable[[tuple[Step, ...]], "Finding | None"]


@dataclass(frozen=True)
class MinimizeResult:
    original: tuple[Step, ...]
    minimized: tuple[Step, ...]
    attempts: int
    duration_s: float
    exhausted: bool = False

    @property
    def reduction(self) -> int:
        return len(self.original) - len(self.minimized)

    @property
    def changed(self) -> bool:
        return self.reduction > 0


def minimize_steps(
    steps: Sequence[Step],
    reproduce: Reproducer,
    target_signature: tuple[str, str, str],
    *,
    max_attempts: int = 40,
    timeout_s: float = 60.0,
) -> MinimizeResult:
    """Return a 1-minimal prefix-preserving sequence that still reproduces."""
    original = tuple(steps)
    current = list(original)
    attempts = 0
    started = monotonic()
    exhausted = False

    def reproduces(candidate: list[Step]) -> bool:
        nonlocal attempts
        if not candidate:
            return False
        if attempts >= max_attempts or monotonic() - started > timeout_s:
            return False
        attempts += 1
        finding = reproduce(tuple(candidate))
        return finding is not None and finding.signature() == target_signature

    changed = True
    while changed:
        changed = False
        for index in range(len(current)):
            if attempts >= max_attempts or monotonic() - started > timeout_s:
                exhausted = True
                break
            candidate = current[:index] + current[index + 1:]
            if reproduces(candidate):
                current = candidate
                changed = True
                break

    return MinimizeResult(
        original=original,
        minimized=tuple(current),
        attempts=attempts,
        duration_s=round(monotonic() - started, 3),
        exhausted=exhausted,
    )
