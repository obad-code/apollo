"""The word, once, as Apollo comes up: the display holds the screen for a few
seconds while the page plays it, then Apollo is whatever it would have been.

Started and ended on the watcher's thread, like every other change of mode.
It began life on a timer thread, which raced the watcher: the watcher saw
the window halfway between two modes, "repaired" it, and deadlocked the
window's thread (see test_overlay_gil).
"""
import apollo


class _UI:
    alive = True

    def __init__(self, log):
        self.log = log

    def intro(self):
        self.log.append("intro")


class _Presence:
    full = False


def _app():
    app = apollo.Apollo.__new__(apollo.Apollo)
    app.log = []
    app.presence = _Presence()
    app.ui = _UI(app.log)
    app.intro_wanted = False
    app.intro_until = 0.0
    app.apply_mode = lambda: app.log.append(app.desired_mode())
    return app


def test_asking_for_it_changes_nothing_until_the_watcher_ticks():
    app = _app()
    app.want_intro()
    assert app.log == [] and app.desired_mode() == apollo.Overlay.ORB


def test_the_watcher_plays_it_then_lets_go(monkeypatch):
    monkeypatch.setattr(apollo, "screen_busy", lambda: False)
    app = _app()
    app.want_intro()
    app.check_intro(now=100.0)
    # The page is told first, while it is still hidden, so the display is
    # never seen for a frame on its way to the intro.
    assert app.log == ["intro", apollo.Overlay.FULL]
    app.check_intro(now=100.0 + apollo.INTRO_SECONDS - 0.1)
    assert len(app.log) == 2                               # still playing
    monkeypatch.setattr(apollo.time, "monotonic", lambda: 100.0 + apollo.INTRO_SECONDS + 0.1)
    app.check_intro(now=100.0 + apollo.INTRO_SECONDS + 0.1)
    assert app.log[-1] == apollo.Overlay.ORB
    assert app.intro_until == 0.0


def test_it_lets_go_to_the_display_if_that_was_asked_for_meanwhile(monkeypatch):
    monkeypatch.setattr(apollo, "screen_busy", lambda: False)
    app = _app()
    app.want_intro()
    app.check_intro(now=100.0)
    app.presence.full = True                  # Ctrl+` pressed during it
    monkeypatch.setattr(apollo.time, "monotonic", lambda: 200.0)
    app.check_intro(now=200.0)
    assert app.log[-1] == apollo.Overlay.FULL


def test_not_over_a_full_screen_program(monkeypatch):
    """A game or a film that was already up when Apollo started is left alone."""
    monkeypatch.setattr(apollo, "screen_busy", lambda: True)
    app = _app()
    app.want_intro()
    app.check_intro(now=100.0)
    assert app.log == [] and app.intro_wanted is False


def test_the_watcher_is_what_runs_it(monkeypatch):
    calls = []

    class App:
        stopping = None

        def quit(self): calls.append("quit")
        def toggle_peek(self): calls.append("peek")
        def check_intro(self): calls.append("intro")
        def check_osiris(self): calls.append("osiris")
        def check_displays(self): calls.append("displays")
        def check_presence(self, idle): calls.append("presence")
        def check_overlay_alive(self): calls.append("alive")

    monkeypatch.setattr(apollo, "chord_down", lambda chord: False)
    monkeypatch.setattr(apollo, "idle_seconds", lambda: 0.0)
    watcher = apollo.Watcher.__new__(apollo.Watcher)
    watcher.app = App()
    watcher._tick({"peek": False, "quit": False})
    assert calls.index("intro") < calls.index("alive")


def test_the_page_is_told_to_play_it():
    class Window:
        scripts = []

        def evaluate_js(self, script):
            self.scripts.append(script)

    ui = apollo.WebReporter.__new__(apollo.WebReporter)
    ui.window, ui.alive = Window(), True
    ui.intro()
    assert ui.window.scripts[-1] == "window.apollo.intro && window.apollo.intro()"
