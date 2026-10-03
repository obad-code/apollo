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


def test_the_colour_reaches_up_the_card(draw, surface):
    """Half way up the card - where the words are - there is colour, not
    just black: the old veil held every light down in the bottom strip."""
    bitmap, graphics = surface
    backdrop = overlay_paint.Backdrop(draw)
    lit = []
    for t in (0.0, 4.0, 8.0, 12.0):
        graphics.Clear(draw.Color.FromArgb(0, 0, 0, 0))
        backdrop.panel(graphics, 30, 0, 500, 200, t=t)
        lit.append(max(sum(pixel(bitmap, x, 100)[1:]) for x in range(60, 500, 20)))
    card = sum(overlay_paint.PALETTE["card"])
    assert min(lit) > card + 90, f"the middle of the card is dark: {lit}"


def test_the_gradient_reads_smooth(draw, surface):
    """Scanlines, but faint: at a third off every third row they striped the
    colour into a grille, and the gradient stopped reading as one."""
    bitmap, graphics = surface
    overlay_paint.Backdrop(draw).panel(graphics, 30, 0, 500, 200, t=3.0)
    light = [sum(pixel(bitmap, 250, y)[1:]) for y in range(120, 196)]
    drops = [1 - light[i] / light[i - 1] for i in range(1, len(light)) if light[i - 1] > 60]
    assert drops and max(drops) < 0.18, f"a row drops by {max(drops):.0%}"


def test_the_ink_is_light_enough_to_read_on_the_card():
    """A black card needs light type; the cream card's dark ink vanishes on it."""
    card = sum(overlay_paint.PALETTE["card"])
    for name in ("ink", "you", "caption", "amber", "up", "down", "cyan"):
        assert sum(overlay_paint.PALETTE[name]) > card + 300, name


def test_the_dots_are_light_on_the_dark_card():
    assert sum(overlay_paint.DOT_INK) > sum(overlay_paint.PALETTE["card"]) + 400


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


def test_the_top_is_clean_paper_and_the_colour_is_at_the_foot(draw, surface):
    """The veil's whole job: plain cream up top, colour down below.

    The card's upper quarter hides above the screen's edge, and the part just
    under it carries the text - so colour up there is both invisible and in
    the way of reading.
    """
    bitmap, graphics = surface
    overlay_paint.Backdrop(draw).panel(graphics, 30, 0, 500, 200, t=0.0)
    top = pixel(bitmap, 250, 10)[1:]
    bottom = pixel(bitmap, 250, 190)[1:]
    assert top == overlay_paint.PALETTE["card"], f"the top is not plain paper: {top}"
    assert bottom != overlay_paint.PALETTE["card"], "no colour reaches the foot"


def test_the_card_is_opaque_all_the_way_down(draw, surface):
    """Paper, not a tint. The veil fading out must not thin the card itself."""
    bitmap, graphics = surface
    overlay_paint.Backdrop(draw).panel(graphics, 30, 0, 500, 200, t=0.0)
    for y in (6, 60, 120, 170, 190):
        assert pixel(bitmap, 250, y)[0] > 250, f"see-through at y={y}"


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


def test_sparkles_wrap_inside_their_field(draw):
    sparkles = overlay_paint.Sparkles(draw, count=60)
    for _ in range(400):
        sparkles.advance(0.05, level=1.0)
    assert all(0 <= p["x"] <= 1 and 0 <= p["y"] <= 1 for p in sparkles.particles)


def test_sparkles_speed_up_with_your_voice(draw):
    quiet = overlay_paint.Sparkles(draw, count=40)
    loud = overlay_paint.Sparkles(draw, count=40)
    loud.particles = [dict(p) for p in quiet.particles]
    quiet.advance(0.2, level=0.0)
    loud.advance(0.2, level=1.0)
    moved_quiet = sum(abs(a["y"] - b["y"]) for a, b in zip(quiet.particles, loud.particles))
    assert moved_quiet > 0


def test_sparkles_follow_the_panel_edge(draw, surface):
    bitmap, graphics = surface
    sparkles = overlay_paint.Sparkles(draw, count=200)
    sparkles.advance(0.1, level=0.5)
    sparkles.draw_at(graphics, 30, 220, 500, 150)
    lit = [(x, y) for x in range(0, 560, 2) for y in range(0, 400, 2)
           if pixel(bitmap, x, y)[0] > 8]
    assert lit, "no sparkles drawn"
    assert all(215 <= y <= 375 for _, y in lit)


def test_horizon_is_brightest_in_the_middle(draw, surface):
    bitmap, graphics = surface
    overlay_paint.horizon(graphics, draw, 30, 200, 500)
    middle = max(pixel(bitmap, 280, y)[0] for y in range(197, 204))
    edge = max(pixel(bitmap, 40, y)[0] for y in range(197, 204))
    assert middle > edge


def test_text_is_measured_in_the_font_it_will_be_drawn_in(draw):
    """The stock card right-aligns its price against a measured width.

    Measuring in one face and drawing in another puts the number a few
    pixels off the card's edge, and the error grows with the string. The
    name face is bold and a different size from the body face, so the two
    measurements must not agree.
    """
    import orb

    view = orb.Orb.__new__(orb.Orb)
    view._D = draw
    view._fonts = None
    view._private = None
    view._collection = None
    view._char_w = 8.0

    body = view._measure("$1,234.56")
    named = view._measure("$1,234.56", font=view._font_set()["name"])

    assert body > 0 and named > 0
    assert abs(body - named) > 0.5, (
        f"the name face measured the same as the body face: {body} vs {named}")


def test_the_card_has_scanlines(draw, surface):
    """The CRT look: every third row a little darker, over the colour."""
    bitmap, graphics = surface
    overlay_paint.Backdrop(draw).panel(graphics, 30, 0, 500, 200, t=0.0)
    # Between two columns of dots, low on the card where the colour is.
    light = [sum(pixel(bitmap, 250, y)[1:]) for y in range(150, 196)]
    dips = [offset for offset in range(3)
            if all(light[i] < light[i - 1] and light[i] < light[i + 1]
                   for i in range(1, len(light) - 1) if i % 3 == offset)]
    assert dips, f"no row in three is darker than its neighbours: {light}"


def test_mini_apollo_blinks_and_looks_about():
    import overlay_paint as P
    shut = [P.MiniApollo.blink(t / 100) for t in range(0, 900)]
    assert max(shut) == 1.0 and min(shut) == 0.0
    assert sum(1 for s in shut if s > 0.5) < len(shut) * 0.1        # open most of the time
    assert P.MiniApollo.gaze(1.0, busy=True) != P.MiniApollo.gaze(1.0)
