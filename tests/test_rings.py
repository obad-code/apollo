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
