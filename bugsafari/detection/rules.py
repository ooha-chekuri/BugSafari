"""Named invariant rules, each a pure function of a captured :class:`Snapshot`.

No rule touches a live page, so the entire detection layer is unit-testable in
milliseconds and can be replayed cheaply during failure minimization.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from bugsafari.detection.invariants import RuleError, format_money, parse_money
from bugsafari.reporting.models import ActionRecord, Finding, Snapshot

RuleCheck = Callable[[Snapshot, dict[str, Any]], "Finding | None"]


@dataclass(frozen=True)
class Rule:
    id: str
    description: str
    check: RuleCheck


_REGISTRY: dict[str, Rule] = {}


def rule(rule_id: str, description: str) -> Callable[[RuleCheck], RuleCheck]:
    """Register a check under a stable id used by scenario files."""

    def decorator(check: RuleCheck) -> RuleCheck:
        if rule_id in _REGISTRY:
            raise RuntimeError(f"duplicate rule id: {rule_id}")
        _REGISTRY[rule_id] = Rule(rule_id, description, check)
        return check

    return decorator


def available_rule_ids() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


def get_rule(rule_id: str) -> Rule:
    try:
        return _REGISTRY[rule_id]
    except KeyError as exc:
        known = ", ".join(available_rule_ids())
        raise RuleError(f"unknown rule {rule_id!r}; known rules: {known}") from exc


def _cents(snapshot: Snapshot, test_id: str, label: str | None = None) -> int:
    if test_id not in snapshot.texts:
        raise RuleError(f"observation {label or test_id!r} was not captured")
    value = parse_money(snapshot.texts[test_id])
    if value is None:
        raise RuleError(
            f"observation {label or test_id!r} is not a money amount: "
            f"{snapshot.texts[test_id]!r}"
        )
    return value


def _finding(
    rule_id: str,
    expected: int,
    actual: int,
    details: str,
    severity: str = "major",
) -> Finding:
    return Finding(
        rule=rule_id,
        expected=format_money(expected),
        actual=format_money(actual),
        reproduction_steps=[],
        details=details,
        severity=severity,
    )


@rule(
    "total_equals_sum_of_line_totals",
    "The displayed total equals the sum of the visible line totals.",
)
def total_equals_sum_of_line_totals(
    snapshot: Snapshot, params: dict[str, Any]
) -> Finding | None:
    if not snapshot.cart:
        return None
    total = _cents(snapshot, "total")
    line_sum = 0
    for item_id in snapshot.cart:
        if item_id not in snapshot.line_totals:
            raise RuleError(f"line total for {item_id!r} was not captured")
        raw = parse_money(snapshot.line_totals[item_id])
        if raw is None:
            raise RuleError(f"line total for {item_id!r} is not money: {snapshot.line_totals[item_id]!r}")
        line_sum += raw
    if line_sum == total:
        return None
    return _finding(
        "total_equals_sum_of_line_totals",
        line_sum,
        total,
        "The cart total does not equal the sum of the visible line totals. "
        "Aggregate totals were not recalculated after a cart change.",
    )


@rule(
    "cart_total_matches_quantities",
    "The displayed total equals the sum of catalog price times quantity.",
)
def cart_total_matches_quantities(snapshot: Snapshot, params: dict[str, Any]) -> Finding | None:
    total = _cents(snapshot, "total")
    expected = 0
    for item_id, quantity in snapshot.cart.items():
        item = snapshot.catalog.get(item_id)
        if item is None:
            raise RuleError(f"cart contains unknown product {item_id!r}")
        expected += item.price_cents * quantity
    if expected == total:
        return None
    return _finding(
        "cart_total_matches_quantities",
        expected,
        total,
        "Displayed cart total does not equal the sum of product prices times quantities.",
    )


@rule(
    "line_total_matches_price_x_qty",
    "Each visible line total equals that product's price times its quantity.",
)
def line_total_matches_price_x_qty(snapshot: Snapshot, params: dict[str, Any]) -> Finding | None:
    for item_id, quantity in snapshot.cart.items():
        item = snapshot.catalog.get(item_id)
        if item is None:
            raise RuleError(f"cart contains unknown product {item_id!r}")
        if item_id not in snapshot.line_totals:
            raise RuleError(f"line total for {item_id!r} was not captured")
        actual = parse_money(snapshot.line_totals[item_id])
        if actual is None:
            raise RuleError(f"line total for {item_id!r} is not money")
        expected = item.price_cents * quantity
        if expected != actual:
            finding = _finding(
                "line_total_matches_price_x_qty",
                expected,
                actual,
                f"Line total for {item.name!r} does not match price x quantity.",
            )
            finding.details += f" Product id: {item_id}."
            return finding
    return None


@rule("subtotal_equals_total", "The subtotal and the total agree.")
def subtotal_equals_total(snapshot: Snapshot, params: dict[str, Any]) -> Finding | None:
    subtotal = _cents(snapshot, "subtotal")
    total = _cents(snapshot, "total")
    if subtotal == total:
        return None
    return _finding(
        "subtotal_equals_total",
        subtotal,
        total,
        "The subtotal and total disagree on the same cart.",
    )


@rule("checkout_total_equals_total", "The checkout summary agrees with the cart total.")
def checkout_total_equals_total(snapshot: Snapshot, params: dict[str, Any]) -> Finding | None:
    total = _cents(snapshot, "total")
    checkout = _cents(snapshot, "checkout-total")
    if checkout == total:
        return None
    return _finding(
        "checkout_total_equals_total",
        total,
        checkout,
        "The checkout summary total disagrees with the cart total.",
    )


@rule("cart_empty_has_zero_total", "An empty cart shows a zero total.")
def cart_empty_has_zero_total(snapshot: Snapshot, params: dict[str, Any]) -> Finding | None:
    if snapshot.cart:
        return None
    total = _cents(snapshot, "total")
    if total == 0:
        return None
    return _finding(
        "cart_empty_has_zero_total",
        0,
        total,
        "The cart is empty but the displayed total is not zero.",
    )


def attach_reproduction(finding: Finding, actions: Iterable[ActionRecord]) -> Finding:
    finding.reproduction_steps = list(actions)
    return finding
