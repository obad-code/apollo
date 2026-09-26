"""The normal display as a HUD you arrange (ui/full/hud.js, hud.py): each
panel moved, resized, scaled or hidden, kept as fractions of the screen,
cleaned the same way on both sides of the bridge; a panel let go of lands
on the grid or lines up with another; a corner resizes it, keeping the far
corner put; Apollo and the consoles grow as a whole; and the page opens the
editor, saves what you did and lays it out."""
import json
import pathlib
import shutil
import subprocess

import pytest

import apollo
import hud
import tools

FULL = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


def node(tmp_path, expression):
    (tmp_path / "hud.mjs").write_text((FULL / "hud.js").read_text(encoding="utf-8"), encoding="utf-8")
    script = tmp_path / "run.mjs"
    script.write_text("import * as H from './hud.mjs';\n"
                      f"console.log(JSON.stringify({expression}));\n", encoding="utf-8")
    done = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


EVERY = {p: {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2} for p in hud.PANELS}
MESSY = [
    None, 7, "a", [],
    {"free": True, "items": EVERY},
    {"free": True, "items": {"core": {"x": 0.3, "y": 0.1, "w": 0.4, "h": 0.5}}},        # half a layout
    {"free": True, "items": dict(EVERY, core={"x": 2, "y": -1, "w": 0.33333333, "h": 9, "s": 7, "hidden": 1})},
    {"free": True, "items": dict(EVERY, feed={"x": "0.1", "y": 0.1, "w": 0.2, "h": 0.2})},
    {"free": True, "items": dict(EVERY, scan={"x": 0.12345678, "y": 0.87654321, "w": 0.01, "h": 0.01,
                                                "s": 0.61234, "hidden": True}), "nobody": 1},
    {"free": "yes", "items": EVERY},
]


@needs_node
@pytest.mark.parametrize("raw", MESSY)
def test_both_sides_clean_a_hud_the_same_way(tmp_path, raw):
    assert node(tmp_path, f"H.sanitize({json.dumps(raw)})") == hud.sanitize(raw)


@needs_node
def test_both_sides_know_the_same_panels(tmp_path):
    assert node(tmp_path, "H.PANELS") == list(hud.PANELS)
    assert node(tmp_path, "[H.MIN_W, H.MIN_H, H.SCALE_MIN, H.SCALE_MAX]") == [
        hud.MIN_W, hud.MIN_H, hud.SCALE_MIN, hud.SCALE_MAX]


def test_half_a_layout_is_no_layout_and_nothing_leaves_the_screen():
    assert hud.sanitize(MESSY[5])["free"] is False
    kept = hud.sanitize(MESSY[6])["items"]["core"]
    assert kept["x"] + kept["w"] <= 1 and kept["y"] == 0 and kept["h"] == 1
    assert kept["s"] == hud.SCALE_MAX and kept["hidden"] is False


def test_it_is_kept_between_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(hud, "PATH", str(tmp_path / "hud.json"))
    monkeypatch.setattr(hud, "_memo", None)
    hud.save({"free": True, "items": EVERY})
    monkeypatch.setattr(hud, "_memo", None)
    assert hud.state()["free"] is True and hud.state()["items"]["core"]["w"] == 0.2


def test_nothing_kept_is_the_display_laying_itself_out(tmp_path, monkeypatch):
    monkeypatch.setattr(hud, "PATH", str(tmp_path / "none.json"))
    monkeypatch.setattr(hud, "_memo", None)
    assert hud.state() == {"free": False, "items": {}}


@needs_node
def test_a_panel_let_go_near_another_lines_up_with_it(tmp_path):
    out = node(tmp_path, "H.snap({x:103,y:47,w:300,h:200},[{x:400,y:50,w:200,h:200}],{w:1920,h:1080})")
    assert out["rect"] == {"x": 100, "y": 50, "w": 300, "h": 200}
    assert {"axis": "x", "at": 400} in out["lines"] and {"axis": "y", "at": 50} in out["lines"]


@needs_node
def test_a_panel_let_go_in_the_open_lands_on_the_grid(tmp_path):
    out = node(tmp_path, "H.snap({x:703,y:421,w:300,h:200},[],{w:1920,h:1080})")
    assert out["rect"]["x"] % 8 == 0 and out["rect"]["y"] % 8 == 0 and out["lines"] == []


@needs_node
def test_a_corner_resizes_and_the_far_corner_stays_put(tmp_path):
    out = node(tmp_path, "H.resize({x:400,y:300,w:300,h:200},'nw',-37,-51,{w:1920,h:1080})")["rect"]
    assert out["x"] + out["w"] == 700 and out["y"] + out["h"] == 500
    assert out["x"] % 8 == 0 and out["y"] % 8 == 0


@needs_node
def test_a_whole_panel_keeps_its_shape(tmp_path):
    out = node(tmp_path, "H.resize({x:400,y:300,w:300,h:200},'se',150,10,{w:1920,h:1080},{whole:true})")
    assert out["rect"]["w"] / out["rect"]["h"] == pytest.approx(1.5)
    assert out["k"] == pytest.approx(1.5)


@needs_node
def test_a_scaled_panel_still_covers_its_place(tmp_path):
    b = node(tmp_path, "H.box({x:100,y:100,w:300,h:200},1.25)")
    # Laid out 1/1.25 as large and scaled about its centre: the same 300x200.
    assert b["width"] * 1.25 == pytest.approx(300) and b["height"] * 1.25 == pytest.approx(200)
    assert b["left"] + b["width"] / 2 == pytest.approx(250) and b["top"] + b["height"] / 2 == pytest.approx(200)


@needs_node
def test_the_spring_settles_with_one_small_overshoot(tmp_path):
    path = node(tmp_path, "(() => { let p = 0, v = 0; const out = []; for (let i = 0; i < 90; i++) {"
                          " [p, v] = H.spring(p, v, 100); out.push(p); } return out; })()")
    assert max(path) < 115 and max(path) > 100                # past it, a little
    assert abs(path[-1] - 100) < 0.5                          # and home


def test_apollo_opens_the_editor_by_voice():
    asked = []
    ctx = tools.Context(display_hook=lambda request: asked.append(request) or True)
    assert tools.run("hud_editor", {"action": "edit"}, ctx)["ok"]
    assert tools.run("hud_editor", {"action": "reset"}, ctx)["ok"]
    assert asked == [{"action": "hud_edit", "do": "edit"}, {"action": "hud_edit", "do": "reset"}]
    assert apollo.Apollo._to_be_seen({"action": "hud_edit", "do": "edit"})
    assert not apollo.Apollo._to_be_seen({"action": "hud_edit", "do": "done"})
    assert "عدل الواجهة" in tools.REGISTRY["hud_editor"].description


def test_the_page_edits_saves_and_lays_it_out():
    app = (FULL / "app.js").read_text(encoding="utf-8")
    html = (FULL / "index.html").read_text(encoding="utf-8")
    assert "import * as Hud from './hud.js';" in app
    assert "api.save_hud(state.hud)" in app
    assert "if (asked.action === 'layout' && 'hud' in asked) { state.hud = Hud.sanitize(asked.hud); applyHud(); }" in app
    assert "event.key === 'F2'" in app
    assert 'id="hud-edit"' in html and 'data-console="hud"' in html and 'data-console="scan"' in html


def test_the_consoles_are_in_the_normal_display_under_the_feed():
    css = (FULL / "app.css").read_text(encoding="utf-8")
    assert "body:not(.viewing):not(.ultra):not(.osiris-map) .console { display: block;" in css
    assert "#headlines { anchor-name: --feed; }" in css
    assert "position-anchor: --feed; top: calc(anchor(bottom) + 12px);" in css


def test_the_consoles_fade_on_the_idle_screen():
    css = (FULL / "app.css").read_text(encoding="utf-8")
    assert "body.asleep .console { opacity: 0 !important; pointer-events: none;" in css


def test_the_display_opens_with_the_hud_you_left():
    source = pathlib.Path(apollo.__file__).read_text(encoding="utf-8")
    assert '{"action": "layout", "layout": displays.state(), "hud": hud.state()}' in source
