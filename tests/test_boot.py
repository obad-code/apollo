"""As Apollo comes up, an old machine boots: its checks typed out line by
line on a green tube, then the name, then the prompt."""
import json
import pathlib
import shutil
import subprocess

import pytest

BOOT = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full" / "boot.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def run(tmp_path, body):
    module = tmp_path / "boot.mjs"
    module.write_text(BOOT.read_text(encoding="utf-8"), encoding="utf-8")
    script = tmp_path / "run.mjs"
    script.write_text("import { typed, bootLines } from './boot.mjs';\n"
                      f"console.log(JSON.stringify({body}));\n", encoding="utf-8")
    out = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


PACE = "{ start: 0.1, gap: 0.5, rate: 10 }"


def test_nothing_shows_before_it_starts(tmp_path):
    assert run(tmp_path, f"typed(['HELLO', 'THERE'], 0.05, {PACE})") == ""


def test_a_line_types_out_letter_by_letter(tmp_path):
    assert run(tmp_path, f"typed(['HELLO', 'THERE'], 0.1 + 0.25, {PACE})") == "HE"


def test_the_next_line_waits_its_turn(tmp_path):
    quick = "{ start: 0.1, gap: 0.5, rate: 20 }"      # the first line is done at 0.25s
    assert run(tmp_path, f"typed(['HELLO', 'THERE'], 0.1 + 0.49, {quick})") == "HELLO"
    assert run(tmp_path, f"typed(['HELLO', 'THERE'], 0.1 + 0.5 + 0.05, {quick})") == "HELLO\nT"


def test_in_the_end_it_is_all_there(tmp_path):
    assert run(tmp_path, f"typed(['HELLO', 'THERE'], 60, {PACE})") == "HELLO\nTHERE"


def test_the_checks_line_up_and_name_apollo_s_own_parts(tmp_path):
    lines = run(tmp_path, "bootLines()")
    checks = [line for line in lines if " .." in line]
    assert len(checks) >= 4
    assert len({len(line) for line in checks}) == 1, checks
    said = "\n".join(lines)
    for part in ("VOICE", "MARKET", "PRIVATE EYE", "MEMORY"):
        assert part in said, said
    # No blocks: the intro is lines of text on the glass, not boxes.
    assert not any(ch in said for ch in "█▀▄■□▪▫"), said
