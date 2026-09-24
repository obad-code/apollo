"""The name arrives scrambled, the way the scramble-text component does it:
every letter a random glyph, settling into the word from the left."""
import json
import pathlib
import shutil
import subprocess

import pytest

LEDWORD = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full" / "ledword.js"
NODE = shutil.which("node")
CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?/~`░▒▓█▀▄■□▪▫●○◆◇◈◊※†‡"


def scrambled(tmp_path, cases):
    module = tmp_path / "ledword.mjs"
    module.write_text(LEDWORD.read_text(encoding="utf-8"), encoding="utf-8")
    script = tmp_path / "run.mjs"
    script.write_text(
        "import { scrambled } from './ledword.mjs';\n"
        f"const cases = {json.dumps(cases)};\n"
        "console.log(JSON.stringify(cases.map(([t, p]) => scrambled(t, p))));\n",
        encoding="utf-8")
    out = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def test_at_the_start_no_letter_has_settled(tmp_path):
    (text,) = scrambled(tmp_path, [["APOLLO", 0]])
    assert len(text) == 6
    assert all(ch in CHARS for ch in text), text


def test_halfway_the_first_half_has(tmp_path):
    (text,) = scrambled(tmp_path, [["APOLLO", 0.5]])
    assert text[:3] == "APO"
    assert all(ch in CHARS for ch in text[3:]), text


def test_at_the_end_it_is_the_word(tmp_path):
    assert scrambled(tmp_path, [["APOLLO", 1]]) == ["APOLLO"]


def test_a_space_stays_a_space(tmp_path):
    (text,) = scrambled(tmp_path, [["HI THERE", 0]])
    assert text[2] == " "


def test_a_letter_settles_only_once_its_share_has_passed(tmp_path):
    """Two fifths of six letters is 2.4: two have settled, the third has not."""
    (text,) = scrambled(tmp_path, [["APOLLO", 0.4]])
    assert text[:2] == "AP"
    assert text[2] in CHARS, text
