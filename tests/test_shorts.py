import datetime as dt
import json

import pytest

import shorts


def test_fact_one_day_story_the_next():
    a, b = dt.date(2026, 10, 4), dt.date(2026, 10, 5)
    assert shorts.kind_for(a) != shorts.kind_for(b)
    assert {shorts.kind_for(dt.date(2026, 10, d)) for d in (4, 5, 6)} == {"fact", "story", "ladder"}


def test_a_script_is_cleaned_up():
    raw = json.dumps({"title": "T", "scenes": [{"say": "Hi", "pose": "moonwalk", "prop": "unicorn"}, {"say": ""}]})
    s = shorts.ask_script("fact", think=lambda p: "here you go " + raw)
    assert len(s["scenes"]) == 1 and s["scenes"][0]["pose"] == "stand" and s["scenes"][0]["prop"] == "none"


def test_no_json_is_an_error():
    with pytest.raises(RuntimeError):
        shorts.ask_script("story", think=lambda p: "sorry")
