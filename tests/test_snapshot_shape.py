"""The snapshot the display reads is a contract; this is the copy of it."""
import time

import dataservice


def test_snapshot_has_every_key_the_display_reads(monkeypatch):
    monkeypatch.setattr(dataservice.market, "quote", lambda s: {
        "symbol": s, "name": s, "price": 1.0, "change": 0.0, "change_pct": 0.0,
        "currency": "USD", "exchange": "NMS", "points": [(1, 1.0)],
        "previous_close": 1.0, "time": 0})
    monkeypatch.setattr(dataservice.market, "history", lambda s, p: {
        "symbol": s, "name": s, "price": 1.0, "change_pct": 0.0, "currency": "USD",
        "exchange": "NMS", "points": [(i, 1.0) for i in range(6)],
        "previous_close": 1.0, "time": 0})
    monkeypatch.setattr(dataservice.feeds, "headlines",
                        lambda topic, limit=5: [{"title": "t", "source": "s",
                                                 "age": "1h ago", "when": 1, "link": ""}])
    monkeypatch.setattr(dataservice.feeds, "posts",
                        lambda hours=24, limit=5: [{"text": "p", "age": "2h ago",
                                                    "when": 1, "market": True}])
    monkeypatch.setattr(dataservice.weather, "now",
                        lambda: {"temp": 32, "high": 42, "low": 30, "text": "clear", "code": 0})

    service = dataservice.DataService()
    service.refresh(force=True)
    snap = service.snapshot

    assert set(snap) >= {"market", "news", "posts", "weather", "system", "usage", "updated"}
    assert set(snap["market"]) == {"indices", "watchlist", "status"}
    stock = snap["market"]["watchlist"][0]
    assert set(stock) >= {"symbol", "name", "price", "change_pct", "currency", "spark"}
    assert set(snap["system"]) >= {"cpu", "ram", "gpu", "gpu_name"}
    assert set(snap["usage"]) >= {"tokens", "cost", "estimated", "turns"}
    headline = snap["news"]["gaming"][0]
    assert set(headline) >= {"title", "source", "age"}
    assert set(snap["posts"][0]) >= {"text", "age", "market"}


def test_a_reader_that_comes_back_empty_keeps_the_last_good_value_and_its_age(monkeypatch):
    """A feed outage must age the panel, not blank it.

    Headlines that vanish for ten minutes are still the last thing that
    happened; showing nothing says the world went quiet, which is a lie. The
    display keeps them and says how old they are, and it can only do that if
    the service stamps each reader separately.
    """
    live = [{"title": "t", "source": "s", "age": "1h ago", "when": 1, "link": ""}]
    monkeypatch.setattr(dataservice.feeds, "headlines", lambda topic, limit=5: list(live))
    monkeypatch.setattr(dataservice.feeds, "posts", lambda hours=24, limit=5: [])
    monkeypatch.setattr(dataservice.weather, "now", lambda: {"temp": 1})

    service = dataservice.DataService()
    service.refresh(force=True)
    assert service.snapshot["news"]["gaming"] == live
    first = service.snapshot["stamps"]["news"]

    # The feed goes down: same call, nothing in it.
    monkeypatch.setattr(dataservice.feeds, "headlines", lambda topic, limit=5: [])
    time.sleep(0.01)
    service.refresh(force=True)

    assert service.snapshot["news"]["gaming"] == live, "the outage blanked the panel"
    assert service.snapshot["stamps"]["news"] == first, "a failed read refreshed the age"
    assert service.snapshot["stamps"]["weather"] > first, "a good read did not stamp"


def test_age_of_a_snapshot_is_readable():
    assert dataservice.age_words(0).endswith("now") or dataservice.age_words(0) == "just now"
    assert dataservice.age_words(3600) == "1h ago"
