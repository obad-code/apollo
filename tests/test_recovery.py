"""A dropped voice session must not swallow what you just said.

Measured 2026-09-20: the Live API sometimes closes a session with
"1011 Internal error occurred" the moment the model goes to call a tool. The
turn's audio is gone with it - but Apollo still has its own transcript of
you, so it can reconnect and ask again instead of standing there silently.
"""
import assistant


class UI:
    def __init__(self):
        self.statuses, self.turns, self.notes = [], [], []

    def status(self, s):
        self.statuses.append(s)

    def turn(self, who, text, visual=None):
        self.turns.append((who, text))

    def note(self, t):
        self.notes.append(t)

    def level(self, v):
        pass

    def partial(self, t):
        pass


class Capture:
    def start(self):
        pass

    def stop(self):
        import numpy as np
        return np.zeros(assistant.SAMPLE_RATE, dtype=np.float32)


class Live:
    def __init__(self, alive=True, reply="", heard="open notepad"):
        self.alive, self._reply, self.heard = alive, reply, heard
        self.prompts = []

    def begin_turn(self):
        pass

    def end_turn(self):
        pass

    def heard_text(self, **kw):
        return self.heard

    def allow_reply(self):
        pass

    def discard_reply(self):
        pass

    def wait_for_reply(self, timeout=60):
        return self.alive

    def reply_text(self):
        return self._reply

    def prompt(self, text):
        self.prompts.append(text)
        self._reply = "Opening Notepad."
        return True

    def wait_for_audio(self, timeout=10):
        return True

    def wait_until_quiet(self, timeout=60):
        return True


class Voice:
    def __init__(self, live, replacement=None):
        self.live, self.capture = live, Capture()
        self.replacement = replacement
        self.auto_vad = False
        self.opened = 0

    def open(self, auto_vad=False):
        self.opened += 1
        if self.replacement is not None:
            self.live = self.replacement
        return True


def test_a_dropped_turn_is_asked_again_after_reconnecting():
    dead = Live(alive=False)
    fresh = Live(alive=True)
    voice = Voice(dead, replacement=fresh)
    ui = UI()
    assistant.push_to_talk_turn(ui, None, voice)
    assert voice.opened == 1
    assert fresh.prompts == ["open notepad"]
    assert ("Apollo", "Opening Notepad.") in ui.turns
    assert any("dropped" in note.lower() for note in ui.notes)


def test_a_healthy_turn_never_reconnects():
    live = Live(alive=True, reply="Opening Notepad.")
    voice = Voice(live)
    ui = UI()
    assistant.push_to_talk_turn(ui, None, voice)
    assert voice.opened == 0 and live.prompts == []
    assert ("Apollo", "Opening Notepad.") in ui.turns


def test_a_second_failure_says_so_out_loud(monkeypatch):
    """If the reconnect's answer dies too, the user hears why rather than
    watching Apollo stand there silently."""
    spoken = []
    monkeypatch.setattr(assistant, "speak", spoken.append)
    dead = Live(alive=False)
    still_dead = Live(alive=False)
    still_dead.prompt = lambda text: False
    voice = Voice(dead, replacement=still_dead)
    ui = UI()
    assistant.push_to_talk_turn(ui, None, voice)
    assert spoken and "again" in spoken[0].lower()
    assert ui.turns and ui.turns[-1][0] == "Apollo"
