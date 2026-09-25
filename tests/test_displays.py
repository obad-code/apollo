"""Ultra mode's layout, kept: which displays are on the screen, where and how
big, and the words that find each one by voice - in either language."""
import json
import pathlib
import shutil
import subprocess

import pytest

import apollo
import displays

TILES = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full" / "tiles.js"
NODE = shutil.which("node")


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(displays, "PATH", str(tmp_path / "layout.json"))
    displays._memo = None


@pytest.mark.parametrize("said,display", [
    ("put the projects on my screen", "projects"),
    ("حط المشاريع على الشاشة", "projects"),
    ("claude code sessions", "projects"),
    ("my ideas", "ideas"), ("الأفكار", "ideas"), ("reminders", "ideas"),
    ("the news", "feed"), ("الاخبار", "feed"), ("trump's posts", "feed"),
    ("stocks", "markets"), ("الأسهم", "markets"), ("my watchlist", "markets"),
    ("osiris", "osiris"), ("اوزيرس", "osiris"), ("the world map", "osiris"),
    ("the system", "system"), ("gemini and claude usage", "system"), ("العدادات", "system"),
    ("today", "today"), ("الطقس", "today"), ("the weather", "today"),
    ("apollo", "core"), ("أبولو", "core"), ("the ring", "core"),
    ("my conversations", "talks"), ("المحادثات", "talks"),
])
def test_found_by_what_you_call_it(said, display):
    assert displays.resolve(said) == display


def test_apollo_s_name_in_a_sentence_is_not_a_display():
    # "Apollo, put the news up" is about the news: the name is who is asked.
    assert displays.resolve("apollo put the news up") == "feed"


def test_nothing_is_found_for_something_that_is_not_there():
    assert displays.resolve("the fireplace") is None
    assert displays.resolve("") is None
    assert displays.resolve(None) is None


def test_refused_with_the_ones_there_are():
    result = displays.unknown("the fireplace")
    assert result["ok"] is False
    for name in ("projects", "ideas", "OSIRIS", "feed"):
        assert name in result["error"]


def test_with_nothing_saved_it_is_the_default():
    assert displays.state() == displays.default()
    assert displays.ultra() is False


def test_kept_across_a_restart():
    layout = displays.default()
    layout["ultra"] = True
    layout["items"]["talks"]["shown"] = True
    layout["order"] = ["talks"] + [d for d in layout["order"] if d != "talks"]
    displays.save(layout)
    displays._memo = None                          # as if Apollo restarted
    kept = displays.state()
    assert kept["ultra"] is True and displays.ultra() is True
    assert kept["items"]["talks"]["shown"] is True
    assert kept["order"][0] == "talks"


def test_the_stocks_stay_folded_across_a_restart():
    layout = displays.default()
    assert layout["folded"] is False
    layout["folded"] = True
    displays.save(layout)
    displays._memo = None                          # as if Apollo restarted
    assert displays.state()["folded"] is True


def test_a_file_that_is_not_a_layout_is_the_default(tmp_path):
    pathlib.Path(displays.PATH).write_text("{not json", encoding="utf-8")
    assert displays.state() == displays.default()


def test_what_is_saved_is_cleaned_first():
    saved = displays.save({"ultra": True, "order": ["feed", "fireplace"],
                           "items": {"feed": {"shown": True, "w": 99, "h": 0}},
                           "layers": ["cctv", "file:///etc"]})
    assert saved["items"]["feed"]["w"] == 12 and saved["items"]["feed"]["h"] == 1
    assert "fireplace" not in saved["order"] and saved["order"][0] == "feed"
    assert saved["layers"] == ["cctv"]
    on_disk = json.loads(pathlib.Path(displays.PATH).read_text(encoding="utf-8"))
    assert on_disk == saved


def test_the_page_keeps_its_layout_through_the_bridge():
    layout = displays.default()
    layout["ultra"] = True
    assert apollo.Api(lambda: None).save_layout(layout) is True
    assert displays.ultra() is True
    assert apollo.Api(lambda: None).save_layout("not a layout") is True
    assert displays.state() == displays.default()


def node(tmp_path, body):
    module = tmp_path / "tiles.mjs"
    module.write_text(TILES.read_text(encoding="utf-8"), encoding="utf-8")
    script = tmp_path / "run.mjs"
    script.write_text("import * as T from './tiles.mjs';\n"
                      f"console.log(JSON.stringify({body}));\n", encoding="utf-8")
    out = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_same_default_as_the_page(tmp_path):
    assert node(tmp_path, "T.defaultLayout()") == displays.default()
    assert node(tmp_path, "T.LAYERS") == list(displays.LAYERS)


RAW = [
    None, 7, "x", [], {},
    {"ultra": True, "focus": "feed", "order": ["feed", "feed", "core"],
     "items": {"feed": {"shown": True, "w": 2.5, "h": 3.5, "min": True},
               "core": {"shown": "yes", "w": True, "h": None},
               "talks": {"shown": True, "w": "4", "h": [2]}},
     "layers": ["cables", "cables", "nope", "cctv"]},
    {"ultra": 1, "focus": "talks", "items": {"talks": {"shown": True, "w": -8, "h": 70}}},
    {"focus": ["feed"], "order": "feed", "layers": "cctv"},
    {"folded": True}, {"folded": "yes"}, {"folded": 1},
]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("raw", RAW, ids=lambda r: json.dumps(r)[:40])
def test_cleaned_the_same_way_here_as_on_the_page(tmp_path, raw):
    assert node(tmp_path, f"T.sanitize({json.dumps(raw)})") == displays.sanitize(raw)
