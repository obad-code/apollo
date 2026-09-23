"""Picking a story on the display by voice: "open story three"."""
import apollo
import assistant
import tools
from tools import Context


def test_open_story_is_registered_and_labelled():
    assert "open_story" in tools.REGISTRY
    assert "open_story" in tools.TOOL_LABELS
    props = tools.REGISTRY["open_story"].parameters["properties"]
    assert props["number"]["type"] == "integer"


def test_it_opens_the_story_and_hands_back_what_it_says():
    asked = []

    def story(number):
        asked.append(number)
        return {"title": "A record weekend", "source": "Example Trade",
                "summary": "The film took $108M.", "number": number}

    result = tools.run("open_story", {"number": 3}, Context(story_hook=story))
    assert asked == [3]
    assert result["ok"] is True
    assert result["title"] == "A record weekend"
    assert result["summary"] == "The film took $108M."


def test_a_number_that_is_not_there_is_said_plainly():
    result = tools.run("open_story", {"number": 40}, Context(story_hook=lambda n: None))
    assert result["ok"] is False and "40" in result["error"]


def test_zero_closes_it():
    asked = []
    result = tools.run("open_story", {"number": 0},
                       Context(story_hook=lambda n: asked.append(n) or {"closed": True}))
    assert asked == [0] and result["ok"] is True


def test_the_tool_runner_reaches_the_page():
    class UI:
        def story(self, number):
            return {"title": "t", "source": "s", "summary": "", "number": number}

    run = assistant.tool_runner(UI())
    assert run("open_story", {"number": 2})["ok"] is True


class FakeWindow:
    def __init__(self):
        self.calls = []

    def evaluate_js(self, js):
        self.calls.append(js)
        return {"title": "t"}


class App:
    """Enough of Apollo for the reporter to open the display."""

    def __init__(self, mode):
        self.overlay = type("O", (), {"mode": mode})()
        self.peeked = 0

    def toggle_peek(self):
        self.peeked += 1
        self.overlay.mode = apollo.Overlay.FULL


def test_asking_for_a_story_opens_the_display_first():
    app = App(apollo.Overlay.ORB)
    window = FakeWindow()
    ui = apollo.WebReporter(window, None, on_status=print, on_turn=print,
                            on_level=print, on_partial=print, app=app)
    assert ui.story(1) == {"title": "t"}
    assert app.peeked == 1
    assert "window.apollo.story(1)" in window.calls[-1]


def test_closing_a_story_does_not_open_the_display():
    app = App(apollo.Overlay.ORB)
    ui = apollo.WebReporter(FakeWindow(), None, on_status=print, on_turn=print,
                            on_level=print, on_partial=print, app=app)
    ui.story(0)
    assert app.peeked == 0
