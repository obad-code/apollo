"""Apollo's shape (ui/full/rings.js), run under node: a circle, drawn as the
old display drew it - rings of lit dots nested inside one another, each
turning the other way from the one inside it, the dots joined round each
ring - and the pace it turns at, eased rather than jumped."""
import json
import math
import pathlib
import shutil
import subprocess

import pytest

RINGS = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full" / "rings.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def run(tmp_path, body):
    module = tmp_path / "rings.mjs"
    module.write_text(RINGS.read_text(encoding="utf-8"), encoding="utf-8")
    script = tmp_path / "run.mjs"
    script.write_text("import * as R from './rings.mjs';\n"
                      f"console.log(JSON.stringify({body}));\n", encoding="utf-8")
    out = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_five_rings_nested_from_a_few_dots_to_many(tmp_path):
    layers = run(tmp_path, "R.LAYERS")
    assert [layer["n"] for layer in layers] == [6, 10, 14, 20, 28]
    radii = [layer["r"] for layer in layers]
    assert radii == sorted(radii) and radii[-1] <= 1.0


def test_each_ring_s_dots_sit_evenly_on_it(tmp_path):
    for i, n in enumerate([6, 10, 14, 20, 28]):
        dots = run(tmp_path, f"R.layerDots({i}, 1234)")
        assert len(dots) == n
        r = run(tmp_path, f"R.LAYERS[{i}].r")
        assert all(math.isclose(math.hypot(d["x"], d["y"]), r, rel_tol=1e-9) for d in dots)
        gaps = {round(math.atan2(b["y"], b["x"]) - math.atan2(a["y"], a["x"]), 6) % round(2 * math.pi, 6)
                for a, b in zip(dots, dots[1:])}
        assert len({round(g, 4) for g in gaps}) == 1


def test_each_ring_turns_the_other_way_from_the_one_inside_it(tmp_path):
    turns = run(tmp_path, """R.LAYERS.map((_, i) => {
        const a = R.layerDots(i, 1000)[0], b = R.layerDots(i, 2000)[0];
        return Math.sign(a.x * b.y - a.y * b.x); })""")
    assert all(t != 0 for t in turns)
    assert all(a == -b for a, b in zip(turns, turns[1:]))


def test_the_inner_rings_turn_faster(tmp_path):
    speeds = [layer["sp"] for layer in run(tmp_path, "R.LAYERS")]
    assert speeds == sorted(speeds, reverse=True)


def test_its_pace_is_eased_not_jumped(tmp_path):
    steps = run(tmp_path, "[R.ease(0, 1, 0.016, 0.3), R.ease(0, 1, 1, 0.3), R.ease(1, 0, 0, 0.3)]")
    assert 0 < steps[0] < 0.1                       # one frame moves it a little
    assert 0.95 < steps[1] <= 1                     # a second gets it nearly there
    assert steps[2] == 1                            # no time, no change


# --- in 3D -----------------------------------------------------------------------
# The same five rings, as the old display's own 3D had them: each a latitude
# of one sphere - the few-dotted ones near the poles, the many-dotted one
# round the equator - still turning against each other, with meridians
# joining them, the whole sphere turning slowly and tipped towards you.

def length(p):
    return math.sqrt(p["x"] ** 2 + p["y"] ** 2 + p["z"] ** 2)


def test_each_ring_is_a_latitude_of_one_sphere(tmp_path):
    for i in range(5):
        dots = run(tmp_path, f"R.sphereDots({i}, 1234)")
        assert all(abs(length(d) - 1) < 1e-9 for d in dots)
        heights = {round(d["y"], 9) for d in dots}
        assert len(heights) == 1                         # all at one latitude


def test_the_few_dotted_rings_sit_near_the_poles_and_the_most_dotted_round_the_middle(tmp_path):
    rims = run(tmp_path, "R.LAYERS.map((_, i) => Math.hypot(R.sphereDots(i, 0)[0].x, R.sphereDots(i, 0)[0].z))")
    counts = [l["n"] for l in run(tmp_path, "R.LAYERS")]
    assert rims[counts.index(28)] == pytest.approx(1.0, abs=0.05)     # the equator
    assert rims[counts.index(6)] < 0.5 and rims[counts.index(10)] < 0.5
    tops = run(tmp_path, "R.LAYERS.map((_, i) => R.sphereDots(i, 0)[0].y)")
    assert (tops[counts.index(6)] < 0) != (tops[counts.index(10)] < 0)   # one pole each


def test_on_the_sphere_they_still_turn_against_each_other(tmp_path):
    turns = run(tmp_path, """R.LAYERS.map((_, i) => {
        const a = R.sphereDots(i, 1000)[0], b = R.sphereDots(i, 2000)[0];
        return Math.sign(a.z * b.x - a.x * b.z); })""")
    assert all(t != 0 for t in turns)
    assert all(a == -b for a, b in zip(turns, turns[1:]))


def test_meridians_run_pole_to_pole(tmp_path):
    line = run(tmp_path, "R.meridian(0, 16)")
    assert all(abs(length(p) - 1) < 1e-9 for p in line)
    assert line[0]["y"] == pytest.approx(-1) and line[-1]["y"] == pytest.approx(1)
    other = run(tmp_path, "R.meridian(3, 16)")
    assert other[8]["x"] != pytest.approx(line[8]["x"])


def test_seen_it_is_tipped_towards_you_and_turning_about_its_axis(tmp_path):
    pole0, pole1, spot0, spot1 = run(tmp_path, """[R.view({ x: 0, y: -1, z: 0 }, 0),
        R.view({ x: 0, y: -1, z: 0 }, 1.2), R.view({ x: 1, y: 0, z: 0 }, 0),
        R.view({ x: 1, y: 0, z: 0 }, 1.2)]""")
    assert pole0 == pytest.approx(pole1)                   # the axis stays put
    assert math.dist((spot0["x"], spot0["y"]), (spot1["x"], spot1["y"])) > 0.3
    assert pole0["y"] < -0.5 and pole0["z"] > 0            # the top pole leans towards you
    assert all(abs(length(p) - 1) < 1e-9 for p in (pole0, spot0, spot1))


# --- the scan line ---------------------------------------------------------------
# One line down the glass, top to bottom, gliding from side to side and back
# and swaying a little as it goes, like a pendulum - never wrapping round or
# jumping, never leaving the bezel.

def scan(tmp_path, times):
    return run(tmp_path, f"{list(times)}.map((c) => R.scanLine(c))")


def test_the_scan_line_runs_top_to_bottom_across_the_glass(tmp_path):
    for s in scan(tmp_path, range(0, 60000, 1500)):
        (x0, y0), (x1, y1) = (s["a"]["x"], s["a"]["y"]), (s["b"]["x"], s["b"]["y"])
        assert math.hypot(x0, y0) == pytest.approx(0.94) and math.hypot(x1, y1) == pytest.approx(0.94)
        assert y0 < -0.5 and y1 > 0.5                                  # top to bottom
        assert abs(x1 - x0) < 0.35 * (y1 - y0)                        # upright, give or take a sway


def test_it_glides_from_side_to_side_and_sways(tmp_path):
    lines = scan(tmp_path, range(0, 40000, 250))
    xs = [s["x"] for s in lines]
    tilts = [s["tilt"] for s in lines]
    assert min(xs) < -0.5 and max(xs) > 0.5 and max(abs(x) for x in xs) < 0.94
    assert min(tilts) < -0.05 and max(tilts) > 0.05 and max(abs(a) for a in tilts) < 0.2


def test_it_moves_smoothly_never_jumping(tmp_path):
    lines = scan(tmp_path, range(0, 40000, 16))                       # a frame at a time
    steps = [abs(b["x"] - a["x"]) for a, b in zip(lines, lines[1:])]
    turns = [abs(b["tilt"] - a["tilt"]) for a, b in zip(lines, lines[1:])]
    assert max(steps) < 0.01 and max(turns) < 0.003
    speeds = [b - a for a, b in zip(steps, steps[1:])]
    assert max(abs(s) for s in speeds) < 0.0005                       # it eases, never lurches
