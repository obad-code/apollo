"""Clear, detailed objects on a clean white background - a coffee cup, a laptop, a stack of cash.

Each object is drawn once by Gemini as a photographic picture on pure white, the white is cut away
(flood-filled from the corners, so white parts of the object itself stay), and the result is kept
by name in Documents\\Apollo\\Shorts\\objects - so every later video reuses it for free. On screen
they pop in one after another, float a little, and a short line of text sits underneath.
Needs a Gemini key with billing (SHORTS_OBJECTS=gemini). Without it the scene is drawn the usual way.
"""

import hashlib
import logging
import math
import os
import re

log = logging.getLogger("apollo.shorts_objects")

PROMPT = ("A single {name}, ultra-detailed realistic studio product photograph, isolated on a pure white "
          "background (#FFFFFF), soft even lighting, sharp focus, centred, the whole object in frame, "
          "nothing else in the picture, no text, no logo, no reflection or shadow on the background.")


def slug(name):
    base = re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")[:40] or "object"
    return f"{base}-{hashlib.sha1(str(name).lower().encode()).hexdigest()[:6]}"


def folder():
    import files
    return os.path.join(files.root(), "Shorts", "objects")


def cutout(path, tol=22):
    """The picture with its white background made transparent, trimmed to the object."""
    from PIL import Image, ImageDraw, ImageFilter
    img = Image.open(path).convert("RGB")
    img.thumbnail((900, 900))
    marker = (255, 0, 255)
    work = img.copy()
    w, h = work.size
    for xy in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        ImageDraw.floodfill(work, xy, marker, thresh=tol)
    mask = Image.new("L", (w, h), 255)
    px, mp = work.load(), mask.load()
    for y in range(h):
        for x in range(w):
            if px[x, y] == marker:
                mp[x, y] = 0
    mask = mask.filter(ImageFilter.GaussianBlur(1.2))               # a soft edge, no white halo
    out = img.convert("RGBA")
    out.putalpha(mask)
    box = mask.point(lambda v: 255 if v > 24 else 0).getbbox()
    return out.crop(box) if box else out


def asset(name, make=None, assets_dir=None):
    """The cut-out object as a saved PNG path, drawing it first if it has never been drawn."""
    assets_dir = assets_dir or folder()
    out = os.path.join(assets_dir, slug(name) + ".png")
    if os.path.exists(out):
        return out
    import images
    os.makedirs(assets_dir, exist_ok=True)
    made = (make or images.make)(PROMPT.format(name=name), save_to=assets_dir)
    cutout(made["path"]).save(out)
    try:
        if os.path.abspath(made["path"]) != os.path.abspath(out):
            os.remove(made["path"])
    except OSError:
        pass
    return out


def prepare(scenes, step=lambda t: None, make=None, assets_dir=None, limit=12):
    """Fetch every object the scenes need. A scene whose object cannot be drawn loses its objects
    (it is drawn the usual way); a quota or billing refusal stops the asking for good."""
    done, count = {}, 0
    for scene in scenes:
        names = scene.get("objects") or []
        ok = True
        for name in names:
            if name in done:
                ok = ok and bool(done[name])
                continue
            if count >= limit:
                done[name] = None
                ok = False
                continue
            step(f"Drawing the object: {name}")
            try:
                done[name] = asset(name, make, assets_dir)
                count += 1
            except Exception as e:  # noqa: BLE001
                text = str(e)
                log.info("object %s failed: %s", name, text[:200])
                done[name] = None
                ok = False
                if any(k in text for k in ("429", "RESOURCE_EXHAUSTED", "billing", "PERMISSION_DENIED", "limit: 0", "quota")):
                    step("Gemini pictures are not available on this key (billing or quota) - drawing without them")
                    limit = 0
        scene["_objects"] = [done[n] for n in names] if (names and ok) else None


# -- on the picture ---------------------------------------------------------------------
POSITIONS = {1: [(0.5, 0.46, 0.62)], 2: [(0.29, 0.5, 0.38), (0.71, 0.42, 0.38)],
             3: [(0.2, 0.5, 0.27), (0.5, 0.45, 0.36), (0.8, 0.5, 0.27)]}


def _pop(age):
    """Scale 0 -> 1.12 -> 1: a quick bounce in."""
    if age <= 0:
        return 0.0
    if age >= 0.42:
        return 1.0
    x = age / 0.42
    return 1.12 * math.sin(x * math.pi / 2) if x < 0.7 else 1.12 - 0.12 * (x - 0.7) / 0.3


def paint(world, paths, t, lead=0.12):
    """Lay the objects on the white `world` (a PIL image): shadow, bounce-in, a gentle float."""
    from PIL import Image, ImageFilter
    W, H = world.size
    paths = paths[:3]
    for i, (path, (fx, fy, fw)) in enumerate(zip(paths, POSITIONS[len(paths)])):
        age = t - (lead + 0.18 + 0.42 * i)
        k = _pop(age)
        if k <= 0.01:
            continue
        obj = Image.open(path).convert("RGBA")
        target = fw * W * k
        scale = min(target / obj.width, target / obj.height * 1.2)
        obj = obj.resize((max(2, int(obj.width * scale)), max(2, int(obj.height * scale))), Image.LANCZOS)
        cx, cy = fx * W, fy * H + math.sin(t * 2.0 + i * 1.7) * 0.006 * H
        shadow = Image.new("RGBA", world.size, (0, 0, 0, 0))
        sh = Image.new("L", (int(obj.width * 0.9), int(obj.height * 0.08) + 6), 0)
        from PIL import ImageDraw
        ImageDraw.Draw(sh).ellipse([0, 0, sh.width - 1, sh.height - 1], fill=70)
        shadow.paste((0, 0, 0, 255), (int(cx - sh.width / 2), int(cy + obj.height / 2 - sh.height * 0.4)), sh)
        world.paste(Image.alpha_composite(Image.new("RGBA", world.size, (255, 255, 255, 0)), shadow.filter(ImageFilter.GaussianBlur(14))).convert("RGB"),
                    (0, 0), shadow.filter(ImageFilter.GaussianBlur(14)).split()[3])
        world.paste(obj, (int(cx - obj.width / 2), int(cy - obj.height / 2)), obj)
    return world
