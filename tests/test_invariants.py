from bugsafari.detection.invariants import check_cart_total, format_money, parse_money


def test_money_and_correct_cart_total():
    assert parse_money("$1,234.50") == 123450
    assert format_money(3050) == "$30.50"
    assert check_cart_total("$30.50", {"mug": 1800, "book": 1250},
                            {"mug": 1, "book": 1}, []) is None


def test_cart_total_mismatch_returns_structured_finding():
    finding = check_cart_total("$18.00", {"mug": 1800}, {"mug": 2}, [])
    assert finding is not None
    assert finding.expected == "$36.00"
    assert finding.actual == "$18.00"
    assert finding.status == "confirmed_violation"
