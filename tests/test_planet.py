"""Apollo as a planet (ui/full/planet.js), run under node: a sphere of dots
spread evenly over it, some of them land and most of them sea, tipped on its
axis and turning, seen from a little above, with a ring of dots round its
middle - and its pace, eased rather than jumped."""
import json
import math
import pathlib
import shutil
import subprocess

import pytest

PLANET = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full" / "planet.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def run(tmp_path, body):
    module = tmp_path / "planet.mjs"
    module.write_text(PLANET.read_text(encoding="utf-8"), encoding="utf-8")
    script = tmp_path / "run.mjs"
    script.write_text("import * as P from './planet.mjs';\n"
                      f"console.log(JSON.stringify({body}));\n", encoding="utf-8")
    out = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def length(p):
    return math.sqrt(p["x"] ** 2 + p["y"] ** 2 + p["z"] ** 2)


def test_the_dots_lie_on_the_sphere(tmp_path):
    dots = run(tmp_path, "P.sphere(400)")
    assert len(dots) == 400
    assert all(abs(length(d) - 1) < 1e-9 for d in dots)


def test_they_are_spread_evenly_not_bunched_at_the_poles(tmp_path):
    dots = run(tmp_path, "P.sphere(300)")
    nearest = []
    for i, a in enumerate(dots):
        nearest.append(min(math.dist((a["x"], a["y"], a["z"]), (b["x"], b["y"], b["z"]))
                           for j, b in enumerate(dots) if j != i))
    assert max(nearest) < 2.2 * min(nearest)
    top = sum(1 for d in dots if d["y"] > 0.5)
    middle = sum(1 for d in dots if abs(d["y"]) < 0.25)
    assert abs(top - 75) < 8 and abs(middle - 75) < 8       # equal areas, equal counts


def test_some_of_it_is_land_and_the_same_land_every_time(tmp_path):
    first, again = run(tmp_path, "[P.sphere(900).map(P.isLand), P.sphere(900).map(P.isLand)]")
    assert first == again
    share = sum(first) / len(first)
    assert 0.22 < share < 0.48


def test_turning_it_moves_the_surface_but_not_the_poles(tmp_path):
    pole0, pole1, spot0, spot1 = run(tmp_path, """[P.project({ x: 0, y: 1, z: 0 }, 0),
        P.project({ x: 0, y: 1, z: 0 }, 1.3), P.project({ x: 1, y: 0, z: 0 }, 0),
        P.project({ x: 1, y: 0, z: 0 }, 1.3)]""")
    assert math.isclose(pole0["x"], pole1["x"], abs_tol=1e-9) and math.isclose(pole0["y"], pole1["y"], abs_tol=1e-9)
    assert math.dist((spot0["x"], spot0["y"]), (spot1["x"], spot1["y"])) > 0.3
    # Tipped on its axis, and seen from a little above: the north pole leans
    # and sits above the middle of the screen, towards you.
    assert pole0["y"] < -0.5 and abs(pole0["x"]) > 0.1 and pole0["z"] > 0


def test_seeing_it_does_not_stretch_it(tmp_path):
    seen = run(tmp_path, "P.sphere(50).map((d) => P.project(d, 0.7))")
    assert all(abs(length(p) - 1) < 1e-9 for p in seen)


def test_a_ring_of_dots_round_its_middle(tmp_path):
    ring = run(tmp_path, "P.ringDots(240)")
    assert len(ring) == 240
    assert all(abs(d["y"]) < 1e-9 for d in ring)              # on the equator's plane
    radii = [math.hypot(d["x"], d["z"]) for d in ring]
    assert min(radii) >= P_RING[0] - 1e-9 and max(radii) <= P_RING[1] + 1e-9
    seen = run(tmp_path, "P.ringDots(240).map((d) => P.project(d, 0))")
    assert any(p["z"] > 0 for p in seen) and any(p["z"] < 0 for p in seen)


P_RING = (1.45, 1.95)


def test_its_pace_is_eased_not_jumped(tmp_path):
    steps = run(tmp_path, "[P.ease(0, 1, 0.016, 0.3), P.ease(0, 1, 1, 0.3), P.ease(1, 0, 0, 0.3)]")
    assert 0 < steps[0] < 0.1
    assert 0.95 < steps[1] <= 1
    assert steps[2] == 1
