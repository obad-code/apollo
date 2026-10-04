import subprocess

import pytest

import shorts
import shorts_art
import shorts_hero


def test_a_picture_prompt_stands_alone():
    hero = shorts_hero.hero_for("x")
    p = shorts_art.prompt_for({"say": "He counts $34.", "pose": "sad", "prop": "key", "bg": "prison", "tier": 1, "grade": "cool", "friend": "guard", "show": "man"}, hero)
    for need in (hero["hair"], "NO nose", "prison cell", "guard", "cool blue", "no text", "He counts $34.", "9:16"):
        assert need in p
    assert "same as before" not in p


def test_pictures_are_used_and_a_quota_error_stops_them(tmp_path, monkeypatch):
    import images
    from PIL import Image
    ff = shorts._ffmpeg()
    calls = []

    def fake_make(prompt, save_to=None, **kw):
        calls.append(prompt)
        if len(calls) == 2:
            raise RuntimeError("429 RESOURCE_EXHAUSTED limit: 0")
        path = str(tmp_path / f"p{len(calls)}.png")
        Image.new("RGB", (576, 1024), (120, 160, 200)).save(path)
        return {"path": path}

    def fake_voice(text, path, voice=None):
        subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=300:duration=0.6", "-c:a", "libmp3lame", path], check=True)

    monkeypatch.setattr(images, "make", fake_make)
    monkeypatch.setattr(shorts, "IMAGES", True)
    scenes = [{"say": "a", "caption": "A", "pose": "stand", "prop": "none", "cam": "push", "bg": "sea"},
              {"say": "b", "caption": "B", "pose": "stand", "prop": "none", "cam": "pull", "bg": "sea"},
              {"say": "c", "caption": "C", "pose": "stand", "prop": "none", "cam": "wide", "bg": "sea"}]
    out = shorts.render({"title": "T", "scenes": scenes}, str(tmp_path / "o.mp4"), fake_voice, work=str(tmp_path / "w"))
    assert (tmp_path / "o.mp4").exists() and out
    assert len(calls) == 2 and scenes[0]["_art"] and "_art" not in scenes[1]      # stopped after the refusal; the rest drawn normally
