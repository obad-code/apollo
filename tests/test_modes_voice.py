"""The display's modes by voice - the ones on the bar along its bottom:
normal, clear (only Apollo and the sign to press Ctrl+Alt), expanded (ultra
mode) and OSIRIS. "Clear mode", "الوضع الموسع": the display comes up if it
has to, and the page switches."""
import pytest

import apollo
import panels
import tools
from test_sleep import make
from tools import Context


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(panels, "PATH", str(tmp_path / "panels.json"))
    panels._memo = None


def asking():
    asked = []
    return asked, Context(display_hook=lambda request: asked.append(request) or True)


@pytest.mark.parametrize("mode", ["normal", "summary", "trading", "agents", "expanded", "osiris"])
def test_each_mode_by_voice(mode):
    asked, ctx = asking()
    result = tools.run("display_mode", {"mode": mode}, ctx)
    assert result == {"ok": True, "mode": mode}
    assert asked == [{"action": "mode", "mode": mode}]


@pytest.mark.parametrize("said,mode", [("ultra", "expanded"), ("Clear", "summary"), ("summary", "summary"),
                                       ("map", "osiris"), ("OSIRIS", "osiris"),
                                       ("Trading", "trading"), ("trade", "trading"),
                                       ("LYLA", "agents")])
def test_what_it_is_called_finds_it(said, mode):
    asked, ctx = asking()
    assert tools.run("display_mode", {"mode": said}, ctx)["mode"] == mode


def test_a_mode_there_is_not_says_so():
    asked, ctx = asking()
    result = tools.run("display_mode", {"mode": "party"}, ctx)
    assert result["ok"] is False and asked == []


def test_with_no_display_to_do_it_on_it_says_so():
    assert tools.run("display_mode", {"mode": "summary"}, Context())["ok"] is False


def test_it_says_what_the_modes_are_in_both_languages():
    description = tools.REGISTRY["display_mode"].description
    for mode in ("normal", "summary", "trading", "agents", "expanded", "osiris"):
        assert mode in description.lower()
    assert any("؀" <= ch <= "ۿ" for ch in description)
    assert "display_mode" in tools.TOOL_LABELS


def test_asked_for_by_voice_the_display_comes_up_in_that_mode(monkeypatch):
    app, log = make(monkeypatch)
    told = []
    app.ui.display = told.append
    app.request_display({"action": "mode", "mode": "summary"})
    app.check_displays()
    assert app.presence.full is True
    assert ("show", apollo.Overlay.FULL) in log
    assert told[-1] == {"action": "mode", "mode": "summary"}
