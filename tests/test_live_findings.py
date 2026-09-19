"""Defects found by the live acceptance run (probes/probe_tools_live.py)."""
import io
import sys

import market
import pc_control
import tools


def test_volume_with_no_action_reads_it(monkeypatch):
    seen = []
    monkeypatch.setattr(pc_control, "volume", lambda action, level=None: seen.append(action) or {"level": 55})
    assert tools.run("volume", {}) == {"ok": True, "level": 55}
    assert seen == ["get"]


def test_a_list_given_for_a_string_takes_its_first_item(monkeypatch):
    resolved = []
    monkeypatch.setattr(market, "resolve", lambda s: resolved.append(s) or "NVDA")
    monkeypatch.setattr(market, "history", lambda s, p: {
        "symbol": "NVDA", "name": "NVIDIA", "currency": "USD", "exchange": "NMS", "price": 1.0,
        "previous_close": 1.0, "change": 0.0, "change_pct": 0.0, "points": [(i, 1.0 + i) for i in range(5)], "time": 0})
    tools.run("show_stock_chart", {"symbols": ["NVDA"], "period": "5D"})
    assert resolved == ["NVDA"]


def test_resolve_ignores_list_punctuation():
    assert market.resolve("['NVDA']") == "NVDA"
    assert market.resolve('"TSLA"') == "TSLA"


def test_console_survives_arabic(monkeypatch):
    import assistant
    raw = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(raw, encoding="cp1252"))
    assistant._utf8_console()
    assistant.ConsolePrinter().turn("You", "افتح المفكرة")
    sys.stdout.flush()
    assert "افتح".encode("utf-8") in raw.getvalue()
