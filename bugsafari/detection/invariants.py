"""Explicit cart invariants; no language model is involved.

The money helpers live in :mod:`bugsafari.money` and are re-exported here so
existing imports keep working.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from bugsafari.money import format_money, parse_money
from bugsafari.reporting.models import ActionRecord, Finding


class RuleError(ValueError):
    """A rule could not be evaluated because an observation was missing or malformed.

    This is *never* evidence of a product defect: it means the run cannot make a
    claim either way, so callers must report an execution error.
    """


def check_cart_total(
    displayed_total: str,
    prices_cents: Mapping[str, int],
    quantities: Mapping[str, int],
    actions: Sequence[ActionRecord],
) -> Finding | None:
    """Return a confirmed finding when the visible total differs from the expected one.

    Kept as a stable, directly testable API; the rule registry in
    :mod:`bugsafari.detection.rules` is the primary path.
    """
    unknown = sorted(set(quantities) - set(prices_cents))
    if unknown:
        raise RuleError(f"no known price for cart item(s): {', '.join(unknown)}")
    actual_cents = parse_money(displayed_total)
    if actual_cents is None:
        raise RuleError(f"displayed total is not a money amount: {displayed_total!r}")
    expected_cents = sum(prices_cents[item] * quantity for item, quantity in quantities.items())
    if expected_cents == actual_cents:
        return None
    return Finding(
        rule="cart_total_matches_quantities",
        expected=format_money(expected_cents),
        actual=format_money(actual_cents),
        reproduction_steps=list(actions),
        details="Displayed cart total does not equal the sum of product prices times quantities.",
    )


__all__ = ["RuleError", "check_cart_total", "format_money", "parse_money"]
