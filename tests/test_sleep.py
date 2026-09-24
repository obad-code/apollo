"""Apollo asleep: ten quiet minutes turn the display into the idle screen.

Built without a window: `Apollo.__new__` and just the attributes the sleep
path touches, so what is tested is the decision and its order, not WebView2.
"""
import presence

import apollo


class Log(list):
    pass


class FakeOverlay:
    def __init__(self, log):
        self.log = log
        self.mode = None

    def show_page(self, mode):
        self.log.append(("show", mode))

    def hide_page(self):
        self.log.append(("hide",))

    def box_for(self, mode):
        return (0, 0, 10, 10)

    def orb_overhang(self):
        return 0


class FakeUI:
    alive = True
    quiet = True               # keeps the recap and the prayer checks out of it

    def __init__(self, log):
        self.log = log

    def mode(self, name):
        self.log.append(("mode", name))

    def sleep(self, on):
        self.log.append(("sleep", on))

    def data(self, snapshot):
        self.log.append(("data",))


class FakeVoice:
    def __init__(self):
        self.listener = None

    def listen(self, fn):
        self.listener = fn


def make(monkeypatch, busy=False):
    monkeypatch.setattr(apollo, "screen_busy", lambda: busy)
    log = Log()
    app = apollo.Apollo.__new__(apollo.Apollo)
    app.presence = presence.Presence(apollo.AFK_SECONDS)
    app.overlay = FakeOverlay(log)
    app.orb = None
    app.ui = FakeUI(log)
    app.voice = FakeVoice()
    app.data = None
    app.wake = presence.VoiceWake()
    app.asleep_shown = False
    app.turn_busy = False
    app.last_engaged = 0.0
    app.last_status = None
    return app, log


def test_ten_minutes_is_the_idle_time():
    assert apollo.AFK_SECONDS == 10 * 60


def test_the_page_is_asleep_before_it_is_shown(monkeypatch):
    """Told after, the page would show the dashboard for a frame and then
    swap - a flash of everything, right as the room goes quiet."""
    app, log = make(monkeypatch)
    app.check_presence(apollo.AFK_SECONDS + 1)
    assert ("sleep", True) in log and ("show", "full") in log
    assert log.index(("sleep", True)) < log.index(("show", "full"))


def test_asleep_it_listens_and_awake_it_stops(monkeypatch):
    app, log = make(monkeypatch)
    app.check_presence(apollo.AFK_SECONDS + 1)
    assert app.voice.listener is not None
    app.check_presence(0.2)                  # a key
    assert ("sleep", False) in log
    assert app.voice.listener is None
    assert app.overlay.mode == "orb"


def test_saying_something_wakes_it(monkeypatch):
    app, log = make(monkeypatch)
    app.check_presence(apollo.AFK_SECONDS + 1)
    for level in (0.6, 0.7, 0.8, 0.6):       # a few hundred ms of a voice
        app.voice.listener(level)
    # The keyboard has still not been touched: only the voice woke it.
    app.check_presence(apollo.AFK_SECONDS + 2)
    assert not app.presence.asleep and ("sleep", False) in log


def test_a_full_screen_film_keeps_it_awake(monkeypatch):
    app, log = make(monkeypatch, busy=True)
    app.check_presence(apollo.AFK_SECONDS + 1)
    assert not app.presence.asleep
    assert ("show", "full") not in log


def test_the_screen_is_only_asked_about_when_it_matters(monkeypatch):
    """SHQueryUserNotificationState is a call into the shell; the watcher
    ticks twenty-five times a second and must not make it every tick."""
    asked = []
    app, log = make(monkeypatch)
    monkeypatch.setattr(apollo, "screen_busy", lambda: asked.append(1) or False)
    for _ in range(50):
        app.check_presence(30.0)
    assert asked == []
    app.check_presence(apollo.AFK_SECONDS + 1)
    assert len(asked) == 1


def test_a_conversation_without_the_keyboard_keeps_it_awake(monkeypatch):
    """Always-listening: you talk, it answers, nobody touches a key."""
    app, log = make(monkeypatch)
    app.view = apollo.turnview.TurnView()
    app.on_status(apollo.assistant.LISTENING)
    app.check_presence(apollo.AFK_SECONDS + 1)
    assert not app.presence.asleep


def test_the_full_display_takes_clicks_and_hidden_it_lets_them_through(monkeypatch):
    """A story is picked by clicking it, and a click-through page cannot be
    clicked. Hidden, it goes back to being nothing under the pointer."""
    styles = {"ex": apollo.Overlay.PASSIVE}
    monkeypatch.setattr(apollo.win32gui, "GetWindowLong", lambda hwnd, index: styles["ex"])

    class User32:                       # see test_overlay_gil for why ctypes
        @staticmethod
        def SetWindowLongPtrW(hwnd, index, value):
            styles["ex"] = value

        @staticmethod
        def SetWindowPos(*args):
            return 1

        @staticmethod
        def ShowWindow(*args):
            return 1

    monkeypatch.setattr(apollo, "_user32", User32)
    overlay = apollo.Overlay()
    overlay.hwnd = 1
    monkeypatch.setattr(overlay, "set_alpha", lambda value: None)
    monkeypatch.setattr(overlay, "rect_for", lambda mode: (0, 0, 100, 100))

    overlay.show_page(apollo.Overlay.FULL)
    assert not styles["ex"] & apollo.WS_EX_TRANSPARENT
    assert styles["ex"] & apollo.WS_EX_NOACTIVATE      # still never takes focus
    overlay.hide_page()
    assert styles["ex"] & apollo.WS_EX_TRANSPARENT
