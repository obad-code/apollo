"""Idle mode when you ask for it - by voice, or by locking the PC - and not
just after ten quiet minutes."""
import presence
import tools
from tools import Context

import apollo
from test_sleep import make


def test_asked_for_it_is_asleep_at_once():
    p = presence.Presence(600)
    p.sleep_now(now=100.0)
    assert p.asleep and p.full


def test_what_happened_before_the_request_does_not_wake_it():
    """The chord you pressed to ask, and Apollo answering, both came before."""
    p = presence.Presence(600)
    p.touch(99.0)                                  # the turn that asked
    p.sleep_now(now=100.0)
    assert not p.check(idle=2.0, now=101.0)        # input at 99: before the request
    assert p.asleep


def test_anything_after_it_wakes_it():
    p = presence.Presence(600)
    p.sleep_now(now=100.0)
    assert p.check(idle=0.2, now=110.0)            # a key at 109.8
    assert not p.asleep and not p.full


def test_it_waits_for_the_answer_to_finish(monkeypatch):
    app, log = make(monkeypatch)
    app.turn_busy = True
    app.request_idle()
    app.check_presence(0.5)
    assert not app.presence.asleep                 # still saying "going idle"
    app.turn_busy = False
    monkeypatch.setattr(apollo.time, "monotonic", lambda: 10_000.0)
    app.check_presence(5.0)
    assert app.presence.asleep and ("sleep", True) in log


def test_locking_the_pc_puts_it_to_sleep_once(monkeypatch):
    app, log = make(monkeypatch)
    locked = [True]
    monkeypatch.setattr(apollo, "pc_locked", lambda: locked[0])
    app.check_presence(0.1)
    assert app.presence.asleep
    app.presence.check(idle=0.0, now=apollo.time.monotonic() + 5)    # woken on the lock screen
    app.check_presence(0.0)
    assert not app.presence.asleep, "still locked is not locking it again"
    locked[0] = False
    app.check_presence(0.0)
    locked[0] = True
    app.check_presence(0.0)
    assert app.presence.asleep, "a new lock is"


def test_the_voice_tool_asks_for_it():
    asked = []
    result = tools.run("idle_mode", {}, Context(idle_hook=lambda: asked.append(1)))
    assert result["ok"] is True and asked == [1]
    assert "الخمول" in tools.REGISTRY["idle_mode"].description
