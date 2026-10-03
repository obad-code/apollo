"""The crew's dashboard grid (tiler.js), the wheel's geometry (wheel.js) and
what the crew view draws (crewview.js), under node."""
import json
import pathlib
import subprocess

FULL = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full"


def run(tmp_path, body, module="tiler.js", name="T"):
    script = tmp_path / "t.mjs"
    script.write_text(f"import * as {name} from '{(FULL / module).as_uri()}';\n"
                      f"const out = (() => {{ {body} }})();\nconsole.log(JSON.stringify(out));",
                      encoding="utf-8")
    done = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


ITEMS = "[{id:'a',size:'wide'},{id:'b',size:'sm'},{id:'c',size:'sm'},{id:'d',size:'sm'},{id:'e',size:'wide'},{id:'f',size:'sm'}]"


def test_the_tiler_leaves_no_gaps(tmp_path):
    cells = run(tmp_path, f"""
        const places = T.layout({ITEMS}, 4), seen = new Set();
        for (const p of places) for (let y = p.row; y < p.row + p.h; y++)
          for (let x = p.col; x < p.col + p.w; x++) seen.add(`${{x}},${{y}}`);
        return [places.length, seen.size, Math.max(...places.map((p) => p.row + p.h))];""")
    assert cells == [6, 8, 2]


def test_a_wide_widget_is_narrowed_to_one_column(tmp_path):
    widths = run(tmp_path, "return T.layout([{id:'a',size:'wide'},{id:'b',size:'sm'}], 1).map((p) => p.w);")
    assert widths == [1, 1]


def test_a_move_changes_the_order_and_a_no_op_keeps_it(tmp_path):
    got = run(tmp_path, f"""const items = {ITEMS};
        return [T.moveTo(items, 'a', 2).map((i) => i.id), T.moveTo(items, 'a', 0) === items];""")
    assert got == [["b", "c", "a", "d", "e", "f"], True]


def test_choose_keeps_home_when_the_centre_is_in_it(tmp_path):
    got = run(tmp_path, """const home = {left: 0, top: 0, right: 100, bottom: 100};
        return T.choose(home, [{order: ['x'], slot: {left: 200, top: 0, right: 300, bottom: 100}}], 50, 50);""")
    assert got is None


def test_choose_takes_a_slot_the_centre_has_entered(tmp_path):
    got = run(tmp_path, """const home = {left: 0, top: 0, right: 100, bottom: 100};
        return T.choose(home, [{order: ['x'], slot: {left: 200, top: 0, right: 300, bottom: 100}}], 250, 50);""")
    assert got == ["x"]


def test_the_wheel_wraps_and_the_front_is_biggest(tmp_path):
    got = run(tmp_path, """
        const at = (o) => W.place(o, {width: 1200, visible: 5, minScale: .5, arc: 50});
        return [W.wrapped(7, 0, 8), W.wrapped(1, 0, 8), at(0).scale, at(2).scale < at(1).scale,
                at(0).y < at(2).y, W.front(-0.4, 8), W.front(7.6, 8)];""", module="wheel.js", name="W")
    assert got == [-1, 1, 1, True, True, 0, 0]


def test_the_map_shows_every_agent_and_lights_the_busy_one(tmp_path):
    svg = run(tmp_path, """return C.mapMarkup({MONEYPENNY: {working: 'x <y>'}}, 'MONEYPENNY');""",
              module="crewview.js", name="C")
    for key in ("LYLA", "THEIA", "MONEYPENNY", "Q", "APOLLO"):
        assert key in svg
    assert 'class="map-agent busy focus"' in svg and "x &lt;y&gt;" in svg


def test_every_widget_draws_with_no_data(tmp_path):
    drawn = run(tmp_path, "return C.WIDGETS.map((w) => C.widget(w.id, {}).length > 40);",
                module="crewview.js", name="C")
    assert all(drawn)
