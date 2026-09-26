"""The replay buffer records while you are here, and only then.

It is the heaviest thing Apollo does - the whole screen captured and encoded
thirty times a second, most of a core - and it ran day and night: asleep,
with Apollo's own display covering the screen, it was recording Apollo's
display. And when it stopped it stayed stopped: Windows allows no capture on
the lock screen, so locking the PC killed it ("[gdigrab] Failed to capture
image (error 5)") and nothing started it again until Apollo was restarted.

So: recording while Apollo is awake and the PC unlocked, paused otherwise,
back the moment you are - unless you paused it yourself from the tray. One
that dies with you here is tried again, but not more than once a minute.
"""
import apollo
from test_sleep import make


class Recorder:
    def __init__(self, running=True):
        self.running = running
        self.starts = 0
        self.stops = 0

    def start(self):
        self.starts += 1
        self.running = True
        return self

    def stop(self):
        self.stops += 1
        self.running = False


def app_with(monkeypatch, running=True):
    app, _log = make(monkeypatch)
    app.clips = Recorder(running)
    clock = [1000.0]
    monkeypatch.setattr(apollo.time, "monotonic", lambda: clock[0])
    return app, clock


def test_asleep_it_stops_and_awake_it_records_again(monkeypatch):
    app, _clock = app_with(monkeypatch)
    app.check_presence(apollo.AFK_SECONDS + 1)
    assert app.presence.asleep
    assert not app.clips.running
    app.check_presence(0.2)                        # a key: you are back
    assert app.clips.running and app.clips.starts == 1


def test_locked_it_waits_and_unlocked_it_records(monkeypatch):
    app, clock = app_with(monkeypatch)
    locked = [True]
    monkeypatch.setattr(apollo, "pc_locked", lambda: locked[0])
    app.check_presence(0.1)
    assert not app.clips.running
    clock[0] += 5
    app.presence.check(idle=0.0, now=clock[0])     # woken on the lock screen
    app.check_presence(0.0)
    assert app.clips.starts == 0, "no capture on the lock screen"
    locked[0] = False
    app.check_presence(0.0)
    assert app.clips.running and app.clips.starts == 1


def test_one_that_died_is_tried_again_but_not_more_than_once_a_minute(monkeypatch):
    app, clock = app_with(monkeypatch, running=False)
    app.check_presence(0.2)
    assert app.clips.starts == 1
    app.clips.running = False                      # died again at once
    clock[0] += 10
    app.check_presence(0.2)
    assert app.clips.starts == 1
    clock[0] += 55
    app.check_presence(0.2)
    assert app.clips.starts == 2


def test_paused_from_the_tray_it_stays_paused(monkeypatch):
    app, _clock = app_with(monkeypatch)
    assert app.toggle_clips() is False
    app.check_presence(apollo.AFK_SECONDS + 1)
    app.check_presence(0.2)
    assert not app.clips.running and app.clips.starts == 0
    assert app.toggle_clips() is True
    assert app.clips.running


def test_awake_and_recording_it_is_left_alone(monkeypatch):
    app, _clock = app_with(monkeypatch)
    app.check_presence(0.2)
    assert app.clips.starts == 0 and app.clips.stops == 0
