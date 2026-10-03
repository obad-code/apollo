"""The overlay: a CRT panel that drops from the top edge while you talk.

Apollo's full display is an HTML page in a WebView2 window. This is not, and
the reason is measured rather than assumed: a WebView2 window here cannot be
made see-through. Its own `DefaultBackgroundColor`, `DwmEnableBlurBehindWindow`
with an empty region (the trick winit and tao use), the layered style and
click-through were all applied in turn and together, and the desktop behind
the window still changed in 81% of pixels - see `apollo.py`'s docstring and
`probes/probe_transparent_matrix.py`. So the overlay is drawn with GDI+ into a
32-bit ARGB bitmap and handed to a layered window with `UpdateLayeredWindow`,
the one path on Windows that gives real per-pixel alpha.

What it draws, in the shape the design asks for:

    at rest      the amber ring, hanging off the top edge, a quarter in view
    talking      a panel drops from the edge: Apollo's three-ring orb, your
                 words in cyan as they are transcribed, and a status word
    searching    the orb spins up and the status says what it is doing
    result       the panel grows and borderless cards fade in, staggered
    answering    the reply in amber, with a gradient chart under it if the
                 answer rests on real numbers
    then         it retracts into the ring, faster than it came

Three things carry the load. `overlay_paint` owns the pieces and pre-renders
everything that does not change shape - the panel's gradient and drifting
colour clouds, the orb's glowing points, the sparkle field - because a frame
built the naive way measured 15.9 ms against a 16.7 ms budget, and rebuilt
this way measures 4.5 ms. `overlay_state` owns the springs, which are
critically damped and retargetable: the panel's height changes while it is
still moving, because live speech re-wraps on every word.
"""

import ctypes
import math
import os
import threading
import time

import overlay_content
import overlay_paint
import overlay_state

ULW_ALPHA = 0x00000002
AC_SRC_OVER, AC_SRC_ALPHA = 0x00, 0x01

WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008

SW_HIDE, SW_SHOWNOACTIVATE = 0, 8

HERE = os.path.dirname(os.path.abspath(__file__))

PALETTE = overlay_paint.PALETTE
# The bleed round light type on the black card, the way a tube's letters
# glowed: drawn once into the cached body, so it costs nothing per frame.
PHOSPHOR = (255, 170, 60)

# The resting ring - the quarter of it that peeks down from the top edge -
# in a yellow phosphor: the same family as the card's glow under it.
AMBER = (255, 184, 0)
AMBER_WARM = (255, 212, 92)

# Thmanyah, which Apollo carries with him rather than expecting Windows to
# have it. One family sets both scripts, so Arabic and English are no longer
# in different faces. GDI+ exposes each weight as its own family name.
FONT_FILES = {"light": "thmanyahsans-Light.otf",
              "regular": "thmanyahsans-Regular.otf",
              "medium": "thmanyahsans-Medium.otf",
              "bold": "thmanyahsans-Bold.otf",
              "black": "thmanyahsans-Black.otf"}
FONT_FAMILIES = {"light": "thmanyah sans Light",
                 "regular": "thmanyah sans",
                 "medium": "thmanyah sans Med",
                 "bold": "thmanyah sans",
                 "black": "thmanyah sans Black"}

# What is used if the font files are not there - a checkout without them still
# has to draw something.
FONT_STACK = ("Segoe UI", "IBM Plex Mono", "Consolas", "Tahoma")
RTL_FONT_STACK = ("Segoe UI", "Tahoma", "Arial")
# Bigger than the card first had: on black, light type reads smaller than
# the same size in dark ink on cream, and the reply was already small.
FONT_PT = 12.5
FONT_SMALL_PT = 9.0
CAPTION_PT = 9.5
NAME_PT = 13.5            # the name on the card, in the proportional face

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
                                    ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p,
                                    ctypes.c_uint32]


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


class Metrics(overlay_content.Metrics):
    """Layout metrics that measure text properly rather than counting it."""

    def __init__(self, char_w, measure, line_h=overlay_content.LINE_H):
        super().__init__(char_w, line_h)
        self._measure = measure

    def width_of(self, text):
        return self._measure(text or "")


class Orb:
    """The overlay window, and everything drawn into it.

    Built on the host's UI thread rather than a thread of its own. A WinForms
    form created on a bare Python thread never gets a window here - `Shown`
    simply never fires, with no error - and the overlay silently does not
    exist. The host's thread already has a running message pump, so the form
    appears and the timer ticks.

    Nothing is ever painted through WinForms itself: every frame is handed to
    the compositor whole by `UpdateLayeredWindow`, which also moves and
    resizes the window, so one call per frame does shape, position and size
    together.

    Everything `apollo.py` calls is safe from any thread: `set_state` for the
    phase, `set_level` for your voice, `set_content` for words and visuals,
    `set_activity` for what Apollo is doing. None of them touch GDI+; they
    leave a note for the drawing thread to pick up.
    """

    TICK_MS = 16       # the timer never changes rate; see `_tick`
    REST_EVERY = 3     # so ~20fps at rest, ~60fps while anything is moving

    # The card, in the proportions of the approved design.
    PANEL_W = overlay_state.PANEL_W
    PAD_X = 26
    PAD_TOP = 22
    PAD_BOTTOM = 20
    ORB_BOX = 50                # Apollo's mark, in the footer row
    ROW_GAP = 14                # between the mark and the name beside it
    BODY_GAP = 13               # between what Apollo said and that row
    FOOT_H = 52
    MARK_BOX = 22               # the company's logo on a stock card
    SHADOW_ROOM = 46
    WINDOW_MARGIN = 30          # room around the card for its shadow
    TRANSCRIPT_LINES = 2
    MAX_CONTENT_H = 420         # no answer may take more of the screen

    # A word of the body rises this far as it fades in, one after another,
    # arriving out of a blur: the reveal from the design brief, at its own
    # numbers. `RISE` is the brief's y: 24, scaled to this card's type.
    WORD_RISE = 11.0
    WORD_STAGGER = 0.045
    WORD_FADE = 0.34
    WORD_BLUR = 5.0             # how far the ghost copies sit from the word

    CARET_BLINK = 1.05
    CARET_DUTY = 0.62

    LEVEL_ATTACK = 0.05
    LEVEL_RELEASE = 0.28

    def __init__(self, size, position, overhang=0):
        # `art` is the resting ring's own box: the figure is drawn into a
        # square of this size at the top of the window, so the window's height
        # is not an input to it and the ring cannot move when the panel grows.
        self.art = int(size)
        self.overhang = int(overhang)
        self.home = (position[0] + int(size) // 2, position[1])   # centre x, top y
        self.rect = (position[0], position[1], int(size), int(size))
        self.ready = threading.Event()
        self.stopping = threading.Event()
        self.hwnd = None
        self.frames = 0
        self.errors = 0
        self._visible = True
        self._form = None
        self._t0 = time.monotonic()
        self._ticks = 0
        self._level = 0.0                 # smoothed mic loudness, drawing thread
        self._level_target = 0.0          # raw, written by the audio thread
        self._clock = 0.0                 # the warped clock everything moves on
        self._last_draw = time.monotonic()
        self._brushes = {}
        self._pens = {}
        self._fades = {}

        self.view = overlay_state.OverlayState()
        self._height = overlay_state.Spring(float(size), response=0.40)
        self.paint = self.mark = None

        # What is on screen: your words, Apollo's body, and what it is doing.
        self._heard = ""
        self._said = ""                   # Apollo's plain reply, in the bar
        self._isl_cache = (None, [])
        self._isl_w = overlay_state.Spring(float(self.ISLAND_REST[0]), response=0.38)
        self._isl_h = overlay_state.Spring(float(self.ISLAND_REST[1]), response=0.38)
        self._isl_icons = overlay_state.Spring(0.0, response=0.3)
        self._isl_eyes = overlay_state.Spring(1.0, response=0.3)
        self._isl_globe = overlay_state.Spring(0.0, response=0.34)
        self._isl_corner = overlay_state.Spring(0.0, response=0.36)
        self._isl_text = overlay_state.Spring(0.0, response=0.3)
        self._content = None              # the built, cached, drawable body
        self._content_at = 0.0            # when it arrived, for the stagger
        self._pending = None
        self._pending_seq = 0
        self._applied_seq = 0
        self._clear_at = None
        self._content_lock = threading.Lock()
        self._w = float(size)
        self._h = float(size)
        self._fonts = None
        self._char_w = 8.0
        self._heard_cache = (None, [])
        self._private = None
        self._collection = None
        self._marks = {}

    # -- lifecycle ----------------------------------------------------------

    def start_on(self, host_form):
        """Create the overlay's window on the thread that owns `host_form`."""
        import clr
        clr.AddReference("System.Windows.Forms")
        clr.AddReference("System.Drawing")
        import System.Drawing as D
        import System.Windows.Forms as WF
        from System import Action, IntPtr

        self._D, self._WF, self._IntPtr = D, WF, IntPtr
        self.paint = overlay_paint.Backdrop(D)
        self.mark = overlay_paint.GlobeMark(D)
        self.mini = overlay_paint.MiniApollo(D)

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
                # first frame lands - exactly the bug this overlay exists to
                # avoid. Touching Handle creates the window without showing it.
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
                    self.raise_above()

                # Frames come from a WinForms timer on this same thread. GDI+
                # objects are created through pythonnet, and first touching a
                # CLR type from a foreign thread can fail outright, which shows
                # up as an overlay that never paints.
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
        """One timer tick. Redraws every tick while anything is moving, every
        third at rest - the interval itself is never changed, because a
        WinForms timer belongs to the thread that made it and the state is set
        from other threads. Setting Interval across threads degrades the timer
        to a couple of ticks a second, which looks exactly like an animation
        that refuses to start."""
        if self.stopping.is_set() or not self.hwnd:
            return
        try:
            self._ticks += 1
            self._sync_content()
            busy = (not self.view.resting or not self._height.resting
                    or self._level > 0.01 or self._level_target > 0.01
                    or self.view.panel_open > 0.01)
            if self._visible and (busy or self._ticks % self.REST_EVERY == 0):
                self._draw()
                self.frames += 1
        except Exception:
            import traceback
            self.last_exc = traceback.format_exc()
            self.errors += 1

    # -- what apollo.py sets ------------------------------------------------

    def set_state(self, state):
        """Which state the overlay is in. Safe from any thread."""
        self.view.set(state)

    def set_active(self, active):
        """Older shape of `set_state`, kept for callers that only know busy."""
        self.set_state(overlay_state.LISTENING if active else overlay_state.REST)

    def set_activity(self, text):
        """What Apollo is doing, in a few words, under your line."""
        self._activity = text or ""

    def set_level(self, value):
        """Live mic loudness, 0-1. Called from the audio thread - one float
        assignment, no allocation, no GDI+."""
        try:
            self._level_target = max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            self._level_target = 0.0

    def set_content(self, role, text, visual=None):
        """Put words (and maybe a chart or cards) in the panel.

        Safe from any thread: it only stores the request. The drawing thread
        picks it up in `_sync_content`, which is where the layout and the
        bitmap are built - both need GDI+, and GDI+ here belongs to that
        thread alone.
        """
        with self._content_lock:
            self._pending = (role, text or "", visual)
            self._pending_seq += 1
            self._clear_at = None

    def clear_content(self, after=0.0):
        """Retract to the bare ring, optionally after a delay."""
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
            self._heard = ""
            self._said = ""
            self._activity = ""
            self._drop(self._content)
            self._content = None
            self.view.set(overlay_state.REST)
            return

        if not fresh:
            return

        role, text, visual = pending
        text = overlay_content.elide(text)
        if role == overlay_content.USER:
            # Your words are one live line: drawn directly every frame, so
            # they can keep up with a transcript that changes on every word.
            self._heard = text
            return

        if not text and not visual:
            return
        if visual is None:
            # Plain words go in Mini Apollo's bar, not on the card.
            self._said = text
            self._drop(self._content)
            self._content = None
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
        # A reply that only grows (streaming) keeps its arrival time, so the
        # lines already on screen do not fade in again on every fragment.
        grew = (previous is not None and previous["role"] == role
                and text.startswith(previous["text"]))
        self._content = built
        self._content_at = previous["at"] if grew else time.monotonic()
        self._content["at"] = self._content_at
        self._drop(previous)

    def _drop(self, content):
        """Free a content bitmap once nothing is drawing it any more.

        Worth doing explicitly rather than leaving to the collector: the
        memory behind a GDI+ bitmap is unmanaged, the collector has no idea
        how much it is sitting on, and a streaming reply rebuilds this several
        times a second.
        """
        if content is None:
            return
        try:
            content["bitmap"].Dispose()
        except Exception:
            pass

    # -- geometry -----------------------------------------------------------

    def panel_left(self, width):
        return int((width - self.PANEL_W) / 2)

    def top_row_height(self):
        """What sits above the body: the hidden paper, and your own words."""
        return self.hidden_height() + self.PAD_TOP + self._heard_height()

    def foot_height(self):
        return self.FOOT_H + self.PAD_BOTTOM

    def _heard_lines(self):
        """Your words, wrapped - cached, because both the height and the
        drawing need them and wrapping measures every prefix."""
        text_w = self.PANEL_W - self.PAD_X * 2
        key = (self._heard, text_w)
        if self._heard_cache[0] != key:
            rtl = overlay_content.is_rtl(self._heard)
            metrics = Metrics(self._char_w, lambda s: self._heard_width(s, rtl))
            lines = overlay_content.wrap(self._heard, 0, metrics, text_w)
            self._heard_cache = (key, lines[-self.TRANSCRIPT_LINES:])
        return self._heard_cache[1]

    def _heard_width(self, text, rtl):
        """Your words' width in the face `_draw_lines` sets them in - the
        caption face, or the Arabic one - not the reply's."""
        fonts = self._font_set()
        return self._measure(text, rtl, font=fonts["rtl"] if rtl else fonts["caption"])

    def _heard_height(self):
        """As tall as your words actually are. Reserving the maximum left a
        band of empty paper under a single line."""
        if not self._heard:
            return 0
        return overlay_content.LINE_H * len(self._heard_lines()) + 6

    def _body_height(self):
        return self._content["layout"]["height"] if self._content else 0

    def content_height(self):
        """Everything that has to be read, plus the padding around it."""
        body = self._body_height()
        return (self.PAD_TOP + self._heard_height()
                + (body + self.BODY_GAP if body else 0)
                + self.foot_height())

    def hidden_height(self):
        """The paper above the screen's edge: a quarter of the whole card.

        It is the empty top of the design's card. Keeping it means the card
        still reads as a card hanging off the edge; putting it above the
        screen means none of it is empty space you have to look at.
        """
        return int(round(self.panel_height() * overlay_paint.HIDDEN))

    def panel_height(self):
        """The card's full height, hidden quarter included."""
        return int(round(self.content_height() / (1.0 - overlay_paint.HIDDEN)))

    MINI_W = overlay_paint.MiniApollo.W + 40

    def _targets(self):
        """The size the window is heading for: (width, height).

        Width is not animated - nothing is drawn near the window's left and
        right edges, so widening it is invisible, and easing it would only
        delay the point at which text has room to wrap into.
        """
        if self._content is None:
            # Mini Apollo's bar, at whatever size it is heading for.
            iw, ih = self._island_target()
            return (float(max(self.art, iw + 60)),
                    float(max(self.art, self.overhang + ih + 30)))
        width = float(max(self.art, self.PANEL_W + self.WINDOW_MARGIN * 2))
        height = (self.overhang - self.hidden_height() + self.panel_height()
                  + self.SHADOW_ROOM)
        return width, float(max(self.art, height))

    # -- Mini Apollo's bar: eyes at rest, Apollo while you talk, words in it --

    ISLAND_REST = (300, 34)        # the row alone: Apollo left, his eyes right
    ISLAND_ON = (300, 34)
    ISLAND_TEXT_W = 540            # the bar, with what is said in its well
    ISLAND_LINES = 4
    ISLAND_LH = 22

    def _island_words(self):
        return self._said or self._heard

    def _island_active(self):
        return bool(self._island_words()) or self.view.state != overlay_state.REST

    def _island_lines(self):
        text = self._island_words()
        width = self.ISLAND_TEXT_W - 16 - 32
        key = (text, width)
        if self._isl_cache[0] != key:
            rtl = overlay_content.is_rtl(text)
            fonts = self._font_set()
            font = fonts["rtl"] if rtl else fonts["caption"]
            metrics = Metrics(self._char_w, lambda t: self._measure(t, rtl, font=font))
            lines = overlay_content.wrap(text, 0, metrics, width) if text else []
            self._isl_cache = (key, lines[-self.ISLAND_LINES:])
        return self._isl_cache[1]

    def _island_target(self):
        if self._island_words():
            n = max(1, len(self._island_lines()))
            return self.ISLAND_TEXT_W, overlay_paint.MiniApollo.HEAD_ROW + 12 + n * self.ISLAND_LH + 18
        if self._island_active():
            return self.ISLAND_ON
        return self.ISLAND_REST

    def _cursor_look(self, ex, ey):
        """Where the pointer is, from the eyes at (ex, ey) in the window, as
        a direction squashed into -1..1."""
        try:
            pt = POINT()
            _user32.GetCursorPos(ctypes.byref(pt))
        except Exception:  # noqa: BLE001
            return (0.0, 0.0)
        dx = pt.x - (self.rect[0] + ex)
        dy = pt.y - (self.rect[1] + ey)
        return (max(-1.0, min(1.0, dx / 500.0)), max(-1.0, min(1.0, dy / 300.0)))

    def _advance_island(self, dt):
        tw, th = self._island_target()
        words = bool(self._island_words())
        active = self._island_active()
        for spring, goal in ((self._isl_w, tw), (self._isl_h, th),
                             (self._isl_icons, 1.0 if active else 0.0),
                             (self._isl_eyes, 0.0 if active else 1.0),
                             (self._isl_globe, 1.0 if active else 0.0),
                             (self._isl_corner, 1.0 if words else 0.0),
                             (self._isl_text, 1.0 if words else 0.0)):
            spring.to(goal)
            spring.step(dt)

    def _draw_island(self, g, cx, t, fade):
        """Mini Apollo's bar: Apollo in the pill on the left, his eyes on
        the right watching the pointer, and what is said in the well."""
        a = 255 * fade
        w, h = self._isl_w.value, self._isl_h.value
        well_box, well = self.mini.shell(g, cx, self.overhang, w, h, a, 1.0)
        slots = self.mini.slots
        # Apollo: always there, spinning up while he works, brighter with your voice.
        ax, ay = slots["apollo"]
        spin = 5.0 if self.view.state == overlay_state.SEARCHING else 1.0
        self.mark.draw_at(g, ax, ay, 8.5 + 1.5 * self._level, t * spin, level=self._level, fade=fade)
        # His eyes, following the pointer.
        ex, ey = slots["eyes"]
        self.mini.eyes(g, ex, ey, t, a, self._cursor_look(ex, ey), size=0.62)
        if well is None:
            return
        wx, wy, ww, wh = well_box
        g.SetClip(well)
        try:
            shown = max(0.0, min(1.0, self._isl_text.value))
            lines = self._island_lines()
            if shown > 0.02 and lines:
                fonts = self._font_set()
                text = self._island_words()
                rtl = overlay_content.is_rtl(text)
                font = fonts["rtl"] if rtl else fonts["caption"]
                fmt = fonts["rtl_fmt"] if rtl else fonts["fmt"]
                colour = PALETTE["you"] if not self._said else PALETTE["ink"]
                left, right = wx + 16.0, wx + ww - 16.0
                y = wy + 9.0
                for line in lines:
                    self._string(g, line, font, fmt, right if rtl else left, y,
                                 colour, 235 * shown * fade)
                    y += self.ISLAND_LH
        finally:
            g.ResetClip()
            well.Dispose()

    def _advance(self, dt):
        self.view.step(dt)
        self._advance_island(dt)
        want_w, want_h = self._targets()
        self._height.to(want_h)
        self._height.step(dt)
        self._h = self._height.value
        self._w = want_w
        cx, top = self.home
        w, h = int(round(self._w)), int(round(self._h))
        self.rect = (cx - w // 2, top, w, h)

    def _advance_level(self, dt):
        """Ease the smoothed level toward the raw one, frame-rate independent."""
        target = self._level_target
        tau = self.LEVEL_ATTACK if target > self._level else self.LEVEL_RELEASE
        self._level += (target - self._level) * (1.0 - math.exp(-dt / tau))
        if self._level < 0.001:
            self._level = 0.0

    # -- fonts and text -----------------------------------------------------

    def _private_faces(self):
        """Thmanyah, loaded from the repository rather than from Windows.

        One family draws both scripts, so Apollo no longer sets Arabic in a
        different face from English. Loading it privately means it works on a
        machine where nobody installed it - and the collection must outlive
        every Font built from it, or GDI+ draws from freed memory, so it is
        held on the instance rather than dropped here.
        """
        if self._private is not None:
            return self._private
        D = self._D
        faces = {}
        collection = D.Text.PrivateFontCollection()
        loaded = 0
        for weight, filename in FONT_FILES.items():
            path = os.path.join(HERE, "ui", "fonts", "thmanyah", filename)
            if os.path.exists(path):
                collection.AddFontFile(path)
                loaded += 1
        if loaded:
            self._collection = collection          # kept alive on purpose
            faces = {family.Name: family for family in collection.Families}
        self._private = faces
        return faces

    def _face(self, weight, size, style=None):
        """One font in Thmanyah if it is there, in the old stack if not.

        Bold is a style of the regular family here, not a family of its own -
        the Light, Medium and Black weights are separate families, which is
        how GDI+ exposes a family with more than four weights.
        """
        D = self._D
        if style is None:
            style = D.FontStyle.Bold if weight == "bold" else D.FontStyle.Regular
        family = self._private_faces().get(FONT_FAMILIES[weight])
        if family is not None:
            return D.Font(family, size, style, D.GraphicsUnit.Point)
        installed = {f.Name for f in D.FontFamily.Families}
        stack = RTL_FONT_STACK if weight == "name" else FONT_STACK
        fallback = next((n for n in stack if n in installed),
                        D.FontFamily.GenericSansSerif.Name)
        return D.Font(fallback, size, style, D.GraphicsUnit.Point)

    def _font_set(self):
        """Every face the card needs, built once.

        GenericTypographic for both measuring and drawing: the default format
        pads around a string, so measuring with one and drawing with the other
        puts the caret a few pixels off the last glyph and drifts further with
        every line.
        """
        if self._fonts is not None:
            return self._fonts

        D = self._D
        # Medium, not regular: light strokes on black thin out, and the
        # reply is the thing on the card that has to read.
        body = self._face("medium", FONT_PT)
        # The same family for Arabic: that is the whole point of it.
        rtl = self._face("medium", FONT_PT)
        small = self._face("light", FONT_SMALL_PT)
        caption = self._face("regular", CAPTION_PT)
        # The name in the footer carries a weight: it is a label, not a readout.
        name_font = self._face("bold", NAME_PT)

        fmt = D.StringFormat(D.StringFormat.GenericTypographic)
        fmt.FormatFlags = fmt.FormatFlags | D.StringFormatFlags.MeasureTrailingSpaces
        rtl_fmt = D.StringFormat(D.StringFormat.GenericTypographic)
        rtl_fmt.FormatFlags = (rtl_fmt.FormatFlags
                               | D.StringFormatFlags.MeasureTrailingSpaces
                               | D.StringFormatFlags.DirectionRightToLeft)

        probe = D.Bitmap(4, 4, D.Imaging.PixelFormat.Format32bppPArgb)
        g = D.Graphics.FromImage(probe)
        try:
            sample = "M" * 40
            self._char_w = g.MeasureString(sample, body, D.PointF(0.0, 0.0),
                                           fmt).Width / len(sample)
            self._measure_with = (g, body, rtl, fmt)
        finally:
            g.Dispose()
            probe.Dispose()

        self._fonts = {"body": body, "rtl": rtl, "small": small, "caption": caption,
                       "name": name_font, "fmt": fmt, "rtl_fmt": rtl_fmt}
        return self._fonts

    def _measure(self, text, rtl=False, font=None):
        """The real width of a string, in pixels, in the face it will be drawn in.

        `font` matters wherever the caller right-aligns against the result:
        the card's price is set in the name face, and measuring it in the
        body face put it a few pixels off the card's edge.
        """
        fonts = self._font_set()
        D = self._D
        probe = D.Bitmap(4, 4, D.Imaging.PixelFormat.Format32bppPArgb)
        g = D.Graphics.FromImage(probe)
        try:
            if font is None:
                font = fonts["rtl"] if rtl else fonts["body"]
            return g.MeasureString(text, font, D.PointF(0.0, 0.0), fonts["fmt"]).Width
        finally:
            g.Dispose()
            probe.Dispose()

    def _string(self, g, text, font, fmt, x, y, colour, alpha, glow=None):
        """One run of text, with the design's soft halo behind it.

        GDI+ has no blur, so this is four offset copies at low alpha under the
        crisp one. Cheap enough because a body line only draws when it is
        built; the live transcript pays it once a frame for one line.
        """
        D = self._D
        if glow:
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                g.DrawString(text, font, self._brush(glow, alpha * 0.16),
                             D.PointF(float(x + dx), float(y + dy)), fmt)
        g.DrawString(text, font, self._brush(colour, alpha),
                     D.PointF(float(x), float(y)), fmt)

    def _brush(self, colour, alpha):
        """A cached SolidBrush. Building one per call is hundreds of GDI+
        allocations a frame, each crossing into the CLR through pythonnet."""
        a = min(255, max(0, (int(alpha) // 2) * 2))
        key = (colour, a)
        brush = self._brushes.get(key)
        if brush is None:
            brush = self._D.SolidBrush(self._D.Color.FromArgb(a, *colour))
            self._brushes[key] = brush
        return brush

    def _pen(self, colour, alpha, width=1.0):
        a = min(255, max(0, (int(alpha) // 2) * 2))
        key = (colour, a, width)
        pen = self._pens.get(key)
        if pen is None:
            pen = self._D.Pen(self._D.Color.FromArgb(a, *colour), float(width))
            self._pens[key] = pen
        return pen

    # -- the body: reply text, cards, chart ---------------------------------

    def _build_content(self, role, text, visual):
        """Lay the body out and render it once into a cached bitmap.

        Cached because a frame cannot afford to draw it: a full render of
        text, a chart and three cards is about 10 ms against a 16.7 ms budget
        the rest of the frame already spends a third of. Blitting the finished
        bitmap is a fraction of a millisecond.
        """
        D = self._D
        fonts = self._font_set()
        rtl = overlay_content.is_rtl(text)
        metrics = Metrics(self._char_w, lambda s: self._measure(s, rtl))

        # The full panel width: `overlay_content.layout` insets by its own
        # PAD_X. Handing it an already-inset width padded the body twice,
        # which squeezed three cards into two rows.
        plan = overlay_content.layout(role, text, visual, metrics, self.PANEL_W,
                                      max_height=self.MAX_CONTENT_H)
        if plan["height"] <= 0:
            return None

        bitmap = D.Bitmap(self.PANEL_W, plan["height"],
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
                    self._render_text(g, block, fonts, rtl)
                elif block["kind"] == "stock":
                    self._render_stock(g, block, fonts)
                elif block["kind"] == "chart":
                    self._render_chart(g, block, fonts)
                elif block["kind"] == "cards":
                    self._render_cards(g, block, fonts)
        finally:
            g.Dispose()

        return {"role": role, "text": text, "layout": plan, "bitmap": bitmap,
                "rtl": rtl, "at": time.monotonic()}

    def _render_text(self, g, block, fonts, rtl):
        font = fonts["rtl"] if rtl else fonts["body"]
        fmt = fonts["rtl_fmt"] if rtl else fonts["fmt"]
        for line in block["lines"]:
            x = line["x"]
            if rtl:
                # The format draws from the right edge of the box it is given.
                x = line["x"] + line.get("width", 0)
            self._string(g, line["text"], font, fmt, x, line["y"],
                         PALETTE["ink"], 255, PHOSPHOR)

    def _render_stock(self, g, block, fonts):
        """One stock, as its own card: the mark, the price, the curve, the
        valuation. The same shape the full display's cards have, at the size
        the overlay has room for.
        """
        D = self._D
        x0, y0 = float(block["x"]), float(block["y"])
        width = float(block["w"])
        up = block.get("change_pct", 0.0) >= 0
        tint = PALETTE["up"] if up else PALETTE["down"]

        # -- the row of identity and price ---------------------------------
        head = y0 + 2.0
        text_x = x0
        mark = self._mark(block.get("logo"))
        if mark is not None:
            g.DrawImage(mark, D.Rectangle(int(x0), int(head), self.MARK_BOX,
                                          self.MARK_BOX))
            text_x = x0 + self.MARK_BOX + 10.0

        self._string(g, block.get("symbol", ""), fonts["name"], fonts["fmt"],
                     text_x, head + 3.0, PALETTE["ink"], 255)
        name = block.get("name") or ""
        if name and name.upper() != block.get("symbol", "").upper():
            offset = self._measure(block.get("symbol", ""), font=fonts["name"]) + 10.0
            self._string(g, name[:22], fonts["caption"], fonts["fmt"],
                         text_x + offset, head + 6.0, PALETTE["caption"], 210)

        unit = block.get("unit") or ""
        price = f"{unit}{block.get('price', 0.0):,.2f}"
        move = f"{'▲' if up else '▼'}{abs(block.get('change_pct', 0.0)):.2f}%"
        move_w = self._measure(move, font=fonts["caption"])
        self._string(g, move, fonts["caption"], fonts["fmt"],
                     x0 + width - move_w, head + 6.0, tint, 255)
        price_w = self._measure(price, font=fonts["name"])
        self._string(g, price, fonts["name"], fonts["fmt"],
                     x0 + width - move_w - price_w - 10.0, head + 3.0,
                     PALETTE["ink"], 255)

        # -- the curve ------------------------------------------------------
        plot_y = y0 + float(block["head_h"])
        self._curve(g, block.get("points") or [], x0, plot_y, width,
                    float(block["plot_h"]), tint)

        # -- what it is worth ----------------------------------------------
        foot = plot_y + float(block["plot_h"]) + 1.0
        parts = []
        if block.get("target"):
            piece = f"{unit}{block['target']:,.2f} target"
            if block.get("upside") is not None:
                piece += f"  {block['upside']:+.1f}%"
            parts.append(piece)
        if block.get("pe"):
            parts.append(f"{block['pe']:.1f} P/E")
        if parts:
            self._string(g, "   ·   ".join(parts), fonts["caption"], fonts["fmt"],
                         x0, foot, PALETTE["caption"], 225)

    def _mark(self, path):
        """The company's logo, loaded once and kept."""
        if not path or not os.path.exists(path):
            return None
        image = self._marks.get(path)
        if image is None:
            try:
                image = self._D.Image.FromFile(path)
            except Exception:  # noqa: BLE001 - a card without a mark is a card
                image = False
            self._marks[path] = image
        return image or None

    def _curve(self, g, points, x0, y0, w, h, colour):
        """A smooth line with its wash underneath, in one colour."""
        D = self._D
        if len(points) < 2:
            return
        low, high = min(points), max(points)
        span = high - low
        if span <= 0:
            low, high, span = low - 1.0, high + 1.0, 2.0
        pad = 6.0
        step = w / (len(points) - 1)
        xs = [x0 + step * i for i in range(len(points))]
        ys = [y0 + pad + (h - pad * 2) * (1.0 - (v - low) / span) for v in points]
        pairs = [D.PointF(float(x), float(y)) for x, y in zip(xs, ys)]

        wash = D.Drawing2D.GraphicsPath()
        # A cardinal spline, not straight segments: daily closes joined by
        # lines read as a saw, and the design's curve is smooth.
        wash.AddCurve(pairs, 0.5)
        wash.AddLine(float(xs[-1]), float(y0 + h), float(xs[0]), float(y0 + h))
        wash.CloseFigure()
        brush = D.Drawing2D.LinearGradientBrush(
            D.RectangleF(float(x0), float(y0), float(w), float(h + 1)),
            D.Color.FromArgb(*overlay_paint.alpha(colour, 0.22)),
            D.Color.FromArgb(0, *colour), D.Drawing2D.LinearGradientMode.Vertical)
        g.FillPath(brush, wash)
        brush.Dispose()
        wash.Dispose()

        pen = D.Pen(D.Color.FromArgb(255, *colour), 2.0)
        pen.LineJoin = D.Drawing2D.LineJoin.Round
        pen.StartCap = pen.EndCap = D.Drawing2D.LineCap.Round
        g.DrawCurve(pen, pairs, 0.5)
        pen.Dispose()

    def _render_chart(self, g, block, fonts):
        """A sparkline: violet into cyan into amber, over a soft fill.

        Sized to the data rather than to a template - the plot is divided into
        exactly as many gaps as the series has, so four readings and forty
        both fill the width without either looking padded.
        """
        D = self._D
        points = block["points"]
        x0, y0 = float(block["x"]), float(block["y"])
        w, h = float(block["plot_w"]), float(block["h"])

        low, high = min(points), max(points)
        span = high - low
        if span <= 0:                     # a flat series still has a shape
            low, high, span = low - 1.0, high + 1.0, 2.0

        top = y0 + 14.0
        plot_h = h - 20.0
        step = w / max(1, len(points) - 1)
        xs = [x0 + step * i for i in range(len(points))]
        ys = [top + plot_h - plot_h * (v - low) / span for v in points]

        # The fill under the line, teal fading to nothing.
        fill = D.Drawing2D.GraphicsPath()
        fill.AddLines([D.PointF(float(x), float(y)) for x, y in zip(xs, ys)])
        fill.AddLine(float(xs[-1]), float(top + plot_h), float(xs[0]), float(top + plot_h))
        fill.CloseFigure()
        brush = D.Drawing2D.LinearGradientBrush(
            D.RectangleF(float(x0), float(top), float(w), float(plot_h + 1)),
            D.Color.FromArgb(*overlay_paint.alpha(PALETTE["teal"], 0.30)),
            D.Color.FromArgb(0, *PALETTE["violet"]),
            D.Drawing2D.LinearGradientMode.Vertical)
        g.FillPath(brush, fill)
        brush.Dispose()
        fill.Dispose()

        line_brush = D.Drawing2D.LinearGradientBrush(
            D.RectangleF(float(x0), float(top - 2), float(w), float(plot_h + 4)),
            D.Color.FromArgb(255, *PALETTE["violet"]),
            D.Color.FromArgb(255, *PALETTE["amber"]),
            D.Drawing2D.LinearGradientMode.Horizontal)
        blend = D.Drawing2D.ColorBlend(3)
        blend.Colors = [D.Color.FromArgb(235, *PALETTE["violet"]),
                        D.Color.FromArgb(235, *PALETTE["cyan"]),
                        D.Color.FromArgb(245, *PALETTE["amber"])]
        blend.Positions = [0.0, 0.6, 1.0]
        line_brush.InterpolationColors = blend
        pen = D.Pen(line_brush, 2.2)
        pen.LineJoin = D.Drawing2D.LineJoin.Round
        pen.StartCap = D.Drawing2D.LineCap.Round
        pen.EndCap = D.Drawing2D.LineCap.Round
        g.DrawLines(pen, [D.PointF(float(x), float(y)) for x, y in zip(xs, ys)])
        pen.Dispose()
        line_brush.Dispose()

        # The reading that matters is the last one.
        g.FillEllipse(self._brush(PALETTE["amber"], 245),
                      float(xs[-1] - 3.5), float(ys[-1] - 3.5), 7.0, 7.0)

        unit = block.get("unit") or ""
        figures = x0 + w + 8.0
        self._string(g, "%g%s" % (high, unit), fonts["small"], fonts["fmt"],
                     figures, top - 5.0, PALETTE["caption"], 150)
        self._string(g, "%g%s" % (low, unit), fonts["small"], fonts["fmt"],
                     figures, top + plot_h - 9.0, PALETTE["caption"], 150)
        if block.get("label"):
            self._string(g, block["label"], fonts["small"], fonts["fmt"],
                         x0, y0 - 2.0, PALETTE["caption"], 165)

    def _render_cards(self, g, block, fonts):
        """Small readouts: label over value, on glass. No outline anywhere."""
        D = self._D
        for card in block["rows"]:
            x, y = float(card["x"]), float(card["y"])
            w, h = float(card["w"]), float(card["h"])
            path = overlay_paint.rounded_path(D, x, y, w, h, 12, top_radius=12)
            g.FillPath(self._brush((255, 255, 255), 11), path)
            path.Dispose()
            self._string(g, card["label"], fonts["caption"], fonts["fmt"],
                         x + 12, y + 10, PALETTE["caption"], 170)
            # A card reads "222.27 ▲1.3%", so the direction is inside the
            # value rather than at the front of it.
            value, colour = card["value"], PALETTE["amber"]
            if "▲" in value or value.lstrip().startswith("+"):
                colour = PALETTE["up"]
            elif "▼" in value or value.lstrip().startswith("-"):
                colour = PALETTE["down"]
            self._string(g, value, fonts["body"], fonts["fmt"],
                         x + 12, y + 26, colour, 240, (255, 150, 0))

    # -- the frame ----------------------------------------------------------

    def _draw(self):
        D = self._D
        now = time.monotonic()
        dt = min(0.1, max(0.0, now - self._last_draw))   # a stall must not lurch
        self._last_draw = now
        self._advance_level(dt)
        self._advance(dt)
        # Motion runs on a clock that speeds up while you are talking, rather
        # than on wall time scaled by the level: scaling wall time rewrites
        # the whole figure's position whenever the level changes.
        self._clock += dt * (1.0 + 2.2 * self._level)
        t = self._clock

        x, y, w, h = self.rect
        w, h = max(8, w), max(8, h)

        # A GDI+ Bitmap built the ordinary way and converted with GetHbitmap()
        # does not dependably preserve alpha - .NET's own docs call it lossy,
        # and in practice it sometimes hands UpdateLayeredWindow a surface
        # that is entirely opaque or entirely transparent with no error. So
        # the Bitmap wraps a DIB section's memory directly, in the
        # premultiplied format the AC_SRC_ALPHA blend expects, and GDI+ draws
        # straight into it: no conversion step left to be unreliable.
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
        # c_void_p raises "value cannot be converted to System.IntPtr".
        bmp = D.Bitmap(w, h, stride, D.Imaging.PixelFormat.Format32bppPArgb,
                       self._IntPtr(bits_ptr.value))
        g = D.Graphics.FromImage(bmp)
        g.SmoothingMode = D.Drawing2D.SmoothingMode.AntiAlias
        g.TextRenderingHint = D.Text.TextRenderingHint.AntiAlias
        g.Clear(D.Color.FromArgb(0, 0, 0, 0))          # genuinely nothing

        try:
            # Mini Apollo's bar, hanging from the screen's edge (`overhang`
            # is where that edge falls in the window). The card drops only
            # for what the bar cannot hold: charts and cards.
            rich = self._content is not None
            card = self.view.panel_open if rich else 0.0
            if card < 0.99:
                self._draw_island(g, w / 2.0, t, 1.0 - card)
            if rich and self.view.panel_open > 0.005:
                self._draw_panel(g, w, t, now)
        finally:
            g.Dispose()
            self._push(hbmp, x, y, w, h)
            bmp.Dispose()          # only releases the wrapper; the DIB memory
            _gdi32.DeleteObject(hbmp)   # is ours, so we free it ourselves

    def _draw_panel(self, g, width, t, now):
        """The card and everything on it, as far as it has dropped."""
        open_amount = self.view.panel_open
        panel_h = self.panel_height()
        hidden = self.hidden_height()
        left = self.panel_left(width)
        # It drops out of the screen's top edge rather than fading in place.
        # Once open, the card's own top sits `hidden` above that edge, which
        # is what takes its upper corners out of sight.
        top = self.overhang - hidden - panel_h * (1.0 - open_amount)

        self.paint.panel(g, left, top, self.PANEL_W, panel_h, t, open_amount)

        # Apollo's mark and his name sit at the foot of the card, as in the
        # design; what he said is above them.
        foot_top = top + panel_h - self.foot_height()
        orb_x = left + self.PAD_X + self.ORB_BOX / 2
        orb_y = foot_top + self.ORB_BOX / 2
        spinning = self.view.state == overlay_state.SEARCHING
        self.mark.draw_at(g, orb_x, orb_y, self.ORB_BOX / 2,
                           t * (5.0 if spinning else 1.0),
                           level=self._level, fade=open_amount)

        self._draw_foot(g, left, foot_top, now, open_amount)
        self._draw_lines(g, left, top + hidden, now, open_amount)
        self._draw_body(g, left, top, panel_h, now, open_amount)

    def _draw_foot(self, g, left, top, now, fade):
        """The design's bottom row: the mark, the name, and what he is doing."""
        fonts = self._font_set()
        text_x = left + self.PAD_X + self.ORB_BOX + self.ROW_GAP
        # In capitals, as the display's sign has it.
        self._string(g, "APOLLO", fonts["name"], fonts["fmt"],
                     text_x, top + 3, PALETTE["ink"], 255 * fade, PHOSPHOR)
        caption = self._activity or self._status_word()
        if caption:
            self._string(g, caption, fonts["caption"], fonts["fmt"],
                         text_x, top + 29, self._caption_colour(), 220 * fade)

    def _draw_lines(self, g, left, top, now, fade):
        """Your own words, above whatever Apollo made of them."""
        if not self._heard:
            return
        fonts = self._font_set()
        text_x = left + self.PAD_X
        text_w = self.PANEL_W - self.PAD_X * 2
        rtl = overlay_content.is_rtl(self._heard)
        font = fonts["rtl"] if rtl else fonts["caption"]
        fmt = fonts["rtl_fmt"] if rtl else fonts["fmt"]

        y = top + self.PAD_TOP
        lines = self._heard_lines()
        for line in lines:
            x = text_x + (text_w if rtl else 0)
            self._string(g, line, font, fmt, x, y, PALETTE["you"], 205 * fade)
            y += overlay_content.LINE_H
        # The caret sits where the next word will land, and blinks only when
        # nothing is arriving - which is how it says "still listening" while
        # you pause for breath.
        if self.view.state in (overlay_state.LISTENING, overlay_state.SEARCHING):
            lit = (now % self.CARET_BLINK) < self.CARET_BLINK * self.CARET_DUTY
            if lit and not rtl:
                caret_x = text_x + self._heard_width(lines[-1], rtl) + 3
                g.FillRectangle(self._brush(PALETTE["cyan"], 190 * fade),
                                float(caret_x), float(y - overlay_content.LINE_H + 2),
                                2.0, float(overlay_content.LINE_H - 6))

    def _status_word(self):
        return {overlay_state.LISTENING: "Listening",
                overlay_state.SEARCHING: "Looking it up",
                overlay_state.RESULT: "Done",
                overlay_state.REPLY: "Speaking"}.get(self.view.state, "")

    def _caption_colour(self):
        # Grey by default, as the design has it. Colour is kept for the two
        # states where it says something: working, and finished working.
        if self.view.state == overlay_state.SEARCHING:
            return PALETTE["amber"]
        if self.view.state == overlay_state.RESULT:
            return PALETTE["up"]
        # Not the grey caption: this sits on the brightest of the glow.
        return PALETTE["you"]

    def _draw_body(self, g, left, top, panel_h, now, fade):
        """The reply, its cards and its chart, arriving a word at a time.

        The reveal from the design brief: each word starts low, blurred and
        invisible, and lands sharp, on a 45 ms stagger. GDI+ has no blur, so
        a word that has not arrived yet is drawn as a few faint copies of
        itself, spread apart and closing in as it settles - which is what a
        blur looks like from a distance, for four more DrawImage calls.

        Charts and cards still come in whole: there are no words in them to
        stagger, and a chart sliding in piecewise would read as a fault.
        """
        content = self._content
        if content is None:
            return
        bitmap = content["bitmap"]
        plan = content["layout"]
        body_top = top + self.top_row_height()
        age = now - content["at"]

        drawn = 0
        for block in plan["blocks"]:
            if block["kind"] == "text":
                for line in block["lines"]:
                    # Arabic is laid out from the right and its letters join,
                    # so a span measured left to right cuts the wrong piece
                    # and shows half-formed shapes. RTL arrives a line at a
                    # time instead - the same reveal, a larger step.
                    spans = ([(0, line["width"])] if block.get("rtl")
                             else line["spans"])
                    for x0, x1 in spans:
                        drawn = self._draw_word(g, bitmap, left, body_top, line,
                                                x0, x1, drawn, age, fade)
                continue
            pieces = block["rows"] if block["kind"] == "cards" else [block]
            for piece in pieces:
                progress = self._arrival(drawn, age)
                drawn += 1
                if progress <= 0.0:
                    continue
                rise = self.WORD_RISE * (1.0 - progress)
                height = piece.get("h", block.get("h", overlay_content.LINE_H))
                source_y = piece.get("y", 0)
                self._blit(g, bitmap, left, body_top + source_y - rise,
                           0, source_y, plan["width"], height,
                           self._fade_attrs(progress * fade))

    def _arrival(self, index, age):
        """How far along the reveal one piece is, 0 before it starts to 1."""
        start = index * self.WORD_STAGGER
        return max(0.0, min(1.0, (age - start) / self.WORD_FADE))

    def _draw_word(self, g, bitmap, left, body_top, line, x0, x1, index, age, fade):
        progress = self._arrival(index, age)
        if progress <= 0.0:
            return index + 1
        source_x = line["x"] + x0
        width = x1 - x0
        source_y = line["y"]
        rise = self.WORD_RISE * (1.0 - progress)
        dx = left + source_x
        dy = body_top + source_y - rise

        # The blur, while it is still arriving: two faint copies either side,
        # drawing together as the word settles. Two rather than four, and only
        # while the spread is wide enough to see - with four, and a ghost on
        # every word still in flight, the worst frame measured 18.3 ms against
        # a 16.7 ms budget.
        spread = self.WORD_BLUR * (1.0 - progress)
        if spread > 1.2:
            ghost = self._fade_attrs(progress * fade * 0.28)
            for ox in (-spread, spread):
                self._blit(g, bitmap, dx + ox, dy, source_x, source_y,
                           width, overlay_content.LINE_H, ghost)

        self._blit(g, bitmap, dx, dy, source_x, source_y,
                   width, overlay_content.LINE_H,
                   self._fade_attrs(progress * fade))
        return index + 1

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

    def _fade_attrs(self, scale):
        """How see-through something is, as ImageAttributes, cached in steps."""
        if scale >= 0.999:
            return None
        key = max(0, min(12, int(scale * 12)))
        attrs = self._fades.get(key)
        if attrs is None:
            D = self._D
            matrix = D.Imaging.ColorMatrix()
            matrix.Matrix33 = key / 12.0
            attrs = D.Imaging.ImageAttributes()
            attrs.SetColorMatrix(matrix)
            self._fades[key] = attrs
        return attrs

    # -- the resting ring ---------------------------------------------------
    #
    # A clock face: N points spaced evenly around one circle, so there is
    # nothing irregular left to look accidental. Drawn from these two numbers
    # rather than a table of hand-picked radii - the table was what made the
    # old shape a zigzag, since every point sat at a different distance from
    # the centre.

    CONSTELLATION_N = 22          # points around the circle
    CONSTELLATION_R = 0.2         # their radius, as a fraction of the box
    CONSTELLATION_DOT = 0.008     # point radius, as a fraction of the box

    def _draw_ring(self, g, ox, oy, w, h, t, fade):
        """At rest: a ring of evenly spaced points over nothing - no ground,
        no panel, and nothing but the points: no lines joining them, no bloom
        round them. Each is one plain round light, twinkling a little, a
        touch brighter and bigger with your voice. The whole figure turns
        together, slowly, and because it is regular the rotation reads as
        rotation rather than as drift."""
        s = min(w, h)
        cx, cy = ox + w / 2.0, oy + h / 2.0
        level = self._level
        rot = t * 0.09

        n = self.CONSTELLATION_N
        r = s * self.CONSTELLATION_R * (1.0 + 0.035 * level)
        dot = s * self.CONSTELLATION_DOT * (1.0 + 0.25 * level)
        for i in range(n):
            # -tau/4 puts the first point at twelve o'clock.
            angle = rot - math.tau / 4 + i * (math.tau / n)
            px, py = cx + math.cos(angle) * r, cy + math.sin(angle) * r
            twinkle = 0.78 + 0.22 * math.sin(t * 1.3 + i * (math.tau / n))
            alpha = max(0.0, min(255.0, 235 * twinkle * fade * (1.0 + 0.3 * level)))
            g.FillEllipse(self._brush(AMBER_WARM, alpha),
                          float(px - dot), float(py - dot), float(dot * 2), float(dot * 2))

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
        HWND_TOPMOST can end up above ours, silently, with nothing in the
        window's own state to show it happened - which is what made this
        overlay look randomly invisible during development.
        """
        if not self.hwnd:
            return
        _user32.SetWindowPos(self.hwnd, ctypes.c_void_p(-1), 0, 0, 0, 0,
                             0x0001 | 0x0002 | 0x0010)  # NOSIZE|NOMOVE|NOACTIVATE

    def place(self, rect, overhang=None):
        """Jump back to the resting footprint with no animation.

        `rect` is the idle box - (x, y, size, size) - which also re-homes the
        ring: its centre x and its top y are taken from here and everything
        else is measured from them. Any content on screen is dropped, because
        this is only ever called when Apollo has been somewhere else entirely
        (the full display) and is coming back.
        """
        x, y, w, _h = (int(v) for v in rect)
        self.art = w
        if overhang is not None:
            self.overhang = int(overhang)
        self.home = (x + w // 2, y)
        self._w = self._h = float(w)
        self._height = overlay_state.Spring(float(w), response=0.40)
        self.rect = (x, y, w, w)
        self._drop(self._content)
        self._content = None
        self._heard = ""
        self._activity = ""
        self.view = overlay_state.OverlayState()

    def close(self):
        self.stopping.set()
        if self.hwnd:
            try:
                _user32.ShowWindow(self.hwnd, SW_HIDE)
            except Exception:
                pass
