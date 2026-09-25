"""Away mode: when you have left the house the PC stays up with Claude open,
so you can reach it from your phone; when you are home it may rest.

You leave when you say so; you are back when you touch the PC or talk to
Apollo."""
import away
import tools
from tools import Context


def test_saying_you_are_going_out_is_away_at_once():
    a = away.Away()
    assert a.leaving(now=100.0) is True
    assert a.away


def test_what_you_did_to_say_it_does_not_bring_you_back():
    a = away.Away()
    a.leaving(now=100.0)
    assert a.update(now=105.0, idle=6.0) is False       # the chord, at 99
    assert a.away


def test_touching_the_pc_is_being_back():
    a = away.Away()
    a.leaving(now=100.0)
    assert a.update(now=400.0, idle=1.0) is True
    assert not a.away


def test_away_keeps_the_pc_up_and_opens_claude_and_back_lets_it_rest():
    states, launched = [], []
    keeper = away.Keeper(set_state=states.append, running=lambda: False,
                         launch=lambda: launched.append(1))
    keeper.apply(True)
    assert states[-1] & away.ES_SYSTEM_REQUIRED and states[-1] & away.ES_CONTINUOUS
    assert launched == [1]
    keeper.apply(False)
    assert states[-1] == away.ES_CONTINUOUS                 # back to the power plan


def test_claude_already_open_is_left_as_it_is():
    launched = []
    keeper = away.Keeper(set_state=lambda s: None, running=lambda: True,
                         launch=lambda: launched.append(1))
    keeper.apply(True)
    assert launched == []


def test_saying_you_are_going_out_by_voice():
    asked = []
    result = tools.run("going_out", {}, Context(away_hook=lambda: asked.append(1)))
    assert result["ok"] is True and asked == [1]
    assert "طالع" in tools.REGISTRY["going_out"].description


def test_the_watcher_does_it_and_lets_it_go_when_you_are_back(monkeypatch):
    import apollo
    from test_sleep import make

    app, log = make(monkeypatch)
    applied = []
    app.away = away.Away()
    app.keeper = type("Keeper", (), {"apply": lambda self, on: applied.append(on)})()
    clock = [1000.0]
    monkeypatch.setattr(apollo.time, "monotonic", lambda: clock[0])
    app.request_away()
    app.check_presence(5.0)
    assert applied == [True]
    clock[0] = 1300.0
    app.check_presence(0.5)                  # a key, at the PC
    assert applied == [True, False]
