"""Ultra mode's displays: where each one is, how big, whether it is shown,
minimized or the one expanded - the rules the page lays them out by
(ui/full/tiles.js), run under node."""
import json
import pathlib
import shutil
import subprocess

import pytest

TILES = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full" / "tiles.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def run(tmp_path, body):
    module = tmp_path / "tiles.mjs"
    module.write_text(TILES.read_text(encoding="utf-8"), encoding="utf-8")
    script = tmp_path / "run.mjs"
    script.write_text("import * as T from './tiles.mjs';\n"
                      f"console.log(JSON.stringify({body}));\n", encoding="utf-8")
    out = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


EVERY = ["today", "osiris", "feed", "markets", "projects", "ideas", "core", "system", "talks"]


def test_every_display_has_a_place_and_a_name(tmp_path):
    layout = run(tmp_path, "T.defaultLayout()")
    assert sorted(layout["order"]) == sorted(EVERY)
    assert set(layout["items"]) == set(EVERY)
    names = run(tmp_path, "T.NAMES")
    assert set(names) == set(EVERY)


def test_the_default_fills_the_screen_and_nothing_more(tmp_path):
    layout = run(tmp_path, "T.defaultLayout()")
    shown = [layout["items"][d] for d in layout["order"] if layout["items"][d]["shown"]]
    # Twelve columns by six rows, every cell used once: a full screen of work.
    assert sum(item["w"] * item["h"] for item in shown) == 12 * 6
    assert layout["ultra"] is False and layout["focus"] is None
    for wanted in ("osiris", "projects", "ideas", "system", "markets", "feed"):
        assert layout["items"][wanted]["shown"] is True, wanted


def test_the_map_is_the_biggest_thing_on_it(tmp_path):
    items = run(tmp_path, "T.defaultLayout().items")
    area = {d: v["w"] * v["h"] for d, v in items.items() if v["shown"]}
    assert max(area, key=area.get) == "osiris"


def test_anything_that_is_not_a_layout_is_the_default(tmp_path):
    for junk in ("null", "42", "'layout'", "[]", "{ order: 7, items: 'x' }"):
        assert run(tmp_path, f"T.sanitize({junk})") == run(tmp_path, "T.defaultLayout()"), junk


def test_a_saved_layout_is_cleaned_not_trusted(tmp_path):
    layout = run(tmp_path, """T.sanitize({
        ultra: true, focus: 'fireplace',
        order: ['feed', 'feed', 'fireplace', 'markets'],
        items: { feed: { shown: true, w: 40, h: -3, min: 'yes' },
                 markets: { shown: false, w: 'wide', h: 2.6 },
                 fireplace: { shown: true, w: 3, h: 3 } },
        layers: ['cctv', 'cctv', 'javascript:alert(1)', 'cables'] })""")
    assert layout["ultra"] is True
    assert layout["focus"] is None                     # nothing called that
    assert layout["order"][:2] == ["feed", "markets"]  # kept, once each, in its order
    assert sorted(layout["order"]) == sorted(EVERY)    # ...and the rest after them
    assert layout["items"]["feed"] == {"shown": True, "w": 12, "h": 1, "min": False}
    assert layout["items"]["markets"]["shown"] is False
    assert layout["items"]["markets"]["w"] == 3        # "wide" is not a width: the default
    assert layout["items"]["markets"]["h"] == 3        # rounded
    assert "fireplace" not in layout["items"]
    assert layout["layers"] == ["cctv", "cables"]


def test_a_display_that_is_hidden_cannot_be_the_expanded_one(tmp_path):
    layout = run(tmp_path, """T.sanitize({ ultra: true, focus: 'talks',
        items: { talks: { shown: false } } })""")
    assert layout["focus"] is None


def test_moving_one_onto_another_swaps_their_places(tmp_path):
    before = run(tmp_path, "T.defaultLayout().order")
    after = run(tmp_path, "T.swap(T.defaultLayout(), 'osiris', 'system').order")
    i, j = before.index("osiris"), before.index("system")
    assert after[i] == "system" and after[j] == "osiris"
    assert [d for d in after if d not in ("osiris", "system")] == \
           [d for d in before if d not in ("osiris", "system")]


def test_a_display_is_never_resized_off_the_grid(tmp_path):
    assert run(tmp_path, "T.resize(T.defaultLayout(), 'feed', 30, 0).items.feed") == \
        {"shown": True, "w": 12, "h": 1, "min": False}
    assert run(tmp_path, "T.resize(T.defaultLayout(), 'feed', 1, 9).items.feed")["w"] == 2
    assert run(tmp_path, "T.resize(T.defaultLayout(), 'feed', 5, 3).items.feed")["h"] == 3


def test_put_on_the_screen_it_is_expanded_and_shown(tmp_path):
    layout = run(tmp_path, """(() => {
        let l = T.defaultLayout();
        l = T.setMin(l, 'talks', true);
        return T.focus(l, 'talks'); })()""")
    assert layout["ultra"] is True and layout["focus"] == "talks"
    assert layout["items"]["talks"]["shown"] is True
    assert layout["items"]["talks"]["min"] is False
    assert run(tmp_path, "T.focus(T.focus(T.defaultLayout(), 'feed'), null).focus") is None


def test_hiding_or_minimizing_the_expanded_one_puts_the_grid_back(tmp_path):
    assert run(tmp_path, "T.setShown(T.focus(T.defaultLayout(), 'feed'), 'feed', false).focus") is None
    assert run(tmp_path, "T.setMin(T.focus(T.defaultLayout(), 'feed'), 'feed', true).focus") is None
    assert run(tmp_path, "T.setShown(T.focus(T.defaultLayout(), 'feed'), 'ideas', false).focus") == "feed"


def test_leaving_ultra_mode_forgets_what_was_expanded(tmp_path):
    layout = run(tmp_path, "T.setUltra(T.focus(T.defaultLayout(), 'feed'), false)")
    assert layout["ultra"] is False and layout["focus"] is None


def test_nothing_is_changed_in_place(tmp_path):
    same = run(tmp_path, """(() => {
        const l = T.defaultLayout(); const copy = JSON.stringify(l);
        T.swap(l, 'feed', 'core'); T.resize(l, 'feed', 9, 5); T.focus(l, 'talks');
        T.setShown(l, 'ideas', false); T.setMin(l, 'core', true); T.setUltra(l, true);
        T.setLayers(l, []);
        return JSON.stringify(l) === copy; })()""")
    assert same is True


def test_dragging_the_corner_by_a_cell_adds_a_cell(tmp_path):
    grid = "colW: 190, rowH: 200, gap: 16"
    assert run(tmp_path, f"T.spansFor({{ w: 3, h: 2, dx: 206, dy: 0, {grid} }})") == {"w": 4, "h": 2}
    assert run(tmp_path, f"T.spansFor({{ w: 3, h: 2, dx: 60, dy: 150, {grid} }})") == {"w": 3, "h": 3}
    assert run(tmp_path, f"T.spansFor({{ w: 3, h: 2, dx: -2000, dy: -2000, {grid} }})") == {"w": 2, "h": 1}
    assert run(tmp_path, f"T.spansFor({{ w: 3, h: 2, dx: 9000, dy: 9000, {grid} }})") == {"w": 12, "h": 6}


def test_a_size_can_be_picked_by_name(tmp_path):
    sizes = run(tmp_path, "T.SIZES")
    assert list(sizes) == ["S", "M", "L", "XL"]
    areas = [w * h for w, h in sizes.values()]
    assert areas == sorted(areas)


SNAPSHOT = """{
  market: { status: 'NYSE opens in 2h',
            indices: [{ name: 'S&P 500', price: 7650.5, change_pct: 0.17 },
                      { name: 'Nasdaq', price: 26522.5, change_pct: -0.39 }],
            watchlist: [{ symbol: 'AAPL', change_pct: -0.26 }, { symbol: 'NVDA', change_pct: 1.34 }] },
  system: { cpu: 16, gpu: 3, ram: 83 },
  usage: { tokens: 1839, cost: 0.02 },
  projects: { sessions: [1, 2, 3], folders: [1, 2], repos: [1] },
  ideas: { ideas: [1, 2, 3, 4], reminders: [1] },
  talks: [{ time: '14:05' }, { time: '13:10' }],
  weather: { temp: 32, text: 'clear' },
  prayer: { name: 'Asr', at: 0 },
}"""


def test_minimized_each_display_still_says_what_matters(tmp_path):
    said = run(tmp_path, f"""(() => {{ const s = {SNAPSHOT};
        const extra = {{ phase: 'idle', layers: 11,
                         feed: [{{ title: 'Wolverine sells out' }}, {{ title: 'Two' }}],
                         clock: '14:55' }};
        return Object.fromEntries(T.DISPLAYS.map((d) => [d, T.summary(d, s, extra)])); }})()""")
    assert "CPU 16%" in said["system"] and "RAM 83%" in said["system"] and "1,839" in said["system"]
    assert "S&P 500 +0.17%" in said["markets"] and "NVDA +1.34%" in said["markets"]
    assert "3 sessions" in said["projects"] and "2 folders" in said["projects"]
    assert "4 ideas" in said["ideas"] and "1 reminder" in said["ideas"]
    assert "Wolverine sells out" in said["feed"] and "2 stories" in said["feed"]
    assert "11 layers" in said["osiris"]
    assert "14:55" in said["today"] and "32°" in said["today"]
    assert "2 talks" in said["talks"] and "14:05" in said["talks"]
    assert said["core"]
    for display, line in said.items():
        assert "undefined" not in line and "NaN" not in line, (display, line)


def test_minimized_with_nothing_known_it_says_so_rather_than_nothing(tmp_path):
    said = run(tmp_path, """Object.fromEntries(T.DISPLAYS.map((d) => [d, T.summary(d, {}, {})]))""")
    for display, line in said.items():
        assert line and "undefined" not in line and "NaN" not in line, (display, line)
