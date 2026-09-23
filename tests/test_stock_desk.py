"""The stocks on the display, under your own hands: open one for its chart
over a day, a week, a month or a year, take it off, put another on."""
import pytest

import apollo
import stockdesk
import watchlist


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(watchlist, "PATH", str(tmp_path / "watchlist.json"))
    watchlist._memo = None
    monkeypatch.setattr(watchlist.market, "resolve", lambda text: text.upper())


@pytest.fixture
def desk():
    pokes = []
    made = stockdesk.StockDesk(poke=lambda *keys: pokes.append(keys))
    made.pokes = pokes
    return made


def test_suggestions_are_the_ones_not_already_watched():
    offered = [s["symbol"] for s in stockdesk.suggestions()]
    assert offered, "nothing to offer"
    assert not set(offered) & set(watchlist.current())
    assert all(s["name"] for s in stockdesk.suggestions())


def test_one_taken_off_is_offered_back(desk):
    desk.unwatch("TSLA")
    assert "TSLA" in [s["symbol"] for s in stockdesk.suggestions()]


def test_adding_one_asks_for_its_card(desk):
    result = desk.watch("PLTR")
    assert result["ok"] is True and "PLTR" in watchlist.current()
    assert desk.pokes == [("market",)]


def test_adding_one_already_there_asks_for_nothing(desk):
    result = desk.watch("NVDA")
    assert result["ok"] is True and result.get("already")
    assert desk.pokes == []


def test_taking_one_off(desk):
    result = desk.unwatch("AAPL")
    assert result["ok"] is True and "AAPL" not in watchlist.current()
    assert desk.pokes == [("market",)]


def test_a_chart_over_the_period_asked_for(desk, monkeypatch):
    asked = []

    def history(symbol, period):
        asked.append((symbol, period))
        return {"symbol": symbol, "name": "NVIDIA", "price": 12.0, "change_pct": 20.0,
                "currency": "USD", "points": [(1, 10.0), (2, 11.0), (3, 12.0)]}

    monkeypatch.setattr(stockdesk.market, "history", history)
    chart = desk.chart("NVDA", "1mo")
    assert asked == [("NVDA", "1mo")]
    assert chart["ok"] is True
    assert chart["points"] == [10.0, 11.0, 12.0]
    assert chart["times"] == [1, 2, 3]            # when each was, for the scrubber
    assert chart["change_pct"] == 20.0
    assert chart["high"] == 12.0 and chart["low"] == 10.0


@pytest.mark.parametrize("symbol, period", [("NVDA", "10y"), ("NVDA", ""),
                                            ("PLTR", "1d"), ("../../x", "1d")])
def test_a_chart_is_only_for_a_watched_stock_over_a_known_period(desk, monkeypatch, symbol, period):
    def history(symbol, period):
        raise AssertionError("nothing should be fetched")

    monkeypatch.setattr(stockdesk.market, "history", history)
    assert desk.chart(symbol, period)["ok"] is False


def test_a_chart_the_feed_will_not_give_is_said_plainly(desk, monkeypatch):
    def history(symbol, period):
        raise stockdesk.market.MarketError("The market feed didn't answer (URLError).")

    monkeypatch.setattr(stockdesk.market, "history", history)
    chart = desk.chart("NVDA", "5d")
    assert chart["ok"] is False and "answer" in chart["error"]


def test_the_page_reaches_the_desk_through_the_api(desk):
    api = apollo.Api(lambda: None, desk=desk)
    assert api.watch("PLTR")["ok"] is True
    assert api.unwatch("PLTR")["ok"] is True
    assert isinstance(api.suggestions(), list)


def test_the_api_holds_nothing_the_bridge_would_walk_into(desk):
    """pywebview recurses into every public attribute that is not a method."""
    api = apollo.Api(lambda: None, open_link=lambda url: True, desk=desk)
    for name in dir(api):
        if not name.startswith("_"):
            assert callable(getattr(api, name)), name
