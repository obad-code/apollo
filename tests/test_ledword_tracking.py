"""APOLLO with room between its letters: each letter keeps the place the font
gives it, and every gap after the first letter gets the same extra space."""
import json
import pathlib
import shutil
import subprocess

import pytest

LEDWORD = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full" / "ledword.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def spaced(tmp_path, prefixes, widths, full, gap):
    module = tmp_path / "ledword.mjs"
    module.write_text(LEDWORD.read_text(encoding="utf-8"), encoding="utf-8")
    script = tmp_path / "run.mjs"
    script.write_text(
        "import { spaced } from './ledword.mjs';\n"
        f"console.log(JSON.stringify(spaced({json.dumps(prefixes)}, {json.dumps(widths)}, "
        f"{full}, {gap})));\n", encoding="utf-8")
    out = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_every_gap_gets_the_same_extra_room(tmp_path):
    got = spaced(tmp_path, [0, 10, 21], [10, 11, 9], 30, 5)
    assert [slot["x"] for slot in got["slots"]] == [0, 15, 31]
    assert [slot["w"] for slot in got["slots"]] == [10, 11, 9]


def test_the_word_is_wider_by_one_gap_less_than_it_has_letters(tmp_path):
    got = spaced(tmp_path, [0, 10, 21], [10, 11, 9], 30, 5)
    assert got["width"] == 30 + 2 * 5


def test_no_tracking_is_the_font_as_it_comes(tmp_path):
    got = spaced(tmp_path, [0, 10, 21], [10, 11, 9], 30, 0)
    assert [slot["x"] for slot in got["slots"]] == [0, 10, 21]
    assert got["width"] == 30
