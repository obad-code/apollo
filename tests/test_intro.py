"""The word, once, as Apollo comes up: the display holds the screen for a few
seconds while the page plays it, then Apollo is whatever it would have been."""
import threading
import time

import apollo


class _UI:
    alive = True

    def __init__(self):
        self.calls = []

    def intro(self):
        self.calls.append("intro")


class _Presence:
    full = False


def _app():
    app = apollo.Apollo.__new__(apollo.Apollo)
    app.presence = _Presence()
    app.ui = _UI()
    app.intro_on = False
    app.modes = []
    app.apply_mode = lambda: app.modes.append(app.desired_mode())
    return app


def test_the_intro_holds_the_full_display_and_then_lets_go(monkeypatch):
    monkeypatch.setattr(apollo, "screen_busy", lambda: False)
    monkeypatch.setattr(apollo, "INTRO_SECONDS", 0.05)
    app = _app()
    assert app.play_intro() is True
    assert app.ui.calls == ["intro"]
    assert app.modes == [apollo.Overlay.FULL]
    deadline = time.monotonic() + 2
    while len(app.modes) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert app.modes == [apollo.Overlay.FULL, apollo.Overlay.ORB]
    assert app.intro_on is False


def test_it_lets_go_to_the_display_if_that_was_asked_for_meanwhile(monkeypatch):
    monkeypatch.setattr(apollo, "screen_busy", lambda: False)
    monkeypatch.setattr(apollo, "INTRO_SECONDS", 0.05)
    app = _app()
    app.play_intro()
    app.presence.full = True                # Ctrl+` pressed during it
    deadline = time.monotonic() + 2
    while len(app.modes) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert app.modes[-1] == apollo.Overlay.FULL


def test_not_over_a_full_screen_program(monkeypatch):
    """A game or a film that was already up when Apollo started is left alone."""
    monkeypatch.setattr(apollo, "screen_busy", lambda: True)
    app = _app()
    assert app.play_intro() is False
    assert app.ui.calls == [] and app.modes == []


def test_the_page_is_told_to_play_it():
    class Window:
        scripts = []

        def evaluate_js(self, script):
            self.scripts.append(script)

    ui = apollo.WebReporter.__new__(apollo.WebReporter)
    ui.window, ui.alive = Window(), True
    ui.intro()
    assert ui.window.scripts[-1] == "window.apollo.intro && window.apollo.intro()"
