import threading

import assistant


class Recorder:
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


class FakeLive:
    def __init__(self, turns):
        self.turns = list(turns)
        self.quiet_waits = 0

    def next_turn(self, timeout=0.25):
        return self.turns.pop(0) if self.turns else None

    def wait_until_quiet(self, timeout=60):
        self.quiet_waits += 1
        return True


class FakeVoice:
    def __init__(self, live):
        self.live = live
        self.auto_vad = True
        self.ready = True
        self.busy = False

    def open(self, auto_vad=False):
        self.auto_vad = auto_vad
        return True


class Toggle:
    def __init__(self, on):
        self.enabled = threading.Event()
        if on:
            self.enabled.set()


def run(voice, toggle, loops):
    n = {"i": 0}

    def stop():
        n["i"] += 1
        return n["i"] > loops

    ui = Recorder()
    assistant.run_loop(ui, whisper=None, stop=stop, voice=voice, toggle=toggle)
    return ui


def test_idle_always_listening_reports_nothing():
    ui = run(FakeVoice(FakeLive([])), Toggle(True), loops=40)
    assert ui.statuses == []


def test_reply_reports_speaking_then_listening_once():
    live = FakeLive([("what time is it", "It's nine.")])
    ui = run(FakeVoice(live), Toggle(True), loops=20)
    assert ui.turns == [("You", "what time is it"), ("Apollo", "It's nine.")]
    assert ui.statuses == [assistant.SPEAKING, assistant.LISTENING]
    assert live.quiet_waits == 1


def test_toggle_off_reports_idle_once():
    voice = FakeVoice(FakeLive([]))
    ui = run(voice, Toggle(False), loops=30)
    assert ui.statuses == [assistant.IDLE]
    assert voice.auto_vad is False
