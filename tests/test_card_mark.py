"""Apollo's mark on the card (overlay_paint.GlobeMark): the full display's
globe and star, small - a wide outline, meridians inside it that widen and
narrow as it turns, lines straight across, and a four-pointed star in the
middle. Drawn here into a stand-in for GDI+ that writes down what it was
asked to draw, so it runs anywhere."""
import math

import overlay_paint


class Colour:
    @staticmethod
    def FromArgb(a, r, g, b):
        return (a, r, g, b)


class Path:
    def __init__(self):
        self.curves = []

    def AddBezier(self, *xy):
        self.curves.append(xy)

    def CloseFigure(self):
        pass

    def Dispose(self):
        pass


class Drawing2D:
    GraphicsPath = Path


class Drawing:
    Color = Colour
    Drawing2D = Drawing2D

    @staticmethod
    def SolidBrush(colour):
        return ("brush", colour)

    @staticmethod
    def Pen(colour, width):
        return ("pen", colour, width)


class Graphics:
    def __init__(self):
        self.ellipses, self.lines, self.fills, self.paths = [], [], [], []

    def DrawEllipse(self, pen, x, y, w, h):
        self.ellipses.append((x, y, w, h, pen[1][0]))

    def DrawLine(self, pen, x0, y0, x1, y1):
        self.lines.append((x0, y0, x1, y1))

    def FillEllipse(self, brush, x, y, w, h):
        self.fills.append((x + w / 2, y + h / 2, w / 2))

    def FillPath(self, brush, path):
        self.paths.append(path)


def drawn(t=0.0, fade=1.0, level=0.0):
    g = Graphics()
    overlay_paint.GlobeMark(Drawing()).draw_at(g, 100, 60, 25, t=t, level=level, fade=fade)
    return g


def test_its_outline_is_the_display_s_wide_globe():
    g = drawn()
    widest = max(g.ellipses, key=lambda e: e[2])
    x, y, w, h, _ = widest
    assert w == 50 and 0.45 <= h / w <= 0.6
    assert (x + w / 2, y + h / 2) == (100, 60)


def test_its_meridians_sit_inside_the_outline_and_turn():
    now, later = drawn(t=0.0), drawn(t=1.5)
    inner = lambda g: sorted(round(e[2], 3) for e in g.ellipses if e[2] < 50)
    assert inner(now) and all(w < 50 for w in inner(now))
    assert inner(now) != inner(later)


def test_it_has_lines_straight_across_inside_it():
    g = drawn()
    across = [l for l in g.lines if l[1] == l[3]]
    assert len(across) == 3
    for x0, y, x1, _ in across:
        assert 75 <= x0 < x1 <= 125 and 47 <= y <= 73


def test_a_four_pointed_star_in_the_middle():
    g = drawn()
    assert len(g.paths) == 1 and len(g.paths[0].curves) == 4
    tips = [(c[0], c[1]) for c in g.paths[0].curves]
    assert sorted((round(x - 100), round(y - 60)) for x, y in tips) == \
        sorted([(r, 0) for r in (-6, 6)] + [(0, r) for r in (-6, 6)])


def test_faded_out_it_draws_nothing():
    g = drawn(fade=0.0)
    assert not (g.ellipses or g.lines or g.fills or g.paths)


def test_the_card_s_lights_are_the_display_s_gradient_warm_to_cool():
    """The card's colours are the display's own CRT band: warm on one side,
    red to amber, cool on the other, teal to blue - not the five neon lights
    it had."""
    import colorsys

    hues = []
    for name, (home_x, _), _drift, _period, strength in overlay_paint.BLOBS:
        r, g, b = overlay_paint.PALETTE[name]
        hue, _light, saturation = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        assert saturation > 0.5 and strength >= 0.3, name
        hues.append((home_x, hue * 360))
    warm = [h for x, h in hues if x < 0.5]
    cool = [h for x, h in hues if x > 0.6]
    assert warm and all(h < 60 or h > 340 for h in warm)          # reds to ambers
    assert cool and all(170 <= h <= 230 for h in cool)            # teal to blue


def test_the_card_s_edge_is_amber():
    r, g, b, _a = overlay_paint.EDGE
    assert r == 255 and 150 <= g <= 200 and b <= 60
