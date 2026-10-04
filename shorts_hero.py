"""The channel's look: 2D flat vector, cel-shaded, bold black outlines.

The hero has a blank pale face - round, chubby, no nose, two dot eyes, thin flat
eyebrows, one flat line for a mouth, a faint stubble on the chin - and a body
that changes with the wealth tier (broke -> stable -> established -> elite).
Hair colour, hairstyle and build are picked once per video and locked. Side
characters get full faces (nose, skin tone, expression) on purpose: the contrast
with the hero's blank face is the style. Colour grading says the mood: warm gold
is comfort, cool blue is stress, cream is information, navy with one warm light
is high stakes.

Everything draws through shorts.Pen (so it works with its camera and scaling).
"""

import math
import random

INK = (26, 24, 30)
SKIN = (250, 245, 238)
OL = 12                       # the bold outline

HAIR_COLOURS = {"dark brown": (74, 48, 34), "black": (28, 26, 30), "sandy blonde": (214, 176, 108),
                "auburn": (140, 62, 38), "dark gray": (84, 86, 92)}
HAIR_STYLES = ("messy swept", "neat parted", "tousled", "curls", "crop")
BUILDS = {"stockier": 1.12, "average": 1.0, "slimmer": 0.92}
LEANS = ("warm", "cool", "earth")
GRADES = ("warm", "cool", "neutral", "night")
SIDES = ("boss", "friend", "landlord", "banker", "stranger")


def hero_for(seed):
    """The protagonist of this video - fresh for each, then locked."""
    r = random.Random(str(seed))
    return {"hair": r.choice(list(HAIR_COLOURS)), "style": r.choice(HAIR_STYLES),
            "build": r.choice(list(BUILDS)), "lean": r.choice(LEANS)}


def outfit(tier, lean):
    """(top, trousers, shoes, accent) for a wealth tier; the lean tints the casual ones."""
    tint = {"warm": (14, 4, -10), "cool": (-14, 0, 14), "earth": (8, 8, -6)}[lean]

    def t(c):
        return tuple(max(0, min(255, a + b)) for a, b in zip(c, tint))
    return {1: (t((132, 142, 156)), t((70, 92, 138)), (150, 132, 112), (200, 190, 175)),
            2: (t((170, 200, 230)), t((196, 170, 128)), (112, 78, 54), (255, 255, 255)),
            3: ((46, 60, 98), (46, 60, 98), (30, 28, 34), (190, 52, 62)),
            4: ((54, 58, 68), (54, 58, 68), (22, 20, 26), (226, 190, 100))}[max(1, min(4, int(tier or 2)))]


def _round_rect(x0, y0, x1, y1, r, n=7):
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _limb(d, pts, width, colour):
    d.line(pts, fill=INK, width=width + 2 * OL, wobble=0)
    d.line(pts, fill=colour, width=width, wobble=0)


def _ball(d, c, r, colour=SKIN):
    d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=colour, outline=INK, width=OL - 2, wobble=0)


def _tip(a, length, angle):
    rad = math.radians(angle)
    return (a[0] + length * math.sin(rad), a[1] + length * math.cos(rad))


def _head(d, c, rx, ry, fill=SKIN):
    """A round, soft-jawed head: two ovals, outlined together so there is no seam."""
    boxes = ([c[0] - rx, c[1] - ry, c[0] + rx, c[1] + ry],
             [c[0] - rx * 0.92, c[1] - ry * 0.55, c[0] + rx * 0.92, c[1] + ry * 1.04])
    for b in boxes:
        d.ellipse([b[0] - OL / 2, b[1] - OL / 2, b[2] + OL / 2, b[3] + OL / 2], fill=INK, outline=None)
    for b in boxes:
        d.ellipse(b, fill=fill, outline=None)


def _hair(d, c, rx, ry, style, colour):
    x, y = c
    top = y - ry
    arc = [(x + rx * 1.03 * math.cos(math.radians(a)), y + ry * 1.0 * math.sin(math.radians(a))) for a in range(200, 341, 10)]
    if style == "curls":
        cap = arc + [(x + rx * 0.8, y - ry * 0.3), (x, y - ry * 0.45), (x - rx * 0.8, y - ry * 0.3)]
        d.polygon(cap, fill=colour, outline=INK, width=OL - 2, wobble=0)
        for i, a in enumerate(range(205, 336, 26)):
            r = ry * 1.06 + (6 if i % 2 else -4)
            _ball(d, (x + rx * 1.04 * math.cos(math.radians(a)), y + r * math.sin(math.radians(a))), 34, colour)
        return
    if style == "crop":
        d.polygon(arc + [(x + rx * 0.82, y - ry * 0.45), (x, y - ry * 0.62), (x - rx * 0.82, y - ry * 0.45)],
                  fill=colour, outline=INK, width=OL - 2, wobble=0)
        return
    if style == "neat parted":
        hair = arc + [(x + rx * 0.98, y - ry * 0.25), (x + rx * 0.5, y - ry * 0.55), (x - rx * 0.1, y - ry * 0.7),
                      (x - rx * 0.55, y - ry * 0.5), (x - rx * 0.98, y - ry * 0.2)]
        d.polygon(hair, fill=colour, outline=INK, width=OL - 2, wobble=0)
        d.line([(x - rx * 0.1, y - ry * 0.7), (x - rx * 0.22, top + 8)], fill=INK, width=6, wobble=0)
        return
    if style == "tousled":
        spiky = []
        for i, (px, py) in enumerate(arc):
            spiky.append((px + (8 if i % 2 else -8), py - (26 if i % 2 else 4)))
        hair = spiky + [(x + rx * 1.06, y + ry * 0.1), (x + rx * 0.7, y - ry * 0.4), (x - rx * 0.6, y - ry * 0.45), (x - rx * 1.06, y + ry * 0.05)]
        d.polygon(hair, fill=colour, outline=INK, width=OL - 2, wobble=0)
        return
    wave = [(x + rx * (0.95 - i * 0.19), y - ry * (0.42 + 0.12 * math.sin(i * 1.4))) for i in range(11)]
    d.polygon(arc + [(x + rx * 0.98, y - ry * 0.1)] + wave[:], fill=colour, outline=INK, width=OL - 2, wobble=0)
    d.line([(x - rx * 0.2, top + 14), (x + rx * 0.5, y - ry * 0.55)], fill=INK, width=6, wobble=0)


def _face(d, c, rx, ry, pose, t, glasses):
    x, y = c
    shut = (t % 3.6) < 0.12
    mood = {"shock": "shock", "sad": "sad", "think": "think"}.get(pose, "calm")
    for side in (-1, 1):
        ex, ey = x + side * rx * 0.36, y + ry * 0.0
        if shut:
            d.line([(ex - 12, ey), (ex + 12, ey)], fill=INK, width=6, wobble=0)
        else:
            d.dot((ex + math.sin(t * 0.7) * 3, ey), 12 if mood == "shock" else 10)
        lift = {"shock": -16, "think": -6 if side > 0 else 4}.get(mood, 0)
        slant = {"sad": -12, "calm": 3}.get(mood, 0) * side * -1
        d.line([(ex - 22, ey - 38 + lift + slant), (ex + 22, ey - 38 + lift - slant)], fill=INK, width=6, wobble=0)
    if glasses:
        for side in (-1, 1):
            gx = x + side * rx * 0.36
            d.ellipse([gx - 38, y - 38, gx + 38, y + 38], fill=None, outline=INK, width=7, wobble=0)
        d.line([(x - 6, y - 4), (x + 6, y - 4)], fill=INK, width=6, wobble=0)
        for side in (-1, 1):
            d.line([(x + side * (rx * 0.36 + 38), y - 8), (x + side * (rx * 0.36 + 74), y - 18)], fill=INK, width=6, wobble=0)
    # no nose at all; one thin flat line for a mouth - the angle is the expression
    tilt = {"shock": 0, "sad": 9, "think": -4}.get(mood, -6)
    half = 22 if mood == "shock" else 32
    d.line([(x - half, y + ry * 0.5 - tilt), (x + half, y + ry * 0.5 + tilt)], fill=INK, width=6, wobble=0)
    rnd = random.Random(11)                                        # a faint stubble shadow on the chin
    for _ in range(34):
        a = math.radians(rnd.uniform(35, 145))
        rr = rnd.uniform(0.7, 0.93)
        d.dot((x + rx * 0.9 * rr * math.cos(a), y + ry * 0.45 + ry * 0.62 * rr * math.sin(a)), 2.6, fill=(176, 170, 164))


def draw_hero(d, cx, ground, pose, t, prop, hero, tier, angles, hold, glasses=False):
    la, ra, ll, rl, jump = angles
    b = BUILDS.get(hero["build"], 1.0)
    top, trousers, shoes, accent = outfit(tier, hero["lean"])
    hip_y = ground - 215 - jump
    sh_y = hip_y - 300 + math.sin(t * 1.8) * 3
    d.ellipse([cx - 240, ground - 22, cx + 240, ground + 28], fill=(214, 210, 200), outline=None)
    for side, ang in ((1, ll), (-1, rl)):                           # legs, then shoes
        hip = (cx + side * 62 * b, hip_y)
        foot = _tip(hip, 190, ang)
        _limb(d, [hip, foot], 58 * b, trousers)
        d.ellipse([foot[0] - 66 + side * 16, foot[1] - 24, foot[0] + 66 + side * 16, foot[1] + 36], fill=shoes, outline=INK, width=OL - 2, wobble=0)
    body = _round_rect(cx - 128 * b, sh_y, cx + 128 * b, hip_y + 44, 70)
    d.polygon(body, fill=top, outline=INK, width=OL, wobble=0)
    if tier == 1:                                                   # plain tee or sweater: a round neckline
        d.line([(cx - 52, sh_y + 6), (cx - 30, sh_y + 40), (cx + 30, sh_y + 40), (cx + 52, sh_y + 6)], fill=INK, width=7, wobble=0)
    elif tier == 2:                                                 # button-down: collar and a placket
        d.polygon([(cx - 46, sh_y), (cx, sh_y + 52), (cx - 6, sh_y + 4)], fill=accent, outline=INK, width=6, wobble=0)
        d.polygon([(cx + 46, sh_y), (cx, sh_y + 52), (cx + 6, sh_y + 4)], fill=accent, outline=INK, width=6, wobble=0)
        d.line([(cx, sh_y + 52), (cx, hip_y + 20)], fill=INK, width=5, wobble=0)
    else:                                                           # suit: shirt, lapels, tie
        d.polygon([(cx - 44, sh_y), (cx + 44, sh_y), (cx, sh_y + 170)], fill=(246, 244, 240), outline=INK, width=6, wobble=0)
        d.polygon([(cx - 18, sh_y + 30), (cx + 18, sh_y + 30), (cx + 24, sh_y + 190), (cx, sh_y + 226), (cx - 24, sh_y + 190)],
                  fill=accent, outline=INK, width=6, wobble=0)
        for side in (-1, 1):
            d.polygon([(cx + side * 44, sh_y), (cx + side * 100 * b, sh_y + 20), (cx + side * 26, sh_y + 200)], fill=top, outline=INK, width=6, wobble=0)
        if tier == 4:                                               # quiet wealth: a pocket square, a sheen
            d.polygon([(cx - 92 * b, sh_y + 110), (cx - 58 * b, sh_y + 106), (cx - 64 * b, sh_y + 126)], fill=accent, outline=INK, width=4, wobble=0)
            d.line([(cx + 82 * b, sh_y + 50), (cx + 90 * b, sh_y + 190)], fill=(96, 102, 116), width=8, wobble=0)
    hc = (cx + math.sin(t * 1.5) * 4, sh_y - 128 + (12 if pose == "sad" else 0))
    rx, ry = 156 * b, 134
    _head(d, hc, rx, ry)
    _hair(d, hc, rx, ry, hero["style"], HAIR_COLOURS.get(hero["hair"], (74, 48, 34)))
    _face(d, hc, rx, ry, pose, t, glasses)
    hands = {}
    for side, ang in ((1, la), (-1, ra)):
        sh = (cx + side * 118 * b, sh_y + 52)
        elbow = _tip(sh, 108, ang)
        hand = _tip(elbow, 100, ang * 0.85 + (-side * 22 if pose in ("stand", "think", "point", "pleased") else 0))
        hands[side] = (sh, elbow, hand)
    hold(d, prop, {s: h[2] for s, h in hands.items()}, t)
    for sh, elbow, hand in hands.values():
        _limb(d, [sh, elbow, hand], 48 * b, top)
        _ball(d, hand, 31)
    return hc


# -- people with real faces ------------------------------------------------------------
_SIDE_LOOK = {"boss": ((200, 150, 120), (60, 50, 46), (86, 90, 110)), "friend": ((232, 190, 150), (120, 70, 40), (210, 120, 90)),
              "landlord": ((186, 136, 104), (150, 150, 150), (120, 140, 100)), "banker": ((240, 205, 175), (40, 40, 46), (40, 56, 90)),
              "stranger": ((150, 106, 80), (28, 26, 30), (90, 90, 96))}


def draw_side(d, role, x, ground, t, mood="calm"):
    """A side character: a normal, fully rendered face, so the blank hero reads as the lead."""
    skin, hair, cloth = _SIDE_LOOK.get(role, _SIDE_LOOK["stranger"])
    hip_y = ground - 200
    sh_y = hip_y - 280
    d.ellipse([x - 190, ground - 20, x + 190, ground + 24], fill=(214, 210, 200), outline=None)
    for s in (-1, 1):
        _limb(d, [(x + s * 54, hip_y), (x + s * 62, ground - 20)], 52, (60, 64, 80))
        d.ellipse([x + s * 62 - 60 + s * 12, ground - 40, x + s * 62 + 60 + s * 12, ground + 14], fill=(32, 28, 30), outline=INK, width=OL - 2, wobble=0)
    d.polygon(_round_rect(x - 116, sh_y, x + 116, hip_y + 40, 62), fill=cloth, outline=INK, width=OL, wobble=0)
    for s in (-1, 1):
        sway = math.sin(t * 2 + s) * 4
        _limb(d, [(x + s * 108, sh_y + 50), (x + s * 130 + sway, sh_y + 190)], 44, cloth)
        _ball(d, (x + s * 130 + sway, sh_y + 196), 27, skin)
    hc = (x, sh_y - 118)
    rx, ry = 124, 120
    _head(d, hc, rx, ry, skin)
    d.polygon([(hc[0] + rx * math.cos(math.radians(a)), hc[1] + ry * math.sin(math.radians(a))) for a in range(195, 346, 10)]
              + [(hc[0] + rx * 0.7, hc[1] - ry * 0.5), (hc[0] - rx * 0.7, hc[1] - ry * 0.5)], fill=hair, outline=INK, width=OL - 3, wobble=0)
    for s in (-1, 1):                                                 # eyes with whites, a nose, a real mouth
        ex = hc[0] + s * 44
        d.ellipse([ex - 18, hc[1] - 18, ex + 18, hc[1] + 14], fill=(255, 255, 255), outline=INK, width=5, wobble=0)
        d.dot((ex, hc[1] - 2), 7)
        d.line([(ex - 20, hc[1] - 34 + (6 if mood == "angry" else 0) * s), (ex + 20, hc[1] - 34 - (6 if mood == "angry" else 0) * s)], fill=INK, width=6, wobble=0)
    d.polygon([(hc[0], hc[1] - 4), (hc[0] + 16, hc[1] + 34), (hc[0] - 14, hc[1] + 36)], fill=tuple(max(0, c - 22) for c in skin), outline=INK, width=4, wobble=0)
    if mood in ("sad", "angry"):
        d.arc([hc[0] - 30, hc[1] + 58, hc[0] + 30, hc[1] + 92], 200, 340, width=6)
    else:
        d.arc([hc[0] - 34, hc[1] + 36, hc[0] + 34, hc[1] + 78], 20, 160, width=6)
    return hc


# -- colour grading -------------------------------------------------------------------
def grade(img, name):
    """The mood of the whole picture: warm gold, cool blue, cream, or navy with one warm light."""
    from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageDraw
    w, h = img.size
    if name == "warm":
        return ImageChops.multiply(img, Image.new("RGB", img.size, (255, 238, 204)))
    if name == "cool":
        return Image.blend(ImageEnhance.Color(img).enhance(0.78), Image.new("RGB", img.size, (176, 200, 238)), 0.24)
    if name == "neutral":
        return Image.blend(img, Image.new("RGB", img.size, (246, 236, 214)), 0.14)
    if name == "night":
        dark = Image.blend(ImageEnhance.Brightness(img).enhance(0.5), Image.new("RGB", img.size, (16, 24, 58)), 0.38)
        glow = Image.new("L", img.size, 0)
        ImageDraw.Draw(glow).ellipse([w * 0.05, h * 0.18, w * 0.7, h * 0.58], fill=150)
        glow = glow.filter(ImageFilter.GaussianBlur(w * 0.12))
        warm = Image.merge("RGB", [glow.point(lambda v, k=k: int(v * k)) for k in (1.0, 0.7, 0.32)])
        return ImageChops.screen(dark, warm)
    return img
