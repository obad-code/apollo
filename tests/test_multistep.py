"""Requests that take more than one step, done to the end (Windows only)."""
import pc_control as pc


def test_search_addresses():
    assert pc.search_url("YouTube", "lofi beats") == "https://www.youtube.com/results?search_query=lofi+beats"
    assert pc.search_url("spotify", "drake") == "https://open.spotify.com/search/drake"
    assert pc.search_url("unknown", "x") is None


def test_an_unknown_site_is_searched_through_google(monkeypatch):
    opened = []
    monkeypatch.setattr(pc, "_try_start", lambda url: opened.append(url) or True)
    pc.search_site("example.org", "docs")
    assert opened == ["https://www.google.com/search?q=docs+site%3Aexample.org"]


def test_waiting_for_an_app_brings_it_forward(monkeypatch):
    fronts = iter([1, 1, 42])
    monkeypatch.setattr(pc, "_focus", lambda h: None)
    hwnd = pc.wait_for_app("discord", timeout=5, sleep=lambda s: None,
                           find=lambda app: [(42, 7, "Discord")], front=lambda: next(fronts))
    assert hwnd == 42


def test_sending_stops_if_the_app_loses_focus(monkeypatch):
    typed = []
    monkeypatch.setattr(pc, "open_app", lambda name: "Switched to discord.")
    monkeypatch.setattr(pc, "wait_for_app", lambda *a, **k: 42)
    monkeypatch.setattr(pc, "wait_for_release", lambda *a, **k: True)
    monkeypatch.setattr(pc, "press_keys", lambda keys: typed.append(keys))
    monkeypatch.setattr(pc, "type_text", lambda text: typed.append(text))
    fronts = iter([42, 42, 42, 99])
    monkeypatch.setattr(pc, "_foreground", lambda: next(fronts, 99))
    said = pc.send_chat("discord", "Ahmed", "hi", sleep=lambda s: None)
    assert said.startswith("Failed") and "hi" not in typed


def test_sending_goes_all_the_way(monkeypatch):
    typed = []
    monkeypatch.setattr(pc, "open_app", lambda name: "Switched to discord.")
    monkeypatch.setattr(pc, "wait_for_app", lambda *a, **k: 42)
    monkeypatch.setattr(pc, "wait_for_release", lambda *a, **k: True)
    monkeypatch.setattr(pc, "press_keys", lambda keys: typed.append(keys))
    monkeypatch.setattr(pc, "type_text", lambda text: typed.append(text))
    monkeypatch.setattr(pc, "_foreground", lambda: 42)
    assert pc.send_chat("discord", "Ahmed", "hi", sleep=lambda s: None) == "Sent to Ahmed on discord."
    assert typed == ["ctrl+k", "Ahmed", "enter", "hi", "enter"]
