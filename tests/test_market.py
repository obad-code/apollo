import json
import os
from datetime import datetime

import pytest

import market

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture(name):
    with open(os.path.join(FIX, name + ".json"), encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    market._cache.clear()
    calls = []

    def fake_get(path, ttl):
        calls.append(path)
        if "/chart/NVDA" in path:
            return fixture("chart_nvda_5d")
        if "/chart/%5EGSPC" in path:
            return fixture("chart_gspc_1d")
        if "/search" in path:
            return fixture("search_nvidia")
        raise market.MarketError("no fixture")
    monkeypatch.setattr(market, "_get_json", fake_get)
    return calls


def test_parse_chart_reads_price_change_and_points():
    d = market.parse_chart(fixture("chart_nvda_5d"))
    assert d["symbol"] == "NVDA" and d["currency"] == "USD"
    assert d["price"] > 0 and d["previous_close"] > 0
    assert d["change"] == pytest.approx(d["price"] - d["previous_close"])
    assert len(d["points"]) > 10 and all(c is not None for _, c in d["points"])


def test_parse_chart_error_payload():
    with pytest.raises(market.MarketError):
        market.parse_chart({"chart": {"result": None, "error": {"description": "No data found"}}})


def test_resolve():
    assert market.resolve("Nvidia") == "NVDA"
    assert market.resolve("the S&P 500") == "^GSPC"
    assert market.resolve("إنفيديا") == "NVDA"
    assert market.resolve("TSLA") == "TSLA"
    assert market.resolve("nvidia corp") == "NVDA"          # via search fixture


def test_history_downsamples_to_64():
    d = market.history("NVDA", "5d")
    assert len(d["points"]) <= 64
    assert d["points"][-1] == market.parse_chart(fixture("chart_nvda_5d"))["points"][-1]


def test_downsample_keeps_ends():
    pts = [(i, float(i)) for i in range(200)]
    out = market.downsample(pts, 64)
    assert len(out) == 64 and out[0] == pts[0] and out[-1] == pts[-1]


def test_market_status_weekday_and_weekend():
    from zoneinfo import ZoneInfo
    ny = ZoneInfo("America/New_York")
    wed_noon = datetime(2026, 9, 16, 12, 0, tzinfo=ny)
    s = market.market_status(wed_noon)
    assert s["open"] is True and s["label"] == "NYSE closes in 4h 00m"
    sat = datetime(2026, 9, 19, 14, 0, tzinfo=ny)
    s = market.market_status(sat)
    assert s["open"] is False and s["next"].weekday() == 0 and s["label"].startswith("NYSE opens in")


def test_tradingview():
    assert market.tradingview_symbol("NVDA", "NMS") == "NASDAQ:NVDA"
    assert market.tradingview_symbol("^GSPC") == "SP:SPX"
    assert market.tradingview_symbol("2222.SR") == "TADAWUL:2222"
    assert market.tradingview_url("NVDA", "NMS") == "https://www.tradingview.com/chart/?symbol=NASDAQ%3ANVDA"


def test_visual_for_builds_chart_and_cards():
    v = market.visual_for(market.history("NVDA", "5d"), "5d")
    assert v["chart"]["label"] == "NVDA · 5D" and len(v["chart"]["points"]) >= 4
    assert [c["label"] for c in v["cards"]] == ["LAST", "5D", "HIGH", "LOW"]


def test_both_hosts_down_raises_market_error(monkeypatch):
    monkeypatch.undo()
    market._cache.clear()

    def refuse(url):
        raise OSError("offline")
    monkeypatch.setattr(market, "_open", refuse)
    with pytest.raises(market.MarketError):
        market.quote("NVDA")
