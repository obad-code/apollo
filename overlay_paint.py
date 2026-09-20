"""The overlay's paint box: every piece of the approved design, drawn in GDI+.

The overlay cannot be a web page - a WebView2 window here paints over the
desktop whatever you ask it (see `apollo.py`'s docstring and
`probes/probe_transparent_matrix.py`) - so the design is built from shapes
instead. What matters most is the frame budget: the overlay redraws sixty
times a second while you are speaking, and GDI+ gradients are far too slow to
build per frame. So anything that does not change every frame is rendered
once into a bitmap and blitted: the panel's gradient, the soft colour clouds
that drift across it, the scanlines. What is left per frame is a handful of
DrawImage calls and the things that genuinely move.

Colours are the ones from the approved mockup, and they are dim on purpose:
this sits on top of whatever you are working in.
"""

import math
import random

PALETTE = {
    "top": (18, 27, 49),          # the panel's gradient, top to bottom
    "upper": (11, 18, 38),
    "lower": (6, 9, 19),
    "bottom": (4, 6, 12),
    "violet": (140, 95, 190),     # the clouds that drift across it
    "teal": (50, 160, 170),
    "rose": (190, 110, 150),
    "amber": (232, 185, 88),      # Apollo's own words
    "you": (210, 238, 243),       # yours
    "caption": (200, 185, 240),   # the line under them
    "up": (95, 227, 154),
    "down": (255, 107, 122),
    "cyan": (127, 224, 238),
    "white": (255, 246, 224),
}

# Each cloud: colour, where it sits (as a fraction of the panel), how far it
# wanders from there, how long one loop takes, and how strong it is. Violet
# hangs at the top left and teal at the top right, as in the design; the rose
# one sits low and is barely there. The periods are deliberately unrelated,
# so the panel never repeats a pose.
NEBULAS = (("violet", (0.20, 0.04), (0.10, 0.07), 16.0, 0.34),
           ("teal", (0.80, 0.06), (0.09, 0.06), 21.0, 0.28),
           ("rose", (0.50, 0.72), (0.12, 0.05), 26.0, 0.14))

RADIUS = 20              # the panel's bottom corners
SCAN_ALPHA = 6           # the CRT lines: barely there, but not nothing
SCAN_EVERY = 3


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


def scanlines(draw, w, h):
    """The CRT's own texture, one bitmap, tiled by nobody - it is exact."""
    bitmap = draw.Bitmap(w, h, draw.Imaging.PixelFormat.Format32bppPArgb)
    graphics = draw.Graphics.FromImage(bitmap)
    try:
        pen = draw.Pen(draw.Color.FromArgb(SCAN_ALPHA, 255, 255, 255), 1.0)
        for y in range(0, h, SCAN_EVERY):
            graphics.DrawLine(pen, 0, y, w, y)
        pen.Dispose()
    finally:
        graphics.Dispose()
    return bitmap


class Backdrop:
    """The panel: a gradient, three drifting clouds, scanlines, round below.

    Everything except the clouds' positions is cached, so a frame costs three
    DrawImage calls and a clip. The cache is keyed on size alone; the clouds
    move by being drawn at a different offset, not by being rebuilt.
    """

    def __init__(self, draw):
        self.draw = draw
        self.cached_size = None
        self._base = None
        self._scan = None
        self._clouds = []

    def invalidate(self):
        for bitmap in [self._base, self._scan] + [c for _, c in self._clouds]:
            try:
                bitmap.Dispose()
            except Exception:
                pass
        self._base = self._scan = None
        self._clouds = []
        self.cached_size = None

    def _build(self, w, h):
        draw = self.draw
        self.invalidate()
        self.cached_size = (w, h)

        base = draw.Bitmap(w, h, draw.Imaging.PixelFormat.Format32bppPArgb)
        graphics = draw.Graphics.FromImage(base)
        try:
            graphics.SmoothingMode = draw.Drawing2D.SmoothingMode.AntiAlias
            # One brush for the whole height. Four separate ones left a seam
            # at every boundary, which on a dark panel reads as a scratch.
            rectangle = draw.Rectangle(0, 0, w, h)
            brush = draw.Drawing2D.LinearGradientBrush(
                rectangle, draw.Color.FromArgb(*alpha(PALETTE["top"], 1.0)),
                draw.Color.FromArgb(*alpha(PALETTE["bottom"], 1.0)),
                draw.Drawing2D.LinearGradientMode.Vertical)
            blend = draw.Drawing2D.ColorBlend(4)
            blend.Colors = [draw.Color.FromArgb(*alpha(PALETTE[name], 1.0))
                            for name in ("top", "upper", "lower", "bottom")]
            blend.Positions = [0.0, 0.40, 0.80, 1.0]
            brush.InterpolationColors = blend
            graphics.FillRectangle(brush, rectangle)
            brush.Dispose()
        finally:
            graphics.Dispose()
        self._base = base
        self._scan = scanlines(draw, w, h)
        size = int(max(w, h) * 0.95)
        self._clouds = [(spec, nebula(draw, size, PALETTE[spec[0]], spec[4]))
                        for spec in NEBULAS]

    def panel(self, g, x, y, w, h, t, alpha_scale=1.0):
        """Paint the panel at (x, y). `t` is seconds; the clouds drift on it."""
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
            self._blit(g, self._base, x, y, w, h, attributes)
            for spec, cloud in self._clouds:
                _, (home_x, home_y), (drift_x, drift_y), period, _ = spec
                phase = 2 * math.pi * (t % period) / period
                offset_x = (x + w * home_x - cloud.Width / 2
                            + math.cos(phase) * w * drift_x)
                offset_y = (y + h * home_y - cloud.Height / 2
                            + math.sin(phase * 1.3) * h * drift_y)
                self._blit(g, cloud, offset_x, offset_y, cloud.Width, cloud.Height,
                           attributes)
            self._blit(g, self._scan, x, y, w, h, attributes)
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

    def __init__(self, draw, colour, dot, spread=1.0):
        self.draw = draw
        self.colour = colour
        self.dot = dot
        radius = dot * BLOOM[0][0] * spread * self.PAD
        self.size = max(4, int(radius * 2) + 2)
        self.centre = self.size / 2.0
        bitmap = draw.Bitmap(self.size, self.size, draw.Imaging.PixelFormat.Format32bppPArgb)
        graphics = draw.Graphics.FromImage(bitmap)
        try:
            graphics.SmoothingMode = draw.Drawing2D.SmoothingMode.AntiAlias
            for multiple, weight in BLOOM:
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

    def __init__(self, draw, colour, count, radius, dot, spread=1.0):
        self.draw = draw
        self.count = count
        self.size = int((radius + dot * BLOOM[0][0] * spread) * 2) + 4
        centre = self.size / 2.0
        glow = Glow(draw, colour, dot, spread)
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
    BREATH = 0.035         # how much the rings widen at full voice

    def __init__(self, draw):
        self.draw = draw
        self._sprites = {}

    def _sprite(self, colour, count, radius, dot, spread):
        # Quantised, or a new sprite would be built on every pixel of voice.
        key = (colour, count, int(radius), round(dot, 1), round(spread, 1))
        found = self._sprites.get(key)
        if found is None:
            found = RingSprite(self.draw, colour, count, radius, dot, spread)
            self._sprites[key] = found
        return found

    def draw_at(self, g, cx, cy, radius, t, level=0.0, fade=1.0):
        if fade <= 0.01:
            return
        radius = radius * (1.0 + self.BREATH * level)
        dot = max(1.2, radius * self.DOT)
        spread = round(1.0 + 0.5 * level, 1)
        glow = min(1.0, fade * (1.0 + 0.6 * level))
        for fraction, count, turns, colour in RING_SPEC:
            sprite = self._sprite(colour, count, radius * fraction, dot, spread)
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
