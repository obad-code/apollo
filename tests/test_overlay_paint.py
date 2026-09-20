import math

import pytest

import overlay_paint


@pytest.fixture(scope="module")
def draw():
    import clr
    clr.AddReference("System.Drawing")
    import System.Drawing as D
    return D


@pytest.fixture
def surface(draw):
    bitmap = draw.Bitmap(560, 400, draw.Imaging.PixelFormat.Format32bppPArgb)
    graphics = draw.Graphics.FromImage(bitmap)
    graphics.SmoothingMode = draw.Drawing2D.SmoothingMode.AntiAlias
    yield bitmap, graphics
    graphics.Dispose()
    bitmap.Dispose()


def pixel(bitmap, x, y):
    colour = bitmap.GetPixel(x, y)
    return (colour.A, colour.R, colour.G, colour.B)


def test_palette_has_the_approved_colours():
    assert overlay_paint.PALETTE["amber"] == (232, 185, 88)
    assert overlay_paint.PALETTE["you"] == (210, 238, 243)
    assert overlay_paint.PALETTE["up"] == (95, 227, 154)
    assert overlay_paint.PALETTE["down"] == (255, 107, 122)


def test_panel_fills_inside_and_leaves_the_outside_clear(draw, surface):
    bitmap, graphics = surface
    backdrop = overlay_paint.Backdrop(draw)
    backdrop.panel(graphics, 30, 0, 500, 200, t=0.0)
    assert pixel(bitmap, 250, 100)[0] > 200          # opaque in the middle
    assert pixel(bitmap, 5, 100)[0] == 0             # nothing outside it
    assert pixel(bitmap, 250, 300)[0] == 0           # nothing below it


def test_the_bottom_corners_are_round_and_the_top_is_not(draw, surface):
    bitmap, graphics = surface
    overlay_paint.Backdrop(draw).panel(graphics, 30, 0, 500, 200, t=0.0)
    assert pixel(bitmap, 32, 2)[0] > 150             # square at the top
    assert pixel(bitmap, 32, 198)[0] < 60            # rounded at the bottom


def test_the_gradient_is_darker_at_the_bottom(draw, surface):
    bitmap, graphics = surface
    overlay_paint.Backdrop(draw).panel(graphics, 30, 0, 500, 200, t=0.0)
    top = sum(pixel(bitmap, 250, 10)[1:])
    bottom = sum(pixel(bitmap, 250, 190)[1:])
    assert bottom < top, f"panel is not darker at the bottom: {top} -> {bottom}"


def test_the_colour_moves_over_time(draw, surface):
    bitmap, graphics = surface
    backdrop = overlay_paint.Backdrop(draw)
    backdrop.panel(graphics, 30, 0, 500, 200, t=0.0)
    early = [pixel(bitmap, x, 40) for x in range(60, 500, 40)]
    graphics.Clear(draw.Color.FromArgb(0, 0, 0, 0))
    backdrop.panel(graphics, 30, 0, 500, 200, t=9.0)
    later = [pixel(bitmap, x, 40) for x in range(60, 500, 40)]
    assert early != later


def test_a_resize_rebuilds_the_cached_pieces(draw, surface):
    _, graphics = surface
    backdrop = overlay_paint.Backdrop(draw)
    backdrop.panel(graphics, 30, 0, 500, 200, t=0.0)
    first = backdrop.cached_size
    backdrop.panel(graphics, 30, 0, 500, 260, t=0.0)
    assert backdrop.cached_size != first


def test_alpha_puts_the_channels_in_the_order_gdi_plus_takes():
    """Color.FromArgb reads alpha first; the colour must follow it."""
    assert overlay_paint.alpha((10, 20, 30), 0.5) == (128, 10, 20, 30)
    assert overlay_paint.alpha((10, 20, 30), 1.0) == (255, 10, 20, 30)
