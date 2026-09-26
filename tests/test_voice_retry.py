"""A voice session that would not open is tried again.

The run loop rebuilt a session that died, once. If that failed too - no
network, or no audio device: a monitor's speakers vanish while it sleeps,
and on 26 September 2026 the prayer reminder woke Apollo into exactly that
("There is no driver installed on your system") - the session was left as
None, and None was never tried again. Apollo was deaf until restarted.
"""
import assistant
import gemini_live


class Voice:
    """A session that will not open the first `failures` times."""

    def __init__(self, failures):
        self.live = None
        self.auto_vad = False
        self.busy = False
        self.failures = failures
        self.opens = 0

    @property
    def ready(self):
        return self.live is not None

    def open(self, auto_vad=False):
        self.opens += 1
        self.auto_vad = auto_vad
        if self.opens <= self.failures:
            return False
        self.live = object()
        return True


class UI:
    def status(self, s):
        pass

    def note(self, t):
        pass

    def level(self, v):
        pass


def run(monkeypatch, voice, seconds, step=1.0):
    clock = [1000.0]
    monkeypatch.setattr(assistant.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(assistant.time, "sleep", lambda s: None)
    monkeypatch.setattr(assistant, "talk_held", lambda: False)
    monkeypatch.setattr(gemini_live, "available", lambda: True)
    loops = int(seconds / step)
    n = {"i": 0}

    def stop():
        n["i"] += 1
        clock[0] += step
        return n["i"] > loops

    assistant.run_loop(UI(), whisper=None, stop=stop, voice=voice)
    return voice


def test_a_session_that_would_not_open_is_tried_again_until_it_does(monkeypatch):
    voice = run(monkeypatch, Voice(failures=3), seconds=300)
    assert voice.live is not None
    assert voice.opens == 4


def test_not_every_tick(monkeypatch):
    voice = run(monkeypatch, Voice(failures=100), seconds=4, step=0.05)
    assert voice.opens == 0, "the first try waits a few seconds"
    voice = run(monkeypatch, Voice(failures=100), seconds=600)
    assert voice.opens < 20, "and then less and less often"


def test_no_key_no_retrying(monkeypatch):
    monkeypatch.setattr(gemini_live, "available", lambda: False)
    voice = Voice(failures=0)
    clock = [1000.0]
    monkeypatch.setattr(assistant.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(assistant.time, "sleep", lambda s: None)
    monkeypatch.setattr(assistant, "talk_held", lambda: False)
    n = {"i": 0}

    def stop():
        n["i"] += 1
        clock[0] += 1.0
        return n["i"] > 300

    assistant.run_loop(UI(), whisper=None, stop=stop, voice=voice)
    assert voice.opens == 0
