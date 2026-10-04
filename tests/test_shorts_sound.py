import wave

import numpy as np
import pytest

import shorts
import shorts_scenes
import shorts_sfx


def test_every_accent_and_place_makes_sound():
    for fn in shorts_sfx.ACCENTS.values():
        x = fn()
        assert len(x) > 100 and np.max(np.abs(x)) > 0.1
    for place in shorts_scenes.NAMES:
        assert len(shorts_sfx.ambient(place, 1.0)) == shorts_sfx.SR


def test_mix_lays_sound_under_the_voice(tmp_path):
    voice = tmp_path / "v.wav"
    shorts_sfx.write_wav(str(voice), np.zeros(shorts_sfx.SR, dtype=np.float32))
    out = shorts_sfx.mix(str(voice), str(tmp_path / "o.wav"), "sea", [(0.0, "whoosh")])
    with wave.open(out) as w:
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    assert len(data) == shorts_sfx.SR and np.max(np.abs(data)) > 500


def test_script_scenes_get_places_and_sound():
    import json
    raw = json.dumps({"scenes": [{"say": "a", "bg": "sea", "show": "env", "sfx": "boom"},
                                 {"say": "b", "bg": "mars", "show": "env", "sfx": "nope"}]})
    s = shorts.ask_script("fact", think=lambda p: raw)["scenes"]
    assert s[0]["bg"] == "sea" and s[0]["show"] == "env" and s[0]["sfx"] == "boom"
    assert s[1]["bg"] == "" and s[1]["show"] == "man" and s[1]["sfx"] == ""


def test_every_place_draws():
    for name in shorts_scenes.NAMES:
        shorts.frame({"pose": "stand", "prop": "none", "cam": "wide", "bg": name, "show": "man", "caption": "x"}, 0.5, 0.5, "t")


def test_every_world_has_places_and_people():
    for name, (places, people) in shorts.WORLDS.items():
        assert all(p in shorts_scenes.NAMES for p in places), name
        assert all(p in shorts.shorts_hero.SIDES for p in people), name


def test_every_prop_and_side_character_draws():
    hero = shorts.shorts_hero.hero_for("t")
    for prop in shorts.PROPS:
        shorts.frame({"pose": "stand", "prop": prop, "cam": "wide", "bg": "room", "show": "man", "caption": "x", "_hero": hero}, 0.5, 0.5, "t")
    for side in shorts.shorts_hero.SIDES:
        shorts.frame({"pose": "sad", "prop": "none", "cam": "wide", "bg": "room", "show": "man", "friend": side, "caption": "x", "_hero": hero}, 0.5, 0.5, "t")
