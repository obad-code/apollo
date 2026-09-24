"""What the people who run your companies are doing with their own shares:
open-market buys and sells, from Finnhub's copy of the SEC's Form 4 filings.
Tax withholding, option exercises, gifts and awards are routine, not a
signal, and are left out."""
import datetime

import pytest

import briefing
import dataservice
import insiders
import tools
import watchlist
from tools import Context

TODAY = datetime.date(2026, 9, 25)


def row(name, code, change, price, day, filed=None):
    return {"name": name, "transactionCode": code, "change": change, "share": 1000,
            "transactionPrice": price, "transactionDate": day, "filingDate": filed or day,
            "symbol": "NVDA", "isDerivative": False}


ROWS = [
    row("STEVENS MARK A", "S", -565615, 210.44, "2026-09-18", "2026-09-22"),
    row("STEVENS MARK A", "S", -319385, 209.70, "2026-09-18", "2026-09-22"),
    row("KRESS COLETTE", "F", -40746, 207.41, "2026-09-17"),          # tax: left out
    row("HUANG JEN HSUN", "P", 10000, 200.00, "2026-09-10"),
    row("PURI AJAY K", "M", 36927, 0.0, "2026-09-17"),                 # exercise: left out
    row("OLD SELLER", "S", -1000, 100.0, "2026-03-01"),                # too long ago
]


def test_buys_and_sells_are_totalled_and_the_rest_left_out():
    s = insiders.summary("NVDA", ROWS, today=TODAY, days=90)
    assert s["sells"]["count"] == 1                      # two lots, one sale
    assert s["sells"]["shares"] == 565615 + 319385
    assert s["sells"]["value"] == pytest.approx(565615 * 210.44 + 319385 * 209.70)
    assert s["buys"] == {"count": 1, "shares": 10000, "value": 2_000_000.0}
    assert s["recent_buy"] is True


def test_the_latest_come_first_with_names_a_person_would_write():
    s = insiders.summary("NVDA", ROWS, today=TODAY, days=90)
    first = s["latest"][0]
    assert first["name"] == "Mark A Stevens" and first["side"] == "sell"
    assert first["date"] == "2026-09-18" and first["filed"] == "2026-09-22"
    assert [t["side"] for t in s["latest"]] == ["sell", "buy"]


def test_a_quiet_stock_is_an_honest_zero():
    s = insiders.summary("NVDA", [], today=TODAY)
    assert s["buys"]["count"] == 0 and s["sells"]["count"] == 0 and s["latest"] == []


def test_no_key_no_request():
    def fetch(symbol, key, since):
        raise AssertionError("asked Finnhub without a key")
    assert insiders.for_watchlist(["NVDA"], key=None, fetch=fetch) == {}


def test_a_stock_finnhub_will_not_answer_for_is_skipped():
    def fetch(symbol, key, since):
        if symbol == "AAPL":
            raise OSError("down")
        return ROWS
    got = insiders.for_watchlist(["AAPL", "NVDA", "2222.SR"], key="k", fetch=fetch, today=TODAY)
    assert list(got) == ["NVDA"]                        # Tadawul is not covered either


def test_notable_trades_are_the_big_recent_ones():
    def fetch(symbol, key, since):
        return ROWS
    got = insiders.notable(["NVDA"], key="k", fetch=fetch, today=TODAY, days=5, least=1_000_000)
    assert [(t["symbol"], t["side"]) for t in got] == [("NVDA", "sell")]


def test_asked_out_loud(monkeypatch):
    monkeypatch.setattr(tools.market, "resolve", lambda text: "NVDA")
    monkeypatch.setattr(insiders, "api_key", lambda: "k")
    monkeypatch.setattr(insiders, "fetch", lambda symbol, key, since: ROWS)
    monkeypatch.setattr(insiders, "_today", lambda: TODAY)
    result = tools.run("insider_trades", {"company": "Nvidia"}, Context())
    assert result["ok"] is True and result["symbol"] == "NVDA"
    assert result["sold"]["count"] == 1 and result["bought"]["count"] == 1
    assert result["latest"][0]["name"] == "Mark A Stevens"


def test_the_display_is_given_them(monkeypatch, tmp_path):
    monkeypatch.setattr(watchlist, "PATH", str(tmp_path / "w.json"))
    watchlist._memo = None
    monkeypatch.setattr(insiders, "api_key", lambda: "k")
    monkeypatch.setattr(insiders, "fetch", lambda symbol, key, since: ROWS if symbol == "NVDA" else [])
    service = dataservice.DataService()
    assert service._read_insiders() is True
    assert service.snapshot["insiders"]["NVDA"]["sells"]["count"] == 1


def test_the_briefing_mentions_a_big_insider_trade(monkeypatch, tmp_path):
    monkeypatch.setattr(watchlist, "PATH", str(tmp_path / "w.json"))
    watchlist._memo = None
    monkeypatch.setattr(briefing.feeds, "headlines", lambda topic, limit=5: [])
    monkeypatch.setattr(briefing.feeds, "posts", lambda hours=24, limit=5: [])
    monkeypatch.setattr(briefing.weather, "now", lambda: {})
    monkeypatch.setattr(briefing.market, "market_status", lambda now=None: {"label": ""})
    monkeypatch.setattr(briefing.market, "quote", lambda s: (_ for _ in ()).throw(OSError()))
    monkeypatch.setattr(briefing.market, "fundamentals", lambda s, timeout=None: {})
    monkeypatch.setattr(briefing.insiders, "notable", lambda symbols, **kw: [
        {"symbol": "NVDA", "name": "Mark A Stevens", "side": "sell", "value": 186e6,
         "shares": 885000, "date": "2026-09-18", "filed": "2026-09-22"}])
    said = briefing.spoken(briefing.compose(now=datetime.datetime(2026, 9, 25, 8)))
    assert "Mark A Stevens" in said and "sold" in said
