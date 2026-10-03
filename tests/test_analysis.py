import analysis


def test_a_strong_company_is_a_strong_buy():
    green, red = analysis.flags({"revenue_growth": .2, "earnings_growth": .3, "margin": .3,
                                 "free_cash": 1e9, "debt_equity": 20, "upside": 25, "rating": 1.8})
    assert not red and len(green) == 7
    assert analysis.call(len(green) - len(red)) == ("STRONG BUY", "BUY")


def test_a_weak_company_is_avoided_and_says_why():
    green, red = analysis.flags({"revenue_growth": -.1, "margin": -.2, "free_cash": -5,
                                 "debt_equity": 300, "pe": 90})
    assert not green and any("debt" in r for r in red)
    assert analysis.call(len(green) - len(red))[0] == "AVOID"


def test_missing_numbers_are_no_flags():
    assert analysis.flags({}) == ([], [])
    assert analysis.call(0) == ("HOLD", "HOLD")
