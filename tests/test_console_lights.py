"""The consoles' readouts and lights (ui/full/consolelights.js), each one
something true: the sources fresh or old, what Apollo is doing, the load;
how long he has been up, how quickly the internet answers, the load and the
card's heat. Run under node."""
import json
import pathlib
import shutil
import subprocess

import pytest

FULL = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def node(tmp_path, expression):
    (tmp_path / "lights.mjs").write_text((FULL / "consolelights.js").read_text(encoding="utf-8"), encoding="utf-8")
    script = tmp_path / "run.mjs"
    script.write_text("import * as L from './lights.mjs';\n"
                      f"console.log(JSON.stringify({expression}));\n", encoding="utf-8")
    done = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_the_sources_are_green_when_fresh_amber_when_old_dark_before_they_are_read(tmp_path):
    lit = node(tmp_path, "L.lights({ now: 10000, stamps: { market: 9990, news: 10000 - 4000, posts: 0 } })")
    assert len(lit) == 18
    assert lit[0]["colour"] == "green" and lit[0]["on"]
    assert lit[1]["colour"] == "amber" and "min old" in lit[1]["title"]
    assert lit[2] == {"colour": "off", "on": False, "blink": False, "title": "Posts: not read yet"}


def test_what_apollo_is_doing_lights_and_blinks_only_while_it_lasts(tmp_path):
    lit = node(tmp_path, "L.lights({ phase: 'speaking', listening: true, lyla: true })")[6:12]
    assert [x["on"] for x in lit] == [False, False, True, True, False, True]
    assert lit[2]["blink"] is True and lit[3]["blink"] is False      # hands-free is steady
    assert lit[5]["colour"] == "blue"


def test_the_load_is_a_meter(tmp_path):
    lit = node(tmp_path, "L.lights({ cpu: 90 })")[12:]
    assert [x["on"] for x in lit] == [True] * 6
    assert [x["colour"] for x in lit] == ["green", "green", "green", "amber", "amber", "red"]
    assert [x["on"] for x in node(tmp_path, "L.lights({ cpu: 20 })")[12:]] == [True, True] + [False] * 4


def test_the_readouts(tmp_path):
    assert node(tmp_path, "[L.uptime(3725), L.linkText(21.4), L.linkText(NaN), L.cpuText(23), L.tempText(47), L.tempText(NaN)]") == [
        "T+01:02:05", "LINK 21ms", "LINK DOWN", "CPU 23%", "GPU 47°C", "GPU —"]


def test_the_bars_are_the_last_six_readings(tmp_path):
    assert node(tmp_path, "L.bars([100, 0, 50])") == [3, 3, 3, 14, 3, 9]
