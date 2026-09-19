import pytest

import market
import pc_control
import reminders
import tools
from tools import Context


def test_expected_tools_are_registered():
    assert {"open_app", "close_app", "open_website", "open_path", "media", "volume",
            "window", "type_text", "press_keys", "lock_pc", "system_power",
            "set_reminder", "list_reminders", "cancel_reminder", "stock_quote",
            "show_stock_chart", "open_tradingview"} <= set(tools.REGISTRY)
    assert tools.REGISTRY["system_power"].confirm is True
    assert all(name in tools.TOOL_LABELS for name in tools.REGISTRY)


def test_open_app_maps_to_pc_control(monkeypatch):
    monkeypatch.setattr(pc_control, "open_app", lambda name: f"Launched {name}.")
    assert tools.run("open_app", {"application_name": "Discord"}) == {"ok": True, "result": "Launched Discord."}


def test_volume_passes_level(monkeypatch):
    seen = []
    monkeypatch.setattr(pc_control, "volume", lambda action, level=None: seen.append((action, level)) or {"level": 40})
    assert tools.run("volume", {"action": "set", "level": "40"}) == {"ok": True, "level": 40}
    assert seen == [("set", 40)]


def fake_data(symbol, price=100.0, pct=1.5):
    return {"symbol": symbol, "name": symbol + " Inc", "currency": "USD", "exchange": "NMS",
            "price": price, "previous_close": price / (1 + pct / 100), "change": 1.0,
            "change_pct": pct, "points": [(i, price - 5 + i) for i in range(6)], "time": 0}


def test_show_stock_chart_shows_and_summarises(monkeypatch):
    monkeypatch.setattr(market, "resolve", lambda s: "NVDA")
    monkeypatch.setattr(market, "history", lambda s, p: fake_data(s))
    shown, doing = [], []
    r = tools.run("show_stock_chart", {"symbol": "nvidia", "period": "5D"},
                  Context(show=shown.append, activity=doing.append))
    assert r["ok"] and r["symbol"] == "NVDA" and r["period"] == "5d" and r["last"] == 100.0
    assert shown and shown[0]["chart"]["label"] == "NVDA · 5D"
    assert doing == ["charting NVDA"]


def test_stock_quote_several_shows_cards(monkeypatch):
    monkeypatch.setattr(market, "resolve", lambda s: s.upper())
    monkeypatch.setattr(market, "quote", lambda s: fake_data(s))
    shown = []
    r = tools.run("stock_quote", {"symbols": ["aapl", "tsla"]}, Context(show=shown.append))
    assert [q["symbol"] for q in r["quotes"]] == ["AAPL", "TSLA"]
    assert [c["label"] for c in shown[0]["cards"]] == ["AAPL", "TSLA"]


def test_market_error_becomes_failed_result(monkeypatch):
    def down(s):
        raise market.MarketError("The market feed didn't answer (URLError).")
    monkeypatch.setattr(market, "resolve", lambda s: s)
    monkeypatch.setattr(market, "quote", down)
    assert tools.run("stock_quote", {"symbols": ["NVDA"]}) == {
        "ok": False, "error": "The market feed didn't answer (URLError)."}


def test_open_tradingview(monkeypatch):
    monkeypatch.setattr(market, "resolve", lambda s: "NVDA")
    monkeypatch.setattr(market, "quote", lambda s: fake_data(s))
    opened = []
    monkeypatch.setattr(pc_control, "open_url", lambda u: opened.append(u) or f"Opened {u}.")
    assert tools.run("open_tradingview", {"symbol": "nvidia"})["ok"]
    assert opened == ["https://www.tradingview.com/chart/?symbol=NASDAQ%3ANVDA"]


def test_reminders_round_trip(monkeypatch, tmp_path):
    monkeypatch.setattr(reminders, "STORE", str(tmp_path / "r.json"))
    monkeypatch.setattr(reminders, "_reminders", None)
    assert tools.run("set_reminder", {"text": "stretch", "in_minutes": 30})["ok"]
    assert "stretch" in tools.run("list_reminders", {})["result"]
    assert tools.run("cancel_reminder", {"which": "stretch"}) == {"ok": True, "result": "Cancelled: stretch"}


def test_system_power_is_guarded(monkeypatch):
    tools.CONFIRM.reset()
    ran = []
    monkeypatch.setattr(pc_control, "system_power", lambda action: ran.append(action) or "ok")
    r = tools.run("system_power", {"action": "shutdown", "confirmed": True}, Context(turn=100))
    assert r["needs_confirmation"] and ran == []
