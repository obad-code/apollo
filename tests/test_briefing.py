import datetime

import pytest

import briefing


@pytest.fixture
def quiet(monkeypatch):
    monkeypatch.setattr(briefing.feeds, "headlines",
                        lambda topic, limit=5: [{"title": f"{topic} story", "source": "IGN",
                                                 "age": "2h ago", "when": 1, "link": ""}])
    monkeypatch.setattr(briefing.feeds, "posts",
                        lambda hours=24, limit=5: [{"text": "Tariffs on chips Monday",
                                                    "age": "3h ago", "when": 1, "market": True}])
    monkeypatch.setattr(briefing.weather, "now", lambda: {"temp": 33, "high": 42, "low": 30, "text": "clear"})
    monkeypatch.setattr(briefing.market, "quote", lambda symbol: {
        "symbol": symbol, "name": symbol, "price": 100.0, "change": 1.0, "change_pct": 1.0,
        "currency": "USD", "exchange": "NMS", "points": [], "previous_close": 99.0, "time": 0})
    monkeypatch.setattr(briefing.market, "market_status", lambda now=None: {
        "open": False, "next": None, "label": "NYSE opens in 8h 00m"})


def test_compose_has_every_section(quiet):
    payload = briefing.compose(now=datetime.datetime(2026, 9, 20, 8, 30))
    assert payload["date"] == "Sunday 20 September 2026"
    assert payload["weather"]["temp"] == 33
    assert payload["market"]["indices"] and payload["market"]["movers"]
    assert payload["headlines"]["gaming"][0]["title"] == "gaming story"
    assert payload["posts"][0]["market"] is True


def test_market_line_says_when_the_market_last_traded(quiet):
    payload = briefing.compose(now=datetime.datetime(2026, 9, 20, 3, 0))
    assert "opens in" in payload["market"]["status"].lower()
    said = briefing.spoken(payload)
    assert "closed" in said.lower() or "opens" in said.lower()


def test_spoken_is_an_instruction_not_a_script(quiet):
    said = briefing.spoken(briefing.compose(now=datetime.datetime(2026, 9, 20, 8, 30)))
    assert "language" in said.lower()
    assert len(said) < 4000


def test_briefing_is_due_once_a_day(tmp_path):
    state = briefing.Schedule(str(tmp_path / "briefing.json"))
    morning = datetime.datetime(2026, 9, 20, 8, 0)
    assert state.due(morning, idle_seconds=0.0) is True
    state.done(morning)
    assert state.due(datetime.datetime(2026, 9, 20, 9, 0), idle_seconds=0.0) is False
    assert state.due(datetime.datetime(2026, 9, 21, 7, 0), idle_seconds=0.0) is True


def test_not_due_while_you_are_away(tmp_path):
    state = briefing.Schedule(str(tmp_path / "briefing.json"))
    assert state.due(datetime.datetime(2026, 9, 20, 8, 0), idle_seconds=600.0) is False


def test_hijri_date():
    assert briefing.hijri(datetime.date(2026, 9, 20)).endswith("1448")


def test_not_due_while_you_are_talking_to_it(tmp_path):
    """Pressing the talk chord must not fetch you the day's recap.

    The chord makes you present, and "present" was the whole test: the first
    Ctrl+Alt of the day set idle to zero, the watcher saw someone at the
    machine who had not been briefed, and the briefing started talking over
    the turn that press was opening. `turn_busy` did not catch it because
    that flag is set from Gemini's status, which arrives after the press.
    """
    state = briefing.Schedule(str(tmp_path / "briefing.json"))
    assert state.due(idle_seconds=0.0) is True
    assert state.due(idle_seconds=0.0, busy=True) is False


def test_due_again_once_you_have_stopped_talking(tmp_path):
    state = briefing.Schedule(str(tmp_path / "briefing.json"))
    assert state.due(idle_seconds=0.0, busy=True) is False
    assert state.due(idle_seconds=0.0, busy=False) is True
