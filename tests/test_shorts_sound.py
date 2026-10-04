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


def test_wealth_kinds_split_stat_tags_and_anchor():
    import json
    raw = json.dumps({"title": "T", "description": "hook", "tags": ["wealth", "pov finance"] + ["x" * 40] * 30,
                      "scenes": [{"say": "a", "bg": "room", "tier": 1, "stat": {"text": "$34", "tone": "loss"}, "arrow": "down", "split": [3, 1]},
                                 {"say": "b", "bg": "office", "tier": 3}, {"say": "c", "bg": "bank", "tier": 4, "newcomer": True}]})
    data = shorts.ask_script("paths", think=lambda p: raw)
    sc = data["scenes"]
    assert sc[0]["split"] == [3, 1] and sc[0]["stat"] == {"text": "$34", "tone": "loss"} and sc[0]["arrow"] == "down"
    assert sc[-1]["bg"] == sc[0]["bg"] == "room" and sc[-1]["newcomer"]       # opens and closes on the same moment
    assert sc[1]["tier"] == 3                                                  # the tiers stay in a wealth story
    assert len(", ".join(data["tags"])) <= 500 and "Disclaimer" in data["description"]
    other = shorts.ask_script("fact", think=lambda p: raw)["scenes"]
    assert {s["tier"] for s in other} == {1} and not any(s["grade"] for s in other)   # one look for non-wealth stories


def test_every_stat_split_and_role_draws():
    hero = shorts.shorts_hero.hero_for("t")
    for extra in ({"stat": {"text": "$9,412", "tone": "gain"}, "arrow": "up"}, {"split": [1, 4]}, {"friend": "elder", "tier": 4}, {"friend": "partner"}):
        shorts.frame({"pose": "stand", "prop": "none", "cam": "wide", "bg": "city", "show": "man", "caption": "x", "_hero": hero, **extra}, 0.5, 0.5, "t")


def test_claude_writes_when_asked_and_gemini_voice_makes_a_wav(tmp_path, monkeypatch):
    import sys
    import types
    import wave
    assistant = types.SimpleNamespace(ask_once=None)
    monkeypatch.setitem(sys.modules, "assistant", assistant)          # the real one needs Windows
    monkeypatch.setattr(shorts, "WRITER", "claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    seen = {}
    monkeypatch.setattr(assistant, "ask_once", lambda system, prompt, max_tokens=0, model=None: seen.update(model=model) or "claude wrote this")
    assert shorts._write("p", "s") == "claude wrote this" and seen["model"] == shorts.CLAUDE_WRITER
    monkeypatch.setattr(assistant, "ask_once", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    import lyla
    monkeypatch.setattr(lyla, "think", lambda p, s: ("gemini wrote this", "Gemini"))
    assert shorts._write("p", "s") == "gemini wrote this"                  # a Claude failure never costs the Short
    monkeypatch.setattr(shorts, "ENGINE", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setattr(shorts, "_gemini_pcm", lambda text, voice: b"\x00\x01" * 2400)
    out = str(tmp_path / "v.mp3")
    shorts.speak("hello", out)
    with wave.open(out) as w:
        assert w.getframerate() == 24000 and w.getnframes() == 2400


def test_elevenlabs_voice_is_written_and_falls_back(tmp_path, monkeypatch):
    monkeypatch.setattr(shorts, "ENGINE", "elevenlabs")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    monkeypatch.setattr(shorts, "_eleven_mp3", lambda text: b"ID3fake")
    out = tmp_path / "v.mp3"
    shorts.speak("hi", str(out))
    assert out.read_bytes() == b"ID3fake"
