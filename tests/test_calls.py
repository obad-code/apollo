import datetime as dt

import calls


def test_calls_are_graded_once_at_a_week_and_a_month(tmp_path):
    path = str(tmp_path / "calls.json")
    day0 = dt.datetime(2026, 9, 1, 10)
    assert calls.record("NVDA", "STRONG BUY", 100, when=day0, path=path)
    assert not calls.record("NVDA", "BUY", 101, when=day0, path=path)          # once a day
    assert calls.record("TSLA", "AVOID", 200, when=day0, path=path)
    assert calls.record("AAPL", "HOLD", 50, when=day0, path=path)
    prices = {"NVDA": 110, "TSLA": 210, "AAPL": 51}
    calls.grade(dt.date(2026, 9, 9), price=prices.get, path=path)
    card = calls.scorecard(path=path)
    assert card["marks"][7] == {"calls": 3, "right": 2, "rate": 67}
    assert card["marks"][30]["calls"] == 0
    prices["NVDA"] = 1                                                          # never re-graded
    calls.grade(dt.date(2026, 9, 10), price=prices.get, path=path)
    assert calls.scorecard(path=path)["marks"][7]["right"] == 2


def test_a_call_with_no_price_or_verdict_is_not_kept(tmp_path):
    path = str(tmp_path / "c.json")
    assert not calls.record("NVDA", "", 10, path=path)
    assert not calls.record("NVDA", "BUY", None, path=path)


def test_a_wrong_call_gets_a_post_mortem_and_its_lesson_reaches_the_next_call(tmp_path):
    path = str(tmp_path / "calls.json")
    calls.record("AMD", "STRONG BUY", 100, when=dt.datetime(2026, 9, 1), path=path)
    calls.record("NVDA", "BUY", 100, when=dt.datetime(2026, 9, 1), path=path)
    calls.grade(dt.date(2026, 9, 9), price={"AMD": 90, "NVDA": 110}.get, path=path)
    asked = []
    n = calls.review(think=lambda p: asked.append(p) or "WHAT HAPPENED: fell 10%.\nWHAT I MISSED: it was above target.\n"
                     "LESSON: Never STRONG BUY above the analysts' target.", path=path)
    assert n == 1 and "AMD" in asked[0]                          # only the wrong one
    assert calls.review(think=lambda p: 1 / 0, path=path) == 0   # never twice
    assert "Never STRONG BUY above" in calls.lessons_prompt(path=path)
