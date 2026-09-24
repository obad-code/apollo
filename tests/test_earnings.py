"""When a stock next reports: on its card, in the opened stock, by voice,
and in the morning briefing when it is this week."""
import datetime

import pytest

import briefing
import market
import tools
import watchlist
from tools import Context

NOV_17 = 1794945600          # what Yahoo gave for Nvidia


def summary(*dates, estimate=False):
    return {"quoteSummary": {"result": [{
        "financialData": {}, "summaryDetail": {}, "defaultKeyStatistics": {},
        "calendarEvents": {"earnings": {
            "earningsDate": [{"raw": d} for d in dates],
            "isEarningsDateEstimate": estimate}}}]}}


@pytest.fixture(autouse=True)
def clear_cache():
    market._cache.clear()
    yield
    market._cache.clear()


def test_the_next_earnings_date_is_read(monkeypatch):
    monkeypatch.setattr(market, "_summary_json", lambda s, timeout=None: summary(NOV_17))
    data = market.fundamentals("NVDA")
    assert data["earnings"] == datetime.datetime.fromtimestamp(
        NOV_17, datetime.timezone.utc).date().isoformat()
    assert data["earnings_estimate"] is False


def test_a_range_gives_its_first_day_and_says_it_is_an_estimate(monkeypatch):
    monkeypatch.setattr(market, "_summary_json",
                        lambda s, timeout=None: summary(NOV_17, NOV_17 + 5 * 86400, estimate=True))
    data = market.fundamentals("NVDA")
    assert data["earnings"].startswith("2026-11-1")
    assert data["earnings_estimate"] is True


def test_no_date_is_a_gap_not_an_error(monkeypatch):
    monkeypatch.setattr(market, "_summary_json", lambda s, timeout=None: summary())
    assert market.fundamentals("NVDA")["earnings"] is None
    assert "earnings" in market.NO_FUNDAMENTALS


def test_asked_out_loud_it_says_when_and_how_long(monkeypatch):
    monkeypatch.setattr(tools.market, "resolve", lambda text: "NVDA")
    monkeypatch.setattr(tools.market, "fundamentals", lambda s, timeout=None: {
        "earnings": "2026-11-17", "earnings_estimate": False})
    result = tools.run("next_earnings", {"company": "Nvidia"},
                       Context(turn=0))
    assert result["ok"] is True and result["symbol"] == "NVDA"
    assert result["date"] == "2026-11-17"
    assert isinstance(result["days_away"], int)
    assert "weekday" in result


def test_no_date_known_is_said_plainly(monkeypatch):
    monkeypatch.setattr(tools.market, "resolve", lambda text: "PLTR")
    monkeypatch.setattr(tools.market, "fundamentals", lambda s, timeout=None: {"earnings": None})
    result = tools.run("next_earnings", {"company": "Palantir"}, Context())
    assert result["ok"] is False and "PLTR" in result["error"]


def test_the_briefing_mentions_a_stock_reporting_this_week(monkeypatch, tmp_path):
    monkeypatch.setattr(watchlist, "PATH", str(tmp_path / "w.json"))
    watchlist._memo = None
    monkeypatch.setattr(briefing.feeds, "headlines", lambda topic, limit=5: [])
    monkeypatch.setattr(briefing.feeds, "posts", lambda hours=24, limit=5: [])
    monkeypatch.setattr(briefing.weather, "now", lambda: {})
    monkeypatch.setattr(briefing.market, "market_status", lambda now=None: {"label": ""})
    monkeypatch.setattr(briefing.market, "quote", lambda s: {
        "symbol": s, "name": s, "price": 1.0, "change_pct": 0.0, "currency": "USD"})
    today = datetime.datetime(2026, 11, 14, 8, 0)
    dates = {"NVDA": "2026-11-17", "AAPL": "2027-01-29"}
    monkeypatch.setattr(briefing.market, "fundamentals",
                        lambda s, timeout=None: {"earnings": dates.get(s)})
    payload = briefing.compose(now=today)
    assert [(e["symbol"], e["days"]) for e in payload["earnings"]] == [("NVDA", 3)]
    said = briefing.spoken(payload)
    assert "NVDA" in said and "earnings" in said.lower()
