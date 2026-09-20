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
