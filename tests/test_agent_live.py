"""Commanding LYLA as an agent, in the pipeline card's style: the display
comes up in agents mode, and her card runs for real - what you said, that
she is asking, and the reply with how long it took, or the error. Other
agents, not built yet, are left as they were."""
import anthropic
import pytest

import assistant


class UI:
    def __init__(self):
        self.events, self.asked, self.notes, self.turns = [], [], [], []

    def agent(self, event):
        self.events.append(event)

    def ask_display(self, request):
        self.asked.append(request)
        return True

    def note(self, text):
        self.notes.append(text)

    def turn(self, who, text, visual=None):
        self.turns.append((who, text))

    def status(self, state):
        pass


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setattr(assistant, "speak", lambda text: None)
    monkeypatch.setattr(assistant.journal, "answered", lambda *a, **k: None)


def test_lyla_comes_up_in_agents_mode_and_runs_live(monkeypatch):
    ui = UI()
    monkeypatch.setattr(assistant.agents, "handle", lambda name, text, ui, ask: "Your notes are sorted.")
    assistant.answer_with_agent("LYLA", "hey lyla sort my notes", ui)
    assert ui.asked == [{"action": "mode", "mode": "agents"}]
    stages = [e["stage"] for e in ui.events]
    assert stages == ["received", "asking", "done"]
    assert ui.events[0] == {"agent": "LYLA", "stage": "received", "text": "hey lyla sort my notes"}
    done = ui.events[-1]
    assert done["text"] == "Your notes are sorted." and isinstance(done["ms"], int) and done["ms"] >= 0
    assert ("LYLA", "Your notes are sorted.") in ui.turns


def test_a_failed_run_shows_as_an_error(monkeypatch):
    ui = UI()

    def fail(name, text, ui, ask):
        raise anthropic.APIConnectionError(request=None)
    monkeypatch.setattr(assistant.agents, "handle", fail)
    assistant.answer_with_agent("LYLA", "hey lyla", ui)
    assert [e["stage"] for e in ui.events] == ["received", "asking", "error"]
    assert ui.notes                                            # and it still says so


def test_the_other_agents_are_left_as_they_were(monkeypatch):
    ui = UI()
    monkeypatch.setattr(assistant.agents, "handle", lambda name, text, ui, ask: "ok")
    assistant.answer_with_agent("ATLAS", "atlas do it", ui)
    assert ui.events == [] and ui.asked == []


def test_a_ui_without_the_card_still_gets_its_answer(monkeypatch):
    class Plain:
        turns = []
        def note(self, text): pass
        def turn(self, who, text, visual=None): self.turns.append(text)
        def status(self, state): pass
    monkeypatch.setattr(assistant.agents, "handle", lambda name, text, ui, ask: "done")
    ui = Plain()
    assistant.answer_with_agent("LYLA", "hey lyla", ui)
    assert ui.turns == ["done"]
