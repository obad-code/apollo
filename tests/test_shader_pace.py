"""The ground's pace and its flicker (ui/full/shader.js), run under node: drawn
often enough to move smoothly on any screen without a full-resolution pass
per refresh of a fast one, its band of colour flowing fast, and alive the
way a lit tube is without ever visibly flickering."""
import json
import pathlib
import shutil
import subprocess

import pytest

SHADER = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full" / "shader.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def run(tmp_path, body):
    module = tmp_path / "shader.mjs"
    module.write_text(SHADER.read_text(encoding="utf-8"), encoding="utf-8")
    script = tmp_path / "run.mjs"
    script.write_text("import * as S from './shader.mjs';\n"
                      f"console.log(JSON.stringify({body}));\n", encoding="utf-8")
    out = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@pytest.mark.parametrize("hertz,every", [(60, 1), (75, 1), (120, 2), (144, 2), (165, 3), (240, 4)])
def test_drawn_on_evenly_spaced_frames_at_55_a_second_or_more(tmp_path, hertz, every):
    assert run(tmp_path, f"S.framesPerDraw(1000 / {hertz})") == every
    assert hertz / every >= 55


def test_a_slow_screen_is_drawn_every_frame(tmp_path):
    assert run(tmp_path, "S.framesPerDraw(1000 / 30)") == 1
    assert run(tmp_path, "S.framesPerDraw(0)") == 1          # nothing measured yet


def test_it_is_alive_but_never_visibly_flickers(tmp_path):
    levels = run(tmp_path, """[0, 0.5, 1].flatMap((shimmer) => [0, 1].map((hum) =>
        S.flickerLevel({ shimmer, hum, dip: 0, calm: 1 })))""")
    assert max(levels) - min(levels) > 0                     # a lit tube, not a still
    assert max(levels) - min(levels) <= 0.03                 # ...and nothing you would notice
    assert max(levels) <= 1.0


def test_it_never_dips_far(tmp_path):
    # Every source of it at once is still only a breath: the ground sits under
    # everything on the screen and is looked at for hours.
    worst = run(tmp_path, "S.flickerLevel({ shimmer: 1, hum: 1, dip: 1, calm: 1 })")
    assert 0.94 <= worst < 1.0


def test_asleep_or_asked_for_less_motion_it_is_calmer(tmp_path):
    awake = run(tmp_path, "S.flickerLevel({ shimmer: 1, hum: 1, dip: 0.2, calm: 1 })")
    calm = run(tmp_path, "S.flickerLevel({ shimmer: 1, hum: 1, dip: 0.2, calm: 0.3 })")
    assert 1 - calm < (1 - awake) / 2


def test_the_ground_s_clock(tmp_path):
    # A unit of its own time a second, and half that for anyone who asked
    # for less motion.
    awake, still = run(tmp_path, "[S.driftPerSecond(false), S.driftPerSecond(true)]")
    assert 0 < awake <= 1.2
    assert still == pytest.approx(awake / 2)


def test_the_gradient_flows_fast(tmp_path):
    # It used to sway on loops of a minute and more, too slow to see move.
    # Now the band runs on its own faster clock: its ridge slides across the
    # screen and a wave runs along it, quick enough to watch.
    flow = run(tmp_path, "S.FLOW")
    assert flow >= 6
    assert run(tmp_path, "S.bandPerSecond(false)") == pytest.approx(flow)
    assert run(tmp_path, "S.bandPerSecond(true)") == pytest.approx(flow / 2)


def test_it_slides_far_enough_to_see(tmp_path):
    # Its middle wanders across a good part of the screen, not a sliver of it.
    assert run(tmp_path, "S.WANDER") >= 0.45


def test_the_idle_sky_keeps_its_slow_pace():
    # Asleep, the dusk is meant to be restful: it is not on the fast clock.
    text = SHADER.read_text(encoding="utf-8")
    assert "band(q, t * FLOW)" in text
    assert "dusk(q, t * 0.38, aspect)" in text
