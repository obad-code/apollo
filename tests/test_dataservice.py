import time

import dataservice


def test_snapshot_gathers_every_reader(monkeypatch):
    monkeypatch.setattr(dataservice.market, "quote", lambda s: {
        "symbol": s, "name": s, "price": 10.0, "change": 0.1, "change_pct": 1.0,
        "currency": "USD", "exchange": "NMS", "points": [(1, 10.0)], "previous_close": 9.9, "time": 0})
    monkeypatch.setattr(dataservice.market, "history", lambda s, p: {
        "symbol": s, "name": s, "price": 10.0, "change_pct": 1.0, "currency": "USD",
        "exchange": "NMS", "points": [(i, 10.0 + i) for i in range(8)], "previous_close": 9.9, "time": 0})
    monkeypatch.setattr(dataservice.feeds, "headlines", lambda topic, limit=5: [{"title": "x", "source": "y", "age": "1h ago", "when": 1, "link": ""}])
    monkeypatch.setattr(dataservice.feeds, "posts", lambda hours=24, limit=5: [])
    monkeypatch.setattr(dataservice.weather, "now", lambda: {"temp": 30, "text": "clear", "high": 40, "low": 25})

    service = dataservice.DataService()
    service.refresh(force=True)
    snap = service.snapshot
    assert snap["market"]["indices"] and snap["market"]["watchlist"]
    assert snap["market"]["watchlist"][0]["spark"]          # a sparkline's points
    assert snap["news"] and snap["weather"]["temp"] == 30
    assert snap["system"]["cpu"] >= 0 and "updated" in snap


def test_a_broken_reader_leaves_the_rest(monkeypatch):
    def boom(*a, **kw):
        raise OSError("offline")
    monkeypatch.setattr(dataservice.market, "quote", boom)
    monkeypatch.setattr(dataservice.market, "history", boom)
    monkeypatch.setattr(dataservice.feeds, "headlines", lambda topic, limit=5: [])
    monkeypatch.setattr(dataservice.feeds, "posts", lambda hours=24, limit=5: [])
    monkeypatch.setattr(dataservice.weather, "now", lambda: {})
    service = dataservice.DataService()
    service.refresh(force=True)
    assert service.snapshot["market"]["watchlist"] == []
    assert service.snapshot["system"]["cpu"] >= 0


def test_it_tells_the_page_only_when_asked():
    seen = []
    service = dataservice.DataService(on_snapshot=seen.append)
    service.refresh(force=True)
    assert len(seen) == 1
