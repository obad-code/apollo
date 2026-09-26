"""The replay buffer is back once the PC is unlocked.

Windows will not let a program capture the screen while it is locked, so
the recorder stops the moment you lock it ("[gdigrab] Failed to capture
image (error 5)" in the log) - and nothing started it again: every clip
asked for after an unlock found nothing recording, until Apollo was
restarted or it was switched back on from the tray.
"""
import apollo
from test_sleep import make


class Recorder:
    def __init__(self, running=True):
        self.running = running
        self.starts = 0

    def start(self):
        self.starts += 1
        self.running = True
        return self


def lock_then_unlock(monkeypatch, app):
    locked = [True]
    monkeypatch.setattr(apollo, "pc_locked", lambda: locked[0])
    app.check_presence(0.1)
    return locked


def test_a_recorder_that_died_on_the_lock_screen_starts_again_on_unlock(monkeypatch):
    app, _log = make(monkeypatch)
    app.clips = Recorder()
    locked = lock_then_unlock(monkeypatch, app)
    app.clips.running = False              # the capture failed while locked
    app.check_presence(0.1)
    assert app.clips.starts == 0, "not while it is still locked"
    locked[0] = False
    app.check_presence(0.0)
    assert app.clips.starts == 1


def test_one_still_recording_is_left_alone(monkeypatch):
    app, _log = make(monkeypatch)
    app.clips = Recorder()
    locked = lock_then_unlock(monkeypatch, app)
    locked[0] = False
    app.check_presence(0.0)
    assert app.clips.starts == 0


def test_one_you_switched_off_stays_off(monkeypatch):
    """Off from the tray before the lock is off by choice, not by the lock."""
    app, _log = make(monkeypatch)
    app.clips = Recorder(running=False)
    locked = lock_then_unlock(monkeypatch, app)
    locked[0] = False
    app.check_presence(0.0)
    assert app.clips.starts == 0
