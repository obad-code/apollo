"""Ultra mode by voice: "ultra mode", "put the projects on my screen" - the
display comes up if it has to, the page does it - and "hide the ideas"
acting on ultra mode's displays while it is up."""
import pytest

import apollo
import displays
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


def in_ultra_mode():
    layout = displays.default()
    layout["ultra"] = True
    displays.save(layout)


def test_ultra_mode_by_voice():
    asked, ctx = asking()
    result = tools.run("ultra_mode", {"on": True}, ctx)
    assert result["ok"] is True and result["ultra"] is True
    assert asked == [{"action": "ultra", "on": True}]
    description = tools.REGISTRY["ultra_mode"].description
    assert "ultra" in description.lower()
    assert any("؀" <= ch <= "ۿ" for ch in description)   # asked for in Arabic too


def test_out_of_ultra_mode_by_voice():
    asked, ctx = asking()
    assert tools.run("ultra_mode", {"on": False}, ctx)["ultra"] is False
    assert asked == [{"action": "ultra", "on": False}]


def test_with_no_display_to_do_it_on_it_says_so():
    assert tools.run("ultra_mode", {"on": True}, Context())["ok"] is False
    assert tools.run("focus_display", {"display": "news"}, Context())["ok"] is False


@pytest.mark.parametrize("said,display", [
    ("المشاريع", "projects"), ("my ideas", "ideas"), ("OSIRIS", "osiris"),
    ("the news", "feed"), ("gemini and claude", "system"),
])
def test_put_it_on_my_screen(said, display):
    asked, ctx = asking()
    result = tools.run("focus_display", {"display": said}, ctx)
    assert result["ok"] is True and result["display"] == display
    assert asked == [{"action": "focus", "id": display}]


@pytest.mark.parametrize("said", ["all", "everything", "كلها", "the grid", ""])
def test_everything_back_the_way_it_was_laid_out(said):
    asked, ctx = asking()
    result = tools.run("focus_display", {"display": said}, ctx)
    assert result["ok"] is True
    assert asked == [{"action": "focus", "id": None}]


def test_a_display_there_is_not_is_refused_by_name():
    asked, ctx = asking()
    result = tools.run("focus_display", {"display": "the fireplace"}, ctx)
    assert result["ok"] is False and asked == []
    assert "projects" in result["error"] and "OSIRIS" in result["error"]


def test_in_ultra_mode_hide_takes_off_one_of_its_displays():
    in_ultra_mode()
    asked, ctx = asking()
    told = []
    ctx.panels = told.append
    result = tools.run("hide_panel", {"panel": "the ideas"}, ctx)
    assert result["ok"] is True and result["display"] == "ideas"
    assert asked == [{"action": "hide", "id": "ideas"}]
    assert told == [] and all(panels.state().values())    # the normal display untouched


def test_in_ultra_mode_show_puts_one_back():
    in_ultra_mode()
    asked, ctx = asking()
    assert tools.run("show_panel", {"panel": "talks"}, ctx)["ok"] is True
    assert asked == [{"action": "show", "id": "talks"}]


def test_in_ultra_mode_lyla_is_still_the_normal_display_s():
    in_ultra_mode()
    asked, ctx = asking()
    result = tools.run("hide_panel", {"panel": "lyla"}, ctx)
    assert result["ok"] is True and asked == []
    assert panels.visible("lyla") is False


def test_out_of_ultra_mode_hide_is_the_normal_display_s():
    asked, ctx = asking()
    told = []
    ctx.panels = told.append
    assert tools.run("hide_panel", {"panel": "the stocks"}, ctx)["ok"] is True
    assert asked == [] and told and told[-1]["markets"] is False


def test_they_say_what_they_are_doing():
    assert "ultra_mode" in tools.TOOL_LABELS and "focus_display" in tools.TOOL_LABELS
    description = tools.REGISTRY["focus_display"].description
    assert "screen" in description and any("؀" <= ch <= "ۿ" for ch in description)


# --- apollo.py: the watcher does it, and the display comes up for it -----------


def test_asked_for_by_voice_the_display_comes_up_in_ultra_mode(monkeypatch):
    app, log = make(monkeypatch)
    told = []
    app.ui.display = told.append
    app.request_display({"action": "ultra", "on": True})
    app.check_displays()
    assert app.presence.full is True
    assert ("show", apollo.Overlay.FULL) in log
    assert told[-1] == {"action": "ultra", "on": True}


def test_put_on_the_screen_the_display_comes_up_with_it(monkeypatch):
    app, log = make(monkeypatch)
    told = []
    app.ui.display = told.append
    app.request_display({"action": "focus", "id": "projects"})
    app.check_displays()
    assert app.presence.full is True
    assert told[-1] == {"action": "focus", "id": "projects"}


@pytest.mark.parametrize("request_", [{"action": "hide", "id": "ideas"},
                                      {"action": "ultra", "on": False}])
def test_taking_something_away_leaves_the_screen_as_it_is(monkeypatch, request_):
    app, log = make(monkeypatch)
    told = []
    app.ui.display = told.append
    app.request_display(request_)
    app.check_displays()
    assert app.presence.full is False and ("show", apollo.Overlay.FULL) not in log
    assert told == [request_]


def asked(told):
    return [request for request in told if request["action"] != "layout"]


def test_done_in_the_order_asked(monkeypatch):
    app, log = make(monkeypatch)
    told = []
    app.ui.display = told.append
    app.request_display({"action": "ultra", "on": True})
    app.request_display({"action": "focus", "id": "ideas"})
    app.check_displays()
    assert asked(told) == [{"action": "ultra", "on": True}, {"action": "focus", "id": "ideas"}]
    app.check_displays()                              # nothing left over
    assert len(asked(told)) == 2


def test_the_display_comes_up_with_its_layout_before_it_is_asked_anything(monkeypatch):
    app, log = make(monkeypatch)
    told = []
    app.ui.display = told.append
    app.request_display({"action": "focus", "id": "ideas"})
    app.check_displays()
    assert [request["action"] for request in told] == ["layout", "focus"]


def test_the_voice_leaves_it_for_the_watcher(monkeypatch):
    app, log = make(monkeypatch)
    reporter = apollo.WebReporter.__new__(apollo.WebReporter)
    reporter._app = app
    assert reporter.ask_display({"action": "focus", "id": "feed"}) is True
    assert log == []                                   # nothing done on the voice's thread
    told = []
    app.ui.display = told.append
    app.check_displays()
    assert asked(told) == [{"action": "focus", "id": "feed"}]


def test_the_display_opens_with_the_layout_you_left(monkeypatch):
    app, log = make(monkeypatch)
    told = []
    app.ui.display = told.append
    in_ultra_mode()
    app.presence.toggle_peek()                         # Ctrl+`
    app.apply_mode()
    assert told and told[-1]["action"] == "layout"
    assert told[-1]["layout"]["ultra"] is True
