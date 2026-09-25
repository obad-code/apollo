"""Apollo's shape (ui/full/globe.js), run under node: a globe drawn the way
a wireframe icon draws one - a wide ellipse, meridians pole to pole as
narrower ellipses inside it, parallels straight across - with a four-pointed
star of light at its heart. Seen from over its equator and turning about
its upright axis, so the meridians widen and narrow as they come round,
their near halves in front of their far ones. And the pace of it all eased
rather than jumped."""
import json
import math
import pathlib
import shutil
import subprocess

import pytest

GLOBE = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full" / "globe.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def run(tmp_path, body):
    module = tmp_path / "globe.mjs"
    module.write_text(GLOBE.read_text(encoding="utf-8"), encoding="utf-8")
    script = tmp_path / "run.mjs"
    script.write_text("import * as G from './globe.mjs';\n"
                      f"console.log(JSON.stringify({body}));\n", encoding="utf-8")
    out = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_it_is_wider_than_it_is_tall_like_the_picture(tmp_path):
    assert 0.45 <= run(tmp_path, "G.ASPECT") <= 0.6


def test_at_rest_the_meridians_are_the_picture_s(tmp_path):
    # An upright line through the middle, the outline, and two ellipses
    # between them - at half the width and at most of it.
    widths = {round(abs(h["w"]), 2) for h in run(tmp_path, "G.meridians(0)")}
    assert widths == {0.0, 0.5, 0.87, 1.0}


def test_each_meridian_is_half_a_great_circle_one_side_near_one_far(tmp_path):
    halves = run(tmp_path, "G.meridians(0.37)")
    assert len(halves) == 2 * run(tmp_path, "G.CIRCLES")
    for h in halves:
        assert h["w"] ** 2 + h["near"] ** 2 == pytest.approx(1)      # on one sphere
    for near, far in zip(halves[::2], halves[1::2]):
        assert near["w"] == pytest.approx(-far["w"])                 # opposite sides
        assert near["near"] == pytest.approx(-far["near"])           # one in front


def test_turning_moves_them_and_comes_round_without_a_jump(tmp_path):
    step = math.pi / run(tmp_path, "G.CIRCLES")
    now, later, round_again = run(tmp_path, f"[G.meridians(0), G.meridians(0.2), G.meridians({step})]")
    assert any(abs(a["w"] - b["w"]) > 0.05 for a, b in zip(now, later))
    # One spacing on, the same picture: the turning loops seamlessly.
    assert sorted(round(h["w"], 6) for h in round_again) == sorted(round(h["w"], 6) for h in now)


def test_the_parallels_run_straight_across_inside_the_outline(tmp_path):
    lines = run(tmp_path, "G.parallels()")
    aspect = run(tmp_path, "G.ASPECT")
    assert len(lines) == 3 and any(p["y"] == 0 for p in lines)      # the equator, and one either side
    assert sorted(p["y"] for p in lines)[0] == pytest.approx(-sorted(p["y"] for p in lines)[-1])
    for p in lines:
        # Each end on the outline.
        assert (p["half"]) ** 2 + (p["y"] / aspect) ** 2 == pytest.approx(1)


def test_the_star_has_four_points_pinched_between_them(tmp_path):
    arms = run(tmp_path, "G.star(10)")
    tips = [a["tip"] for a in arms]
    assert sorted((round(x), round(y)) for x, y in tips) == [(-10, 0), (0, -10), (0, 10), (10, 0)]
    for arm in arms:
        assert math.hypot(*arm["pinch"]) < 2.5                     # thin, curved-in arms


def test_its_pace_is_eased_not_jumped(tmp_path):
    steps = run(tmp_path, "[G.ease(0, 1, 0.016, 0.3), G.ease(0, 1, 1, 0.3), G.ease(1, 0, 0, 0.3)]")
    assert 0 < steps[0] < 0.1
    assert 0.95 < steps[1] <= 1
    assert steps[2] == 1
