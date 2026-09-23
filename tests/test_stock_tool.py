"""Opening a stock on the display by voice: "open Nvidia"."""
import apollo
import tools
from tools import Context


def test_open_stock_is_registered_and_labelled():
    assert "open_stock" in tools.REGISTRY
    assert "open_stock" in tools.TOOL_LABELS
    props = tools.REGISTRY["open_stock"].parameters["properties"]
    assert props["company"]["type"] == "string"
    assert "English" in props["company"]["description"]


def test_it_opens_the_stock_and_hands_back_what_it_shows(monkeypatch):
    monkeypatch.setattr(tools.market, "resolve", lambda text: "NVDA")
    asked = []

    def stock(symbol):
        asked.append(symbol)
        return {"symbol": "NVDA", "name": "NVIDIA", "price": 228.87, "change_pct": 0.66}

    result = tools.run("open_stock", {"company": "Nvidia"}, Context(stock_hook=stock))
    assert asked == ["NVDA"]
    assert result["ok"] is True and result["symbol"] == "NVDA" and result["price"] == 228.87


def test_one_not_on_the_watchlist_is_said_plainly(monkeypatch):
    monkeypatch.setattr(tools.market, "resolve", lambda text: "PLTR")
    result = tools.run("open_stock", {"company": "Palantir"},
                       Context(stock_hook=lambda symbol: None))
    assert result["ok"] is False and "PLTR" in result["error"]
    assert "watch_stock" in result["error"] or "add" in result["error"].lower()


def test_an_empty_name_closes_it():
    asked = []
    result = tools.run("open_stock", {"company": ""},
                       Context(stock_hook=lambda symbol: asked.append(symbol) or {"closed": True}))
    assert asked == [""] and result == {"ok": True, "closed": True}


class _Window:
    def __init__(self):
        self.scripts = []

    def evaluate_js(self, script):
        self.scripts.append(script)
        return {"symbol": "NVDA"}


class _App:
    def __init__(self, mode):
        self.overlay = type("Overlay", (), {"mode": mode})()
        self.toggled = 0

    def toggle_peek(self):
        self.toggled += 1


def _reporter(mode):
    ui = apollo.WebReporter.__new__(apollo.WebReporter)
    ui.window, ui.alive, ui._app = _Window(), True, _App(mode)
    return ui


def test_a_stock_asked_for_brings_the_display_up():
    ui = _reporter(apollo.Overlay.ORB)
    assert ui.stock("NVDA") == {"symbol": "NVDA"}
    assert ui._app.toggled == 1


def test_closing_one_does_not_bring_the_display_up():
    ui = _reporter(apollo.Overlay.ORB)
    ui.stock("")
    assert ui._app.toggled == 0


def test_the_symbol_reaches_the_page_as_a_string_literal():
    """It came from a market search; it goes into script quoted, not spliced."""
    ui = _reporter(apollo.Overlay.FULL)
    ui.stock('X");alert(1);("')
    script = ui.window.scripts[-1]
    assert 'window.apollo.stock("X\\");alert(1);(\\"")' in script
