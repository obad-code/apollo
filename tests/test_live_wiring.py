"""Where the streamed prices go: the display, its second-by-second ticks, and
a price asked for out loud."""
import json
import time

import pytest

import apollo
import live
import tools
from tools import Context


class _Feed:
    def __init__(self, ticks):
        self._ticks = ticks

    def latest(self, symbol):
        return self._ticks.get(symbol)

    def ticks(self):
        return dict(self._ticks)


@pytest.fixture
def feed(monkeypatch):
    made = _Feed({"NVDA": (110.0, time.time())})
    monkeypatch.setattr(live, "_feed", made)
    return made


def test_a_price_asked_for_is_the_streamed_one(monkeypatch, feed):
    monkeypatch.setattr(tools.market, "resolve", lambda text: "NVDA")
    monkeypatch.setattr(tools.market, "quote", lambda symbol: {
        "symbol": "NVDA", "name": "NVIDIA", "price": 100.0, "previous_close": 80.0,
        "change": 20.0, "change_pct": 25.0, "currency": "USD", "points": [(1, 100.0)]})
    monkeypatch.setattr(tools.market, "visual_for", lambda data, period: {"price": data["price"]})
    monkeypatch.setattr(tools.market, "market_status", lambda: {"label": "open", "open": True})
    shown = []
    result = tools.run("stock_quote", {"symbols": ["Nvidia"]}, Context(show=shown.append))
    assert result["quotes"][0]["price"] == 110.0
    assert result["quotes"][0]["change_pct"] == pytest.approx(37.5)
    assert shown and shown[0]["price"] == 110.0         # the card opens on it too


class _Window:
    def __init__(self):
        self.scripts = []

    def evaluate_js(self, script):
        self.scripts.append(script)


def _ui():
    ui = apollo.WebReporter.__new__(apollo.WebReporter)
    ui.window, ui.alive = _Window(), True
    return ui


def test_ticks_reach_the_page_as_prices_and_times():
    ui = _ui()
    ui.live({"NVDA": (110.5, 1790265159.1)})
    script = ui.window.scripts[-1]
    assert script.startswith("window.apollo.live && window.apollo.live(")
    payload = json.loads(script[script.index("live(") + 5:-1])
    assert payload == {"NVDA": {"price": 110.5, "time": 1790265159.1}}


def _app(mode):
    app = apollo.Apollo.__new__(apollo.Apollo)
    app.ui = _ui()
    app.overlay = type("Overlay", (), {"mode": mode})()
    app.ticker = _Feed({"NVDA": (110.0, time.time())})
    return app


def test_the_display_is_given_the_streamed_prices():
    app = _app(apollo.Overlay.FULL)
    sent = []
    app.ui.data = sent.append
    app.on_data({"market": {"watchlist": [{"symbol": "NVDA", "price": 100.0, "previous": 80.0,
                                           "change_pct": 25.0, "spark": [100.0]}]}})
    assert sent[0]["market"]["watchlist"][0]["price"] == 110.0


def test_ticks_go_to_the_page_only_while_it_is_up():
    app = _app(apollo.Overlay.ORB)
    app.on_ticks({"NVDA": (111.0, 1.0)})
    assert app.ui.window.scripts == []
    app.overlay.mode = apollo.Overlay.FULL
    app.on_ticks({"NVDA": (111.0, 1.0)})
    assert len(app.ui.window.scripts) == 1
