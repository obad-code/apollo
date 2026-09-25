"""OSIRIS inside Apollo: the open-source intelligence map, in a window of its
own laid over the frame the display leaves for it, on screen only while the
display is - and Apollo dressed the way OSIRIS is while it is open.

The site will not be drawn inside another page (X-Frame-Options: SAMEORIGIN),
which is why it is a window rather than a frame on the page."""
import pytest

import apollo
import osiris
import tools
from test_sleep import make
from tools import Context

LAYERS = ("maritime", "cctv", "cctv_previews", "live_news", "earthquakes",
          "global_incidents", "day_night", "cables", "sdk_sea", "sdk_air", "sdk_naval")


class Native:
    """The window, as the controller drives it."""

    def __init__(self):
        self.calls = []
        self.ready = None

    def create(self, rect, on_ready, on_closed):
        self.calls.append(("create", rect))
        self.ready = on_ready
        self.closed = on_closed
        return "window"

    def place(self, window, rect):
        self.calls.append(("place", rect))

    def show(self, window):
        self.calls.append(("show",))

    def hide(self, window):
        self.calls.append(("hide",))

    def destroy(self, window):
        self.calls.append(("destroy",))


def controller(origin=(0, 0), on_gone=None):
    native = Native()
    return osiris.Osiris(create=native.create, place=native.place, show=native.show,
                         hide=native.hide, destroy=native.destroy,
                         origin=lambda: origin, on_gone=on_gone), native


FRAME = {"x": 700, "y": 180, "w": 1700, "h": 1000}


def test_it_is_osiris_with_the_layers_you_use():
    assert osiris.URL.startswith("https://osirisai.live/?layers=")
    for layer in LAYERS:
        assert layer in osiris.URL


def test_opened_where_the_display_left_room_for_it():
    o, native = controller(origin=(0, 0))
    assert o.open(FRAME) is True
    assert native.calls[0] == ("create", (700, 180, 1700, 1000))
    native.ready()                                 # the window is up
    assert ("place", (700, 180, 1700, 1000)) in native.calls


def test_on_the_screen_the_frame_is_on():
    o, native = controller(origin=(0, 48))         # a taskbar along the top
    o.open(FRAME)
    assert native.calls[0] == ("create", (700, 228, 1700, 1000))


def test_opening_it_again_only_moves_it():
    o, native = controller()
    o.open(FRAME)
    native.ready()
    o.open({"x": 10, "y": 20, "w": 900, "h": 600})
    assert [c for c in native.calls if c[0] == "create"] == [("create", (700, 180, 1700, 1000))]
    assert native.calls[-2:] == [("place", (10, 20, 900, 600)), ("show",)]


@pytest.mark.parametrize("frame", [
    None, {}, {"x": 1, "y": 2, "w": 0, "h": 500}, {"x": 1, "y": 2, "w": 900, "h": -1},
    {"x": "left", "y": 2, "w": 900, "h": 600},
])
def test_a_frame_that_is_not_one_opens_nothing(frame):
    o, native = controller()
    assert o.open(frame) is False
    assert native.calls == []


def test_it_goes_with_the_display_and_comes_back_with_it():
    o, native = controller()
    o.open(FRAME)
    native.ready()
    o.follow(False)                                # the display went away, or to sleep
    assert native.calls[-1] == ("hide",)
    o.follow(True)
    assert native.calls[-2:] == [("place", (700, 180, 1700, 1000)), ("show",)]


def test_closed_is_gone_for_good():
    o, native = controller()
    o.open(FRAME)
    native.ready()
    o.close()
    assert native.calls[-1] == ("destroy",)
    native.calls.clear()
    o.follow(True)
    assert native.calls == []


def test_closed_from_its_own_side_apollo_is_told():
    gone = []
    o, native = controller(on_gone=lambda: gone.append(1))
    o.open(FRAME)
    native.ready()
    native.closed()                                # Alt+F4 on the map
    assert gone == [1]
    assert o.window is None
    o.close()                                      # nothing left to close
    assert ("destroy",) not in native.calls


def test_never_opened_nothing_follows():
    o, native = controller()
    o.follow(True)
    o.follow(False)
    o.close()
    assert native.calls == []


def test_asked_for_by_voice():
    asked = []
    result = tools.run("osiris", {"open": True}, Context(osiris_hook=asked.append))
    assert result["ok"] is True and result["open"] is True and asked == [True]
    description = tools.REGISTRY["osiris"].description
    assert "OSIRIS" in description and "اوزيرس" in description


def test_closed_by_voice():
    asked = []
    result = tools.run("osiris", {"open": False}, Context(osiris_hook=asked.append))
    assert result["ok"] is True and result["open"] is False and asked == [False]


def test_the_display_opens_and_closes_it():
    opened, closed = [], []

    class Fake:
        def open(self, rect):
            opened.append(rect)
            return True

        def close(self):
            closed.append(True)

    api = apollo.Api(lambda: None, osiris=Fake())
    assert api.osiris_open(FRAME) is True and opened == [FRAME]
    assert api.osiris_close() is True and closed == [True]


def test_asked_for_by_voice_the_display_comes_up_with_it(monkeypatch):
    app, log = make(monkeypatch)
    told = []
    app.ui.osiris = told.append
    app.request_osiris(True)
    app.check_osiris()
    assert app.presence.full is True
    assert ("show", apollo.Overlay.FULL) in log
    assert told == [True]


def test_closed_by_voice_the_window_goes(monkeypatch):
    app, log = make(monkeypatch)
    told, closed = [], []
    app.ui.osiris = told.append
    app.osiris = type("O", (), {"close": lambda self: closed.append(1),
                                "follow": lambda self, shown: None})()
    app.request_osiris(False)
    app.check_osiris()
    assert told == [False] and closed == [1]


def test_the_window_follows_the_display(monkeypatch):
    app, log = make(monkeypatch)
    followed = []
    app.osiris = type("O", (), {"follow": lambda self, shown: followed.append(shown)})()
    app.presence.toggle_peek()                     # Ctrl+`
    app.apply_mode()
    assert followed[-1] is True
    app.presence.toggle_peek()
    app.apply_mode()
    assert followed[-1] is False
