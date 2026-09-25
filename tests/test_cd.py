"""Apollo at rest, as a CD (overlay_paint.cd_disc and cd_sheen): a black
disc with a hole in the middle and a clear hub round it, four bands of tape
on it - blue inside, then green, then yellow, then red at the edge - each
laid in tiny triangles pointing the way it turns, so that its turning shows,
and over it a rainbow that stays where the light is while the disc turns
under it.

The pixels are worked out with numpy, so they can be checked anywhere; only
handing them to GDI+ needs Windows."""
import math

import numpy as np
import pytest

import overlay_paint

SIZE = 190
RADIUS = 67


@pytest.fixture(scope="module")
def disc():
    return overlay_paint.cd_disc(SIZE, RADIUS)


@pytest.fixture(scope="module")
def sheen():
    return overlay_paint.cd_sheen(SIZE, RADIUS)


def at(pixels, fraction, degrees):
    """The pixel `fraction` of the radius out from the centre, at `degrees`
    (0 to the right, 90 straight down)."""
    c = SIZE / 2.0
    a = math.radians(degrees)
    x = int(round(c + math.cos(a) * RADIUS * fraction))
    y = int(round(c + math.sin(a) * RADIUS * fraction))
    return pixels[y, x].astype(int)


def test_it_is_a_square_of_premultiplied_pixels(disc, sheen):
    for pixels in (disc, sheen):
        assert pixels.shape == (SIZE, SIZE, 4) and pixels.dtype == np.uint8
        # Premultiplied, as GDI+ and UpdateLayeredWindow take them: no colour
        # brighter than its own coverage.
        assert (pixels[..., :3].max(axis=2) <= pixels[..., 3]).all()


def test_the_hole_and_the_space_round_it_are_clear(disc, sheen):
    assert disc[SIZE // 2, SIZE // 2, 3] == 0
    assert sheen[SIZE // 2, SIZE // 2, 3] == 0
    assert disc[2, 2, 3] == 0 and disc[SIZE - 3, SIZE - 3, 3] == 0


def test_the_hub_round_the_hole_is_clear_plastic(disc):
    hub = at(disc, 0.25, 45)
    assert 0 < hub[3] < 200                          # see-through, not solid


def round_the_circle(pixels, fraction, steps=720):
    return [at(pixels, fraction, d * 360.0 / steps) for d in range(steps)]


def test_four_bands_of_tape_blue_green_yellow_red_from_the_middle_out(disc):
    def brightest(fraction, channel_test):
        return any(channel_test(p) for p in round_the_circle(disc, fraction))
    assert brightest(0.45, lambda p: p[2] > p[0] + 90 and p[2] > p[1] + 30)       # blue
    assert brightest(0.59, lambda p: p[1] > p[0] + 60 and p[1] > p[2] + 40)       # green
    assert brightest(0.73, lambda p: p[0] > p[2] + 90 and p[1] > p[2] + 80)       # yellow
    assert brightest(0.88, lambda p: p[0] > p[1] + 90 and p[0] > p[2] + 90)       # red


def lit(p):
    return max(p[:3]) > 90


def test_the_tape_is_tiny_triangles_not_lengths(disc):
    # Along the middle of the red band a triangle is widest; near the band's
    # edge only its base is there. A rectangle would cover both the same; at
    # this size, with its point smoothed over a pixel, a triangle covers the
    # middle at least twice as much.
    middle = sum(lit(p) for p in round_the_circle(disc, 0.88))
    edge = sum(lit(p) for p in round_the_circle(disc, 0.925))
    assert middle > 2.0 * max(edge, 1)
    # ...and they are small: many of them round the band.
    runs = sum(1 for a, b in zip(round_the_circle(disc, 0.88), round_the_circle(disc, 0.88)[1:])
               if lit(b) and not lit(a))
    assert runs >= 24


def test_the_disc_between_the_tapes_is_black(disc):
    for fraction in (0.52, 0.66, 0.80):
        between = at(disc, fraction, 20)
        assert between[3] > 230                          # solid
        assert max(between[:3]) < 70                     # ...and dark


def test_the_edge_is_smooth_not_stepped(disc):
    alphas = {int(at(disc, 1.0, d)[3]) for d in range(0, 90, 3)}
    assert any(0 < a < 255 for a in alphas)          # part-covered pixels on the rim


def test_the_rainbow_has_more_than_one_colour_and_lies_on_the_disc(sheen):
    lit = sheen[sheen[..., 3] > 40]
    assert len(lit) > 50
    leaders = {int(np.argmax(p[:3])) for p in lit}
    assert leaders == {0, 1, 2}                      # red, green and blue all lead somewhere
    # It is on the disc - and some of it in the part that hangs below the edge.
    ys, xs = np.nonzero(sheen[..., 3] > 40)
    assert np.hypot(xs - SIZE / 2, ys - SIZE / 2).max() <= RADIUS * 1.25
    assert ys.max() > SIZE / 2 + RADIUS * 0.6
