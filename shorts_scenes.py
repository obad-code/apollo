"""The places a Short's story happens: the sea, a desert, a city, space...

Drawn in the same pencil-ink style as the man (see shorts.Pen), over a soft
colour wash, and gently alive: waves roll, clouds drift, stars twinkle, rain
falls. Each is `draw(d, t)` in 1080x1920 numbers; the man stands in front.
"""

import math
import random

W, H = 1080, 1920
INK = (30, 29, 33)
PAPER = (248, 247, 242)

SKY = (226, 238, 248)
SEA = (196, 224, 240)
SAND = (244, 228, 190)
SUN = (255, 233, 160)
GREEN = (206, 230, 196)
GREY = (226, 228, 232)
DUSK = (232, 226, 246)
NIGHT = (206, 212, 236)
TEAL = (190, 232, 228)
STONE = (232, 226, 218)


def _rect(d, x0, y0, x1, y1, color):
    d.polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], fill=color, outline=None)


def _cloud(d, x, y, s=1.0):
    for dx, dy, r in ((0, 0, 50), (55, -20, 62), (115, 0, 48), (60, 18, 50)):
        d.ellipse([x + (dx - r) * s, y + (dy - r) * s, x + (dx + r) * s, y + (dy + r) * s], fill=PAPER, width=5)
    _rect(d, x - 30 * s, y + 8 * s, x + 150 * s, y + 66 * s, PAPER)
    d.line([(x - 30 * s, y + 66 * s), (x + 150 * s, y + 66 * s)], width=5, wobble=1.5)


def _sun(d, x, y, r, t):
    d.ellipse([x - r, y - r, x + r, y + r], fill=SUN, width=6)
    for i in range(12):
        a = i * math.pi / 6 + t * 0.2
        d.line([(x + math.cos(a) * (r + 18), y + math.sin(a) * (r + 18)), (x + math.cos(a) * (r + 52), y + math.sin(a) * (r + 52))], width=5, wobble=1)


def _moon(d, x, y, r):
    d.ellipse([x - r, y - r, x + r, y + r], fill=PAPER, width=6)
    d.ellipse([x - r * 0.2, y - r * 1.1, x + r * 1.3, y + r * 0.9], fill=NIGHT, outline=None)
    d.arc([x - r, y - r, x + r, y + r], 100, 260, width=6)


def _star(d, x, y, r, t, i):
    r *= 0.75 + 0.25 * math.sin(t * 3 + i * 1.7)
    d.line([(x - r, y), (x + r, y)], width=4, wobble=0.6)
    d.line([(x, y - r), (x, y + r)], width=4, wobble=0.6)


def _bird(d, x, y, t):
    f = math.sin(t * 6 + x) * 8
    d.line([(x - 26, y - 6 + f), (x, y + 8), (x + 26, y - 6 + f)], width=5, wobble=0.8)


def _wave(d, y, t, i, amp=12, x0=-20, x1=W + 20):
    pts = [(x, y + amp * math.sin(x * 0.018 + t * 2.0 + i * 1.3)) for x in range(x0, x1, 36)]
    d.line(pts, width=5, wobble=1.0)


def _boat(d, x, y, t):
    y += math.sin(t * 2) * 6
    d.polygon([(x - 90, y), (x + 90, y), (x + 60, y + 44), (x - 60, y + 44)], fill=PAPER, width=6)
    d.line([(x, y), (x, y - 190)], width=6, wobble=1)
    d.polygon([(x + 8, y - 180), (x + 8, y - 20), (x + 100, y - 20)], fill=PAPER, width=5)
    d.polygon([(x - 8, y - 150), (x - 8, y - 20), (x - 70, y - 20)], fill=PAPER, width=5)


def _tree(d, x, base, h, t, i):
    sway = math.sin(t * 1.4 + i) * 6
    d.line([(x, base), (x + sway * 0.3, base - h * 0.55)], width=9, wobble=1.5)
    for dx, dy, r in ((-40, -0.62, 60), (30, -0.7, 64), (-4, -0.88, 62)):
        d.ellipse([x + dx + sway - r, base + dy * h - r, x + dx + sway + r, base + dy * h + r], fill=GREEN, width=6)


def _building(d, x, w, h, ground, seed):
    rnd = random.Random(seed)
    d.polygon([(x, ground), (x, ground - h), (x + w, ground - h), (x + w, ground)], fill=PAPER, width=6, wobble=1.5)
    d.hatch(x + w * 0.72, ground - h + 12, x + w - 4, ground - 4, gap=16, width=3)
    for wy in range(int(ground - h + 40), int(ground - 40), 56):
        for wx in range(int(x + 22), int(x + w * 0.65), 40):
            if rnd.random() < 0.75:
                d.polygon([(wx, wy), (wx + 22, wy), (wx + 22, wy + 30), (wx, wy + 30)], fill=(255, 238, 190) if rnd.random() < 0.5 else PAPER, width=3, wobble=0.6)


def _sand(d, top=1400):
    _rect(d, 0, top, W, H, SAND)
    d.line([(0, top), (W, top + 8)], width=6, wobble=3)
    d.hatch(60, top + 20, 420, top + 70, gap=18, width=3)
    d.hatch(640, top + 30, 1000, top + 80, gap=18, width=3)


# -- the places ----------------------------------------------------------------------
def sea(d, t):
    _rect(d, 0, 0, W, 960, SKY)
    _rect(d, 0, 960, W, 1400, SEA)
    _sun(d, 800, 480, 95, t)
    _cloud(d, 140 + (t * 12) % 1300 - 200, 330, 1.1)
    _bird(d, 380, 620, t)
    _bird(d, 470, 560, t + 1)
    d.line([(0, 960), (W, 965)], width=6, wobble=2)
    _boat(d, 300, 940, t)
    for i in range(7):
        _wave(d, 1010 + i * 58, t, i, amp=9 + i)
    _sand(d)


def beach(d, t):
    sea(d, t)


def desert(d, t):
    _rect(d, 0, 0, W, 900, (252, 236, 205))
    _rect(d, 0, 900, W, H, SAND)
    _sun(d, 250, 420, 100, t)
    d.line([(0, 900), (260, 760), (560, 930), (820, 780), (W, 900)], width=6, wobble=2)
    d.hatch(560, 800, 800, 930, gap=16, width=3)
    d.line([(0, 1130), (300, 1060), (640, 1150), (W, 1070)], width=6, wobble=2)
    d.hatch(300, 1080, 640, 1150, gap=18, width=3)
    for x, h in ((880, 260), (150, 200)):                                  # cactus
        d.line([(x, 1420), (x, 1420 - h)], width=22, wobble=1.2)
        d.line([(x, 1420 - h * 0.55), (x - 55, 1420 - h * 0.55), (x - 55, 1420 - h * 0.85)], width=16, wobble=1)
        d.line([(x, 1420 - h * 0.4), (x + 50, 1420 - h * 0.4), (x + 50, 1420 - h * 0.7)], width=16, wobble=1)
    _bird(d, 620, 520, t)


def city(d, t):
    _rect(d, 0, 0, W, 1380, SKY)
    _cloud(d, (t * 10) % 1300 - 220, 260, 1.0)
    for i, (x, w, h) in enumerate(((20, 190, 620), (230, 150, 420), (400, 220, 760), (640, 170, 500), (830, 230, 680))):
        _building(d, x, w, h, 1380, i + 3)
    _rect(d, 0, 1380, W, H, GREY)
    d.line([(0, 1380), (W, 1384)], width=7, wobble=2)
    for x in range(40, W, 200):
        d.line([(x, 1640), (x + 90, 1640)], width=8, wobble=1)


def space(d, t):
    _rect(d, 0, 0, W, H, DUSK)
    rnd = random.Random(7)
    for i in range(22):
        _star(d, rnd.randint(40, W - 40), rnd.randint(60, 1300), rnd.randint(10, 22), t, i)
    d.ellipse([640, 300, 940, 600], fill=(255, 226, 190), width=7)                # a planet, ringed
    d.hatch(790, 330, 930, 590, gap=14, width=3)
    d.line([(600, 520), (700, 580), (900, 600), (990, 540)], width=6, wobble=1.5)
    d.ellipse([110, 880, 230, 1000], fill=PAPER, width=6)
    d.arc([130, 900, 190, 960], 20, 200, width=4)
    d.ellipse([250 + math.sin(t) * 10, 1180, 330 + math.sin(t) * 10, 1260], fill=(214, 232, 255), width=5)


def night(d, t):
    _rect(d, 0, 0, W, H, NIGHT)
    _moon(d, 780, 420, 110)
    rnd = random.Random(3)
    for i in range(18):
        _star(d, rnd.randint(40, W - 40), rnd.randint(60, 1000), rnd.randint(9, 18), t, i)
    d.line([(0, 1130), (230, 980), (470, 1100), (740, 940), (W, 1090)], width=6, wobble=2)
    _rect(d, 0, 1400, W, H, (186, 194, 220))
    d.line([(0, 1400), (W, 1406)], width=6, wobble=3)


def forest(d, t):
    _rect(d, 0, 0, W, 1380, SKY)
    _sun(d, 860, 360, 80, t)
    for i, x in enumerate((90, 330, 560, 800, 990)):
        _tree(d, x, 1380 - (i % 2) * 40, 520 - (i % 3) * 70, t, i)
    _rect(d, 0, 1380, W, H, (214, 232, 200))
    d.line([(0, 1380), (W, 1386)], width=6, wobble=3)
    d.hatch(80, 1420, 440, 1470, gap=18, width=3)
    _bird(d, 500, 560, t)


def mountains(d, t):
    _rect(d, 0, 0, W, 1380, SKY)
    _sun(d, 190, 380, 80, t)
    _cloud(d, 520 + (t * 10) % 700 - 300, 300, 1.0)
    for x, w, h in ((-60, 620, 700), (420, 700, 860), (200, 540, 520)):
        top = (x + w / 2, 1380 - h)
        d.polygon([(x, 1380), top, (x + w, 1380)], fill=STONE, width=7, wobble=2)
        d.hatch(top[0], top[1] + 50, x + w - 30, 1370, gap=18, width=3)
        d.polygon([(top[0] - 60, top[1] + 86), top, (top[0] + 60, top[1] + 86), (top[0] + 20, top[1] + 66), (top[0] - 20, top[1] + 96)], fill=PAPER, width=5)
    _rect(d, 0, 1380, W, H, (214, 228, 205))
    d.line([(0, 1380), (W, 1384)], width=6, wobble=3)


def rain(d, t):
    _rect(d, 0, 0, W, H, GREY)
    _cloud(d, 90, 250, 1.6)
    _cloud(d, 560, 360, 1.3)
    for i in range(46):
        x = (i * 97 + t * 220) % (W + 200) - 100
        y = (i * 211 + t * 900) % 1500 + 380
        d.line([(x, y), (x - 24, y + 70)], width=5, wobble=0.6)
    d.line([(0, 1500), (W, 1506)], width=6, wobble=3)
    for i in range(5):
        x = 140 + i * 200
        d.line([(x - 40, 1520), (x + 40, 1520)], width=4, wobble=0.5)


def underwater(d, t):
    _rect(d, 0, 0, W, H, TEAL)
    for i in range(3):
        _wave(d, 180 + i * 34, t, i, amp=10)
    rnd = random.Random(5)
    for i in range(14):                                       # bubbles
        x = rnd.randint(60, W - 60) + math.sin(t * 2 + i) * 14
        y = 1700 - ((t * 120 + rnd.randint(0, 1500)) % 1500)
        d.ellipse([x - 16, y - 16, x + 16, y + 16], fill=PAPER, width=4)
    for fx, fy, dirn in ((260, 620, 1), (760, 900, -1), (420, 1160, 1)):         # fish
        x = (fx + t * 40 * dirn) % (W + 200) - 100
        d.polygon([(x - 50 * dirn, fy), (x, fy - 28), (x + 50 * dirn, fy), (x, fy + 28)], fill=(255, 214, 170), width=5)
        d.polygon([(x - 50 * dirn, fy), (x - 82 * dirn, fy - 24), (x - 82 * dirn, fy + 24)], fill=(255, 214, 170), width=5)
        d.dot((x + 24 * dirn, fy - 6), 5)
    for x in (80, 960, 520):                                  # seaweed
        pts = [(x + math.sin(t * 2 + y * 0.01) * 18, 1700 - y) for y in range(0, 360, 40)]
        d.line(pts, width=9, wobble=1)
    _rect(d, 0, 1700, W, H, SAND)


def room(d, t):
    _rect(d, 0, 0, W, 1380, (240, 232, 220))
    d.polygon([(300, 360), (760, 360), (760, 800), (300, 800)], fill=SKY, width=8)               # window
    d.line([(530, 360), (530, 800)], width=6, wobble=1)
    d.line([(300, 580), (760, 580)], width=6, wobble=1)
    _cloud(d, 330 + (t * 8) % 300, 450, 0.45)
    d.polygon([(70, 520), (250, 520), (250, 700), (70, 700)], fill=PAPER, width=7)               # a frame
    d.ellipse([110, 560, 210, 660], fill=SUN, width=5)
    _rect(d, 0, 1380, W, H, (222, 206, 184))
    d.line([(0, 1380), (W, 1384)], width=7, wobble=2)
    d.hatch(60, 1420, 420, 1470, gap=18, width=3)


def chart(d, t):
    """Money and markets: a line that climbs, with coins."""
    _rect(d, 0, 0, W, H, (238, 244, 236))
    for gy in range(300, 1300, 140):
        d.line([(120, gy), (980, gy)], width=3, wobble=1, fill=(200, 205, 196))
    d.line([(120, 280), (120, 1300), (980, 1300)], width=7, wobble=1.5)
    grow = min(1.0, 0.25 + (t % 6) / 5)
    pts = [(120 + i * 70, 1240 - (i * 62 + 60 * math.sin(i * 1.3)) * grow) for i in range(13)]
    d.line(pts, width=9, wobble=1.2)
    x, y = pts[-1]
    d.polygon([(x + 36, y - 36), (x - 22, y - 30), (x + 6, y + 20)], fill=(150, 214, 150), width=5)
    for cx, cy in ((250, 1360), (330, 1380), (410, 1360)):
        d.ellipse([cx - 40, cy - 40, cx + 40, cy + 40], fill=(255, 226, 140), width=5)
        d.text((cx, cy + 2), "$", font=None, fill=INK, anchor="mm") if False else d.line([(cx, cy - 18), (cx, cy + 18)], width=5, wobble=0.5)


def office(d, t):
    _rect(d, 0, 0, W, 1380, (236, 238, 242))
    _rect(d, 120, 300, 960, 900, SKY)                                              # a big window onto the city
    for i, (x, w, h) in enumerate(((150, 120, 360), (290, 150, 260), (460, 130, 420), (620, 170, 300), (810, 120, 380))):
        _building(d, x, w, h, 900, i + 9)
    d.line([(120, 300), (960, 300), (960, 900), (120, 900), (120, 300)], width=10, wobble=1)
    d.line([(540, 300), (540, 900)], width=7, wobble=1)
    _rect(d, 0, 1380, W, H, (210, 196, 176))
    d.line([(0, 1380), (W, 1384)], width=7, wobble=2)
    d.polygon([(70, 1230), (330, 1230), (330, 1380), (70, 1380)], fill=(190, 170, 140), width=7)      # a cabinet


def bank(d, t):
    _rect(d, 0, 0, W, 1380, SKY)
    d.polygon([(100, 700), (540, 420), (980, 700)], fill=STONE, width=8, wobble=1)                    # a pediment
    d.polygon([(100, 700), (980, 700), (980, 760), (100, 760)], fill=PAPER, width=8, wobble=1)
    for x in range(160, 960, 150):
        d.polygon([(x, 760), (x + 70, 760), (x + 70, 1330), (x, 1330)], fill=STONE, width=7, wobble=1)
        d.hatch(x + 46, 770, x + 66, 1320, gap=12, width=3)
    d.polygon([(70, 1330), (1010, 1330), (1010, 1390), (70, 1390)], fill=PAPER, width=8, wobble=1)
    _rect(d, 0, 1390, W, H, GREY)
    d.ellipse([500, 560, 580, 640], fill=(255, 226, 140), width=6)


PLACES = {"sea": sea, "beach": beach, "desert": desert, "city": city, "space": space, "night": night,
          "forest": forest, "mountains": mountains, "rain": rain, "underwater": underwater,
          "room": room, "chart": chart, "office": office, "bank": bank}
NAMES = tuple(PLACES)


def draw(d, name, t):
    fn = PLACES.get(name)
    if fn:
        fn(d, t)
