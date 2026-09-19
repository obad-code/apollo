"""The mesh at the top of the screen, and everything that hangs under it.

Apollo's full display is the HTML design in a WebView2 window. This layer is
not, and the file exists because of one measured limitation: a WebView2 window
cannot be given per-pixel transparency on this stack. Its content reaches the
screen through DirectComposition, so it never passes through the layered
surface that a colour key or `UpdateLayeredWindow` would act on - see the
table in `apollo.py`'s docstring. Whatever the page draws, the window is a
rectangle, and a rectangle is exactly what Apollo must not be.

So everything here is drawn with GDI+ into a 32-bit ARGB bitmap and pushed to
a layered window with `UpdateLayeredWindow`. That is the one path on Windows
that gives real per-pixel alpha: lit where it is lit, invisible everywhere
else, click-through by construction, with soft glow edges no colour key could
manage.

A turn never changes which window Apollo is; it changes how far this one
reaches down the screen. Three things follow from that, and they are the
reason the geometry here looks the way it does:

- The mesh is drawn into a square of `art` pixels anchored at the *top* of the
  window, horizontally centred. The window's own height is not an input to it,
  so the figure cannot move when the window grows - "the top edge never moves"
  is a property of the drawing code rather than a number kept in step by hand.

- The window is exactly as tall as what it is showing. There is no ground, no
  border and no panel at any size: the words, the chart and the cards sit
  directly on the desktop, the same way the mesh does. Only cards have a
  background, because they have one in the design too.

- Height is eased toward its target with an exponential follow rather than a
  fixed-duration tween, because the target keeps moving: live speech re-wraps
  every time another word is transcribed, and a tween restarted on every word
  is a stutter.

The content itself - text, sparkline, cards - is rendered once into a cached
bitmap when the words change, and every frame in between is a blit. Measured
here, rendering it costs about 10ms and blitting it 0.17ms, against a 16.7ms
frame; doing it per frame would drop frames exactly while you were speaking.
`overlay_content.py` decides what the content is and how tall it comes out;
this file paints it.
"""

import ctypes
import math
import threading
import time

import overlay_content

ULW_ALPHA = 0x00000002
AC_SRC_OVER, AC_SRC_ALPHA = 0x00, 0x01

WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008

SW_HIDE, SW_SHOWNOACTIVATE = 0, 8

# The design's palette, so the orb and the panel are recognisably one object.
AMBER = (255, 176, 0)
AMBER_WARM = (255, 193, 94)
# The one colour outside the amber family, and it earns its place: it marks
# the innermost ring while Apollo is listening, so "attending to you" reads as
# a different thing at a glance rather than as more of the same amber.
CYAN = (86, 197, 214)

# What Apollo's own words are drawn in - the mesh's colour, so a reply reads
# as the same object speaking rather than as a second thing arriving.
REPLY_INK = AMBER_WARM
REPLY_GLOW = (255, 150, 0)     # the page's text-shadow, in a colour
# ...and what yours are drawn in. Cooler and dimmer on purpose: your words are
# a receipt for what Apollo heard, not something for you to read back, so they
# have to be distinguishable from an answer at a glance and never compete with
# one. No amber anywhere in it, because a dimmer amber would read as a faded
# reply instead of as a different voice.
SPEECH_INK = (150, 170, 190)
SPEECH_GLOW = (96, 132, 170)

# A card's ground and hairline, matching the ones the full display uses:
# rgba(26,13,0,0.86) over a 1px rgba(255,176,0,0.13-0.2) border. Cards are the
# one thing here with a background, and they have one in the design too - what
# the overlay itself must never grow is a panel behind everything.
CARD_GROUND = (26, 13, 0)
CARD_GROUND_ALPHA = 200
CARD_EDGE_ALPHA = 46
CARD_RADIUS = 2

# The monospace face, in preference order. The page asks for IBM Plex Mono and
# falls back through the platform's monospace to Consolas; since Plex is not
# installed here, what the page actually renders in is Consolas, and matching
# what is on screen matters more than matching what the stylesheet asks for.
FONT_STACK = ("IBM Plex Mono", "Consolas", "Cascadia Mono", "Courier New")
FONT_PT = 10.5            # body text: the reply, and your words
FONT_SMALL_PT = 8.0       # card labels, chart axis figures

_user32 = ctypes.windll.user32
_gdi32 = ctypes.windll.gdi32

# Every one of these returns or takes a handle, and a handle is 64 bits on a
# 64-bit build. ctypes defaults a return type to c_int, which silently chops
# the top half off and hands back a DC that is not a DC. The symptom is an orb
# that never paints and no error anywhere, so the prototypes are spelled out
# rather than left to the defaults.
_user32.GetDC.restype = ctypes.c_void_p
_user32.GetDC.argtypes = [ctypes.c_void_p]
_user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_user32.GetWindowLongW.restype = ctypes.c_long
_user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
_user32.SetWindowLongW.restype = ctypes.c_long
_user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
_user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
_user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_uint]
_gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
_gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
_gdi32.SelectObject.restype = ctypes.c_void_p
_gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
_gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
_gdi32.CreateDIBSection.restype = ctypes.c_void_p
_gdi32.CreateDIBSection.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                                    ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.c_uint32]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_byte), ("BlendFlags", ctypes.c_byte),
                ("SourceConstantAlpha", ctypes.c_byte), ("AlphaFormat", ctypes.c_byte)]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
        ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]


def _ease_out(p):
    """Strong ease-out, the same shape as the design's --ap-ease-out."""
    return 1.0 - (1.0 - p) ** 3


def _lerp(a, b, p):
    return a + (b - a) * p


class Orb:
    """The overlay: a mesh with real per-pixel alpha, and what it is saying.

    Built on the host's UI thread rather than a thread of its own. A WinForms
    form created on a bare Python thread never gets a window here - `Shown`
    simply never fires, with no error - and the orb silently does not exist.
    The host's thread already has a running message pump, so the form appears
    and the timer ticks.

    Nothing is ever painted through WinForms itself: every frame is handed to
    the compositor whole by `UpdateLayeredWindow`, which also moves and resizes
    the window, so one call per frame does shape, position and size together.

    Three entry points are safe from any thread and are all `apollo.py` uses:
    `set_active` for the pattern, `set_level` for your voice, and
    `set_content` / `clear_content` for the words underneath. None of them
    touch GDI+; they leave a note for the drawing thread to pick up.
    """

    TICK_MS = 16       # the timer never changes rate; see `_tick`
    REST_EVERY = 3     # so ~20fps at rest, ~60fps while anything is moving

    def __init__(self, size, position):
        # `art` is the mesh's own box and never changes: the figure is drawn
        # into a square of this size at the top of the window, horizontally
        # centred, whatever the window has grown to underneath it. That is the
        # whole trick behind "the top edge never moves" - the window's own
        # height is not an input to the figure at all.
        self.art = int(size)
        self.home = (position[0] + int(size) // 2, position[1])   # centre x, top y
        self.rect = (position[0], position[1], int(size), int(size))
        self.active = False               # False = idle constellation, True = listening/thinking ring
        self.ready = threading.Event()
        self.stopping = threading.Event()
        self.hwnd = None
        self.frames = 0
        self.errors = 0
        self._visible = True
        self._form = None
        self._t0 = time.monotonic()
        self._ticks = 0
        self._blend_from = 0.0            # pattern crossfade: see `set_active`
        self._blend_t0 = None
        self._level = 0.0                 # smoothed mic loudness, drawing thread
        self._level_target = 0.0          # raw, written by the audio thread
        self._clock = 0.0                 # the warped clock everything moves on
        self._last_draw = time.monotonic()
        self._brushes = {}                # see `_brush`
        self._pens = {}

        # -- what is under the mesh, and how tall it has grown to show it ---
        self._w = float(size)             # the window's live size, eased
        self._h = float(size)
        self._closing = False             # ...and on its way back out
        self._collapse_from = float(size)  # height the current collapse began at
        self._content_lock = threading.Lock()
        self._pending = None              # (role, text, visual), from any thread
        self._pending_seq = 0             # ...and its version, so a repeat of
        self._applied_seq = 0             # the same text is not rebuilt
        self._clear_at = None             # monotonic deadline to drop it all
        self._content = None              # the built, cached, drawable content
        self._fades = {}                  # see `_fade_attrs`
        self._reveal = 0.0                # characters the typewriter has reached
        self._fonts = None                # (body, small, format), built once

    # -- lifecycle ----------------------------------------------------------

    def start_on(self, host_form):
        """Create the orb's window on the thread that owns `host_form`."""
        import clr
        clr.AddReference("System.Windows.Forms")
        clr.AddReference("System.Drawing")
        import System.Drawing as D
        import System.Windows.Forms as WF
        from System import Action, IntPtr

        self._D, self._WF, self._IntPtr = D, WF, IntPtr

        def build():
            try:
                form = WF.Form()
                form.FormBorderStyle = getattr(WF.FormBorderStyle, "None")
                form.ShowInTaskbar = False
                form.StartPosition = WF.FormStartPosition.Manual
                form.Text = "ApolloOrb"
                form.Size = D.Size(self.rect[2], self.rect[3])
                form.Location = D.Point(self.rect[0], self.rect[1])
                self._form = form

                # Never call Show() on a form that has not been painted yet. A
                # WinForms form shows its BackColor the instant it appears, so
                # showing first would put a white square on screen until the
                # first frame lands - exactly the bug this orb exists to avoid.
                # Touching Handle creates the window without showing it; after
                # one UpdateLayeredWindow the layered surface keeps its
                # content, so every later hide/show is clean too.
                self.hwnd = int(form.Handle.ToInt64())

                style = _user32.GetWindowLongW(self.hwnd, -20)
                _user32.SetWindowLongW(
                    self.hwnd, -20,
                    style | WS_EX_LAYERED | WS_EX_TRANSPARENT
                    | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TOPMOST)

                self._draw()
                if self._visible:
                    _user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
                    # WS_EX_TOPMOST above is not enough on its own: the style
                    # bit does not take through SetWindowLong, and a window
                    # that asked for it that way is left sitting behind
                    # whatever is maximised - visible, correct, and invisible.
                    # Only SetWindowPos actually puts it on top.
                    self.raise_above()

                # Frames come from a WinForms timer on this same thread. GDI+
                # objects are created through pythonnet, and first touching a
                # CLR type from a foreign thread can fail outright ("Failed to
                # create Python type for System.Drawing.Color"), which shows up
                # as an orb that never paints.
                self._timer = WF.Timer()
                self._timer.Interval = self.TICK_MS
                self._timer.Tick += lambda s, e: self._tick()
                self._timer.Start()
            except Exception:
                import traceback
                self.run_exc = traceback.format_exc()
            finally:
                self.ready.set()

        host_form.Invoke(Action(build))
        self.ready.wait(timeout=10)
        return self.hwnd is not None

    def _tick(self):
        """One timer tick. Redraws every tick while morphing, every third at
        rest - the interval itself is never changed, because a WinForms timer
        belongs to the thread that made it and `morph_to` is called from the
        watcher's thread. Setting Interval across threads degrades the timer to
        a couple of ticks a second, which looked exactly like an animation that
        refused to start."""
        if self.stopping.is_set() or not self.hwnd:
            return
        try:
            self._ticks += 1
            self._sync_content()
            busy = (self._settling() or self._typing()
                    or self._blend_t0 is not None
                    or self._level > 0.01 or self._level_target > 0.01)
            if self._visible and (busy or self._ticks % self.REST_EVERY == 0):
                self._draw()
                self.frames += 1
        except Exception:
            import traceback
            self.last_exc = traceback.format_exc()
            self.errors += 1

    # -- growing downward ---------------------------------------------------
    #
    # The window is always exactly as big as what it is showing, and the mesh
    # is drawn in a fixed square at its top, so growth is downward by
    # construction rather than by arithmetic that has to be kept honest.
    #
    # Height is eased with an exponential follow rather than a fixed-duration
    # tween, because the target moves while the animation is running: live
    # speech re-wraps and re-measures every time another word is transcribed,
    # and a tween restarted on every word is a stutter. A follow just bends
    # toward wherever the target is now. Width is not eased at all - nothing
    # is drawn near the left or right edges of a transparent window, so
    # widening it is invisible, and easing it would only delay the point at
    # which text has room to wrap into.

    GROW_TAU = 0.085          # seconds to fold toward a taller target
    SHRINK_TAU = 0.150        # ...and back down, a little softer
    CONTENT_W = 560           # the window's width once anything is under the mesh
    CHARS_PER_SEC = 90.0      # the typewriter's rate
    CONTENT_GAP = 10          # between the mesh's lowest glow and the first line

    def content_top(self):
        """Where content starts, measured down from the window's top.

        Derived from the figure rather than picked, so it still clears the
        mesh if the pattern's radius or its glow is ever retuned: the lowest
        thing the figure paints is the bottom of the outermost bloom on the
        lowest point of the ring.
        """
        reach = 0.5 + self.CONSTELLATION_R + self.CONSTELLATION_DOT * self.BLOOM_LAYERS[0][0]
        return int(self.art * reach) + self.CONTENT_GAP

    def _targets(self):
        """The size the window is heading for: (width, height).

        Width is held for as long as there is anything to draw, the collapse
        included: narrowing the window first would clip the words to the
        mesh's own 190 pixels and cut every line in half on the way out.
        """
        if self._content is None:
            return float(self.art), float(self.art)
        width = float(max(self.art, self.CONTENT_W))
        if self._closing:
            return width, float(self.art)
        height = self.content_top() + self._revealed_height()
        return width, float(max(self.art, height))

    def _revealed_height(self):
        """How tall the content is *so far*.

        The window follows the typewriter rather than jumping to the finished
        answer's height, so a four-line reply opens over four short steps
        instead of leaving three empty lines of nothing under the first one.
        Each step is eased, so it reads as one continuous unfolding.
        """
        content = self._content
        plan = content["layout"]
        if self._reveal >= plan["chars"]:
            return plan["height"]

        height = 0
        for block in plan["blocks"]:
            if block["kind"] != "text":
                continue
            for line in block["lines"]:
                if self._reveal > line["start"]:
                    height = line["y"] + overlay_content.LINE_H
        return height + overlay_content.BOTTOM_PAD if height else 0

    def _settling(self):
        """True while the window is still on its way to that size."""
        want_w, want_h = self._targets()
        return (abs(want_h - self._h) > 0.4 or abs(want_w - self._w) > 0.4
                or self._closing)

    def _typing(self):
        """True while the typewriter still has characters to get through."""
        return (self._content is not None and not self._closing
                and self._reveal < self._content["layout"]["chars"])

    def _advance_box(self, dt):
        """Ease the window toward its target size, and the reveal along.

        The content outlives the request to remove it, on purpose: it is held
        and faded across the collapse rather than cut, so the words leave with
        the window instead of vanishing off a full-height overlay.
        """
        want_w, want_h = self._targets()
        tau = self.GROW_TAU if want_h > self._h else self.SHRINK_TAU
        self._h += (want_h - self._h) * (1.0 - math.exp(-dt / tau))
        if abs(want_h - self._h) <= 0.4:
            self._h = want_h
        self._w = want_w                  # see the note above: no easing

        if self._closing and self._h <= self.art + 0.5:
            self._drop(self._content)     # the collapse is over; let it go
            self._content = None
            self._closing = False
            self._collapse_from = float(self.art)
        elif self._content is not None and not self._closing:
            self._reveal = min(self._content["layout"]["chars"],
                               self._reveal + self.CHARS_PER_SEC * dt)

        # The window is centred on the same axis whatever it is showing, so
        # the mesh sits over the same pixels at every size.
        cx, top = self.home
        w, h = int(round(self._w)), int(round(self._h))
        self.rect = (cx - w // 2, top, w, h)

    # -- what is under the mesh ---------------------------------------------

    def set_content(self, role, text, visual=None):
        """Put words (and maybe a chart or cards) under the mesh.

        Safe from any thread: it only stores the request. The drawing thread
        picks it up in `_sync_content`, which is where the layout and the
        bitmap are built - both need GDI+, and GDI+ here belongs to that
        thread alone.

        Called repeatedly with a growing `text` while you are still speaking.
        The typewriter's position is deliberately *not* reset when that
        happens, so live speech types on from where it had got to instead of
        starting again every time another word is transcribed.
        """
        with self._content_lock:
            self._pending = (role, text or "", visual)
            self._pending_seq += 1
            self._clear_at = None

    def clear_content(self, after=0.0):
        """Collapse back to the bare mesh, optionally after a delay."""
        with self._content_lock:
            self._clear_at = time.monotonic() + max(0.0, after)

    def _sync_content(self):
        """Adopt whatever `set_content` last asked for. Drawing thread only."""
        with self._content_lock:
            pending, seq = self._pending, self._pending_seq
            clear_at = self._clear_at
            fresh = seq != self._applied_seq
            if fresh:
                self._applied_seq = seq

        if clear_at is not None and time.monotonic() >= clear_at:
            self._close()
            return

        if not fresh:
            return

        role, text, visual = pending
        text = overlay_content.elide(text)
        if not text and not visual:
            self._close()
            return

        previous = self._content
        try:
            built = self._build_content(role, text, visual)
        except Exception:
            import traceback
            self.last_exc = traceback.format_exc()
            self.errors += 1
            return
        if built is None:
            return
        self._content = built
        self._drop(previous)
        self._closing = False

        # Carry the typewriter across an update that only extended the text -
        # which is every update during live speech. A different line, or a
        # rewritten one, starts again from the beginning.
        if not (previous and previous["role"] == role
                and text.startswith(previous["text"])):
            self._reveal = 0.0
        self._reveal = min(self._reveal, float(len(text)))

    # No answer may take more of the screen than this. A deep research pass
    # can come back with several hundred words, and an overlay that grows to
    # meet it stops being an overlay.
    MAX_CONTENT_H = 460

    def _drop(self, content):
        """Free a content bitmap once nothing is drawing it any more.

        Worth doing explicitly rather than leaving to the collector: a rebuild
        happens every time the running transcription gets further through your
        sentence, so a minute of talking is a hundred or so half-megabyte
        surfaces, and the memory behind a GDI+ bitmap is unmanaged - the
        collector has no idea how much it is sitting on and is in no hurry.
        Only ever called from the drawing thread, which is the only thread
        that ever holds one.
        """
        if content is None:
            return
        try:
            content["bitmap"].Dispose()
        except Exception:
            pass                          # already gone; nothing to free

    def _close(self):
        """Begin collapsing, once.

        The height the collapse starts from is stamped here rather than worked
        out while it runs, because it is what the fade is measured against -
        re-stamping it on a later frame would measure the fade against a
        window that has already half closed, and the words would never
        actually fade.
        """
        if self._content is None or self._closing:
            return
        self._closing = True
        self._collapse_from = max(float(self.art) + 1.0, self._h)

    def _build_content(self, role, text, visual):
        """Lay the content out and render it once into a cached bitmap.

        Cached because a frame cannot afford to draw it: measured on this
        machine, a full render of text, a chart and three cards is about 10ms
        against a 16.7ms budget that the mesh already spends most of. Blitting
        the finished bitmap is 0.17ms, so the content is rendered only when
        its words change, and every frame in between is just the blit.
        """
        D = self._D
        body, small, fmt = self._font_set()
        metrics = overlay_content.Metrics(self._char_w)

        plan = overlay_content.layout(role, text, visual, metrics,
                                      self.CONTENT_W, max_height=self.MAX_CONTENT_H)
        if plan["height"] <= 0:
            return None

        bitmap = D.Bitmap(self.CONTENT_W, plan["height"],
                          D.Imaging.PixelFormat.Format32bppPArgb)
        g = D.Graphics.FromImage(bitmap)
        try:
            g.SmoothingMode = D.Drawing2D.SmoothingMode.AntiAlias
            # AntiAlias, never ClearType: sub-pixel rendering assumes it knows
            # what is behind the glyph, and on a surface whose whole point is
            # that nothing is, it leaves coloured fringes on every letter.
            g.TextRenderingHint = D.Text.TextRenderingHint.AntiAlias
            g.Clear(D.Color.FromArgb(0, 0, 0, 0))
            for block in plan["blocks"]:
                if block["kind"] == "text":
                    self._render_text(g, block, body, fmt)
                elif block["kind"] == "chart":
                    self._render_chart(g, block, small, fmt)
                elif block["kind"] == "cards":
                    self._render_cards(g, block, body, small, fmt)
        finally:
            g.Dispose()

        # The words come first; everything after them is the evidence, and it
        # is held back until the words have finished typing.
        extras_top = None
        for block in plan["blocks"]:
            if block["kind"] == "chart":
                extras_top = block["y"]
                break
            if block["kind"] == "cards":
                extras_top = block["rows"][0]["y"]
                break

        return {"role": role, "text": text, "layout": plan,
                "bitmap": bitmap, "extras_top": extras_top}

    def _font_set(self):
        """The monospace face, built once, with the width of one character.

        GenericTypographic for both measuring and drawing: the default format
        pads around a string, so measuring with one and drawing with the other
        would put the typing caret a few pixels off the last glyph and drift
        further with every line.
        """
        if self._fonts is not None:
            return self._fonts

        D = self._D
        installed = set()
        for family in D.FontFamily.Families:
            installed.add(family.Name)
        name = next((n for n in FONT_STACK if n in installed), None)
        if name is None:
            name = D.FontFamily.GenericMonospace.Name

        body = D.Font(name, FONT_PT, D.FontStyle.Regular, D.GraphicsUnit.Point)
        small = D.Font(name, FONT_SMALL_PT, D.FontStyle.Regular, D.GraphicsUnit.Point)
        fmt = D.StringFormat(D.StringFormat.GenericTypographic)
        fmt.FormatFlags = fmt.FormatFlags | D.StringFormatFlags.MeasureTrailingSpaces

        probe = D.Bitmap(4, 4, D.Imaging.PixelFormat.Format32bppPArgb)
        g = D.Graphics.FromImage(probe)
        try:
            sample = "M" * 40
            self._char_w = g.MeasureString(sample, body, D.PointF(0.0, 0.0),
                                           fmt).Width / len(sample)
        finally:
            g.Dispose()
            probe.Dispose()

        self._fonts = (body, small, fmt)
        return self._fonts

    def _string(self, g, text, font, fmt, x, y, colour, alpha, glow=None):
        """One run of text, with the design's soft halo behind it.

        The page gets its glow from `text-shadow: 0 0 7px`; GDI+ has no blur,
        so this is four offset copies at low alpha under the crisp one. Cheap
        enough because it only runs when the words change, never per frame.
        """
        D = self._D
        if glow:
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                g.DrawString(text, font, self._brush(glow, alpha * 0.16),
                             D.PointF(float(x + dx), float(y + dy)), fmt)
        g.DrawString(text, font, self._brush(colour, alpha),
                     D.PointF(float(x), float(y)), fmt)

    def _render_text(self, g, block, font, fmt):
        user = block["role"] == overlay_content.USER
        ink = SPEECH_INK if user else REPLY_INK
        glow = SPEECH_GLOW if user else REPLY_GLOW
        alpha = 205.0 if user else 235.0
        for line in block["lines"]:
            self._string(g, line["text"], font, fmt, line["x"], line["y"],
                         ink, alpha, glow)

    def _render_chart(self, g, block, small, fmt):
        """A sparkline: the series, over a grid faint enough to read through.

        Sized to the data rather than to a template - the plot is divided into
        exactly as many gaps as the series has, so four readings and forty
        both fill the width without either looking padded.
        """
        points = block["points"]
        x0, y0 = float(block["x"]), float(block["y"])
        w, h = float(block["plot_w"]), float(block["h"])

        low, high = min(points), max(points)
        span = high - low
        if span <= 0:                     # a flat series still has a shape
            low, high, span = low - 1.0, high + 1.0, 2.0

        top = y0 + 14.0                   # room for the label above the plot
        plot_h = h - 20.0
        grid = self._pen(AMBER, 20)
        for i in range(4):
            y = top + plot_h * i / 3.0
            g.DrawLine(grid, x0, y, x0 + w, y)
        columns = min(8, max(2, len(points) - 1))
        for i in range(columns + 1):
            x = x0 + w * i / columns
            g.DrawLine(grid, x, top, x, top + plot_h)

        step = w / max(1, len(points) - 1)
        xs = [x0 + step * i for i in range(len(points))]
        ys = [top + plot_h - plot_h * (v - low) / span for v in points]

        line = self._pen(AMBER, 225, 1.8)
        for i in range(len(points) - 1):
            g.DrawLine(line, xs[i], ys[i], xs[i + 1], ys[i + 1])

        dot = self._brush(AMBER_WARM, 165)
        for x, y in zip(xs, ys):
            g.FillEllipse(dot, x - 1.5, y - 1.5, 3.0, 3.0)
        # The reading that matters is the last one, so it gets the mesh's own
        # bloom - the same glow as a point on the figure above it.
        self._bloom(g, xs[-1], ys[-1], 2.2, AMBER_WARM, 235.0, 1.0)

        unit = block.get("unit") or ""
        figures = x0 + w + 8.0
        self._string(g, "%g%s" % (high, unit), small, fmt, figures, top - 5.0,
                     AMBER_WARM, 125)
        self._string(g, "%g%s" % (low, unit), small, fmt, figures,
                     top + plot_h - 9.0, AMBER_WARM, 125)
        if block.get("label"):
            self._string(g, block["label"], small, fmt, x0, y0 - 2.0,
                         AMBER_WARM, 140)

    def _render_cards(self, g, block, body, small, fmt):
        """Small readouts: label over value, on the design's own card ground."""
        D = self._D
        for card in block["rows"]:
            x, y = float(card["x"]), float(card["y"])
            w, h = float(card["w"]), float(card["h"])
            self._round_rect(g, x, y, w, h, CARD_RADIUS,
                             D.Color.FromArgb(CARD_GROUND_ALPHA, *CARD_GROUND))
            self._round_rect(g, x, y, w, h, CARD_RADIUS,
                             D.Color.FromArgb(CARD_EDGE_ALPHA, *AMBER), outline=1.0)
            self._string(g, card["label"], small, fmt, x + 11, y + 9,
                         AMBER_WARM, 130)
            self._string(g, card["value"], body, fmt, x + 11, y + 25,
                         REPLY_INK, 235, REPLY_GLOW)

    # -- reacting to your voice ---------------------------------------------

    # An envelope follower, in seconds. Rising fast is what makes the bloom
    # feel connected to the syllable that caused it; falling slowly is what
    # keeps it dreamy instead of strobing on every gap between words.
    LEVEL_ATTACK = 0.05
    LEVEL_RELEASE = 0.28

    SPEED_GAIN = 2.2       # how much faster the figure turns at full voice
    # Both bloom gains are deliberately modest. Tried at 1.1/1.3 first: at
    # full voice the glows grew past the ~19px gap between neighbouring
    # points, merged, and the ring became a solid donut with every disc's
    # edge showing. The glow has to stay inside its own point's share of the
    # ring for the bloom to read as bloom.
    BLOOM_GAIN = 0.5       # how much wider the glow gets at full voice
    BLOOM_ALPHA_GAIN = 0.6
    BREATH_GAIN = 0.035    # how much the rings widen at full voice

    # Concentric layers making up one point's glow: (radius multiple, weight),
    # widest first so the core lands on top. Flat translucent discs are a
    # crude radial falloff, but they are one FillEllipse each - a real
    # PathGradientBrush per point per frame is an allocation the 60fps path
    # cannot afford. Eight closely spaced steps rather than four wide ones:
    # with wide steps each disc's own edge is visible as a ring inside the
    # glow, which is the opposite of dreamy. The outermost reaches about 4.6x
    # the core, which at this dot spacing is roughly a third of the way to
    # the next point - far enough to be a real halo, near enough that
    # neighbouring glows never merge into a solid band.
    BLOOM_LAYERS = ((4.6, 0.018), (3.9, 0.028), (3.3, 0.042), (2.75, 0.062),
                    (2.25, 0.090), (1.8, 0.130), (1.4, 0.230), (1.0, 1.000))

    def set_level(self, value):
        """Live mic loudness, 0-1. Called from the audio thread - one float
        assignment, no allocation, no GDI+."""
        try:
            self._level_target = max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            self._level_target = 0.0

    def _advance_level(self, dt):
        """Ease the smoothed level toward the raw one, frame-rate independent."""
        target = self._level_target
        tau = self.LEVEL_ATTACK if target > self._level else self.LEVEL_RELEASE
        self._level += (target - self._level) * (1.0 - math.exp(-dt / tau))
        if self._level < 0.001:
            self._level = 0.0

    # Alpha is quantised to this many steps before it keys the brush cache.
    # 2/255 is well under a visible difference on a glow layer, and it caps
    # the cache at a few hundred entries instead of one per frame per point.
    # Not coarser than this: the outermost bloom layers land at alpha 4-9, so
    # a step of 4 collapsed the two faintest into one and put back the very
    # banding the extra layers exist to remove.
    ALPHA_STEP = 2

    def _brush(self, colour, alpha):
        """A cached SolidBrush.

        Building one per point per layer is 200-odd GDI+ allocations a frame,
        each crossing into the CLR through pythonnet, and measured that alone
        put a full-voice frame at 13.7ms against a 16.7ms budget - it dropped
        frames exactly while you were speaking. These are immutable and never
        disposed, so caching them is free.
        """
        a = min(255, (int(alpha) // self.ALPHA_STEP) * self.ALPHA_STEP)
        key = (colour, a)
        brush = self._brushes.get(key)
        if brush is None:
            brush = self._D.SolidBrush(self._D.Color.FromArgb(a, *colour))
            self._brushes[key] = brush
        return brush

    def _pen(self, colour, alpha, width=1.0):
        """A cached Pen, for the same reason as `_brush`."""
        a = min(255, (int(alpha) // self.ALPHA_STEP) * self.ALPHA_STEP)
        key = (colour, a, width)
        pen = self._pens.get(key)
        if pen is None:
            pen = self._D.Pen(self._D.Color.FromArgb(a, *colour), float(width))
            self._pens[key] = pen
        return pen

    def _bloom(self, g, px, py, r, colour, alpha, spread):
        """One glowing point: a soft halo with a solid core inside it."""
        for mult, weight in self.BLOOM_LAYERS:
            a = alpha * weight
            if a <= 1.0:
                continue
            # The core stays the size it is - a point that fattens with your
            # voice reads as wobbling. Only the glow around it breathes.
            rr = r * mult * (1.0 if mult <= 1.0 else spread)
            g.FillEllipse(self._brush(colour, a),
                          float(px - rr), float(py - rr),
                          float(rr * 2), float(rr * 2))

    # -- what it looks like -------------------------------------------------

    def _draw(self):
        D = self._D
        # Motion runs on a clock that speeds up while you are talking, rather
        # than on wall time scaled by the level. Scaling wall time would
        # rewrite the whole figure's position every time the level changed -
        # `t * rate * k` jumps backwards when k drops - so the elapsed time is
        # integrated instead and the figure only ever moves forwards.
        now = time.monotonic()
        dt = min(0.1, max(0.0, now - self._last_draw))   # a stall must not lurch
        self._last_draw = now
        self._advance_level(dt)
        self._advance_box(dt)
        self._clock += dt * (1.0 + self.SPEED_GAIN * self._level)
        t = self._clock
        x, y, w, h = self.rect
        w, h = max(8, w), max(8, h)

        # A GDI+ Bitmap built the ordinary way and converted with GetHbitmap()
        # is what this used to do, and it is the reason the orb has been
        # unreliable: GetHbitmap does not dependably preserve alpha - .NET's
        # own docs describe it as lossy, and in practice it sometimes hands
        # UpdateLayeredWindow a fully-opaque or fully-transparent surface with
        # no error anywhere to show for it. Measured directly: a hand-built
        # CreateDIBSection buffer painted correctly on this machine every time;
        # a GetHbitmap-derived one did not. So the Bitmap is built to wrap a
        # DIB section's memory directly (Format32bppPArgb - the premultiplied
        # format UpdateLayeredWindow's AC_SRC_ALPHA blend expects) and GDI+
        # draws straight into that memory. There is no conversion step left to
        # be unreliable.
        bi = BITMAPINFOHEADER()
        bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bi.biWidth = w
        bi.biHeight = -h  # negative = top-down, matching how we read it back
        bi.biPlanes = 1
        bi.biBitCount = 32
        bi.biCompression = 0  # BI_RGB

        bits_ptr = ctypes.c_void_p()
        hbmp = _gdi32.CreateDIBSection(None, ctypes.byref(bi), 0,
                                       ctypes.byref(bits_ptr), None, 0)
        if not hbmp or not bits_ptr.value:
            self.errors += 1
            return

        stride = w * 4
        # pythonnet needs a real System.IntPtr here - handing it a ctypes
        # c_void_p directly raises "value cannot be converted to System.IntPtr".
        bmp = D.Bitmap(w, h, stride, D.Imaging.PixelFormat.Format32bppPArgb,
                       self._IntPtr(bits_ptr.value))
        g = D.Graphics.FromImage(bmp)
        g.SmoothingMode = D.Drawing2D.SmoothingMode.AntiAlias
        g.Clear(D.Color.FromArgb(0, 0, 0, 0))          # genuinely nothing

        # No ground, at any size. The overlay is a figure on the desktop, not
        # a window with a background - so the only thing that ever changes
        # when an answer arrives is how much is drawn below the mesh.
        #
        # The mesh has its own square at the top of the window, always
        # `self.art` on a side and horizontally centred, which is what holds
        # it still while the window grows underneath it: neither `w` nor `h`
        # is an input to it.
        self._draw_core(g, (w - self.art) // 2, 0, self.art, self.art, t, 1.0)

        if self._content is not None:
            self._draw_content(g, w, h, now)

        g.Dispose()
        self._push(hbmp, x, y, w, h)
        bmp.Dispose()          # only releases the wrapper; the DIB memory is
        _gdi32.DeleteObject(hbmp)  # ours, so we free it ourselves, after use

    def _round_rect(self, g, x, y, w, h, r, colour, outline=0):
        D = self._D
        r = max(0.5, min(r, min(w, h) / 2.0))
        path = D.Drawing2D.GraphicsPath()
        d = r * 2
        path.AddArc(float(x), float(y), float(d), float(d), 180, 90)
        path.AddArc(float(x + w - d), float(y), float(d), float(d), 270, 90)
        path.AddArc(float(x + w - d), float(y + h - d), float(d), float(d), 0, 90)
        path.AddArc(float(x), float(y + h - d), float(d), float(d), 90, 90)
        path.CloseFigure()
        if outline:
            g.DrawPath(D.Pen(colour, float(outline)), path)
        else:
            g.FillPath(D.SolidBrush(colour), path)
        path.Dispose()

    # The idle pattern is a clock face: N points spaced evenly around one
    # circle, so there is nothing irregular left to look accidental. Drawn
    # from these two numbers rather than a table of hand-picked radii - the
    # table was what made the old shape a zigzag, since every point sat at a
    # different distance from the centre.
    CONSTELLATION_N = 22          # points around the circle
    CONSTELLATION_R = 0.355       # their radius, as a fraction of the box
    CONSTELLATION_STEP = 6        # star polygon {N/6}: the chords across it
    CONSTELLATION_DOT = 0.009     # point radius, as a fraction of the box

    # How long the idle pattern takes to become the listening one. Short,
    # because this fires on every single thing you say to Apollo - long enough
    # to not be a cut, short enough to never be in the way.
    BLEND_SECONDS = 0.20

    def _blend(self):
        """Where the crossfade is: 0 is fully idle, 1 fully listening.

        Read (and finished) on the drawing thread only. A reversal partway
        through starts from wherever the fade had got to, so talking again
        before the previous fade lands never snaps.
        """
        target = 1.0 if self.active else 0.0
        if self._blend_t0 is None:
            return target
        p = (time.monotonic() - self._blend_t0) / self.BLEND_SECONDS
        if p >= 1.0:
            self._blend_t0 = None
            return target
        return _lerp(self._blend_from, target, _ease_out(p))

    def _draw_core(self, g, ox, oy, w, h, t, art):
        """Draw the phase's pattern - or both of them, mid-crossfade.

        The weights are square-rooted rather than linear. Two patterns fading
        through each other at 50/50 linear alpha are each half-lit, and the
        orb visibly dims through the middle of the swap; sqrt holds the
        perceived brightness roughly level across the fade.
        """
        p = self._blend()
        if p < 0.999:
            self._draw_constellation(g, ox, oy, w, h, t, art * (1.0 - p) ** 0.5)
        if p > 0.001:
            self._draw_orbits(g, ox, oy, w, h, t, art * p ** 0.5)

    def _draw_constellation(self, g, ox, oy, w, h, t, art):
        """Idle: a ring of evenly spaced points over nothing - no ground fill,
        no solid shape. Two sets of lines, both symmetric: the ring itself,
        joining each point to its neighbours, and a fainter star polygon of
        chords across the middle, which is what gives it the look of a chart
        rather than a plain circle. `CONSTELLATION_STEP` is kept well short of
        half of N, so no chord joins opposite points and none runs through the
        exact centre: they leave an open well in the middle instead of piling
        into a hub, which is what the old nearest-neighbour attempt did. The whole figure
        turns together, slowly, and because the figure is regular the rotation
        reads as rotation rather than as drift."""
        D = self._D
        s = min(w, h)
        cx, cy = ox + w / 2.0, oy + h / 2.0
        lvl = self._level
        rot = t * 0.09

        n = self.CONSTELLATION_N
        r = s * self.CONSTELLATION_R * (1.0 + self.BREATH_GAIN * lvl)
        pts = []
        for i in range(n):
            # -tau/4 puts the first point at twelve o'clock.
            ang = rot - math.tau / 4 + i * (math.tau / n)
            pts.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r))

        def line(pen, i, j):
            x0, y0 = pts[i]
            x1, y1 = pts[j]
            g.DrawLine(pen, float(x0), float(y0), float(x1), float(y1))

        chord_pen = self._pen(AMBER_WARM, max(0, int(24 * art)))
        step = self.CONSTELLATION_STEP
        for i in range(n):
            line(chord_pen, i, (i + step) % n)

        ring_pen = self._pen(AMBER_WARM, max(0, int(52 * art)))
        for i in range(n):
            line(ring_pen, i, (i + 1) % n)

        # Every point is the same size; only the brightness breathes, and only
        # gently - a wide swing would undo the evenness the layout just bought.
        dot = s * self.CONSTELLATION_DOT
        spread = 1.0 + self.BLOOM_GAIN * lvl
        glow = 1.0 + self.BLOOM_ALPHA_GAIN * lvl
        for i, (px, py) in enumerate(pts):
            tw = 0.78 + 0.22 * math.sin(t * 1.3 + i * (math.tau / n))
            self._bloom(g, px, py, dot, AMBER_WARM,
                        max(0.0, min(255.0, 225 * tw * art * glow)), spread)

    # Listening / thinking: concentric rings of the same family of points.
    # Each entry is (radius as a fraction of CONSTELLATION_R, how many points,
    # turns per second, colour). The outermost radius is exactly 1.0 of the
    # idle ring, which is what keeps both states cropping identically at the
    # screen edge - `Overlay.orb_overhang` is derived from that same number,
    # so the reveal is the same 25% in either state and the outer ring does
    # not jump when the pattern changes.
    #
    # The inner radii are close together on purpose. Only the bottom of the
    # figure ever reaches the screen, so rings spaced far apart would leave
    # all but the outermost above the edge, unseen; at 0.85 and 0.70 all three
    # dip below it and read as nested arcs.
    ORBITS = (
        (1.00, 22, 0.026, AMBER_WARM),
        (0.85, 18, -0.034, AMBER),
        (0.70, 14, 0.045, CYAN),
    )

    def _draw_orbits(self, g, ox, oy, w, h, t, art):
        """Listening / thinking: three concentric rings, turning against each
        other, cyan at the core.

        This is a state indicator, not an entrance, so the motion is constant
        and linear - no easing, nothing that starts or stops. It is also the
        one pattern that has to say something at a glance: the idle ring turns
        at 0.09 rad/s and reads as still, while these turn several times
        faster and in opposite directions, which is legible as *attending*
        even in the sliver of the figure that clears the screen edge.

        Counter-rotation is what does the work. Three rings turning the same
        way would read as one object; turning against each other they read as
        something running.
        """
        D = self._D
        s = min(w, h)
        cx, cy = ox + w / 2.0, oy + h / 2.0
        lvl = self._level
        base = s * self.CONSTELLATION_R * (1.0 + self.BREATH_GAIN * lvl)
        dot = s * self.CONSTELLATION_DOT
        spread = 1.0 + self.BLOOM_GAIN * lvl
        glow = 1.0 + self.BLOOM_ALPHA_GAIN * lvl

        for radius_f, n, turns, colour in self.ORBITS:
            r = base * radius_f
            rot = t * turns * math.tau
            pts = []
            for i in range(n):
                ang = rot - math.tau / 4 + i * (math.tau / n)
                pts.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r))

            # Only the ring's own edges - no chords across it. Three rings of
            # chords would be a thicket; the idle pattern is where the web
            # belongs, and leaving it out here is part of how the two states
            # stay distinguishable.
            pen = self._pen(colour, max(0, int(46 * art)))
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                g.DrawLine(pen, float(x0), float(y0), float(x1), float(y1))

            for i, (px, py) in enumerate(pts):
                tw = 0.80 + 0.20 * math.sin(t * 2.1 + i * (math.tau / n))
                self._bloom(g, px, py, dot, colour,
                            max(0.0, min(255.0, 225 * tw * art * glow)), spread)

    # The caret: a block that sits where the next character will land. It
    # holds steady while text is still arriving - a cursor being pushed along
    # by the words reads as typing - and only starts blinking once it has
    # nothing left to type, which is how it says "still listening" while you
    # pause for breath.
    CARET_BLINK = 1.05
    CARET_DUTY = 0.62

    def _draw_content(self, g, w, h, now):
        """Blit the cached content under the mesh, as far as it has typed.

        Nothing here re-renders text. The reveal is a source rectangle - the
        face is monospace, so the width of the first n characters is n times
        one character and needs no measuring - and the whole per-frame cost is
        a handful of DrawImage calls plus the caret.
        """
        D = self._D
        content = self._content
        plan = content["layout"]
        bitmap = content["bitmap"]
        top = self.content_top()
        if top >= h:
            return                        # the window has not opened this far yet

        ox = (w - plan["width"]) // 2
        attrs = self._fade_attrs()
        char_w = self._char_w
        line_h = overlay_content.LINE_H
        reveal = self._reveal

        caret = None
        for block in plan["blocks"]:
            if block["kind"] != "text":
                continue
            for line in block["lines"]:
                shown = reveal - line["start"]
                if shown <= 0:
                    break
                count = min(len(line["text"]), int(shown))
                if count <= 0:
                    break
                # One pixel of margin each side, so the glow pass that sits
                # just outside the glyphs is not sheared off by the clip.
                width = int(round(count * char_w)) + 2
                self._blit(g, bitmap, ox + line["x"] - 1, top + line["y"],
                           line["x"] - 1, line["y"], width, line_h, attrs)
                caret = (ox + line["x"] + count * char_w, top + line["y"])

        done = reveal >= plan["chars"]
        extras = content["extras_top"]
        if done and extras is not None:
            self._blit(g, bitmap, ox, top + extras, 0, extras,
                       plan["width"], plan["height"] - extras, attrs)

        # Yours keeps a caret after it lands, because you may still be
        # talking; Apollo's goes away, because the answer is finished.
        if caret and not self._closing:
            if not done:
                lit = True
            elif content["role"] == overlay_content.USER:
                lit = (now % self.CARET_BLINK) < self.CARET_BLINK * self.CARET_DUTY
            else:
                lit = False
            if lit:
                user = content["role"] == overlay_content.USER
                ink = SPEECH_INK if user else REPLY_INK
                x, y = caret
                g.FillRectangle(self._brush(ink, 150 if user else 180),
                                float(x + 1), float(y + 2),
                                max(3.0, char_w - 1.0), float(line_h - 5))

    def _blit(self, g, bitmap, dx, dy, sx, sy, sw, sh, attrs):
        """One clipped copy out of the content bitmap onto the frame."""
        D = self._D
        sx, sy = max(0, int(sx)), max(0, int(sy))
        sw = min(int(sw), bitmap.Width - sx)
        sh = min(int(sh), bitmap.Height - sy)
        if sw <= 0 or sh <= 0:
            return
        dest = D.Rectangle(int(dx), int(dy), sw, sh)
        if attrs is None:
            g.DrawImage(bitmap, dest, sx, sy, sw, sh, D.GraphicsUnit.Pixel)
        else:
            g.DrawImage(bitmap, dest, sx, sy, sw, sh, D.GraphicsUnit.Pixel, attrs)

    def _fade_attrs(self):
        """How see-through the content is right now, as ImageAttributes.

        Only ever used on the way out: the words fade across exactly the
        distance the window has left to collapse, so they leave with it rather
        than being cut from a full-height overlay. On the way in there is no
        fade at all - the window opening downward is the reveal.
        """
        if not self._closing:
            return None
        span = max(1.0, self._collapse_from - self.art)
        alpha = max(0.0, min(1.0, (self._h - self.art) / span))
        key = int(alpha * 12)             # 12 steps is under a visible change
        attrs = self._fades.get(key)
        if attrs is None:
            D = self._D
            matrix = D.Imaging.ColorMatrix()
            matrix.Matrix33 = key / 12.0
            attrs = D.Imaging.ImageAttributes()
            attrs.SetColorMatrix(matrix)
            self._fades[key] = attrs
        return attrs

    def _push(self, hbmp, x, y, w, h):
        """Hand the finished frame to the compositor, alpha and all.

        `hbmp` is the CreateDIBSection handle from `_draw` - already the exact
        premultiplied 32bpp surface UpdateLayeredWindow wants, so this is
        nothing but SelectObject and the call itself; freeing `hbmp` is the
        caller's job, since the caller is also the one who created it.
        """
        screen_dc = _user32.GetDC(None)
        mem_dc = _gdi32.CreateCompatibleDC(screen_dc)
        old = _gdi32.SelectObject(mem_dc, hbmp)
        try:
            size = SIZE(w, h)
            src = POINT(0, 0)
            dst = POINT(x, y)
            blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
            if not _user32.UpdateLayeredWindow(
                    ctypes.c_void_p(self.hwnd), ctypes.c_void_p(screen_dc),
                    ctypes.byref(dst), ctypes.byref(size),
                    ctypes.c_void_p(mem_dc), ctypes.byref(src), 0,
                    ctypes.byref(blend), ULW_ALPHA):
                self.last_error = ctypes.get_last_error()
        finally:
            _gdi32.SelectObject(mem_dc, old)
            _gdi32.DeleteDC(mem_dc)
            _user32.ReleaseDC(None, screen_dc)

    # -- what apollo.py drives ----------------------------------------------

    def set_visible(self, on):
        """Show or hide, from any thread.

        ShowWindow rather than anything WinForms offers, so this can be called
        off the UI thread without marshalling and without ever stealing focus.
        Showing again is safe: the layered surface still holds the last frame
        drawn, so it comes back as itself rather than as a blank form.
        """
        self._visible = bool(on)
        if not self.hwnd:
            return
        _user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE if on else SW_HIDE)
        if on:
            self.raise_above()

    def raise_above(self):
        """Reassert topmost, with no visibility or paint side effects.

        Z-order is not sticky: any other window that later asserts
        HWND_TOPMOST can end up above ours, silently, with no error and
        nothing in the window's own state to show it happened - that is
        exactly what made this orb look randomly invisible during
        development. Cheap enough to call defensively, from any thread.
        """
        if not self.hwnd:
            return
        _user32.SetWindowPos(self.hwnd, ctypes.c_void_p(-1), 0, 0, 0, 0,
                             0x0001 | 0x0002 | 0x0010)  # NOSIZE|NOMOVE|NOACTIVATE

    def place(self, rect):
        """Jump back to the resting footprint with no animation.

        `rect` is the idle box - (x, y, size, size) - which also re-homes the
        mesh: its centre x and its top y are taken from here and everything
        else is measured from them. Any content on screen is dropped, because
        this is only ever called when Apollo has been somewhere else entirely
        (the full display) and is coming back.
        """
        x, y, w, _h = (int(v) for v in rect)
        self.art = w
        self.home = (x + w // 2, y)
        self._w = self._h = float(w)
        self.rect = (x, y, w, w)
        self._drop(self._content)
        self._content = None
        self._closing = False
        self._reveal = 0.0

    def set_active(self, active):
        """Switch the pattern drawn inside the same footprint: the idle
        constellation, or the listening/thinking orbits.

        Safe from any thread. It sets the target and stamps the clock; the
        drawing thread does the crossfade itself in `_blend`, so nothing here
        touches GDI+ or the timer from a foreign thread.
        """
        active = bool(active)
        if active == self.active:
            return
        self._blend_from = self._blend()
        self._blend_t0 = time.monotonic()
        self.active = active

    def close(self):
        self.stopping.set()
        if self.hwnd:
            try:
                _user32.ShowWindow(self.hwnd, SW_HIDE)
            except Exception:
                pass
