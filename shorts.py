"""YouTube Shorts, made by LYLA: a stick-man video, vertical, with a voice.

One a day at the peak hour (SHORTS_HOUR, 13:00 by default), a fact one day and
a story the next, or any time you ask ("ليلى سوي شورت عن ..."). Each one:

    1. the script - Gemini writes it as scenes: a hook first, then the beats,
       each with what is said, a pose for the stick man, a prop over him and
       a few words of caption;
    2. the voice - Edge TTS (free), one clip per scene;
    3. the pictures - drawn here: a stick man on white, moving (he breathes,
       his arms swing, he jumps when shocked), the prop beside him, and the
       caption in big type, its words lighting up as they are said;
    4. the video - FFmpeg, 1080x1920, every scene with its voice, joined.

It lands in Documents\\Apollo\\Shorts with a .txt beside it: the title, the
description and the hashtags, ready to paste when you upload.

Needs: pip install pillow edge-tts imageio-ffmpeg (FFmpeg comes with it).
SHORTS_LANG=ar for Arabic (default English); SHORTS_VOICE to pick a voice.
"""

import datetime as dt
import functools
import json
import logging
import math
import os
import re
import subprocess
import tempfile
import threading

log = logging.getLogger("apollo.shorts")

W, H, FPS = 1080, 1920, 15
LANG = (os.environ.get("SHORTS_LANG") or "en").lower()
VOICE = os.environ.get("SHORTS_VOICE") or ("ar-SA-HamedNeural" if LANG == "ar" else "en-US-AndrewNeural")
GLASSES = os.environ.get("SHORTS_GLASSES", "1").strip().lower() in ("1", "true", "yes", "on")
HOUR = int(os.environ.get("SHORTS_HOUR") or 13)

POSES = ("stand", "wave", "point", "think", "shock", "run", "cheer", "sad", "shrug")
CAMS = ("close", "push", "fisheye", "pull", "shake", "pan", "wide")
PROPS = ("none", "note", "question", "exclaim", "bulb", "money", "clock", "skull", "heart", "earth", "fire")

SYSTEM = (
    "You write YouTube Shorts scripts for a stick-man animation channel. 35-50 seconds "
    "spoken. The first line is a hook that stops the scroll. Short punchy sentences. No "
    "music, nothing indecent, nothing against Islam. Answer ONLY with JSON: "
    '{"title": "...", "description": "...", "hashtags": ["#..."], "scenes": [{"say": '
    '"what the narrator says", "caption": "3-6 key words", "pose": one of '
    + json.dumps(POSES) + ', "prop": one of ' + json.dumps(PROPS) + ', "cam": one of ' + json.dumps(CAMS)
    + "}]} with 6 to 9 scenes. The camera must keep moving: open on a close-up or fisheye "
    "for the hook, never the same cam twice in a row, shake for shocks. Use prop \"note\" "
    "(he writes on a pad) for facts and explanations.")


def kind_for(day):
    """A fact one day, a story the next."""
    return "fact" if day.toordinal() % 2 == 0 else "story"


def ask_script(kind, topic="", think=None):
    language = "Arabic (clear Gulf-friendly Fusha)" if LANG == "ar" else "English"
    prompt = (f"Language: {language}. Kind: {'one amazing true fact, explained' if kind == 'fact' else 'a gripping short story with a twist (fiction is fine)'}. "
              f"Topic: {topic or 'your choice - something people would share'}.")
    if think is None:
        import lyla
        text, _brain = lyla.think(prompt, SYSTEM)
    else:
        text = think(prompt)
    found = re.search(r"\{.*\}", text or "", re.S)
    if not found:
        raise RuntimeError("The script did not come back as JSON.")
    data = json.loads(found.group(0))
    scenes = [s for s in data.get("scenes", []) if str(s.get("say", "")).strip()]
    if not scenes:
        raise RuntimeError("The script had no scenes.")
    for s in scenes:
        s["pose"] = s.get("pose") if s.get("pose") in POSES else "stand"
        s["prop"] = s.get("prop") if s.get("prop") in PROPS else "none"
        s["caption"] = str(s.get("caption") or s["say"])[:60]
    for i, s in enumerate(scenes):
        if s.get("cam") not in CAMS or (i and s["cam"] == scenes[i - 1]["cam"]):
            s["cam"] = CAMS[i % len(CAMS)]
    data["scenes"] = scenes
    return data


# -- drawing -------------------------------------------------------------------------

SS = 1.25         # the world is drawn this much bigger, so a close-up stays sharp
INK = (38, 36, 42)
CREAM = (252, 249, 241)
SHADE = (236, 233, 226)
OL = 13           # the outline: thick and even, like a sticker
# soft backgrounds (top, bottom, ray), by mood - pale, so the cream character and the colourful props pop
LOOKS = {
    "shock": ((255, 255, 255), (255, 224, 214), (255, 238, 228)),
    "cheer": ((255, 255, 255), (255, 240, 190), (255, 247, 215)),
    "sad": ((255, 255, 255), (214, 224, 244), (232, 238, 250)),
    "think": ((255, 255, 255), (230, 222, 250), (240, 234, 252)),
    "run": ((255, 255, 255), (214, 242, 236), (232, 248, 244)),
    "point": ((255, 255, 255), (216, 234, 255), (232, 242, 255)),
    "wave": ((255, 255, 255), (220, 246, 228), (236, 250, 240)),
    "shrug": ((255, 255, 255), (252, 226, 236), (254, 238, 244)),
    "stand": ((255, 255, 255), (232, 238, 248), (242, 246, 252)),
}
_cache = {}


@functools.lru_cache(maxsize=16)
def _font(size):
    from PIL import ImageFont
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(here, "fonts", "thmanyahsans-Black.otf"),
                 "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/seguibl.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


class Pen:
    """An ImageDraw that scales everything by k, so the drawing code stays in
    plain 1080x1920 numbers while the picture is drawn bigger."""

    def __init__(self, d, k):
        self.d, self.k = d, k

    def _p(self, pts):
        if pts and isinstance(pts[0], (int, float)):
            pts = list(zip(pts[::2], pts[1::2]))
        return [(x * self.k, y * self.k) for x, y in pts]

    def _w(self, width):
        return max(1, round(width * self.k))

    def line(self, pts, fill=None, width=1):
        pts = self._p(pts)
        w = self._w(width)
        self.d.line(pts, fill=fill, width=w)
        r = w / 2 - 0.5    # round caps: every limb is a sausage, not a plank
        for x, y in pts:
            self.d.ellipse([x - r, y - r, x + r, y + r], fill=fill)

    def ellipse(self, box, fill=None, outline=None, width=1):
        (x0, y0), (x1, y1) = self._p([(box[0], box[1]), (box[2], box[3])])
        self.d.ellipse([x0, y0, x1, y1], fill=fill, outline=outline, width=self._w(width))

    def rounded(self, box, radius, fill=None, outline=None, width=1):
        (x0, y0), (x1, y1) = self._p([(box[0], box[1]), (box[2], box[3])])
        self.d.rounded_rectangle([x0, y0, x1, y1], radius * self.k, fill=fill, outline=outline, width=self._w(width))

    def arc(self, box, start, end, fill=None, width=1):
        (x0, y0), (x1, y1) = self._p([(box[0], box[1]), (box[2], box[3])])
        self.d.arc([x0, y0, x1, y1], start, end, fill=fill, width=self._w(width))

    def polygon(self, pts, fill=None, outline=None, width=1):
        pts = self._p(pts)
        self.d.polygon(pts, fill=fill)
        if outline:
            self.line(list(pts_back(pts, self.k)) + [pts_back(pts, self.k)[0]], fill=outline, width=width)

    def text(self, xy, text, font=None, fill=None, anchor=None):
        (x, y), = self._p([xy])
        if hasattr(font, "font_variant"):
            font = font.font_variant(size=max(1, int(font.size * self.k)))
        self.d.text((x, y), text, font=font, fill=fill, anchor=anchor)


def pts_back(pts, k):
    return [(x / k, y / k) for x, y in pts]


def limbs(pose, t):
    """Angles (degrees from straight down) of the +x arm, the -x arm, the +x leg,
    the -x leg, and a small hop in px, for `pose` at time `t` seconds."""
    s = math.sin(t * 5.0)
    table = {
        "stand": (22 + 4 * s, -22 - 4 * s, 5, -5, 0),
        "wave": (22, -140 + 26 * math.sin(t * 8), 5, -5, 0),
        "point": (22, -100 + 4 * s, 5, -5, 0),
        "think": (22, -150, 5, -5, 0),
        "shock": (125 + 6 * s, -125 - 6 * s, 12, -12, abs(math.sin(t * 7)) * 14),
        "run": (45 * s, -45 * s, 28 * s, -28 * s, abs(s) * 8),
        "cheer": (150 + 8 * s, -150 - 8 * s, 10, -10, abs(math.sin(t * 6)) * 14),
        "sad": (8, -8, 3, -3, 0),
        "pleased": (22, -22, 5, -5, 0),
        "shrug": (70 + 4 * s, -70 - 4 * s, 5, -5, 0),
    }
    return table.get(pose, table["stand"])


def _tip(a, length, angle):
    rad = math.radians(angle)
    return (a[0] + length * math.sin(rad), a[1] + length * math.cos(rad))


def _limb(d, pts, width):
    """An outlined, filled limb through `pts` - the outline first, so joints merge."""
    d.line(pts, fill=INK, width=width + 2 * OL)
    d.line(pts, fill=CREAM, width=width)


def _ball(d, c, r):
    d.ellipse([c[0] - r - OL, c[1] - r - OL, c[0] + r + OL, c[1] + r + OL], fill=INK)
    d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=CREAM)


def draw_man(d, cx, ground, pose, t, talking=False, prop="none", glasses=GLASSES):
    la, ra, ll, rl, jump = limbs(pose, t)
    breathe = math.sin(t * 2.2) * 4
    hip_y = ground - 215 - jump
    sh_y = hip_y - 300 + breathe                       # shoulder line
    # soft shadow on the floor
    d.ellipse([cx - 230, ground - 22, cx + 230, ground + 26], fill=SHADE)
    # legs and shoes
    for side, ang in ((1, ll), (-1, rl)):
        hip = (cx + side * 62, hip_y)
        foot = _tip(hip, 190, ang)
        _limb(d, [hip, foot], 54)
        d.ellipse([foot[0] - 70 + side * 14 - OL, foot[1] - 22 - OL, foot[0] + 70 + side * 14 + OL, foot[1] + 38 + OL], fill=INK)
        d.ellipse([foot[0] - 70 + side * 14, foot[1] - 22, foot[0] + 70 + side * 14, foot[1] + 38], fill=CREAM)
    # the torso
    d.rounded([cx - 125 - OL, sh_y - OL, cx + 125 + OL, hip_y + 40 + OL], 80, fill=INK)
    d.rounded([cx - 125, sh_y, cx + 125, hip_y + 40], 80, fill=CREAM)
    # the head: big, flat cream, a soft shade where it sits on the body
    head_c = (cx + math.sin(t * 1.6) * 6, sh_y - 128 + (14 if pose == "sad" else 0))
    d.ellipse([cx - 120, sh_y - 30, cx + 120, sh_y + 40], fill=SHADE)
    r = 165
    d.ellipse([head_c[0] - r - OL, head_c[1] - r - OL, head_c[0] + r + OL, head_c[1] + r + OL], fill=INK)
    d.ellipse([head_c[0] - r, head_c[1] - r, head_c[0] + r, head_c[1] + r], fill=CREAM)
    _face(d, head_c, pose, t, talking, glasses)
    # arms in front, hands as fists; the prop is held in them
    hands = {}
    for side, ang in ((1, la), (-1, ra)):
        sh = (cx + side * 118, sh_y + 55)
        elbow = _tip(sh, 105, ang)
        hand = _tip(elbow, 95, ang * 0.85 + (-side * 25 if pose in ("stand", "think", "point") else 0))
        hands[side] = hand
    # items first, so a fist closes over them
    _hold(d, prop, hands, t)
    for side, ang in ((1, la), (-1, ra)):
        sh = (cx + side * 118, sh_y + 55)
        elbow = _tip(sh, 105, ang)
        _limb(d, [sh, elbow, hands[side]], 46)
        _ball(d, hands[side], 33)
    return head_c


def _face(d, head_c, pose, t, talking=False, glasses=GLASSES):
    x, y = head_c
    shut = (t % 3.3) < 0.12
    big = pose == "shock"
    look = math.sin(t * 0.9) * 5
    for side in (-1, 1):
        ex, ey = x + side * 58, y - 6
        if shut:
            d.line([ex - 18, ey, ex + 18, ey], fill=INK, width=8)
        else:
            w, h = (17, 30) if big else (13, 22)
            d.ellipse([ex + look - w, ey - h, ex + look + w, ey + h], fill=INK)
        lift = {"shock": -26, "sad": 0, "think": -10 if side > 0 else 6, "cheer": -14}.get(pose, 0)
        slant = {"sad": -14, "shock": 0, "cheer": 0}.get(pose, 0 if pose == "pleased" else 16) * side * -1   # angry-ish by default, like the reference
        d.line([ex - 26, ey - 52 + lift + slant, ex + 26, ey - 52 + lift - slant], fill=INK, width=10)
    if glasses:
        for side in (-1, 1):
            gx, gy = x + side * 58, y - 6
            d.ellipse([gx - 50, gy - 46, gx + 50, gy + 46], outline=INK, width=11, fill=None)
            d.line([gx - 38, gy - 30, gx - 18, gy - 40], fill=(255, 255, 255), width=6)    # a glint
        d.line([x - 10, y - 8, x + 10, y - 8], fill=INK, width=9)
        d.line([x - 108, y - 14, x - 164, y - 30], fill=INK, width=9)
        d.line([x + 108, y - 14, x + 164, y - 30], fill=INK, width=9)
    mx, my = x, y + 62
    open_ = abs(math.sin(t * 13)) if talking else 0
    if big or (talking and open_ > 0.45):
        h = 18 + 28 * (open_ if talking else 1)
        d.ellipse([mx - 24, my - 8, mx + 24, my - 8 + h], fill=INK)
    elif pose in ("cheer", "wave", "pleased"):
        d.arc([mx - 44, my - 40, mx + 44, my + 22], 20, 160, fill=INK, width=9)
    elif pose == "sad":
        d.arc([mx - 38, my + 4, mx + 38, my + 50], 200, 340, fill=INK, width=9)
    else:
        d.arc([mx - 30, my - 4, mx + 30, my + 30], 200, 340, fill=INK, width=9)    # the little frown


def _outlined(d, shape, *args, fill, width=OL - 3):
    getattr(d, shape)(*args, fill=INK)


def _hold(d, prop, hands, t):
    """What he is holding or showing, drawn at his hands."""
    if prop == "none":
        return
    hx, hy = hands[1]
    ox, oy = hands[-1]
    f = _font(110)
    bob = math.sin(t * 3) * 6
    if prop == "note":                                   # a pencil and a pad, like the picture
        pad = [(hx - 50, hy - 150), (hx + 95, hy - 135), (hx + 70, hy + 40), (hx - 70, hy + 25)]
        d.polygon(pad, fill=(255, 239, 196), outline=INK, width=OL - 3)
        a, b = (ox - 70, oy - 150), (ox + 55, oy + 25)
        d.line([a, b], fill=INK, width=44 + 2 * (OL - 4))
        d.line([a, b], fill=(246, 190, 40), width=44)
        d.ellipse([a[0] - 26, a[1] - 26, a[0] + 26, a[1] + 26], fill=(238, 140, 120), outline=INK, width=OL - 4)
        d.polygon([(b[0] - 20, b[1] - 4), (b[0] + 20, b[1] - 8), (b[0] + 18, b[1] + 44)], fill=(244, 214, 160), outline=INK, width=OL - 5)
        return
    cx, cy = hx + 10, hy - 95 + bob
    if prop in ("question", "exclaim"):
        col = (232, 70, 70) if prop == "exclaim" else (60, 120, 230)
        d.ellipse([cx - 78, cy - 78, cx + 78, cy + 78], fill=(255, 255, 255), outline=INK, width=OL - 3)
        d.text((cx, cy + 4), "?" if prop == "question" else "!", font=f, fill=col, anchor="mm")
    elif prop == "bulb":
        d.ellipse([cx - 66, cy - 80, cx + 66, cy + 52], fill=(255, 214, 60), outline=INK, width=OL - 3)
        d.rounded([cx - 34, cy + 44, cx + 34, cy + 90], 14, fill=(190, 190, 200), outline=INK, width=OL - 5)
        for ang in (-60, -20, 20, 60, 100, 140, 180, 220):
            a = math.radians(ang - 90)
            d.line([cx + math.cos(a) * 95, cy - 14 + math.sin(a) * 95, cx + math.cos(a) * 125, cy - 14 + math.sin(a) * 125], fill=(245, 170, 20), width=9)
    elif prop == "money":
        d.rounded([cx - 100, cy - 58, cx + 100, cy + 58], 16, fill=(140, 208, 130), outline=INK, width=OL - 3)
        d.ellipse([cx - 38, cy - 38, cx + 38, cy + 38], fill=(190, 232, 176), outline=INK, width=7)
        d.text((cx, cy + 2), "$", font=f, fill=(40, 120, 60), anchor="mm")
    elif prop == "heart":
        col = (236, 70, 100)
        d.ellipse([cx - 78, cy - 66, cx + 6, cy + 20], fill=col, outline=INK, width=OL - 4)
        d.ellipse([cx - 6, cy - 66, cx + 78, cy + 20], fill=col, outline=INK, width=OL - 4)
        d.polygon([(cx - 76, cy - 10), (cx + 76, cy - 10), (cx, cy + 80)], fill=col, outline=INK, width=OL - 4)
        d.polygon([(cx - 66, cy - 14), (cx + 66, cy - 14), (cx, cy + 68)], fill=col)
    elif prop == "clock":
        d.ellipse([cx - 78, cy - 78, cx + 78, cy + 78], fill=(255, 255, 255), outline=INK, width=OL - 3)
        a = t * 2
        d.line([cx, cy, cx + math.sin(a) * 52, cy - math.cos(a) * 52], fill=INK, width=9)
        d.line([cx, cy, cx + math.sin(a / 12) * 36, cy - math.cos(a / 12) * 36], fill=INK, width=11)
    elif prop == "earth":
        d.ellipse([cx - 80, cy - 80, cx + 80, cy + 80], fill=(100, 176, 240), outline=INK, width=OL - 3)
        d.ellipse([cx - 52, cy - 44, cx + 4, cy + 12], fill=(120, 200, 120))
        d.ellipse([cx + 8, cy + 6, cx + 56, cy + 52], fill=(120, 200, 120))
    elif prop == "fire":
        sway = math.sin(t * 9) * 8
        d.polygon([(cx - 70, cy + 60), (cx - 50 + sway, cy - 20), (cx - 8, cy - 60), (cx + sway, cy - 110), (cx + 36, cy - 40), (cx + 70, cy - 10), (cx + 66, cy + 60)],
                  fill=(250, 130, 40), outline=INK, width=OL - 4)
        d.ellipse([cx - 32, cy - 10, cx + 32, cy + 60], fill=(255, 214, 70))
    elif prop == "skull":
        d.ellipse([cx - 70, cy - 76, cx + 70, cy + 40], fill=(250, 250, 250), outline=INK, width=OL - 3)
        d.rounded([cx - 38, cy + 20, cx + 38, cy + 76], 12, fill=(250, 250, 250), outline=INK, width=OL - 5)
        for s in (-1, 1):
            d.ellipse([cx + s * 30 - 17, cy - 22, cx + s * 30 + 17, cy + 14], fill=INK)


def draw_prop(*_):
    """Kept for old callers: props are held by the man now (see draw_man)."""


def avatar(path, size=1024, pose="pleased", prop="note", glasses=True):
    """A portrait of the character on white, in the channel's style - a profile picture."""
    from PIL import Image, ImageDraw
    k = 2.0
    big = Image.new("RGB", (int(W * k), int(H * k)), "white")
    d = Pen(ImageDraw.Draw(big), k)
    draw_man(d, W / 2, 1500, pose, 0.4, prop=prop, glasses=glasses)
    box = tuple(int(v * k) for v in (W / 2 - 330, 640, W / 2 + 330, 1560))
    art = big.crop(box)
    side = max(art.size)
    canvas = Image.new("RGB", (side, side), "white")
    canvas.paste(art, ((side - art.width) // 2, (side - art.height) // 2))
    canvas.resize((size, size), Image.LANCZOS).save(path)
    return path


def _background(pose, size):
    key = (pose, size)
    if key not in _cache:
        from PIL import Image, ImageOps
        top, bottom, _ = LOOKS.get(pose, LOOKS["stand"])
        _cache[key] = ImageOps.colorize(Image.linear_gradient("L").resize(size), top, bottom)
    return _cache[key].copy()


def _ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def camera(cam, t, p, head, body):
    """Where the camera looks: (zoom, focus x, focus y, bulge), in 1080x1920 numbers."""
    punch = 1 + 0.30 * _ease(1 - t / 0.28) if t < 0.28 else 1      # every cut starts with a punch-in
    bulge = 0.0
    if cam == "close":
        z, f = 1.7 + 0.3 * _ease(p), (head[0], head[1] + 40)
    elif cam == "push":
        z, f = 1.35 + 0.55 * _ease(p), (body[0], body[1] + (head[1] - body[1]) * _ease(p))
    elif cam == "pull":
        z, f = 2.1 - 0.75 * _ease(p), (head[0], head[1] + 140 * _ease(p))
    elif cam == "fisheye":
        z, f, bulge = 1.5 + 0.1 * math.sin(t * 2), (body[0], body[1] - 40), 0.35 + 0.1 * math.sin(t * 3)
    elif cam == "shake":
        z, f = 1.55, (body[0] + math.sin(t * 47) * 16, body[1] + math.cos(t * 39) * 16)
    elif cam == "pan":
        z, f = 1.6, (W * (0.3 + 0.4 * _ease(p)), body[1])
    else:
        z, f = 1.4, (body[0], body[1])
    return z * punch, f[0], f[1], bulge


def _bulge(img, s):
    """A fisheye: the middle swells, the edges hold."""
    import numpy as np
    from PIL import Image
    s = round(s, 1)
    key = ("bulge", s)
    if key not in _cache:
        ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
        dx, dy = (xs - W / 2) / (W / 2), (ys - H / 2) / (H / 2)
        r2 = np.clip((dx * dx + dy * dy) / 2, 0, 1)
        k = 1 - s * (1 - r2)
        _cache[key] = (np.clip(W / 2 + dx * k * W / 2, 0, W - 1).astype(np.int32),
                       np.clip(H / 2 + dy * k * H / 2, 0, H - 1).astype(np.int32))
    sx, sy = _cache[key]
    return Image.fromarray(np.asarray(img)[sy, sx])


def frame(scene, t, progress, title):
    """One picture of `scene`, `t` seconds in, `progress` 0..1 through its words."""
    from PIL import Image, ImageDraw
    pose = scene["pose"]
    world = _background(pose, (int(W * SS), int(H * SS)))
    raw = ImageDraw.Draw(world)
    # light rays behind him when the mood is loud
    if pose in ("shock", "cheer") or scene["prop"] in ("fire", "money"):
        ray = LOOKS.get(pose, LOOKS["stand"])[2]
        ox, oy = W / 2 * SS, 760 * SS
        for i in range(14):
            a0 = t * 0.35 + i * (math.pi * 2 / 14)
            a1 = a0 + math.pi / 14
            raw.polygon([(ox, oy)] + [(ox + math.cos(a) * 2600 * SS, oy + math.sin(a) * 2600 * SS) for a in (a0, a1)], fill=ray)
    d = Pen(raw, SS)
    ground = 1500
    cx = W / 2 + math.sin(t * 0.7) * 14
    head = draw_man(d, cx, ground, pose, t, talking=progress < 1, prop=scene["prop"])
    # the camera: crop the big world to a window and scale it to the screen
    z, fx, fy, bulge = camera(scene.get("cam", "wide"), t, progress, head, (cx, 1000))
    cw, ch = W / z, H / z
    left = min(max(fx - cw / 2, 0), W - cw)
    top = min(max(fy - ch / 2, 0), H - ch)
    img = world.resize((W, H), Image.BILINEAR, box=(left * SS, top * SS, (left + cw) * SS, (top + ch) * SS))
    if bulge:
        try:
            img = _bulge(img, bulge)
        except ImportError:
            pass
    # the caption sits on the screen, never zoomed: big, outlined, spoken words in yellow
    d = ImageDraw.Draw(img)
    big, small = _font(100), _font(38)
    words = scene["caption"].split()
    lit = max(1, math.ceil(len(words) * min(1.0, progress * 1.15)))
    lines, cur = [], []
    for w in words:
        if len(" ".join(cur + [w])) > 15 and cur:
            lines.append(cur)
            cur = []
        cur.append(w)
    lines.append(cur)
    y, n = 170, 0
    rtl = LANG == "ar"
    for line in lines:
        text_w = d.textlength(" ".join(line), font=big)
        x = W / 2 - text_w / 2
        for w in (reversed(line) if rtl else line):
            n += 1
            colour = (255, 221, 40) if n <= lit else (255, 255, 255)
            d.text((x, y), w, font=big, fill=colour, stroke_width=9, stroke_fill=(15, 15, 20))
            x += d.textlength(w + " ", font=big)
        y += 120
    d.text((W / 2, 1850), title[:40], font=small, fill=(150, 150, 165), anchor="mm")
    return img


# -- voice and video -----------------------------------------------------------------

def _ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def speak(text, path, voice=VOICE):
    import asyncio
    import edge_tts
    asyncio.run(edge_tts.Communicate(text, voice).save(path))


def duration(path):
    out = subprocess.run([_ffmpeg(), "-i", path], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 3.0


def render(script, out_path, speak_fn=speak, work=None, step=lambda t: None):
    """The whole video. Returns out_path."""
    work = work or tempfile.mkdtemp(prefix="short-")
    parts = []
    for i, scene in enumerate(script["scenes"]):
        step(f"Scene {i + 1} of {len(script['scenes'])}: voice and drawing")
        audio = os.path.join(work, f"s{i}.mp3")
        speak_fn(scene["say"], audio)
        secs = duration(audio) + 0.25
        clip = os.path.join(work, f"s{i}.mp4")
        cmd = [_ffmpeg(), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS),
               "-i", "-", "-i", audio, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
               "-c:a", "aac", "-shortest", clip]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        count = int(secs * FPS)
        for f in range(count):
            t = f / FPS
            frame(scene, t, t / max(0.1, secs - 0.25), script.get("title", "")).save(proc.stdin, "PNG", compress_level=1)
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError("FFmpeg could not make a scene.")
        parts.append(clip)
    listing = os.path.join(work, "list.txt")
    with open(listing, "w", encoding="utf-8") as f:
        f.writelines(f"file '{p}'\n" for p in parts)
    subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listing,
                    "-c", "copy", out_path], check=True)
    return out_path


def folder():
    import files
    path = os.path.join(files.root(), "Shorts")
    os.makedirs(path, exist_ok=True)
    return path


def make(kind=None, topic="", think=None, speak_fn=speak, now=None, step=lambda t: None):
    """Write, voice, draw and join one Short. Returns {path, title, notes}."""
    now = now or dt.datetime.now()
    kind = kind or kind_for(now.date())
    for need in ("PIL", "edge_tts", "imageio_ffmpeg"):
        try:
            __import__(need)
        except ImportError as e:
            raise RuntimeError("Missing a library: run  python -m pip install pillow edge-tts imageio-ffmpeg") from e
    step(f"Writing the script ({kind})")
    script = ask_script(kind, topic, think)
    slug = re.sub(r"[^\w\- ]+", "", script.get("title", "short"))[:50].strip() or "short"
    base = os.path.join(folder(), f"{now:%Y-%m-%d %H%M} {slug}")
    render(script, base + ".mp4", speak_fn, step=step)
    step("Joining the scenes")
    notes = (f"{script.get('title', '')}\n\n{script.get('description', '')}\n\n"
             + " ".join(script.get("hashtags", []) + ["#shorts"]))
    with open(base + ".txt", "w", encoding="utf-8") as f:
        f.write(notes)
    log.info("short made: %s", base)
    return {"path": base + ".mp4", "title": script.get("title", ""), "notes": base + ".txt", "kind": kind}


def make_in_background(kind=None, topic="", done=None):
    """Hand it to LYLA's desk: her card shows it, Apollo tells you when done."""
    try:
        import crew
        what = f"Make a YouTube Short{(' about ' + topic) if topic else ''}"
        return crew.desk("LYLA").take(what, short=True, kind=kind, topic=topic)
    except Exception:  # noqa: BLE001 - no desk: make it on a thread of its own
        log.debug("no LYLA desk for the short", exc_info=True)
    return _make_on_thread(kind, topic, done)


def _make_on_thread(kind=None, topic="", done=None):
    def run():
        try:
            result = make(kind, topic)
        except Exception as e:  # noqa: BLE001
            log.warning("short failed: %s", e)
            result = {"error": str(e) or type(e).__name__}
        if done:
            done(result)
    threading.Thread(target=run, daemon=True, name="short").start()
