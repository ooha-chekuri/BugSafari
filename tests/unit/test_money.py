"""Money handling and the stable cart-total check."""

import pytest

from bugsafari.detection.invariants import (
    RuleError,
    check_cart_total,
    format_money,
    parse_money,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("text", "cents"),
    [
        ("$1,234.50", 123_450),
        ("$18.00", 1_800),
        ("$0.00", 0),
        ("18.5", 1_850),
        ("Total due: $36.00", 3_600),
        ("   $7.05  ", 705),
    ],
)
def test_parse_money_accepts_displayed_amounts(text, cents):
    assert parse_money(text) == cents


@pytest.mark.parametrize("text", ["", "$", "free", ".50", "-$5.00", None, 42])
def test_parse_money_returns_none_for_non_amounts(text):
    assert parse_money(text) is None


def test_format_money():
    assert format_money(3_050) == "$30.50"
    assert format_money(0) == "$0.00"
    assert format_money(123_450) == "$1234.50"
    assert format_money(-150) == "-$1.50"


def test_correct_cart_total_has_no_finding():
    assert check_cart_total(
        "$30.50", {"mug": 1800, "book": 1250}, {"mug": 1, "book": 1}, []
    ) is None


def test_cart_total_mismatch_returns_structured_finding():
    finding = check_cart_total("$18.00", {"mug": 1800}, {"mug": 2}, [])
    assert finding is not None
    assert finding.rule == "cart_total_matches_quantities"
    assert finding.expected == "$36.00"
    assert finding.actual == "$18.00"
    assert finding.status == "confirmed_violation"
    assert finding.signature() == ("cart_total_matches_quantities", "$36.00", "$18.00")


def test_unknown_cart_item_is_a_rule_error_not_a_finding():
    with pytest.raises(RuleError, match="no known price"):
        check_cart_total("$18.00", {"mug": 1800}, {"mug": 1, "ghost": 1}, [])


def test_malformed_total_is_a_rule_error_not_a_finding():
    with pytest.raises(RuleError, match="not a money amount"):
        check_cart_total("not money", {"mug": 1800}, {"mug": 1}, [])
