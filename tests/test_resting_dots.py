"""Apollo at rest (orb.Orb._draw_ring): the ring of points hanging off the top
edge, and nothing but the points - no lines joining them, no star of chords
across it, no bloom round them. Each point one plain round light, turning
with the rest, twinkling a little. Drawn here into a stand-in for GDI+ that
writes down what it was asked to draw."""
import math

import pytest

import orb
import overlay_paint


class Colour:
    @staticmethod
    def FromArgb(a, r, g, b):
        return (a, r, g, b)


class Drawing:
    """Just enough of System.Drawing for the brushes and pens orb asks for."""
    Color = Colour

    @staticmethod
    def SolidBrush(colour):
        return ("brush", colour)

    @staticmethod
    def Pen(colour, width):
        return ("pen", colour, width)


class Graphics:
    def __init__(self):
        self.dots, self.lines = [], []

    def FillEllipse(self, brush, x, y, w, h):
        self.dots.append((x + w / 2, y + h / 2, w / 2, brush[1][0]))

    def DrawLine(self, *args):
        self.lines.append(args)

    def DrawEllipse(self, *args):
        self.lines.append(args)


def resting(monkeypatch, t=0.0, level=0.0):
    monkeypatch.setattr(overlay_paint, "bloom", lambda *a, **k: pytest.fail("no bloom at rest"))
    o = orb.Orb.__new__(orb.Orb)
    o._D = Drawing()
    o._brushes, o._pens = {}, {}
    o._level = level
    g = Graphics()
    o._draw_ring(g, 0, 0, 190, 190, t, 1.0)
    return g


def test_only_the_points_no_lines_and_no_bloom(monkeypatch):
    g = resting(monkeypatch)
    assert g.lines == []
    assert len(g.dots) == orb.Orb.CONSTELLATION_N


def test_the_points_sit_evenly_round_one_circle(monkeypatch):
    g = resting(monkeypatch)
    radii = [math.hypot(x - 95, y - 95) for x, y, _, _ in g.dots]
    assert max(radii) - min(radii) < 1e-6
    assert radii[0] == pytest.approx(190 * orb.Orb.CONSTELLATION_R)


def test_each_point_is_a_plain_light_big_enough_to_see(monkeypatch):
    g = resting(monkeypatch)
    sizes = {round(r, 6) for _, _, r, _ in g.dots}
    assert len(sizes) == 1 and 2.0 <= sizes.pop() <= 4.5
    assert all(0 < a <= 255 for _, _, _, a in g.dots)


def test_they_turn_together(monkeypatch):
    first = resting(monkeypatch, t=0.0).dots[0]
    later = resting(monkeypatch, t=5.0).dots[0]
    assert math.dist(first[:2], later[:2]) > 5
