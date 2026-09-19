import numpy as np

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
    frames = []

    def start(self):
        pass

    def stop(self):
        return np.zeros(assistant.SAMPLE_RATE, dtype=np.float32)


class Live:
    def __init__(self, heard):
        self.heard, self.allowed, self.discarded = heard, 0, 0

    def begin_turn(self):
        pass

    def end_turn(self):
        pass

    def heard_text(self, **kw):
        return self.heard

    def allow_reply(self):
        self.allowed += 1

    def discard_reply(self):
        self.discarded += 1

    def wait_for_reply(self, timeout=60):
        return True

    def reply_text(self):
        return "Opening Chrome."


class Voice:
    def __init__(self, live):
        self.live, self.capture = live, Capture()


class NoWhisper:
    def transcribe(self, *a, **k):
        raise AssertionError("Whisper must not run when Gemini heard the turn")


class Whisper:
    def transcribe(self, audio, **kw):
        return iter([type("S", (), {"text": " open chrome"})()]), None


def test_gemini_transcript_routes_the_turn_without_whisper():
    ui, live = UI(), Live("open chrome")
    assistant.push_to_talk_turn(ui, NoWhisper(), Voice(live))
    assert ("You", "open chrome") in ui.turns and ("Apollo", "Opening Chrome.") in ui.turns
    assert live.allowed == 1


def test_whisper_is_the_backup_when_gemini_heard_nothing():
    ui, live = UI(), Live("")
    assistant.push_to_talk_turn(ui, Whisper(), Voice(live))
    assert ("You", "open chrome") in ui.turns


def test_agent_name_discards_gemini_reply(monkeypatch):
    ui, live = UI(), Live("hey lyla open chrome")
    asked = []
    monkeypatch.setattr(assistant, "answer_with_agent", lambda name, said, ui: asked.append(name))
    assistant.push_to_talk_turn(ui, NoWhisper(), Voice(live))
    assert live.discarded == 1 and live.allowed == 0 and asked == ["LYLA"]
