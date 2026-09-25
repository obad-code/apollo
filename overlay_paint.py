"""The overlay's paint box: every piece of the approved design, drawn in GDI+.

The overlay cannot be a web page - a WebView2 window here paints over the
desktop whatever you ask it (see `apollo.py`'s docstring and
`probes/probe_transparent_matrix.py`) - so the design is built from shapes
instead. What matters most is the frame budget: the overlay redraws sixty
times a second while you are speaking, and GDI+ gradients are far too slow to
build per frame. So anything that does not change every frame is rendered
once into a bitmap and blitted: the card's stock, the veil over it, the dot
grid, and the four soft colours that drift underneath. What is left per frame
is a handful of DrawImage calls and the things that genuinely move.

The card hangs out of the top edge of the screen, so its top corners are
square - that edge is above the screen. It was cream; it is black now, a
tube's glass with five coloured lights drifting slowly through it - the full
display's own rose, sky, sun, iris and mint - overlapping into one moving
gradient, the printed dots kept, faint scanlines, and light ink. Apollo's own
mark kept its colours.
"""

import ctypes
import math
import random

import numpy as np

PALETTE = {
    # The card itself: the glass, and the light on it.
    "card": (10, 9, 7),
    "ink": (255, 239, 208),       # Apollo's own words, warm white
    "you": (224, 206, 170),       # yours, and the line under them
    "caption": (184, 162, 122),
    # The five lights that drift through it: the full display's colours, so
    # the two halves of Apollo glow the same. It was one amber, which read
    # as a brown smear at the foot of the card.
    "rose": (255, 70, 150),
    "sky": (40, 186, 255),
    "sun": (255, 158, 40),
    "iris": (138, 92, 255),
    "mint": (40, 226, 158),
    # The ring, the charts and the cards, at the brightness a black card
    # needs - the darker set was for cream paper.
    "amber": (255, 190, 70),
    "up": (104, 226, 146),
    "down": (255, 112, 120),
    "cyan": (110, 214, 232),
    "violet": (196, 166, 255),
    "teal": (100, 214, 214),
    "white": (255, 246, 224),
}

# Each light: colour, where it rests (as a fraction of the card), how far it
# wanders, how long one loop takes, and how strong it is. Spread across the
# card and wandering wide, on long loops of their own lengths, so they cross
# and mix into different gradients all the time and never in step. Two sit
# up where the words are; none reaches the strip above the screen's edge,
# which the veil keeps black.
BLOBS = (("rose", (0.12, 0.95), (0.30, 0.22), 17.0, 0.58),
         ("sky", (0.88, 0.90), (0.28, 0.24), 19.0, 0.56),
         ("sun", (0.50, 1.10), (0.38, 0.16), 23.0, 0.50),
         ("iris", (0.70, 0.62), (0.26, 0.20), 21.0, 0.50),
         ("mint", (0.30, 0.66), (0.24, 0.18), 26.0, 0.46))

# Where the glass stops covering the colour, as fractions of the card's
# height: opaque down to the first - the strip that hides above the screen -
# and clear by the second.
SCRIM = (0.12, 0.60)

DOT_ALPHA = 30           # light dots, faint, on the black
DOT_EVERY = 9
DOT_INK = (255, 226, 160)

# A tube's scanlines: one darker row in every three, over the colour and the
# dots alike, drawn once into a bitmap like the rest. Faint: at 30% they
# striped the gradient into a grille and it stopped reading as one.
SCANLINE_EVERY = 3
SCANLINE_ALPHA = 0.12
# The design lays a noise tile over the card as well. It is left out: in GDI+
# it costs a SetPixel per pixel to build, and at the card's size the dot grid
# carries the same texture for the price of one blit.

RADIUS = 28              # the card's bottom corners; the top ones are square
                         # because that edge sits above the screen
EDGE = (255, 214, 140, 70)   # the hairline around it, warm, over any desktop
# How much of the card hides above the screen's edge. The part that hides is
# paper the content does not need, so nothing readable is ever cut off.
HIDDEN = 0.25


def alpha(colour, a):
    """An (r, g, b) and an alpha 0-1, in the (a, r, g, b) order GDI+ takes.

    The order matters and it is easy to get wrong: `Color.FromArgb` reads
    four arguments as alpha first, so returning (r, g, b, a) here paints the
    red channel as transparency - which looked like a green panel.
    """
    return (max(0, min(255, int(round(a * 255)))), colour[0], colour[1], colour[2])


def rounded_path(draw, x, y, w, h, radius, top_radius=0):
    """A rectangle with independent top and bottom corner radii."""
    path = draw.Drawing2D.GraphicsPath()
    top_d, bottom_d = top_radius * 2, radius * 2
    if top_radius:
        path.AddArc(float(x), float(y), float(top_d), float(top_d), 180, 90)
        path.AddArc(float(x + w - top_d), float(y), float(top_d), float(top_d), 270, 90)
    else:
        path.AddLine(float(x), float(y), float(x + w), float(y))
    if radius:
        path.AddArc(float(x + w - bottom_d), float(y + h - bottom_d),
                    float(bottom_d), float(bottom_d), 0, 90)
        path.AddArc(float(x), float(y + h - bottom_d), float(bottom_d), float(bottom_d), 90, 90)
    else:
        path.AddLine(float(x + w), float(y + h), float(x), float(y + h))
    path.CloseFigure()
    return path


def nebula(draw, size, colour, strength):
    """One soft round cloud, rendered once and then moved around.

    A real radial gradient (PathGradientBrush with a bell falloff), not a
    stack of discs: discs band, and banding is exactly what a soft light must
    not do.
    """
    bitmap = draw.Bitmap(size, size, draw.Imaging.PixelFormat.Format32bppPArgb)
    graphics = draw.Graphics.FromImage(bitmap)
    try:
        graphics.SmoothingMode = draw.Drawing2D.SmoothingMode.AntiAlias
        path = draw.Drawing2D.GraphicsPath()
        path.AddEllipse(0.0, 0.0, float(size), float(size))
        brush = draw.Drawing2D.PathGradientBrush(path)
        brush.CenterColor = draw.Color.FromArgb(*alpha(colour, strength))
        brush.SurroundColors = [draw.Color.FromArgb(0, *colour)]
        # A blend rather than SetSigmaBellShape: the bell leaves a dark speck
        # at the centre point (visible on a dark panel) and concentrates the
        # colour too tightly to read as a cloud.
        blend = draw.Drawing2D.ColorBlend(5)
        blend.Colors = [draw.Color.FromArgb(0, *colour),
                        draw.Color.FromArgb(*alpha(colour, strength * 0.25)),
                        draw.Color.FromArgb(*alpha(colour, strength * 0.65)),
                        draw.Color.FromArgb(*alpha(colour, strength * 0.92)),
                        draw.Color.FromArgb(*alpha(colour, strength))]
        blend.Positions = [0.0, 0.35, 0.65, 0.85, 1.0]
        brush.InterpolationColors = blend
        graphics.FillPath(brush, path)
        brush.Dispose()
        path.Dispose()
    finally:
        graphics.Dispose()
    return bitmap


def dot_grid(draw, w, h):
    """The card's printed texture: one ink dot every nine pixels.

    Drawn once into a bitmap the size of the card and blitted, like everything
    else here - a few thousand FillEllipse calls per frame would cost more
    than the whole rest of the overlay.
    """
    bitmap = draw.Bitmap(w, h, draw.Imaging.PixelFormat.Format32bppPArgb)
    graphics = draw.Graphics.FromImage(bitmap)
    try:
        graphics.SmoothingMode = draw.Drawing2D.SmoothingMode.AntiAlias
        brush = draw.SolidBrush(draw.Color.FromArgb(DOT_ALPHA, *DOT_INK))
        for y in range(4, h, DOT_EVERY):
            for x in range(4, w, DOT_EVERY):
                graphics.FillEllipse(brush, float(x), float(y), 1.6, 1.6)
        brush.Dispose()
    finally:
        graphics.Dispose()
    return bitmap


def scanlines(draw, w, h):
    """Every third row darkened, for the whole card: the tube's raster."""
    bitmap = draw.Bitmap(w, h, draw.Imaging.PixelFormat.Format32bppPArgb)
    graphics = draw.Graphics.FromImage(bitmap)
    try:
        brush = draw.SolidBrush(draw.Color.FromArgb(*alpha((0, 0, 0), SCANLINE_ALPHA)))
        for y in range(0, h, SCANLINE_EVERY):
            graphics.FillRectangle(brush, 0, y, w, 1)
        brush.Dispose()
    finally:
        graphics.Dispose()
    return bitmap


def paper(draw, w, h, colour):
    """The card's stock: opaque, edge to edge.

    It has to be solid everywhere. The colour goes on top of it and the veil
    on top of that; paper that thinned out where the veil ends would leave the
    card see-through in its lower half, because soft blobs do not cover.
    """
    bitmap = draw.Bitmap(w, h, draw.Imaging.PixelFormat.Format32bppPArgb)
    graphics = draw.Graphics.FromImage(bitmap)
    try:
        brush = draw.SolidBrush(draw.Color.FromArgb(*alpha(colour, 1.0)))
        graphics.FillRectangle(brush, draw.Rectangle(0, 0, w, h))
        brush.Dispose()
    finally:
        graphics.Dispose()
    return bitmap


def veil(draw, w, h, colour):
    """Paper laid back over the colour: solid at the top, gone by the bottom.

    This is the design's scrim and its blob mask in one pass - both are the
    same cream fading downward, and one gradient does the work of two.
    """
    bitmap = draw.Bitmap(w, h, draw.Imaging.PixelFormat.Format32bppPArgb)
    graphics = draw.Graphics.FromImage(bitmap)
    try:
        rectangle = draw.Rectangle(0, 0, w, h)
        brush = draw.Drawing2D.LinearGradientBrush(
            rectangle, draw.Color.FromArgb(*alpha(colour, 1.0)),
            draw.Color.FromArgb(0, *colour),
            draw.Drawing2D.LinearGradientMode.Vertical)
        # A ColorBlend has to run all the way to 1.0, so the last stop repeats
        # the clear one at the card's foot rather than stopping at the scrim.
        blend = draw.Drawing2D.ColorBlend(5)
        blend.Colors = [draw.Color.FromArgb(*alpha(colour, 1.0)),
                        draw.Color.FromArgb(*alpha(colour, 1.0)),
                        draw.Color.FromArgb(*alpha(colour, 0.42)),
                        draw.Color.FromArgb(0, *colour),
                        draw.Color.FromArgb(0, *colour)]
        blend.Positions = [0.0, SCRIM[0], (SCRIM[0] + SCRIM[1]) / 2.0, SCRIM[1], 1.0]
        brush.InterpolationColors = blend
        graphics.FillRectangle(brush, rectangle)
        brush.Dispose()
    finally:
        graphics.Dispose()
    return bitmap


class Backdrop:
    """The card: glass, five lights drifting under it, and a printed grid.

    The order is the design's: blobs at the bottom, a mask that keeps them out
    of the upper half, the paper's scrim over them, then the dot grid on top.
    Everything except the blobs' positions is cached and blitted, so a frame
    costs six DrawImage calls and a clip; the blobs move by being drawn
    somewhere else, never by being rebuilt.

    Its top corners are square on purpose. That edge lives above the top of
    the screen, so rounding it would round something nobody can see.
    """

    def __init__(self, draw):
        self.draw = draw
        self.cached_size = None
        self._paper = None
        self._veil = None
        self._dots = None
        self._lines = None
        self._blobs = []

    def invalidate(self):
        for bitmap in ([self._paper, self._veil, self._dots, self._lines]
                       + [b for _, b in self._blobs]):
            try:
                bitmap.Dispose()
            except Exception:
                pass
        self._paper = self._veil = self._dots = self._lines = None
        self._blobs = []
        self.cached_size = None

    def _build(self, w, h):
        draw = self.draw
        self.invalidate()
        self.cached_size = (w, h)
        self._paper = paper(draw, w, h, PALETTE["card"])
        self._veil = veil(draw, w, h, PALETTE["card"])
        self._dots = dot_grid(draw, w, h)
        self._lines = scanlines(draw, w, h)
        # Wider than the card: a light that only just reaches the edge reads
        # as a disc, and these are meant to spill past it and into each other.
        size = int(max(w, h) * 1.3)
        self._blobs = [(spec, nebula(draw, size, PALETTE[spec[0]], spec[4]))
                       for spec in BLOBS]

    def panel(self, g, x, y, w, h, t, alpha_scale=1.0):
        """Paint the card at (x, y). `t` is seconds; the blobs drift on it."""
        w, h = int(w), int(h)
        if h <= 0 or w <= 0:
            return
        if self.cached_size != (w, h):
            self._build(w, h)

        draw = self.draw
        path = rounded_path(draw, x, y, w, h, RADIUS)
        state = g.Save()
        try:
            g.SetClip(path)
            attributes = self._fade(alpha_scale)
            # The stock first, at full strength, so the card is opaque paper
            # rather than a tint over the desktop.
            self._blit(g, self._paper, x, y, w, h, attributes)
            for spec, blob in self._blobs:
                _, (home_x, home_y), (drift_x, drift_y), period, _ = spec
                phase = 2 * math.pi * (t % period) / period
                offset_x = (x + w * home_x - blob.Width / 2
                            + math.cos(phase) * w * drift_x)
                offset_y = (y + h * home_y - blob.Height / 2
                            + math.sin(phase * 1.3) * h * drift_y)
                self._blit(g, blob, offset_x, offset_y, blob.Width, blob.Height,
                           attributes)
            self._blit(g, self._veil, x, y, w, h, attributes)
            self._blit(g, self._dots, x, y, w, h, attributes)
            self._blit(g, self._lines, x, y, w, h, attributes)
            # The hairline around the card, which is what separates it from a
            # desktop as dark as it is.
            pen = draw.Pen(draw.Color.FromArgb(
                int(EDGE[3] * max(0.0, min(1.0, alpha_scale))), *EDGE[:3]), 1.0)
            g.DrawPath(pen, path)
            pen.Dispose()
        finally:
            g.Restore(state)
            path.Dispose()

    def _blit(self, g, bitmap, x, y, w, h, attributes):
        draw = self.draw
        destination = draw.Rectangle(int(round(x)), int(round(y)), int(w), int(h))
        if attributes is None:
            g.DrawImage(bitmap, destination, 0, 0, bitmap.Width, bitmap.Height,
                        draw.GraphicsUnit.Pixel)
        else:
            g.DrawImage(bitmap, destination, 0, 0, bitmap.Width, bitmap.Height,
                        draw.GraphicsUnit.Pixel, attributes)

    def _fade(self, scale):
        if scale >= 0.999:
            return None
        draw = self.draw
        matrix = draw.Imaging.ColorMatrix()
        matrix.Matrix33 = max(0.0, min(1.0, scale))
        attributes = draw.Imaging.ImageAttributes()
        attributes.SetColorMatrix(matrix)
        return attributes


# The searching orb: three rings of points turning against each other, cyan
# at the core. Each is (radius as a fraction, how many points, turns per
# second, colour). Counter-rotation is what makes it read as something
# running rather than as one object spinning.
RING_SPEC = ((1.00, 22, 0.026, (255, 193, 94)),
             (0.85, 18, -0.034, (255, 176, 0)),
             (0.70, 14, 0.045, (86, 197, 214)))

# The same mark at the size it sits in the card's footer. Twenty-two points
# around a 22-pixel radius are three pixels apart and read as a smudge, so the
# small mark keeps the three counter-turning rings and drops the point count
# until each one is a point again. On the black card it takes the big ring's
# own colours; the darkened set was for cream paper.
RING_SPEC_SMALL = ((1.00, 11, 0.026, (255, 204, 96)),
                   (0.72, 8, -0.034, (255, 176, 0)),
                   (0.44, 5, 0.045, (86, 197, 214)))
SMALL_BELOW = 34         # outer radius, in pixels

# One point's glow: concentric discs, widest first. Eight closely spaced
# steps rather than four wide ones - with wide steps each disc's own edge
# shows inside the glow, which is the opposite of soft.
BLOOM = ((4.6, 0.018), (3.9, 0.028), (3.3, 0.042), (2.75, 0.062),
         (2.25, 0.090), (1.8, 0.130), (1.4, 0.230), (1.0, 1.000))

SPARKLE_COLOURS = ("white", "cyan", "violet", "amber")


class _Brushes:
    """Cached solid brushes. Building one per point per frame is hundreds of
    allocations across pythonnet; measured, that alone took a full-voice frame
    from comfortable to dropping."""

    STEP = 2

    def __init__(self, draw):
        self.draw = draw
        self._brushes = {}
        self._pens = {}

    def brush(self, colour, a):
        a = min(255, (int(a) // self.STEP) * self.STEP)
        key = (colour, a)
        found = self._brushes.get(key)
        if found is None:
            found = self.draw.SolidBrush(self.draw.Color.FromArgb(a, *colour))
            self._brushes[key] = found
        return found

    def pen(self, colour, a, width=1.0):
        a = min(255, (int(a) // self.STEP) * self.STEP)
        key = (colour, a, width)
        found = self._pens.get(key)
        if found is None:
            found = self.draw.Pen(self.draw.Color.FromArgb(a, *colour), float(width))
            self._pens[key] = found
        return found


def bloom(g, brushes, x, y, r, colour, a, spread=1.0):
    """One glowing point: a soft halo with a solid core inside it."""
    for multiple, weight in BLOOM:
        strength = a * weight
        if strength <= 1.0:
            continue
        radius = r * multiple * (1.0 if multiple <= 1.0 else spread)
        g.FillEllipse(brushes.brush(colour, strength),
                      float(x - radius), float(y - radius),
                      float(radius * 2), float(radius * 2))


class Glow:
    """One pre-rendered glowing point, stamped wherever a point goes.

    Measured: drawing the eight bloom discs per point cost 8.9 ms a frame for
    the orb's fifty-four points - more than half the frame budget on its own.
    The glow does not change shape, only place and brightness, so it is drawn
    once per colour and blitted after that.
    """

    PAD = 1.15          # the sprite is a little wider than the widest disc

    def __init__(self, draw, colour, dot, spread=1.0, bloom=True):
        self.draw = draw
        self.colour = colour
        self.dot = dot
        # Without a bloom the sprite is the point itself and nothing more.
        self.bloom = BLOOM if bloom else ((1.0, 1.0),)
        radius = dot * self.bloom[0][0] * spread * self.PAD
        self.size = max(4, int(radius * 2) + 2)
        self.centre = self.size / 2.0
        bitmap = draw.Bitmap(self.size, self.size, draw.Imaging.PixelFormat.Format32bppPArgb)
        graphics = draw.Graphics.FromImage(bitmap)
        try:
            graphics.SmoothingMode = draw.Drawing2D.SmoothingMode.AntiAlias
            for multiple, weight in self.bloom:
                strength = 255 * weight
                if strength <= 1.0:
                    continue
                r = dot * multiple * (1.0 if multiple <= 1.0 else spread)
                brush = draw.SolidBrush(draw.Color.FromArgb(*alpha(colour, weight)))
                graphics.FillEllipse(brush, float(self.centre - r), float(self.centre - r),
                                     float(r * 2), float(r * 2))
                brush.Dispose()
        finally:
            graphics.Dispose()
        self.bitmap = bitmap
        self._fades = {}

    def fade(self, a):
        """ImageAttributes for a given brightness, cached in 16 steps."""
        key = min(16, max(0, int(a / 255 * 16)))
        found = self._fades.get(key)
        if found is None:
            draw = self.draw
            matrix = draw.Imaging.ColorMatrix()
            matrix.Matrix33 = key / 16.0
            found = draw.Imaging.ImageAttributes()
            found.SetColorMatrix(matrix)
            self._fades[key] = found
        return found

    def stamp(self, g, x, y, a):
        if a <= 6:
            return
        destination = self.draw.Rectangle(int(round(x - self.centre)),
                                          int(round(y - self.centre)),
                                          self.size, self.size)
        g.DrawImage(self.bitmap, destination, 0, 0, self.size, self.size,
                    self.draw.GraphicsUnit.Pixel, self.fade(a))


class RingSprite:
    """One ring of glowing points, drawn once and then rotated into place.

    Stamping fifty-four glows a frame cost 4 ms; a ring does not change shape
    as it turns, so each is rendered once and drawn with a rotation. The
    twinkle that gives the orb its life would be lost that way, so a handful
    of variants are rendered with the brightness pattern shifted, and the
    frame picks one - the eye reads that as the same shimmer.
    """

    VARIANTS = 6

    def __init__(self, draw, colour, count, radius, dot, spread=1.0, bloom=True):
        self.draw = draw
        self.count = count
        reach = dot * BLOOM[0][0] * spread if bloom else dot
        self.size = int((radius + reach) * 2) + 4
        centre = self.size / 2.0
        # On cream paper a bloom has nothing to bloom into: the halos merge
        # and the mark reads as one fuzzy disc instead of three rings. The
        # small mark is drawn as plain points.
        glow = Glow(draw, colour, dot, spread, bloom=bloom)
        self.frames = []
        for variant in range(self.VARIANTS):
            bitmap = draw.Bitmap(self.size, self.size, draw.Imaging.PixelFormat.Format32bppPArgb)
            graphics = draw.Graphics.FromImage(bitmap)
            try:
                graphics.SmoothingMode = draw.Drawing2D.SmoothingMode.AntiAlias
                points = [(centre + math.cos(-math.tau / 4 + i * math.tau / count) * radius,
                           centre + math.sin(-math.tau / 4 + i * math.tau / count) * radius)
                          for i in range(count)]
                pen = draw.Pen(draw.Color.FromArgb(40, *colour), 1.0)
                for i, (px, py) in enumerate(points):
                    qx, qy = points[(i + 1) % count]
                    graphics.DrawLine(pen, float(px), float(py), float(qx), float(qy))
                pen.Dispose()
                phase = variant / self.VARIANTS * math.tau
                for i, (px, py) in enumerate(points):
                    twinkle = 0.80 + 0.20 * math.sin(phase + i * math.tau / count)
                    glow.stamp(graphics, px, py, 225 * twinkle)
            finally:
                graphics.Dispose()
            self.frames.append(bitmap)
        self._fades = {}

    def _fade(self, scale):
        key = min(16, max(0, int(scale * 16)))
        found = self._fades.get(key)
        if found is None:
            matrix = self.draw.Imaging.ColorMatrix()
            matrix.Matrix33 = key / 16.0
            found = self.draw.Imaging.ImageAttributes()
            found.SetColorMatrix(matrix)
            self._fades[key] = found
        return found

    def draw_at(self, g, cx, cy, turn_degrees, t, fade=1.0):
        bitmap = self.frames[int(t * 3) % self.VARIANTS]
        state = g.Save()
        try:
            g.TranslateTransform(float(cx), float(cy))
            g.RotateTransform(float(turn_degrees))
            rectangle = self.draw.Rectangle(int(-self.size / 2), int(-self.size / 2),
                                            self.size, self.size)
            g.DrawImage(bitmap, rectangle, 0, 0, self.size, self.size,
                        self.draw.GraphicsUnit.Pixel, self._fade(fade))
        finally:
            g.Restore(state)


class Rings:
    """Apollo itself: the three-ring searching orb from the mockup."""

    DOT = 0.037            # point radius as a fraction of the outer radius
    DOT_SMALL = 0.115      # ...and at the size it sits on the card
    BREATH = 0.035         # how much the rings widen at full voice

    def __init__(self, draw):
        self.draw = draw
        self._sprites = {}

    def _sprite(self, colour, count, radius, dot, spread, bloom=True):
        # Quantised, or a new sprite would be built on every pixel of voice.
        key = (colour, count, int(radius), round(dot, 1), round(spread, 1), bloom)
        found = self._sprites.get(key)
        if found is None:
            found = RingSprite(self.draw, colour, count, radius, dot, spread,
                               bloom=bloom)
            self._sprites[key] = found
        return found

    def draw_at(self, g, cx, cy, radius, t, level=0.0, fade=1.0):
        if fade <= 0.01:
            return
        radius = radius * (1.0 + self.BREATH * level)
        small = radius <= SMALL_BELOW
        spec = RING_SPEC_SMALL if small else RING_SPEC
        dot = max(1.2, radius * (self.DOT_SMALL if small else self.DOT))
        spread = round(1.0 + 0.5 * level, 1)
        glow = min(1.0, fade * (1.0 + 0.6 * level))
        for fraction, count, turns, colour in spec:
            sprite = self._sprite(colour, count, radius * fraction, dot, spread,
                                  bloom=not small)
            sprite.draw_at(g, cx, cy, t * turns * 360.0, t, glow)


class Sparkles:
    """The sparkle field under the panel, from your sparkles component.

    Particles live in unit space, so the field can be drawn into any
    rectangle - which is what lets it follow the panel's bottom edge as the
    panel grows. They are masked into a dome: brightest just under the
    horizon, gone by the corners.
    """

    def __init__(self, draw, count=260, seed=7):
        self.draw = draw
        self.brushes = _Brushes(draw)
        rng = random.Random(seed)
        self.particles = [{"x": rng.random(), "y": rng.random(),
                           "vx": (rng.random() - 0.5) * 0.02,
                           "vy": (rng.random() - 0.5) * 0.02,
                           "r": 0.6 + rng.random() * 1.1,
                           "phase": rng.random() * math.tau,
                           "rate": 0.4 + rng.random() * 1.4,
                           "colour": PALETTE[SPARKLE_COLOURS[rng.randrange(4)]]}
                          for _ in range(count)]
        self.clock = 0.0
        self._field = None
        self._field_size = None
        self._field_at = -1.0
        self._fades = {}

    def advance(self, dt, level=0.0):
        self.clock += dt
        speed = 1.0 + 3.0 * level
        for particle in self.particles:
            particle["x"] = (particle["x"] + particle["vx"] * speed * dt * 10) % 1.0
            particle["y"] = (particle["y"] + particle["vy"] * speed * dt * 10) % 1.0

    # How often the field is actually redrawn. Two hundred and sixty dots cost
    # 3.6 ms a frame drawn one at a time, which is a fifth of the budget for
    # something that drifts across a minute; at twenty a second the motion is
    # identical to the eye and the cost is a single blit.
    FIELD_FPS = 20

    def draw_at(self, g, x, y, w, h, fade=1.0):
        if fade <= 0.01:
            return
        w, h = int(w), int(h)
        if (self._field is None or self._field_size != (w, h)
                or self.clock - self._field_at >= 1.0 / self.FIELD_FPS):
            self._render_field(w, h)
        destination = self.draw.Rectangle(int(x), int(y), w, h)
        g.DrawImage(self._field, destination, 0, 0, w, h,
                    self.draw.GraphicsUnit.Pixel, self._fade(fade))

    def _fade(self, scale):
        key = min(16, max(0, int(scale * 16)))
        found = self._fades.get(key)
        if found is None:
            matrix = self.draw.Imaging.ColorMatrix()
            matrix.Matrix33 = key / 16.0
            found = self.draw.Imaging.ImageAttributes()
            found.SetColorMatrix(matrix)
            self._fades[key] = found
        return found

    def _render_field(self, w, h):
        draw = self.draw
        if self._field is None or self._field_size != (w, h):
            if self._field is not None:
                self._field.Dispose()
            self._field = draw.Bitmap(w, h, draw.Imaging.PixelFormat.Format32bppPArgb)
            self._field_size = (w, h)
        graphics = draw.Graphics.FromImage(self._field)
        try:
            graphics.Clear(draw.Color.FromArgb(0, 0, 0, 0))
            # Antialiasing a one-pixel dot costs more than it shows.
            graphics.SmoothingMode = draw.Drawing2D.SmoothingMode.HighSpeed
            self._draw(graphics, 0, 0, w, h, 1.0)
        finally:
            graphics.Dispose()
        self._field_at = self.clock

    def _draw(self, g, x, y, w, h, fade):
        for particle in self.particles:
            px, py = x + particle["x"] * w, y + particle["y"] * h
            # The dome: strongest just under the horizon, gone by the corners
            # and by the bottom, so the field has no edges of its own. Sideways
            # and downward fall off separately - a round mask left the middle
            # of the field dark, which is where the sparkles should be.
            across = abs(particle["x"] - 0.5) * 2
            down = particle["y"]
            mask = max(0.0, 1.0 - across ** 2) * max(0.0, 1.0 - down ** 1.4)
            if mask <= 0.02:
                continue
            twinkle = 0.25 + 0.75 * abs(math.sin(self.clock * particle["rate"] + particle["phase"]))
            a = 255 * twinkle * mask * fade
            if a < 8:
                continue
            radius = particle["r"]
            g.FillEllipse(self.brushes.brush(particle["colour"], a),
                          float(px - radius), float(py - radius),
                          float(radius * 2), float(radius * 2))


def horizon(g, draw, x, y, w, fade=1.0):
    """The three hairlines under the panel: blurred, thin, and a bright core.

    A horizontal gradient that fades at both ends, so the line has no ends -
    the same trick the component uses, and the reason it reads as light on an
    edge rather than as a drawn rule.
    """
    if fade <= 0.01:
        return
    # GDI+ has no blur, so the "blurred" line is three stacked ones whose
    # alpha falls off - the same read, at the cost of two extra fills.
    layers = ((w * 0.58, 4.0, 0.16), (w * 0.56, 2.0, 0.40),
              (w * 0.52, 1.0, 1.0), (w * 0.26, 1.0, 1.0))
    for width, thickness, strength in layers:
        left = x + (w - width) / 2
        # Snapped to whole pixels: a 1px line drawn on a half-pixel is split
        # across two rows at half alpha each, which is how the brightest line
        # here managed to look like a smudge.
        top = int(round(y - thickness / 2))
        rectangle = draw.RectangleF(float(int(left)), float(top),
                                    float(int(width)), float(max(1, int(round(thickness)))))
        brush = draw.Drawing2D.LinearGradientBrush(
            rectangle, draw.Color.FromArgb(0, *PALETTE["violet"]),
            draw.Color.FromArgb(0, *PALETTE["cyan"]),
            draw.Drawing2D.LinearGradientMode.Horizontal)
        blend = draw.Drawing2D.ColorBlend(5)
        blend.Colors = [draw.Color.FromArgb(0, *PALETTE["violet"]),
                        draw.Color.FromArgb(int(215 * strength * fade), *PALETTE["violet"]),
                        draw.Color.FromArgb(int(255 * strength * fade), *PALETTE["white"]),
                        draw.Color.FromArgb(int(215 * strength * fade), *PALETTE["cyan"]),
                        draw.Color.FromArgb(0, *PALETTE["cyan"])]
        blend.Positions = [0.0, 0.25, 0.5, 0.75, 1.0]
        brush.InterpolationColors = blend
        g.FillRectangle(brush, rectangle)
        brush.Dispose()


# --- Apollo at rest, as a CD ----------------------------------------------------
#
# A black disc with a hole in the middle and a clear hub round it, and four
# bands of tape on it - blue inside, then green, then yellow, then red at the
# edge - each laid in tiny triangles, every one pointing the way the disc
# turns, so that its turning shows. Over it, a rainbow where the light
# catches the tracks, the way a CD throws one: it stays where the light is
# while the disc turns under it, so it is a layer of its own. Both are worked
# out in numpy, once per size, and drawn each frame as two bitmaps - one
# turned, one not.

CD_HOLE = 0.15           # the hole, as a fraction of the disc's radius
CD_HUB = 0.34            # ...the clear hub round it, out to here
CD_MIRROR = 0.38         # ...and a bright ring where the tracks start
CD_TAPES = ((0.40, 0.50, (60, 130, 255)),      # blue, innermost
            (0.54, 0.64, (46, 196, 96)),       # green
            (0.68, 0.78, (252, 206, 44)),      # yellow
            (0.82, 0.94, (232, 44, 52)))       # red, at the edge
CD_TIP = 0.78            # how far along its place a triangle reaches; the rest is black
CD_BLACK = (14, 15, 20)
CD_RAINBOW = (70.0, 250.0)   # where the light falls on it, degrees (90 is down)
CD_HALO = (120, 170, 255)    # the faint light round its rim: blue


def _cd_polar(size):
    """Each pixel's distance from the middle of a size x size square, and its
    angle - 0 to the right, pi/2 straight down."""
    ys, xs = np.mgrid[0:size, 0:size].astype(np.float64) + 0.5
    dx, dy = xs - size / 2.0, ys - size / 2.0
    return np.hypot(dx, dy), np.arctan2(dy, dx)


def _between(r, low, high):
    """How much of each pixel lies between two radii, edges smoothed over a
    pixel so a circle is round rather than stepped."""
    return np.clip(r - low + 0.5, 0.0, 1.0) * np.clip(high - r + 0.5, 0.0, 1.0)


def _premultiplied(colour, cover):
    """Straight colour (h x w x 3, 0-255) and coverage (h x w, 0-1) as the
    premultiplied RGBA bytes GDI+ and UpdateLayeredWindow take: no channel
    brighter than its pixel's own coverage."""
    a = np.round(np.clip(cover, 0.0, 1.0) * 255.0)
    rgb = np.minimum(np.round(np.clip(colour, 0.0, 255.0) * np.clip(cover, 0.0, 1.0)[..., None]),
                     a[..., None])
    return np.dstack([rgb, a]).astype(np.uint8)


def cd_disc(size, radius):
    """The disc itself, the part that turns: RGBA, premultiplied, size x size,
    the disc `radius` pixels round the middle."""
    r, theta = _cd_polar(size)
    R = float(radius)
    # Black, with the tracks' fine grooves just showing in it.
    shade = 1.0 + 0.35 * np.sin(r * 2.7)
    colour = np.empty((size, size, 3))
    colour[:] = CD_BLACK
    colour *= shade[..., None]
    cover = _between(r, R * CD_HOLE, R)

    # The hub: clear plastic, faintly ringed, a brighter lip round the hole.
    hub = r < R * CD_HUB
    colour[hub] = (225, 230, 236)
    hub_cover = 0.3 + 0.12 * np.sin(r * 3.0) + 0.3 * np.exp(-((r - R * CD_HOLE) / 1.6) ** 2)
    cover = np.where(hub, cover * hub_cover, cover)
    # The bright ring where the tracks start, a little blue.
    mirror = _between(r, R * CD_HUB, R * CD_MIRROR)
    colour = colour * (1 - mirror[..., None]) + np.array((196, 214, 248)) * mirror[..., None]

    # The tapes: each band laid in tiny triangles, one after another round
    # it, each with its base across the band and its point the way the disc
    # turns (clockwise on the screen, as theta runs). About as long as the
    # band is wide, so a band carries twenty to forty of them.
    for low, high, tint in CD_TAPES:
        middle = (low + high) / 2.0
        count = max(8, int(round(2 * np.pi * middle / (1.3 * (high - low)))))
        half = R * (high - low) / 2.0                      # the band's half width, pixels
        place = 2 * np.pi * np.maximum(r, 1.0) / count     # one triangle's place, pixels along
        along = (theta / (2 * np.pi) * count + low * 7.0) % 1.0
        # Pixels from the triangle's base, forward along the band; just before
        # the base (the end of the last place) counts as a little behind it.
        ahead = np.where(along < 0.5, along, along - 1.0) * place
        tip = CD_TIP * place
        width = half * np.clip(1.0 - ahead / tip, 0.0, 1.0)
        across = np.abs(r - R * middle)
        inside = np.clip(width - across + 0.5, 0.0, 1.0) \
               * np.clip(ahead + 0.5, 0.0, 1.0) * np.clip(tip - ahead + 0.5, 0.0, 1.0)
        tape = inside * _between(r, R * low, R * high)
        gloss = np.exp(-(across / (half * 0.45)) ** 2)
        lit = np.array(tint, dtype=np.float64)[None, None, :] * (0.88 + 0.12 * gloss[..., None]) \
            + 14.0 * gloss[..., None]
        colour = colour * (1 - tape[..., None]) + lit * tape[..., None]

    # The rim: a thin line of blue light round the black.
    rim = _between(r, R - 1.5, R)
    colour = colour * (1 - rim[..., None]) + np.array((70, 120, 220)) * rim[..., None]
    return _premultiplied(colour, cover)


def _hues(hue):
    """Hue 0-1 to a fully saturated RGB, 0-255."""
    k = (hue[..., None] * 6.0 + np.array((0.0, 4.0, 2.0))) % 6.0
    return 255.0 * (1.0 - np.clip(np.minimum(k, 4.0 - k), 0.0, 1.0))


def cd_sheen(size, radius):
    """What the light does on it, the part that stays still: a rainbow thrown
    across the tracks where the light falls, a soft white highlight in it,
    and a faint warm halo round the rim. RGBA, premultiplied."""
    r, theta = _cd_polar(size)
    R = float(radius)
    colour = np.zeros((size, size, 3))
    cover = np.zeros((size, size))
    tracks = _between(r, R * CD_MIRROR, R - 1.0)
    for i, degrees in enumerate(CD_RAINBOW):
        centre = np.radians(degrees)
        off = np.angle(np.exp(1j * (theta - centre)))            # -pi..pi from the light
        strength = np.exp(-(off / 0.36) ** 2) * tracks * (0.74 if i == 0 else 0.5)
        hue = (r / R * 1.3 + off * 0.45 + 0.05) % 1.0
        rainbow = _hues(hue) * 0.82 + 255.0 * 0.12
        colour = colour * (1 - strength[..., None]) + rainbow * strength[..., None]
        cover = cover + strength * (1 - cover)
    # A soft white highlight where the light is brightest.
    spot_at = np.radians(CD_RAINBOW[0])
    sx, sy = np.cos(spot_at) * R * 0.66, np.sin(spot_at) * R * 0.66
    ys, xs = np.mgrid[0:size, 0:size].astype(np.float64) + 0.5
    spot = np.exp(-(((xs - size / 2.0 - sx) ** 2 + (ys - size / 2.0 - sy) ** 2) / (R * 0.2) ** 2))
    spot = spot * tracks * 0.38
    colour = colour * (1 - spot[..., None]) + 255.0 * spot[..., None]
    cover = cover + spot * (1 - cover)
    # A faint warm halo just outside the rim, so it reads as lit on any desktop.
    outside = np.clip(r - R + 0.5, 0.0, 1.0)
    halo = 0.24 * np.exp(-((r - R) / (R * 0.07)) ** 2) * outside
    colour = colour * (1 - halo[..., None]) + np.array(CD_HALO) * halo[..., None]
    cover = cover + halo * (1 - cover)
    # Each layer above was laid over the last the way premultiplied colour is
    # (colour * (1 - a) + new * a), so `colour` is premultiplied already;
    # back to straight colour before it is premultiplied the once. None of it
    # in the hole or the hub.
    straight = colour / np.where(cover > 0, cover, 1.0)[..., None]
    cover = np.where(r < R * CD_HUB, 0.0, cover)
    return _premultiplied(straight, cover)


def bitmap_from_pixels(draw, pixels):
    """A GDI+ bitmap holding `pixels` - height x width x 4, RGBA, premultiplied
    bytes - copied in a row at a time, as the premultiplied 32bpp format lays
    them out: blue, green, red, alpha."""
    height, width = pixels.shape[:2]
    kind = draw.Imaging.PixelFormat.Format32bppPArgb
    bitmap = draw.Bitmap(width, height, kind)
    data = bitmap.LockBits(draw.Rectangle(0, 0, width, height),
                           draw.Imaging.ImageLockMode.WriteOnly, kind)
    try:
        bgra = np.ascontiguousarray(pixels[..., [2, 1, 0, 3]])
        base = int(data.Scan0.ToInt64())
        for row in range(height):
            ctypes.memmove(base + row * data.Stride, bgra[row].ctypes.data, width * 4)
    finally:
        bitmap.UnlockBits(data)
    return bitmap


class Cd:
    """Apollo at rest: the disc, turned, and the light on it, still - each a
    bitmap made once for a size (cd_disc, cd_sheen) and drawn into place
    every frame, faded as the rest is."""

    def __init__(self, draw):
        self.draw = draw
        self._made = {}
        self._fades = {}

    def _bitmaps(self, radius):
        key = max(4, int(round(radius)))
        found = self._made.get(key)
        if found is None:
            # Room for the halo past the rim.
            size = int(key * 2.5) + 4
            found = (bitmap_from_pixels(self.draw, cd_disc(size, key)),
                     bitmap_from_pixels(self.draw, cd_sheen(size, key)), size)
            self._made[key] = found
        return found

    def _fade(self, scale):
        key = min(16, max(0, int(scale * 16)))
        found = self._fades.get(key)
        if found is None:
            matrix = self.draw.Imaging.ColorMatrix()
            matrix.Matrix33 = key / 16.0
            found = self.draw.Imaging.ImageAttributes()
            found.SetColorMatrix(matrix)
            self._fades[key] = found
        return found

    def draw_at(self, g, cx, cy, radius, turn_degrees, fade=1.0):
        if fade <= 0.01:
            return
        disc, sheen, size = self._bitmaps(radius)
        attributes = self._fade(fade)
        box = self.draw.Rectangle(int(-size / 2), int(-size / 2), size, size)
        state = g.Save()
        try:
            g.TranslateTransform(float(cx), float(cy))
            g.RotateTransform(float(turn_degrees))
            g.DrawImage(disc, box, 0, 0, size, size, self.draw.GraphicsUnit.Pixel, attributes)
            g.RotateTransform(float(-turn_degrees))
            g.DrawImage(sheen, box, 0, 0, size, size, self.draw.GraphicsUnit.Pixel, attributes)
        finally:
            g.Restore(state)

