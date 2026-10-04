import os

from PIL import Image, ImageDraw

import shorts
import shorts_objects


def fake_make(prompt, save_to=None, **kw):
    im = Image.new("RGB", (400, 400), (255, 255, 255))
    ImageDraw.Draw(im).ellipse([100, 100, 300, 300], fill=(30, 90, 200))
    ImageDraw.Draw(im).rectangle([180, 180, 220, 220], fill=(255, 255, 255))     # a white part INSIDE the object
    path = os.path.join(save_to, "raw.png")
    im.save(path)
    return {"path": path}


def test_the_white_goes_but_white_inside_the_object_stays(tmp_path):
    p = shorts_objects.asset("a blue ball", fake_make, str(tmp_path))
    img = Image.open(p)
    assert img.mode == "RGBA" and img.width < 260                       # trimmed to the object
    assert img.getpixel((2, 2))[3] == 0 and img.getpixel((img.width // 2, img.height // 2))[3] == 255
    assert shorts_objects.asset("a blue ball", lambda *a, **k: 1 / 0, str(tmp_path)) == p      # drawn once, kept


def test_a_refusal_stops_the_asking_and_the_scene_loses_its_objects(tmp_path):
    calls = []

    def refuse(prompt, save_to=None, **kw):
        calls.append(prompt)
        raise RuntimeError("429 RESOURCE_EXHAUSTED limit: 0")

    scenes = [{"objects": ["a cup", "a laptop"]}, {"objects": ["cash"]}, {}]
    shorts_objects.prepare(scenes, make=refuse, assets_dir=str(tmp_path))
    assert len(calls) == 1 and all(s.get("_objects") is None for s in scenes)


def test_an_objects_scene_draws(tmp_path):
    scenes = [{"say": "x", "caption": "Lock in", "pose": "stand", "prop": "none", "cam": "push", "show": "env", "objects": ["a ball", "a ball two", "a ball three"]}]
    shorts_objects.prepare(scenes, make=fake_make, assets_dir=str(tmp_path))
    img = shorts.frame(scenes[0], 2.0, 0.5, "t")
    assert img.size == (1080, 1920) and img.getpixel((5, 5)) == (255, 255, 255)
