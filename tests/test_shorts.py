import datetime as dt
import json

import pytest

import shorts


def test_fact_one_day_story_the_next():
    a, b = dt.date(2026, 10, 4), dt.date(2026, 10, 5)
    assert shorts.kind_for(a) != shorts.kind_for(b)
    assert {shorts.kind_for(dt.date(2026, 10, d)) for d in range(1, 6)} == {"fact", "story", "ladder", "paths", "treatment"}


def test_a_script_is_cleaned_up():
    raw = json.dumps({"title": "T", "scenes": [{"say": "Hi", "pose": "moonwalk", "prop": "unicorn"}, {"say": ""}]})
    s = shorts.ask_script("fact", think=lambda p: "here you go " + raw)
    assert len(s["scenes"]) == 1 and s["scenes"][0]["pose"] == "stand" and s["scenes"][0]["prop"] == "none"


def test_no_json_is_an_error():
    with pytest.raises(RuntimeError):
        shorts.ask_script("story", think=lambda p: "sorry")


def test_a_prose_answer_gets_one_firm_retry_and_a_clear_error():
    import json
    answers = iter(["Sure! Here is a short idea about octopuses.", json.dumps({"scenes": [{"say": "Hi"}]})])
    s = shorts.ask_script("fact", think=lambda p: next(answers))
    assert s["scenes"][0]["say"] == "Hi"
    with pytest.raises(RuntimeError, match="It said: I cannot"):
        shorts.ask_script("fact", think=lambda p: "I cannot do that.")


def test_a_weak_hook_gets_one_sharper_rewrite_and_a_worse_one_is_ignored():
    score, band, weakest = shorts.hook_score("So basically today we talk about some stuff.")
    assert band == "WEAK"
    scenes = [{"say": "So basically today we talk about some stuff."}]
    shorts._sharpen_hook(scenes, lambda p: "Your bank quietly takes $34 from you every month - here is why.")
    assert scenes[0]["say"].startswith("Your bank")
    scenes = [{"say": "So basically today we talk about some stuff."}]
    shorts._sharpen_hook(scenes, lambda p: "stuff")
    assert scenes[0]["say"].startswith("So basically")
