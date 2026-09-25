"""Apollo's own modes on the display's bar, beside the display's: Idle (the
idle screen, now), Away (the PC kept up with Claude open while you are out)
and Hands-free (always listening, what Ctrl+1 does). A click asks for them
through the page's bridge, and they light while they are on - the page is
told when they change. A click leaves a few seconds of grace: the hand still
on the mouse is part of asking, not you coming back."""
import threading
from types import SimpleNamespace

import apollo
import away
import presence


class _App:
    def __init__(self):
        self.asked = []

    def request_idle(self, grace=None):
        self.asked.append(("idle", grace))

    def request_away(self, grace=None):
        self.asked.append(("away", grace))

    def set_listening(self, on):
        self.asked.append(("listen", on))

    def mode_states(self):
        return {"away": False, "listening": True}


def test_the_bar_asks_for_them_through_the_bridge():
    app = _App()
    api = apollo.Api(lambda: None, app=app)
    assert api.idle() is True and api.away() is True and api.listen(True) is True
    assert app.asked == [("idle", apollo.CLICK_GRACE), ("away", apollo.CLICK_GRACE),
                         ("listen", True)]
    assert api.states() == {"away": False, "listening": True}


def test_with_no_app_behind_it_nothing_happens():
    api = apollo.Api(lambda: None)
    assert api.idle() is False and api.away() is False and api.listen(True) is False


def test_a_click_s_grace_is_a_few_seconds():
    assert 2.0 <= apollo.CLICK_GRACE <= 8.0


def test_idle_by_click_is_not_woken_by_the_hand_leaving_the_mouse():
    p = presence.Presence(600)
    p.sleep_now(100.0, grace=4.0)
    assert p.check(idle=0.5, now=103.0) is False and p.asleep       # the mouse, letting go
    assert p.check(idle=0.5, now=110.0) is True and not p.asleep    # a touch, later


def test_away_by_click_the_same():
    a = away.Away()
    a.leaving(now=100.0, grace=4.0)
    assert a.update(now=103.5, idle=0.2) is False and a.away
    assert a.update(now=110.0, idle=0.2) is True and not a.away


def test_by_voice_the_grace_is_as_it_was():
    p = presence.Presence(600)
    p.sleep_now(100.0)
    assert p.check(idle=0.1, now=103.0) is True                     # half a second, as before
    a = away.Away()
    a.leaving(now=100.0)
    assert a.update(now=103.5, idle=0.2) is True


def test_hands_free_from_the_bar_throws_the_same_switch_as_ctrl_1():
    app = apollo.Apollo.__new__(apollo.Apollo)
    app.listen_toggle = SimpleNamespace(enabled=threading.Event())
    told = []
    app.ui = SimpleNamespace(alive=True, note=lambda text: None, states=told.append)
    app.set_listening(True)
    assert app.listen_toggle.enabled.is_set() and told[-1]["listening"] is True
    app.set_listening(False)
    assert not app.listen_toggle.enabled.is_set() and told[-1]["listening"] is False


def test_the_page_hears_when_away_changes(monkeypatch):
    from test_sleep import make
    app, log = make(monkeypatch)
    app.away = away.Away()
    app.keeper = SimpleNamespace(apply=lambda on: None)
    told = []
    app.ui.states = told.append
    app.request_away(grace=4.0)
    app.check_presence(0.1)
    assert told and told[-1]["away"] is True
