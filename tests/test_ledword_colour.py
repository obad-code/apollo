"""APOLLO in colour, and steady (ui/full/ledword.js), run under node: the word
takes its colours from left to right across its width, and the display's
wordmark burns steadily - no dips, no band rolling down it - where the intro's
old tube may still misbehave."""
import json
import pathlib
import shutil
import subprocess

import pytest

LEDWORD = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full" / "ledword.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def run(tmp_path, body):
    module = tmp_path / "ledword.mjs"
    module.write_text(LEDWORD.read_text(encoding="utf-8"), encoding="utf-8")
    script = tmp_path / "run.mjs"
    script.write_text("import * as L from './ledword.mjs';\n"
                      f"console.log(JSON.stringify({body}));\n", encoding="utf-8")
    out = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


STOPS = "[[0, 240, 255], [150, 140, 255], [255, 120, 210]]"


def test_the_word_starts_and_ends_on_its_first_and_last_colour(tmp_path):
    first, last = run(tmp_path, f"[L.tint({STOPS}, 0), L.tint({STOPS}, 1)]")
    assert first == [0, 240, 255]
    assert last == [255, 120, 210]


def test_between_two_colours_it_is_part_of_each(tmp_path):
    middle, quarter = run(tmp_path, f"[L.tint({STOPS}, 0.5), L.tint({STOPS}, 0.25)]")
    assert middle == [150, 140, 255]
    assert quarter == [75, 190, 255]


def test_outside_the_word_it_keeps_the_nearest_colour(tmp_path):
    before, after = run(tmp_path, f"[L.tint({STOPS}, -0.3), L.tint({STOPS}, 1.4)]")
    assert before == [0, 240, 255]
    assert after == [255, 120, 210]


def test_a_steady_word_never_dips(tmp_path):
    # The same draws that would dip the intro's tube leave the wordmark lit.
    steady = run(tmp_path, "[0, 0.01, 0.5, 0.99].flatMap((a) => [0, 1].map((b) => L.flickerOf(a, b, true)))")
    assert min(steady) >= 0.95
    assert max(steady) <= 1.0


def test_the_old_tube_still_dips_now_and_then(tmp_path):
    dip, lit = run(tmp_path, "[L.flickerOf(0.01, 0.5, false), L.flickerOf(0.5, 0.5, false)]")
    assert dip < 0.6
    assert 0.87 <= lit <= 1.0
