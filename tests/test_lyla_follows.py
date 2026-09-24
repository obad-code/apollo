"""Click the display and LYLA comes after the pointer for a while, a little
behind it, then goes back to what she was doing."""
import json
import pathlib
import shutil
import subprocess

import pytest

LYLA = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full" / "lyla.js"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def run(tmp_path, body):
    (tmp_path / "lyla.mjs").write_text(LYLA.read_text(encoding="utf-8"), encoding="utf-8")
    script = tmp_path / "run.mjs"
    script.write_text(
        "globalThis.window = { innerWidth: 1600, innerHeight: 900, devicePixelRatio: 1 };\n"
        "globalThis.document = { getElementById: () => null };\n"
        "import { Lyla } from './lyla.mjs';\n"
        "const lyla = new Lyla(null, { sound: () => {} });\n"
        "lyla.ly = { st: 'read', until: 1e12, x: 20, y: 200, face: 1, chatQ: ['hi'] };\n"
        + body, encoding="utf-8")
    out = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_a_click_brings_her_after_the_pointer(tmp_path):
    got = run(tmp_path, """
      lyla.follow(1200, 300, 10);
      const start = { x: lyla.ly.x, y: lyla.ly.y };
      for (let i = 0; i < 400; i++) lyla._chase(i * 16, 16);
      console.log(JSON.stringify({ start, now: { x: lyla.ly.x, y: lyla.ly.y }, st: lyla.ly.st,
                                   face: lyla.ly.face }));
    """)
    # 1200/4 = 300 in her grid; she stops a little behind and below it.
    assert got["st"] == "chase"
    assert abs(got["now"]["x"] - 290) < 3 and abs(got["now"]["y"] - 81) < 3
    assert got["face"] == 1


def test_she_keeps_following_as_the_pointer_moves(tmp_path):
    got = run(tmp_path, """
      lyla.follow(1200, 300, 30);            // long enough for both legs
      for (let i = 0; i < 400; i++) lyla._chase(i * 16, 16);
      lyla.pointer(200, 400);
      for (let i = 400; i < 800; i++) lyla._chase(i * 16, 16);
      console.log(JSON.stringify({ x: lyla.ly.x, face: lyla.ly.face }));
    """)
    assert abs(got["x"] - 40) < 3
    assert got["face"] == -1 or got["x"] < 50


def test_when_the_time_is_up_she_goes_back_to_her_day(tmp_path):
    got = run(tmp_path, """
      lyla.follow(1200, 300, 0.5);
      const t0 = performance.now();
      lyla._chase(t0, 16);
      const during = lyla.ly.st;
      lyla._chase(t0 + 1000, 16);
      console.log(JSON.stringify({ during, after: lyla.ly.st, until: lyla.ly.until, t: t0 + 1000,
                                   chasing: lyla.chase !== null }));
    """)
    assert got["during"] == "chase"
    assert got["after"] != "chase" and got["until"] <= got["t"] and got["chasing"] is False
