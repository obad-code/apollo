"""The feed, fuller (ui/full/feed.js), run under node: each story with a
picture beside it - its own, or its source's initials on a tile where it
came without one - a two-line gist, and what it is about; and over the list
a line saying how much is in it, from how many places, and how new."""
import json
import pathlib
import shutil
import subprocess

import pytest

FEED = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full" / "feed.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def run(tmp_path, body):
    (tmp_path / "feed.mjs").write_text(FEED.read_text(encoding="utf-8"), encoding="utf-8")
    script = tmp_path / "run.mjs"
    script.write_text("import * as F from './feed.mjs';\n"
                      f"console.log(JSON.stringify({body}));\n", encoding="utf-8")
    out = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@pytest.mark.parametrize("source,letters", [
    ("Truth Social", "TS"),
    ("Murphy's Multiverse", "MM"),            # not "MS": the apostrophe is not a word break
    ("Investor's Business Daily", "IB"),
    ("GameGPU", "GG"),                        # one word in capitals: its capitals
    ("levelup", "LE"),                        # one word: its first two letters
    ("Notebookcheck", "NO"),
    ("  ", ""),
    ("", ""),
])
def test_a_source_s_initials(tmp_path, source, letters):
    assert run(tmp_path, f"F.initials({json.dumps(source)})") == letters


def test_initials_for_a_source_in_arabic(tmp_path):
    assert run(tmp_path, "F.initials('العربية نت')") == "ان"


def test_what_a_story_is_about_is_said_only_where_the_chip_does_not(tmp_path):
    shown = run(tmp_path, """[F.topicTag('movies', 'all'), F.topicTag('gaming', 'all'),
        F.topicTag('movies', 'movies'), F.topicTag('posts', 'all'), F.topicTag('private eye', 'all')]""")
    # "Private Eye" is already flagged on its row.
    assert shown == ["movies", "gaming", "", "post", ""]


def test_the_line_over_the_list(tmp_path):
    line = run(tmp_path, """F.summaryLine([
        { source: "Murphy's Multiverse", age: '14m ago' }, { source: 'Truth Social', age: '25m ago' },
        { source: 'truth social', age: '8h ago' }, { source: 'LevelUp', age: '1h ago' }])""")
    assert line == "4 stories · 3 sources · newest 14m ago"


def test_one_story_is_one_story(tmp_path):
    assert run(tmp_path, "F.summaryLine([{ source: 'IGN', age: '2m ago' }])") == \
        "1 story · 1 source · newest 2m ago"


def test_nothing_in_it_says_nothing(tmp_path):
    assert run(tmp_path, "F.summaryLine([])") == ""
