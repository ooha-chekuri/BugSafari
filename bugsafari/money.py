"""Money parsing and formatting shared by the browser and detection layers.

Kept in a neutral module so neither layer has to import the other.
"""

from __future__ import annotations

import re

_MONEY_PATTERN = re.compile(
    r"(?<![\d.])(?P<sign>-)?\s*\$?\s*(?P<dollars>\d[\d,]*)(?:\.(?P<cents>\d{1,2}))?"
)


def parse_money(value: str | None) -> int | None:
    """Convert a displayed amount to integer cents.

    Tolerates surrounding text (``"Total due: $18.00"``), thousands separators,
    and one- or two-digit fractions. Returns ``None`` for anything that is not a
    non-negative money amount instead of raising.
    """
    if not isinstance(value, str):
        return None
    match = None
    for match in _MONEY_PATTERN.finditer(value):
        pass
    if match is None or match.group("sign"):
        return None
    dollars = int(match.group("dollars").replace(",", ""))
    fraction = (match.group("cents") or "").ljust(2, "0")[:2]
    return dollars * 100 + int(fraction)


def format_money(cents: int) -> str:
    """Format integer cents as a USD display value."""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}${cents // 100}.{cents % 100:02d}"
