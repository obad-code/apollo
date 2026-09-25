"""Apollo at rest, as a CD (overlay_paint.cd_disc and cd_sheen): a silver
disc with a hole in the middle and a clear hub round it, three bands of tape
on it - green inside, then yellow, then red at the edge - broken into lengths
so that its turning shows, and over it a rainbow that stays where the light
is while the disc turns under it.

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
    hub = at(disc, 0.27, 45)
    assert 0 < hub[3] < 200                          # see-through, not solid


def test_three_bands_of_tape_green_yellow_red_from_the_middle_out(disc):
    def colour_of(fraction):
        # Several angles, so a gap in the tape cannot decide it.
        samples = [at(disc, fraction, d) for d in range(3, 360, 17)]
        return np.median(np.array(samples), axis=0)
    green, yellow, red = colour_of(0.48), colour_of(0.66), colour_of(0.85)
    assert green[1] > green[0] + 60 and green[1] > green[2] + 40
    assert yellow[0] > yellow[2] + 90 and yellow[1] > yellow[2] + 80
    assert red[0] > red[1] + 90 and red[0] > red[2] + 90


def test_the_tape_is_in_lengths_so_the_turning_shows(disc):
    round_the_red = [at(disc, 0.85, d / 2.0) for d in range(720)]
    reds = [p[0] - p[1] for p in round_the_red]
    assert max(reds) > 90                            # tape
    assert min(reds) < 30                            # ...and the silver between lengths


def test_the_disc_between_the_tapes_is_silver(disc):
    between = at(disc, 0.57, 20)
    assert between[3] > 230
    assert max(between[:3]) - min(between[:3]) < 40   # grey, not a colour


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
