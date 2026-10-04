import analysis


def test_a_strong_company_is_a_strong_buy():
    green, red = analysis.flags({"revenue_growth": .2, "earnings_growth": .3, "margin": .3,
                                 "free_cash": 1e9, "debt_equity": 20, "upside": 25, "rating": 1.8})
    assert not red and len(green) == 6              # the analysts count once, not twice
    assert analysis.call(len(green) - len(red)) == ("STRONG BUY", "BUY")


def test_a_weak_company_is_avoided_and_says_why():
    green, red = analysis.flags({"revenue_growth": -.1, "margin": -.2, "free_cash": -5,
                                 "debt_equity": 300, "pe": 90})
    assert not green and any("debt" in r for r in red)
    assert analysis.call(len(green) - len(red))[0] == "AVOID"


def test_missing_numbers_are_no_flags():
    assert analysis.flags({}) == ([], [])
    assert analysis.call(0) == ("HOLD", "HOLD")


def test_a_price_above_the_analysts_target_can_never_be_a_strong_buy():
    n = {"revenue_growth": .2, "earnings_growth": .3, "margin": .3, "free_cash": 1e9, "debt_equity": 20,
         "rating": 1.4, "upside": -2.3, "price": 250, "avg200": 200, "pe": 15, "forward_pe": 10}
    green, red = analysis.flags(n)
    assert analysis.call(len(green) - len(red))[0] == "STRONG BUY"           # the tally alone would have said so
    words, tone, why = analysis.verdict(len(green) - len(red), n)
    assert (words, tone) == ("HOLD", "HOLD") and "above the analysts' target" in why[0]


def test_an_extreme_price_holds_a_buy_at_buy_and_a_downtrend_is_a_red_flag():
    n = {"revenue_growth": .5, "earnings_growth": .5, "margin": .3, "free_cash": 1, "debt_equity": 10, "rating": 1.5,
         "upside": 20, "price": 100, "avg200": 90, "pe": 160, "forward_pe": 70}
    green, red = analysis.flags(n)
    words, _tone, why = analysis.verdict(len(green) - len(red), n)
    assert words in ("GOOD", "DECENT", "HOLD") and why
    _g, r = analysis.flags({"price": 80, "avg200": 100})
    assert any("Downtrend" in x for x in r)


def test_the_analysts_never_count_twice():
    g, _r = analysis.flags({"rating": 1.2, "upside": 40})
    assert len(g) == 1 and "rating 1.2" in g[0] and "target 40%" in g[0]


def test_six_grades_from_the_score():
    got = [analysis.call(s)[0] for s in (7, 6, 5, 4, 3, 2, 1, 0, -1, -2, -3)]
    assert got == ["STRONG BUY", "STRONG BUY", "GOOD", "GOOD", "DECENT", "DECENT", "HOLD", "HOLD",
                   "WEAK", "WEAK", "AVOID"]
