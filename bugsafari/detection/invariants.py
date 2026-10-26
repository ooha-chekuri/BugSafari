"""Explicit cart invariants; no language model is involved in detection."""

from bugsafari.reporting.models import ActionRecord, Finding


def parse_money(value: str) -> int:
    """Convert a displayed dollar amount to integer cents."""
    cleaned = value.strip().replace("$", "").replace(",", "")
    dollars, _, cents = cleaned.partition(".")
    return int(dollars) * 100 + int((cents + "00")[:2])


def format_money(cents: int) -> str:
    """Format integer cents as a USD display value."""
    return f"${cents // 100}.{cents % 100:02d}"


def check_cart_total(displayed_total: str, prices_cents: dict[str, int],
                     quantities: dict[str, int], actions: list[ActionRecord]) -> Finding | None:
    """Return a confirmed finding when visible total differs from computed total."""
    expected_cents = sum(prices_cents[item] * quantities[item] for item in quantities)
    actual_cents = parse_money(displayed_total)
    if expected_cents == actual_cents:
        return None
    return Finding(rule="cart_total_matches_quantities", expected=format_money(expected_cents),
                   actual=format_money(actual_cents), reproduction_steps=list(actions),
                   details="Displayed cart total does not equal the sum of product prices times quantities.")
