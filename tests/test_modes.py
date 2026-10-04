"""The display's modes (ui/full/modes.js), run under node: normal, clear,
expanded and OSIRIS, one at a time, and the steps from whichever is on to
whichever is asked for - leaving before arriving, so the map and ultra mode
never fight over the screen."""
import json
import pathlib
import shutil
import subprocess

import pytest

MODES = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full" / "modes.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def run(tmp_path, body):
    (tmp_path / "modes.mjs").write_text(MODES.read_text(encoding="utf-8"), encoding="utf-8")
    script = tmp_path / "run.mjs"
    script.write_text("import * as M from './modes.mjs';\n"
                      f"console.log(JSON.stringify({body}));\n", encoding="utf-8")
    out = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def flags(**on):
    return json.dumps({"ultra": False, "osiris": False, "view": "normal", **on})


def test_the_modes_on_the_bar(tmp_path):
    assert run(tmp_path, "M.MODES.map((m) => m.id)") == ["normal", "summary", "trading", "agents",
                                                        "expanded", "osiris"]


@pytest.mark.parametrize("on,mode", [({}, "normal"), ({"view": "summary"}, "summary"),
                                     ({"view": "trading"}, "trading"), ({"view": "agents"}, "agents"),
                                     ({"ultra": True}, "expanded"), ({"osiris": True}, "osiris"),
                                     ({"ultra": True, "view": "summary"}, "expanded")])
def test_which_is_on(tmp_path, on, mode):
    assert run(tmp_path, f"M.current({flags(**on)})") == mode


@pytest.mark.parametrize("on,wanted,steps", [
    ({}, "summary", [["view", "summary"]]),
    ({"view": "summary"}, "normal", [["view", "normal"]]),
    ({"view": "summary"}, "trading", [["view", "trading"]]),
    ({"view": "trading"}, "agents", [["view", "agents"]]),
    ({"ultra": True}, "summary", [["ultra", False], ["view", "summary"]]),
    ({"ultra": True}, "trading", [["ultra", False], ["view", "trading"]]),
    ({"view": "summary"}, "expanded", [["view", "normal"], ["ultra", True]]),
    ({"ultra": True}, "osiris", [["ultra", False], ["osiris", True]]),
    ({"osiris": True}, "summary", [["osiris", False], ["view", "summary"]]),
    ({"osiris": True}, "agents", [["osiris", False], ["view", "agents"]]),
    ({"view": "trading"}, "osiris", [["view", "normal"], ["osiris", True]]),
    ({"osiris": True}, "expanded", [["ultra", True]]),        # the map goes with it, as a tile
    ({}, "normal", []),
    ({"view": "summary"}, "summary", []),
])
def test_the_steps_between_them(tmp_path, on, wanted, steps):
    assert run(tmp_path, f"M.plan({flags(**on)}, {json.dumps(wanted)})") == steps


def test_a_mode_there_is_not_changes_nothing(tmp_path):
    assert run(tmp_path, f"M.plan({flags(view='clear')}, 'party')") == []
