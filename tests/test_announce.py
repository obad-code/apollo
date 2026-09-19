import assistant


class UI:
    def __init__(self):
        self.statuses, self.turns = [], []

    def status(self, s):
        self.statuses.append(s)

    def turn(self, who, text, visual=None):
        self.turns.append((who, text))


class Live:
    def __init__(self, ok=True):
        self.ok, self.prompts = ok, []

    def prompt(self, text):
        self.prompts.append(text)
        return self.ok

    def wait_for_audio(self, timeout=10):
        return True

    def wait_until_quiet(self, timeout=60):
        return True


class Voice:
    def __init__(self, live, auto_vad=False):
        self.live, self.auto_vad = live, auto_vad


def test_reminder_is_spoken_by_gemini(monkeypatch):
    ui, live = UI(), Live()
    assistant.fire_reminder(ui, Voice(live), {"text": "stretch"}, late=False)
    assert "stretch" in live.prompts[0]
    assert ui.statuses == [assistant.SPEAKING, assistant.IDLE]


def test_reminder_falls_back_to_local_voice(monkeypatch):
    spoken = []
    monkeypatch.setattr(assistant, "speak", spoken.append)
    ui = UI()
    assistant.fire_reminder(ui, Voice(Live(ok=False)), {"text": "stretch"}, late=True)
    assert spoken == ["Reminder: stretch"]
    assert ui.turns == [("Apollo", "Reminder: stretch")]


def test_always_listening_returns_to_listening(monkeypatch):
    ui = UI()
    assistant.announce(ui, Voice(Live(), auto_vad=True), "say hi", "Hi")
    assert ui.statuses == [assistant.SPEAKING, assistant.LISTENING]
