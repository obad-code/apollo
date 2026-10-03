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
square - that edge is above the screen. It is a tube's black glass in the
full display's own style: its CRT gradient drifting along the foot - warm on
the left, red to amber, cool on the right, teal to blue - under an amber
hairline, the printed dots kept, faint scanlines, light ink, and Apollo
himself as the display draws him, a globe with a star at its heart.
"""

import math
import random

PALETTE = {
    # The card itself: the glass, and the light on it.
    "card": (10, 9, 7),
    "ink": (255, 239, 208),       # Apollo's own words, warm white
    "you": (224, 206, 170),       # yours, and the line under them
    "caption": (184, 162, 122),
    # The lights that drift along its foot: the full display's CRT band, so
    # the two halves of Apollo are one style - warm to cool, left to right.
    "ember": (240, 70, 30),
    "sun": (255, 158, 40),
    "gold": (255, 196, 60),
    "sky": (40, 186, 255),
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
# wanders, how long one loop takes, and how strong it is. In the display's
# order, warm to cool from left to right, each swaying about its place on
# loops of its own length so the band flows the way the display's does;
# none reaches the strip above the screen's edge, which the veil keeps black.
BLOBS = (("ember", (0.06, 1.02), (0.10, 0.10), 9.0, 0.60),
         ("sun", (0.30, 1.08), (0.12, 0.10), 11.0, 0.55),
         ("gold", (0.48, 1.00), (0.10, 0.08), 13.0, 0.36),
         ("teal", (0.70, 0.98), (0.10, 0.10), 10.0, 0.45),
         ("sky", (0.94, 0.90), (0.10, 0.10), 12.0, 0.55))

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
EDGE = (255, 176, 0, 90)     # the hairline around it, the display's amber
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
    """The card: glass, the display's gradient drifting under it, and a
    printed grid.

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


# Apollo's mark on the card: the full display's globe with the star at its
# heart (ui/full/globe.js), small. As wide as it is tall times this...
GLOBE_ASPECT = 0.52
# ...great circles through its poles, 30 degrees apart...
GLOBE_CIRCLES = 6
# ...lines across it, as the sine of their latitude...
GLOBE_ACROSS = (-0.5, 0.0, 0.5)
# ...turning this many radians a second, faster while it is looking something
# up (the card passes a faster clock), in the display's warm white.
GLOBE_TURN = 0.35
GLOBE_LINE = (255, 244, 222)

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


class GlobeMark:
    """Apollo himself, on the card: the globe and its star, as the full
    display draws him, at the size of the card's footer - a wide outline,
    meridians that widen and narrow as it turns, three lines across, and a
    four-pointed star of white in the middle, growing with your voice.

    Plain strokes and one filled path a frame: at fifty pixels across there
    is nothing here worth caching into a bitmap."""

    def __init__(self, draw):
        self.draw = draw
        self.brushes = _Brushes(draw)

    @staticmethod
    def geometry(radius, t, level=0.0):
        """Half-width and half-height, each meridian's half-width, each line
        across as (y, half-length), and the star's reach - about (0, 0)."""
        a = radius * (1.0 + 0.04 * level)
        b = a * GLOBE_ASPECT
        turn = t * GLOBE_TURN
        meridians = [abs(math.sin(turn + k * math.pi / GLOBE_CIRCLES)) * a
                     for k in range(GLOBE_CIRCLES)]
        across = [(s * b, math.sqrt(1.0 - s * s) * a) for s in GLOBE_ACROSS]
        star = a * (0.24 + 0.08 * level)
        return a, b, meridians, across, star

    def draw_at(self, g, cx, cy, radius, t, level=0.0, fade=1.0):
        if fade <= 0.01:
            return
        a, b, meridians, across, star = self.geometry(radius, t, level)
        strength = 245 * min(1.0, fade)
        faint = self.brushes.pen(GLOBE_LINE, strength * 0.45, 1.0)
        for w in meridians:
            if w < 0.75:
                # Edge on: an upright line.
                g.DrawLine(faint, float(cx), float(cy - b), float(cx), float(cy + b))
            elif w < a - 0.5:
                g.DrawEllipse(faint, float(cx - w), float(cy - b), float(w * 2), float(b * 2))
        for y, half in across:
            g.DrawLine(faint, float(cx - half), float(cy + y), float(cx + half), float(cy + y))
        g.DrawEllipse(self.brushes.pen(GLOBE_LINE, strength, 1.3),
                      float(cx - a), float(cy - b), float(a * 2), float(b * 2))

        # The star: a little halo, then four thin points of white.
        for reach, share in ((2.4, 0.10), (1.6, 0.18), (1.05, 0.30)):
            r = star * reach
            g.FillEllipse(self.brushes.brush(GLOBE_LINE, strength * share),
                          float(cx - r), float(cy - r), float(r * 2), float(r * 2))
        tips = [(star, 0.0), (0.0, star), (-star, 0.0), (0.0, -star)]
        pinch = star * 0.11
        path = self.draw.Drawing2D.GraphicsPath()
        for i, (x0, y0) in enumerate(tips):
            x3, y3 = tips[(i + 1) % 4]
            # The pinch between two tips, as a quadratic's control point,
            # raised to the cubic GDI+ draws.
            qx = pinch if (x0 + x3) > 0 else -pinch
            qy = pinch if (y0 + y3) > 0 else -pinch
            c1 = (x0 + (qx - x0) * 2 / 3, y0 + (qy - y0) * 2 / 3)
            c2 = (x3 + (qx - x3) * 2 / 3, y3 + (qy - y3) * 2 / 3)
            path.AddBezier(float(cx + x0), float(cy + y0), float(cx + c1[0]), float(cy + c1[1]),
                           float(cx + c2[0]), float(cy + c2[1]), float(cx + x3), float(cy + y3))
        path.CloseFigure()
        g.FillPath(self.brushes.brush((255, 255, 255), strength), path)
        path.Dispose()


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


class MiniApollo:
    """Mini Apollo: the overlay at rest, as a small dark bar hanging from the
    top edge of the screen - home, chat and new on the left, settings and
    sound on the right, and in the well under them Apollo himself: a soft
    white face with two black eyes and two little hands, a warm glow behind
    him. He blinks every few seconds, looks about, and leans in and brightens
    with your voice; while he is working his eyes go to the side.

    Everything is a filled path or an ellipse a frame - a few dozen calls -
    so nothing here is cached."""

    W = 300                 # the bar's width
    H = 78                  # how much of it shows under the screen's edge
    RADIUS = 20
    WELL_INSET = 8
    HEAD_ROW = 24           # the icon row above the well

    INK = (14, 14, 17)
    WELL = (24, 24, 29)
    LINE = (255, 255, 255)
    FACE = (250, 250, 247)
    EYE = (16, 16, 18)
    GLOW = (255, 186, 70)
    ICON = (196, 196, 204)

    def __init__(self, draw):
        self.draw = draw
        self.brushes = _Brushes(draw)

    @staticmethod
    def blink(t):
        """0 open .. 1 shut: a quick blink every ~4.3 s, a double one now and then."""
        phase = t % 4.3
        shut = max(0.0, 1.0 - abs(phase - 0.12) / 0.12)
        if int(t / 4.3) % 3 == 2:
            shut = max(shut, max(0.0, 1.0 - abs(phase - 0.42) / 0.11))
        return min(1.0, shut)

    @staticmethod
    def gaze(t, busy=False):
        """Where the eyes look, as an (x, y) shift in eye-widths."""
        if busy:
            return (0.55 * math.sin(t * 2.4), -0.2)
        return (0.35 * math.sin(t * 0.37) * math.sin(t * 0.11 + 1.0), 0.12 * math.sin(t * 0.29))

    def _round(self, x, y, w, h, r):
        return rounded_path(self.draw, x, y, w, h, r, top_radius=r)

    def _poly(self, points):
        """A closed path through `points` - lines, so no CLR array is needed."""
        path = self.draw.Drawing2D.GraphicsPath()
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            path.AddLine(float(x0), float(y0), float(x1), float(y1))
        path.CloseFigure()
        return path

    def draw_at(self, g, cx, top, t, level=0.0, fade=1.0, busy=False):
        """The bar, centred on `cx`, its visible part starting at `top` (the
        screen's edge, in window coordinates)."""
        if fade <= 0.01:
            return
        b = self.brushes
        a = 255 * min(1.0, fade)
        x = cx - self.W / 2.0
        y = top - self.RADIUS             # the top corners sit above the edge
        h = self.H + self.RADIUS

        # A soft shadow, then the bar, then a hairline round it.
        for spread, share in ((10, 0.10), (5, 0.16)):
            path = self._round(x - spread, y, self.W + spread * 2, h + spread, self.RADIUS + spread)
            g.FillPath(b.brush((0, 0, 0), a * share), path)
            path.Dispose()
        bar = self._round(x, y, self.W, h, self.RADIUS)
        g.FillPath(b.brush(self.INK, a * 0.94), bar)
        g.DrawPath(b.pen(self.LINE, a * 0.07, 1.0), bar)
        bar.Dispose()

        # The icon row: home (lit, in a pill), chat, new; settings, sound.
        row = top + 4 + self.HEAD_ROW / 2.0
        pill = self._round(x + 12, row - 10, 34, 20, 10)
        g.FillPath(b.brush(self.LINE, a * 0.10), pill)
        pill.Dispose()
        self._home(g, x + 29, row, a)
        self._chat(g, x + 62, row, a * 0.75)
        self._plus(g, x + 86, row, a * 0.75)
        self._gear(g, x + self.W - 50, row, a * 0.75)
        self._sound(g, x + self.W - 24, row, a * 0.75)
        # A small sensor dot in the middle, like the reference.
        g.FillEllipse(b.brush(self.LINE, a * 0.12), float(cx - 2.5), float(top + 4), 5.0, 5.0)

        # The well Apollo sits in.
        wx, wy = x + self.WELL_INSET, top + self.HEAD_ROW + 6
        ww, wh = self.W - self.WELL_INSET * 2, self.H - self.HEAD_ROW - 6 - self.WELL_INSET
        well = self._round(wx, wy, ww, wh, 14)
        g.FillPath(b.brush(self.WELL, a), well)
        # Apollo and his glow stay inside the well, as in the design.
        g.SetClip(well)
        try:
            self._face(g, cx, wy + wh / 2.0 + 1, t, level, a, busy)
        finally:
            g.ResetClip()
            well.Dispose()

    def _face(self, g, cx, cy, t, level, a, busy):
        b = self.brushes
        bob = math.sin(t * 1.6) * 1.2 - level * 2.0
        grow = 1.0 + 0.10 * level
        fw, fh = 36.0 * grow, 27.0 * grow
        cy += bob
        # The glow behind him, warmer and wider as you speak.
        for reach, share in ((2.6, 0.06 + 0.10 * level), (1.9, 0.10 + 0.12 * level), (1.35, 0.16)):
            gw, gh = fw * reach, fh * reach
            g.FillEllipse(b.brush(self.GLOW, a * share), float(cx - gw / 2), float(cy - gh / 2),
                          float(gw), float(gh))
        # Two little hands either side, one waving a touch.
        wave = math.sin(t * 2.2) * 2.0
        g.FillEllipse(b.brush(self.FACE, a), float(cx - fw / 2 - 11), float(cy + 4), 8.0, 8.0)
        g.FillEllipse(b.brush(self.FACE, a), float(cx + fw / 2 + 3), float(cy - 5 + wave), 8.0, 8.0)
        # The head: a soft rounded block.
        head = self._round(cx - fw / 2, cy - fh / 2, fw, fh, 10 * grow)
        g.FillPath(b.brush(self.FACE, a), head)
        head.Dispose()
        # The eyes: solid black ovals that blink and look about.
        shut = self.blink(t)
        gx, gy = self.gaze(t, busy)
        ew, eh = 4.6 * grow, 8.0 * grow * (1.0 - 0.85 * shut)
        for side in (-1, 1):
            ex = cx + side * 6.5 * grow + gx * ew
            ey = cy - 1.0 + gy * eh
            g.FillEllipse(b.brush(self.EYE, a), float(ex - ew / 2), float(ey - eh / 2),
                          float(ew), float(max(1.2, eh)))

    # -- the icons, drawn small ------------------------------------------------

    def _home(self, g, cx, cy, a):
        path = self._poly([(cx - 6, cy), (cx, cy - 6), (cx + 6, cy), (cx + 4.5, cy),
                           (cx + 4.5, cy + 5.5), (cx - 4.5, cy + 5.5), (cx - 4.5, cy)])
        g.FillPath(self.brushes.brush(self.LINE, a), path)
        path.Dispose()

    def _chat(self, g, cx, cy, a):
        bubble = self._round(cx - 7, cy - 5, 14, 9, 4)
        g.FillPath(self.brushes.brush(self.ICON, a), bubble)
        bubble.Dispose()
        g.FillEllipse(self.brushes.brush(self.ICON, a), float(cx - 6), float(cy + 2), 4.0, 4.0)

    def _plus(self, g, cx, cy, a):
        pen = self.brushes.pen(self.ICON, a, 1.6)
        g.DrawLine(pen, float(cx - 6), float(cy), float(cx + 6), float(cy))
        g.DrawLine(pen, float(cx), float(cy - 6), float(cx), float(cy + 6))

    def _gear(self, g, cx, cy, a):
        pen = self.brushes.pen(self.ICON, a, 1.4)
        g.DrawEllipse(pen, float(cx - 4), float(cy - 4), 8.0, 8.0)
        for i in range(8):
            ang = i * math.pi / 4
            g.DrawLine(pen, float(cx + math.cos(ang) * 5), float(cy + math.sin(ang) * 5),
                       float(cx + math.cos(ang) * 7), float(cy + math.sin(ang) * 7))

    def _sound(self, g, cx, cy, a):
        b = self.brushes
        path = self._poly([(cx - 7, cy - 2.5), (cx - 4, cy - 2.5), (cx, cy - 6), (cx, cy + 6),
                           (cx - 4, cy + 2.5), (cx - 7, cy + 2.5)])
        g.FillPath(b.brush(self.ICON, a), path)
        path.Dispose()
        pen = b.pen(self.ICON, a, 1.3)
        g.DrawArc(pen, float(cx - 2), float(cy - 4), 6.0, 8.0, -60, 120)
        g.DrawArc(pen, float(cx - 2), float(cy - 7), 10.0, 14.0, -55, 110)
