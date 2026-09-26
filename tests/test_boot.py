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
    script.write_text("import { typed, bootLines, checkLine, readyLine, schedule, typedAt, "
                      "lastLines } from './boot.mjs';\n"
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


STEPS = """[
  {"id": "keys", "label": "API KEYS", "status": "ok", "detail": "all there"},
  {"id": "mic", "label": "MICROPHONE", "status": "fail", "detail": "no microphone (PaError -9996)"},
  {"id": "disk", "label": "DISK", "status": "warn", "detail": "8 GB free"},
  {"id": "voice", "label": "VOICE LINK", "status": "ok", "detail": "gemini"}
]"""


def test_the_checks_are_the_real_ones_and_line_up(tmp_path):
    lines = run(tmp_path, f"bootLines({STEPS})")
    checks = [line for line in lines if " .." in line]
    assert len(checks) == 4
    assert len({len(line) for line in checks}) == 1, checks
    said = "\n".join(lines)
    for part in ("API KEYS", "MICROPHONE", "DISK", "VOICE LINK", "APOLLO/OS"):
        assert part in said, said
    # No blocks: the intro is lines of text on the glass, not boxes.
    assert not any(ch in said for ch in "█▀▄■□▪▫"), said


def test_each_says_how_it_went(tmp_path):
    assert run(tmp_path, "checkLine({label: 'DISK', status: 'ok'})").endswith(" OK")
    assert run(tmp_path, "checkLine({label: 'DISK', status: 'warn'})").endswith(" WARN")
    assert run(tmp_path, "checkLine({label: 'DISK', status: 'fail'})").endswith(" FAIL")


def test_what_went_wrong_is_said_under_it_and_what_went_right_is_not(tmp_path):
    lines = run(tmp_path, f"bootLines({STEPS})")
    mic = next(i for i, line in enumerate(lines) if line.startswith("MICROPHONE"))
    assert "no microphone" in lines[mic + 1]
    keys = next(i for i, line in enumerate(lines) if line.startswith("API KEYS"))
    assert "all there" not in lines[keys + 1]


def test_the_last_line_says_whether_there_is_anything_to_fix(tmp_path):
    assert run(tmp_path, "readyLine({issues: 0, fails: 0})") == "> SYSTEM ONLINE"
    one = run(tmp_path, "readyLine({issues: 1, fails: 0})")
    assert "1 ISSUE " in one + " " and "SYSTEM PANEL" in one
    assert "3 ISSUES" in run(tmp_path, "readyLine({issues: 3, fails: 1})")
    assert run(tmp_path, "readyLine(null)").startswith("> SYSTEM ONLINE")


def test_a_line_types_from_when_it_came_not_from_the_start(tmp_path):
    # Three lines: two there at once, one arriving late - it waits its turn
    # after the one before it, and types from when it came.
    at = run(tmp_path, "schedule([{text: 'A', arrived: 0}, {text: 'B', arrived: 0}, "
                       "{text: 'C', arrived: 5}], 0.1).map((e) => e.at)")
    assert at == [0, 0.1, 5]
    shown = run(tmp_path, "typedAt(schedule([{text: 'HELLO', arrived: 0}, "
                          "{text: 'LATE', arrived: 5}], 0.1), 5.05, 20)")
    assert shown == "HELLO\nL"


def test_the_log_scrolls_like_a_terminal(tmp_path):
    assert run(tmp_path, "lastLines('a\\nb\\nc\\nd', 2)") == "c\nd"
    assert run(tmp_path, "lastLines('a\\nb', 5)") == "a\nb"
