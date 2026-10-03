"""Apollo: an always-on voice assistant that lives on your desktop.

Apollo starts once and stays running. At rest it is a mesh of glowing points
hanging off the top edge of the screen, centre. It stays exactly there for a
whole turn: your words appear under it as you say them, then the answer
replaces them, and the overlay grows downward to hold whatever that answer
turns out to be - a couple of lines, a chart, a row of readouts - with no
panel and no background behind any of it. It grows to the whole screen only
when you have been away from the machine for a while, or when you ask for it
with CTRL+`. The talk hotkey is a global Windows hook, so it fires from
inside any application without Apollo ever taking focus.

    start.bat                                 (silent, no console)
    install-startup.bat                       (also launch it at sign-in)
    .\\.venv\\Scripts\\python.exe apollo.py    (console, for debugging)

Quit from the tray icon, or with CTRL+ALT+SHIFT+Q.

What this window can and cannot do about transparency
----------------------------------------------------
WebView2 itself is transparent here - its DefaultBackgroundColor is already
alpha 0. What shows through it is the WinForms host, and pywebview never gives
that host a colour: `transparent=True` assigns `DefaultBackgroundColor` to
pywebview's own `EdgeChrome` wrapper, a plain Python object, so the value lands
on a dead attribute and the form keeps the system Control colour (#F0F0F0).
That near-white square around the orb is the form, not the page.

Measured, on this machine, against a known window underneath:

  * form BackColor            works  - black instead of near-white
  * SetLayeredWindowAttributes
      LWA_ALPHA               works  - real, uniform translucency
      LWA_COLORKEY            ignored - the page's pixels reach the screen
                                        through DirectComposition, never
                                        through the layered surface
  * Form.TransparencyKey      ignored, for the same reason
  * DwmExtendFrameIntoClientArea(-1)  no effect
  * SetWindowCompositionAttribute (blur / acrylic / transparent gradient)
                              no effect
  * WS_EX_NOREDIRECTIONBITMAP rejected - it is creation-only, and pywebview
                              owns window creation
  * SetWindowRgn              clips the form, but the backdrop still paints,
                              so a faint square survives around the circle
  * DwmEnableBlurBehindWindow with an empty region - the winit/tao trick for
                              transparent windows - no effect either, alone or
                              with the WebView2 control's own
                              DefaultBackgroundColor cleared, with or without
                              WS_EX_LAYERED. Measured 2026-09-20 by
                              probes/probe_transparent_matrix.py: the desktop
                              behind the window changed in 81% of pixels every
                              time, i.e. the window painted over it.

So per-pixel transparency - a genuinely round orb with nothing behind it - is
not reachable while the orb is an HTML page in this host. What is reachable is
a black ground and uniform translucency, which is what the panel and the full
display use. The orb itself does not settle for that: it is drawn natively, in
`orb.py`, into a layered window with `UpdateLayeredWindow` - the one path that
gives real per-pixel alpha.

One more finding worth keeping, because it cost real debugging time: building
that layered window's surface via .NET's `Bitmap.GetHbitmap(Color)` is NOT
reliable for this. It is undocumented behaviour, not a hard failure - it
sometimes hands `UpdateLayeredWindow` a surface with the wrong alpha and no
error anywhere to show for it, which reads as "the orb randomly stops
rendering." `orb.py` instead builds the bitmap directly on a `CreateDIBSection`
buffer (`Format32bppPArgb`, matching `AC_SRC_ALPHA`'s premultiplied
expectation) and draws GDI+ straight into that memory - no conversion step
left to be unreliable.

Apollo therefore never covers anything it is not actively using: the window is
only as big as what it needs to show, and covering the screen happens only in
the two states where covering the screen is the entire point.

Why not a true wallpaper
------------------------
Reparenting into Explorer's WorkerW, the way Wallpaper Engine does, puts Apollo
*behind* every window, so it could never be read at the moment you talk to it.
The WorkerW handle also dies whenever Explorer restarts, and WebView2
composites unreliably outside the normal window hierarchy.
"""

import collections
import ctypes
from ctypes import wintypes
import faulthandler
import json
import logging
import logging.handlers
import os
import sys
import threading
import time
import traceback

import win32api
import win32con
import win32event
import win32gui
import winerror

# WebView2 reads this on startup. Without it the page's AudioContext stays
# suspended forever: the overlay is deliberately never focused, so it never
# receives the user gesture the autoplay policy is waiting for, and every
# interface sound would be silently dropped.
os.environ.setdefault(
    "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
    "--autoplay-policy=no-user-gesture-required",
)

import webview  # noqa: E402  - must follow the env var above

import assistant  # noqa: E402
import away as away_mode  # noqa: E402
import briefing  # noqa: E402
import clips  # noqa: E402
import dataservice  # noqa: E402
import diagnostics  # noqa: E402
import displays  # noqa: E402
import ideas  # noqa: E402
import interests  # noqa: E402
import issues  # noqa: E402
import journal  # noqa: E402
import hud  # noqa: E402
import live  # noqa: E402
import lyla  # noqa: E402
import crew  # noqa: E402
import youtube  # noqa: E402
import private_eye  # noqa: E402
import scanner  # noqa: E402
import projects  # noqa: E402
import orb as orb_module  # noqa: E402
import osiris as osiris_module  # noqa: E402
import overlay_content  # noqa: E402
import overlay_state  # noqa: E402
import panels  # noqa: E402
import prayer  # noqa: E402
import presence  # noqa: E402
import reminders  # noqa: E402
import stockdesk  # noqa: E402
import tools  # noqa: E402
import turnview  # noqa: E402
import watchlist  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

log = logging.getLogger("apollo")

# Where Apollo writes what goes wrong. It runs under pythonw, which has no
# console, so without this a failure in a background thread - the watcher, the
# data service, the prayer check - happened and left no trace at all. Every
# module logs under "apollo.*", so this one file catches all of them.
LOG_PATH = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                        "Apollo", "apollo.log")


def start_log(path=LOG_PATH):
    """One rotating file for the whole app: a megabyte, three kept.

    If the file cannot be opened, it writes beside it under its own pid
    rather than not at all - returning None there would send every later line
    nowhere, and awake with an empty log looks exactly like not running.

    A note for whoever debugs this from an agent's shell: a sandboxed shell
    can keep its own copy of %LOCALAPPDATA%, so a log that looks empty from
    there may be full in the real folder. Apollo launched through Explorer
    writes the real one. That, not a locked file, is what made this look
    broken when it was written.
    """
    root = logging.getLogger("apollo")
    # Once per process. A second call must not write every line twice.
    for existing in root.handlers:
        if getattr(existing, "_apollo_log", False):
            return existing

    handler = None
    reason = None
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except OSError:
        return None                   # no folder at all: nothing to fall back to
    for attempt, target in enumerate((path, path, _beside(path))):
        try:
            handler = logging.handlers.RotatingFileHandler(
                target, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
            break
        except OSError as exc:
            reason = exc
            if attempt == 0:
                time.sleep(0.5)       # a copy that is exiting lets go quickly
    if handler is None:
        return None                   # no log is survivable; no Apollo is not

    handler._apollo_log = True
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    if handler.baseFilename != os.path.abspath(path):
        root.warning("could not open %s (%s); logging here instead",
                     os.path.basename(path), reason)
    return handler


def _beside(path):
    """Where to write when the usual file is held: next to it, by pid."""
    stem, ext = os.path.splitext(path)
    return f"{stem}-{os.getpid()}{ext}"


# A replay buffer that died with you here is tried again after this long,
# twice as long each time it dies again, up to half an hour.
CLIPS_RETRY = 60
CLIPS_RETRY_MOST = 30 * 60

CRASH_PATH = os.path.join(os.path.dirname(LOG_PATH), "crash.log")


def watch_crashes(path=CRASH_PATH):
    """Have a crash leave a line, where under pythonw it left nothing.

    An exception nobody caught - on the main thread or any other - goes into
    the log with its traceback. A crash inside a DLL (PortAudio, WebView2)
    never reaches Python's handlers at all; faulthandler writes every
    thread's stack to `path` as it happens, which is what says where it was.
    Returns the crash file, kept open for as long as Apollo runs.
    """
    def logged(kind, exc_type, exc, tb):
        log.critical("%s crashed", kind, exc_info=(exc_type, exc, tb))

    sys.excepthook = lambda *exc: logged("Apollo", *exc)
    threading.excepthook = lambda a: logged(
        f"thread {a.thread.name if a.thread else '?'}", a.exc_type, a.exc_value, a.exc_traceback)
    handle = open(path, "a", encoding="utf-8")
    faulthandler.enable(file=handle, all_threads=True)
    return handle


# The hand-written display. `ui/legacy/` holds the generated page this one
# replaced; `build_ui.py` still builds that, and nothing in the run reads it.
INDEX = os.path.join(HERE, "ui", "full", "index.html")

STARTING = "Waking"          # shown while the API check and model load run
MUTEX_NAME = "Local\\ApolloVoiceAssistantSingleton"

# How big Apollo is at rest. The overlay is centred on the TOP-CENTRE of the
# work area; the full display is the whole work area.
ORB_PX = 190                 # the mesh's own box, drawn by orb.py. The resting
                             # window is this square; once there is something
                             # to show, the native layer grows its own window
                             # downward from this one's top edge and the mesh
                             # stays in a box of exactly this size at the top.
# The resting orb does not sit on the screen - it hangs off the top edge, and
# only this fraction of the CONSTELLATION stays in view: the bottom arc of it
# coming down out of the edge, which is the whole point of the resting state -
# present, not in the way. Measured against the pattern rather than the window
# because the two are not the same size: the ring of points only reaches
# `Orb.CONSTELLATION_R` of the box, so revealing a quarter of the window would
# reveal barely a sixth of the figure. The window really is positioned at a
# negative Y; UpdateLayeredWindow composites the off-screen part away without
# complaint, so no clipping region is needed.
ORB_REVEAL = 0.25

# Per-shape window translucency, 0-255. This is the one transparency mechanism
# that actually works on a WebView2 window (see the module docstring). Only
# the full display is a page window now - an answer is drawn by the native
# layer, under the mesh, on no background at all.
ALPHA = {"orb": 225, "full": 250}

# Global chords. The talk chord is CTRL+ALT, held (see `assistant.talk_held`,
# which tests it exclusively so these two do not fire it on their way past).
# Expand is CTRL+` deliberately: it shares no keys with the talk chord, so
# opening the display never records a fragment of a turn.
# Chords are spelled as Windows virtual-key codes and tested with
# GetAsyncKeyState, not with `keyboard.is_pressed`. Measured on this machine:
# `keyboard.is_pressed("ctrl+`")` returns False the whole time both keys are
# genuinely held down - `parse_hotkey` resolves the backtick to scan code 41
# and the library's hook never matches it - so the chord silently never fired.
# GetAsyncKeyState reported both keys correctly at the same moment, and it is
# what the talk chord already relies on.
VK_CTRL, VK_ALT, VK_SHIFT = 0x11, 0x12, 0x10
QUIT_CHORD = (VK_CTRL, VK_ALT, VK_SHIFT, 0x51)   # Q
PEEK_CHORD = (VK_CTRL, 0xC0)                     # VK_OEM_3, the backtick key
QUIT_HOTKEY = "ctrl+alt+shift+q"                 # for messages and the README
PEEK_HOTKEY = "ctrl+`"

# A click on the display's bar - Idle, Away - still has its hand on the mouse
# for a moment after: this long of it is part of asking, not you coming back.
CLICK_GRACE = 4.0

# Whether the day's recap plays by itself, the first time you are at the
# machine each day. Off: it came every time Apollo started, you could not get
# a word in over it, and it was more in the way than it was worth. It is still
# there the moment you ask for it - "brief me", "catch me up" (the
# daily_briefing tool) - as an ordinary answer, which Ctrl+Alt cuts off like
# any other.
DAILY_RECAP = False

# How long after a turn the day's recap waits before it will start. Long
# enough that pressing the chord, thinking, and pressing it again is one
# conversation rather than an opening for the recap to talk over.
BRIEF_SETTLE = 25.0

# How long the machine must go untouched - no key, no mouse, no voice - before
# Apollo falls asleep: the display becomes the idle screen, screensaver style,
# over whatever was there. The very next keypress, mouse movement or sentence
# wakes it (see `presence.Presence`).
AFK_SECONDS = 10 * 60
# The word, once, as Apollo comes up (see `Apollo.play_intro`): long enough
# for the page's sweep, hold and switch-off, and not a moment longer.
INTRO_SECONDS = 3.6
# ...and it is a real loading screen: it stays while the checks and the start
# run (diagnostics.py), and goes INTRO_TAIL after they are done - time to read
# the last line - but never holds the screen longer than INTRO_MOST.
INTRO_TAIL = 1.8
INTRO_MOST = 12.0
# The boot screen's lines: every check, and the six parts of Apollo that
# say they are up (the Claude API, the voice, the replay buffer, the data
# service, live prices, Private Eye) - for its progress line.
BOOT_TOTAL = len(diagnostics.CHECKS) + 6

# SHQueryUserNotificationState's answers that mean someone is using the
# machine without touching it: a full-screen program (a film in a browser, a
# borderless game), a Direct3D exclusive-mode game, presentation mode.
QUNS_BUSY, QUNS_RUNNING_D3D_FULL_SCREEN, QUNS_PRESENTATION_MODE = 2, 3, 4

def user32_releasing_gil():
    """user32 through ctypes' WinDLL, which lets go of the GIL for the length
    of each call.

    Changing another thread's window - its style, whether it shows, where it
    sits - makes Windows send that thread a message and wait for the answer.
    pywin32's wrappers wait holding the GIL. The page window belongs to the
    WebView2 thread, which runs Python callbacks (every evaluate_js answer is
    one), so the first time it needed the GIL while the watcher sat in
    SetWindowLong holding it, both stopped for good: Apollo came up, said "API
    reachable", and never spoke. Every such call on the page window goes
    through here instead.
    """
    lib = ctypes.WinDLL("user32", use_last_error=True)
    lib.SetWindowLongPtrW.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t)
    lib.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    lib.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
    lib.ShowWindow.restype = wintypes.BOOL
    lib.SetWindowPos.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, ctypes.c_uint)
    lib.SetWindowPos.restype = wintypes.BOOL
    return lib


_user32 = user32_releasing_gil()

# Extended window styles. pywebview's `focus=False` already sets NOACTIVATE;
# the rest are ours. See Overlay for why TRANSPARENT and LAYERED come as a pair.
GWL_EXSTYLE = -20
LWA_ALPHA = 0x00000002
WS_EX_TRANSPARENT = 0x00000020   # clicks fall through to whatever is beneath
WS_EX_TOOLWINDOW = 0x00000080    # keep out of the taskbar and Alt+Tab
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_APPWINDOW = 0x00040000


def single_instance():
    """Return a held mutex, or None if Apollo is already running.

    Worth guarding: once Apollo is in the Startup folder it is easy to also
    double-click start.bat, and two copies means two global hooks on the same
    hotkey, two microphone captures and two voices answering at once.
    """
    handle = win32event.CreateMutex(None, False, MUTEX_NAME)
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        return None
    return handle


class Overlay:
    """The window's Win32 side: how big it is, and where.

    Two shapes now. ORB is the resting overlay - the native layer's mesh and
    whatever it has grown to show underneath it - and it is the only one
    Apollo wears while you are working; this page window is not even on
    screen for it. FULL is the whole work area, for the AFK display and for
    CTRL+`.

    There used to be a third, PANEL: a reply squared the orb off into a
    rectangle and the page drew the answer inside it. It is gone because the
    page window cannot be anything but an opaque rectangle here (see the
    module docstring), and an answer arriving as a box is exactly what the
    overlay is meant not to do. Replies are drawn by `orb.py` instead, as
    text on the desktop under the mesh, so there is no panel to put up.
    """

    ORB, FULL = "orb", "full"

    PASSIVE = (WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
               | WS_EX_LAYERED | WS_EX_TRANSPARENT)

    def __init__(self):
        self.hwnd = None
        self.mode = None

    # -- attaching ----------------------------------------------------------

    def attach(self, tries=20, gap=0.25):
        """Find our window and turn it into a desktop overlay.

        Retried, and with the re-show in a `finally`, because the `shown` event
        can fire before the native window is findable and the style change has
        to hide the window to take effect. Lose between those two points and
        Apollo is left running with its window hidden forever: no orb, no
        error, no way in. Far harder to notice than failing to start at all.
        """
        for _ in range(tries):
            self.hwnd = win32gui.FindWindow(None, "Apollo")
            if self.hwnd:
                break
            time.sleep(gap)
        else:
            return False

        # TOOLWINDOW only takes properly while the window is hidden, and the
        # re-show must not activate - that would steal focus from whatever you
        # were typing in at the time.
        try:
            _user32.ShowWindow(self.hwnd, win32con.SW_HIDE)
            style = win32gui.GetWindowLong(self.hwnd, GWL_EXSTYLE)
            style |= self.PASSIVE
            style &= ~WS_EX_APPWINDOW
            _user32.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, style)
        finally:
            _user32.ShowWindow(self.hwnd, win32con.SW_SHOWNOACTIVATE)

        # Deliberately does NOT pick a mode. The resting mode hides this
        # window, and a hidden WebView2 never finishes navigating - so hiding
        # it here would mean the `loaded` event never fires and nothing that
        # depends on it (the orb, the backend) ever starts. Shape is chosen by
        # `Apollo.apply_mode` once the page is up.
        return True

    def verify(self):
        """Confirm the window is the shape its mode wants.

        At rest "correct" means hidden, because the native orb has the screen
        instead - so an invisible window is the pass condition, not a failure.
        """
        if not self.hwnd:
            return False
        if self.mode is None:
            return True          # nothing has claimed a shape yet
        visible = win32gui.IsWindowVisible(self.hwnd)
        if self.mode == self.ORB:
            return not visible
        if not visible:
            return False
        left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
        want = self.rect_for(self.mode or self.FULL)
        return (abs((right - left) - (want[2] - want[0])) < 8
                and abs((bottom - top) - (want[3] - want[1])) < 8)

    # -- geometry -----------------------------------------------------------

    @staticmethod
    def work_area():
        monitor = win32api.MonitorFromPoint((0, 0), win32con.MONITOR_DEFAULTTOPRIMARY)
        return win32api.GetMonitorInfo(monitor)["Work"]

    def box_for(self, mode):
        """`rect_for` as (x, y, w, h), which is what the native layer wants."""
        left, top, right, bottom = self.rect_for(mode)
        return (left, top, right - left, bottom - top)

    def rect_for(self, mode):
        """Where this mode's window goes, in real device pixels.

        Straight off the monitor rect rather than through pywebview's sizing,
        which would raise the question of which pixels the numbers were in. The
        work area rather than the full bounds, so a topmost window never sits
        on top of the taskbar.

        For the orb this is the *resting* box only. Once there are words under
        the mesh the native layer grows its own window downward from this
        one's top edge, and that top edge is the thing it never moves.
        """
        left, top, right, bottom = self.work_area()
        if mode == self.FULL:
            return left, top, right, bottom
        cx = (left + right) // 2
        w = h = ORB_PX
        y0 = top - self.orb_overhang()
        x0 = cx - w // 2
        return (x0, y0, x0 + w, y0 + h)

    @staticmethod
    def orb_overhang():
        """How far above the top edge the resting orb's window starts.

        Worked back from the constellation so `ORB_REVEAL` means what it says.
        The pattern is a ring of radius `r` about the box's centre; leaving
        `ORB_REVEAL` of its height showing puts that centre at `r * (2f - 1)`
        relative to the edge, and the window's own top is half a box above
        that. At the default quarter the centre lands half a radius above the
        edge, so the bottom arc - two or three points and the chords between
        them - is what hangs into view.
        """
        r = ORB_PX * orb_module.Orb.CONSTELLATION_R
        centre = r * (2.0 * ORB_REVEAL - 1.0)
        return int(round(ORB_PX / 2.0 - centre))

    def show_page(self, mode):
        """Put the page window on screen at the size `mode` wants.

        The page only ever shows as the full display. Everything else - the
        resting mesh, your words as you say them, and the answer - is drawn by
        `orb.py` on a layered window with real per-pixel alpha, because a
        WebView2 window cannot be made round or see-through here.
        """
        if not self.hwnd:
            return
        if mode == self.ORB:
            self.hide_page()
            return
        left, top, right, bottom = self.rect_for(mode)
        # Clickable while it is the display: a story in the feed is picked by
        # clicking it. It still never takes focus - NOACTIVATE stays - so
        # whatever you were typing in keeps the keyboard.
        self.set_clickable(True)
        _user32.SetWindowPos(
            self.hwnd, win32con.HWND_TOPMOST,
            left, top, right - left, bottom - top,
            win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW,
        )
        _user32.ShowWindow(self.hwnd, win32con.SW_SHOWNOACTIVATE)
        self.set_alpha(ALPHA.get(mode, 255))

    def hide_page(self):
        if self.hwnd:
            _user32.ShowWindow(self.hwnd, win32con.SW_HIDE)
            self.set_clickable(False)

    def set_clickable(self, on):
        """Whether the page takes the mouse, or lets it fall through."""
        if not self.hwnd:
            return
        style = win32gui.GetWindowLong(self.hwnd, GWL_EXSTYLE)
        style = style & ~WS_EX_TRANSPARENT if on else style | WS_EX_TRANSPARENT
        _user32.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, style)

    def set_alpha(self, alpha):
        """Make the whole window translucent.

        LWA_ALPHA is the only transparency that survives WebView2's
        DirectComposition path - a colour key set here is simply ignored,
        because the page's pixels never pass through the layered surface the
        key would be applied to. Uniform, so it dims Apollo's own art as well
        as its ground; the values in ALPHA are picked with that in mind.
        """
        if not self.hwnd:
            return
        ctypes.windll.user32.SetLayeredWindowAttributes(
            self.hwnd, 0, max(0, min(255, int(alpha))), LWA_ALPHA)

    def raise_above(self):
        """Reassert topmost, without taking focus.

        Another topmost window (a full-screen player, an installer) can end up
        over Apollo. Re-pinning when a turn starts means the answer is visible
        when it matters, and never fights for z-order the rest of the time.
        """
        if not self.hwnd:
            return
        _user32.SetWindowPos(
            self.hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE,
        )


def pc_locked():
    """True while Windows is locked (Win+L): the input desktop is the secure
    one then, and an ordinary process is refused it."""
    try:
        handle = ctypes.windll.user32.OpenInputDesktop(0, False, 0x0100)
    except (AttributeError, OSError):
        return False
    if not handle:
        return True
    ctypes.windll.user32.CloseDesktop(handle)
    return False


def screen_busy():
    """True while a full-screen program has the screen.

    Asked only on the way to falling asleep: it is a call into the shell, and
    the watcher ticks twenty-five times a second.
    """
    state = ctypes.c_int(0)
    try:
        if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state)) != 0:
            return False
    except (AttributeError, OSError):
        return False
    return state.value in (QUNS_BUSY, QUNS_RUNNING_D3D_FULL_SCREEN,
                           QUNS_PRESENTATION_MODE)


def idle_seconds():
    """How long since the last keyboard or mouse input anywhere in Windows.

    GetLastInputInfo is system-wide and does not care which application has
    focus, which is exactly the question "has the user walked away" asks.
    """
    class LastInput(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    info = LastInput()
    info.cbSize = ctypes.sizeof(LastInput)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    return (ctypes.windll.kernel32.GetTickCount() - info.dwTime) / 1000.0


def chord_down(chord):
    """True while every key in `chord` is held. See the note by PEEK_CHORD."""
    for vk in chord:
        if not ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000:
            return False
    return True


class Watcher(threading.Thread):
    """Owns the global chords, and decides when Apollo has been left alone.

    A thread of its own rather than a check inside `run_loop`, because that
    loop is busy for the whole of a turn - recording, transcribing, waiting on
    the API, speaking - and a chord that only answered between turns would feel
    broken during the twenty seconds it matters most.

    Chords are polled rather than registered with `keyboard.add_hotkey`: the
    callback form does not fire at all on this machine. They are polled
    through `chord_down` rather than `keyboard.is_pressed`, which does not see
    every key - see the note by PEEK_CHORD.
    """

    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app

    def run(self):
        held = {"peek": False, "quit": False}
        last_error = None
        while not self.app.stopping.is_set():
            # One bad tick must not end the thread. It used to: an exception
            # anywhere in here escaped `run`, the daemon thread died, and with
            # it went Ctrl+`, the quit chord, presence, the day's recap and the
            # prayer reminders - silently, because pythonw has no console.
            try:
                self._tick(held)
                last_error = None
            except Exception as exc:  # noqa: BLE001 - the loop outlives any check
                # Logged once per distinct failure, not once per tick: at
                # twenty-five ticks a second a stuck check would otherwise
                # write the same traceback into the log for as long as it lasts.
                signature = (type(exc).__name__, str(exc))
                if signature != last_error:
                    log.exception("watcher tick failed")
                    last_error = signature
            time.sleep(0.04)

    def _tick(self, held):
        # Quit is checked first and wins: it contains the peek chord's CTRL,
        # and on the way to CTRL+ALT+SHIFT+Q you should not get a full display
        # you did not ask for.
        for name, chord, fn in (("quit", QUIT_CHORD, self.app.quit),
                                ("peek", PEEK_CHORD, self.app.toggle_peek)):
            down = chord_down(chord)
            if down and not held[name]:    # act on the press, not the hold
                held[name] = True
                fn()
                break
            if not down:
                held[name] = False

        self.app.check_intro()
        self.app.check_osiris()
        self.app.check_displays()
        self.app.check_presence(idle_seconds())
        self.app.check_overlay_alive()


class Tray:
    """A notification-area icon, because the overlay has no chrome to quit from.

    Runs its own WinForms message loop on its own thread. pywebview owns the
    main thread's loop, and a NotifyIcon only pumps on the thread that made it.
    """

    def __init__(self, on_quit, on_toggle_clips=None):
        self.on_quit = on_quit
        self.on_toggle_clips = on_toggle_clips
        self.icon = None
        self.clips_item = None
        self.ready = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()
        self.ready.wait(timeout=5)

    def _run(self):
        try:
            import clr
            clr.AddReference("System.Windows.Forms")
            clr.AddReference("System.Drawing")
            import System.Drawing as D
            import System.Windows.Forms as WF

            menu = WF.ContextMenuStrip()
            quit_item = WF.ToolStripMenuItem("Quit Apollo")
            quit_item.Click += lambda s, e: self._quit()
            menu.Items.Add(WF.ToolStripLabel("Apollo - hold Ctrl+Alt to talk"))
            menu.Items.Add(WF.ToolStripSeparator())
            if self.on_toggle_clips is not None:
                # The replay buffer records the screen into memory whenever
                # Apollo runs, so it is worth being able to see and stop it.
                self.clips_item = WF.ToolStripMenuItem("Pause replay buffer")
                self.clips_item.Click += lambda s, e: self._toggle_clips()
                menu.Items.Add(self.clips_item)
            menu.Items.Add(quit_item)

            self.icon = WF.NotifyIcon()
            self.icon.Icon = self._make_icon(D)
            self.icon.Text = "Apollo"
            self.icon.ContextMenuStrip = menu
            self.icon.Visible = True

            self.context = WF.ApplicationContext()
            self.ready.set()
            WF.Application.Run(self.context)
        except Exception:
            # A missing tray icon is survivable - the quit hotkey still works.
            self.ready.set()

    def _make_icon(self, D):
        """Draw the core as a 32px amber ring rather than ship an .ico file."""
        bmp = D.Bitmap(32, 32)
        g = D.Graphics.FromImage(bmp)
        g.SmoothingMode = D.Drawing2D.SmoothingMode.AntiAlias
        g.Clear(D.Color.Transparent)
        pen = D.Pen(D.Color.FromArgb(255, 255, 176, 0), 3.0)
        g.DrawEllipse(pen, 4, 4, 23, 23)
        g.FillEllipse(D.SolidBrush(D.Color.FromArgb(220, 20, 10, 0)), 10, 10, 12, 12)
        g.Dispose()
        return D.Icon.FromHandle(bmp.GetHicon())

    def _toggle_clips(self):
        try:
            recording = self.on_toggle_clips()
            self.clips_item.Text = "Pause replay buffer" if recording else "Resume replay buffer"
        except Exception:
            pass          # the tray must never take Apollo down

    def _quit(self):
        self.close()
        self.on_quit()

    def close(self):
        try:
            if self.icon:
                self.icon.Visible = False
                self.icon.Dispose()
            self.context.ExitThread()
        except Exception:
            pass


class WebReporter:
    """The reporter `assistant.run_loop` writes to, backed by the page.

    Every call marshals into the web view as a one-line JS expression. The
    worker thread owns this object; `evaluate_js` is safe to call from it once
    the document has loaded, which is why the worker only starts on `loaded`.
    """

    # Phases where Apollo is busy talking with you, whether or not there is
    # anything to show for it yet.
    ENGAGED = {assistant.LISTENING, assistant.THINKING, assistant.SPEAKING}

    def __init__(self, window, overlay, on_status, on_turn, on_level,
                 on_partial, on_visual=None, on_activity=None, app=None):
        self.window = window
        self.overlay = overlay
        self._app = app     # for `refresh`, which reaches the data service
        self.on_status = on_status
        self.on_turn = on_turn
        self.on_level = on_level
        self.on_partial = on_partial
        self.on_visual = on_visual
        self.on_activity = on_activity
        self.alive = True
        self.quiet = True   # until the backend has finished waking up
        self._last = None   # the last (state, quiet) forwarded - see `status`

    def _call(self, fn, *args):
        if not self.alive:
            return
        payload = ", ".join(json.dumps(a) for a in args)
        # Guarded on the page's side: the front end and the backend ship
        # separately, and a call into a handler an older page does not have
        # would raise here - which `except` below reads as "the window went
        # away" and silences every later update. A missing handler is a
        # no-op; a missing window is still an error.
        try:
            self.window.evaluate_js(
                f"window.apollo.{fn} && window.apollo.{fn}({payload})")
        except Exception:
            # The window went away mid-turn. Nothing left to report to.
            self.alive = False

    def status(self, state):
        # The run loop may report the same phase many times a second - in
        # always-listening it used to report LISTENING after every 250ms
        # poll - and every forward costs a page call, a chime and a wipe of
        # the overlay. A phase is an event only when it changes. Quiet is
        # part of the key: the page saw "Waking" while quiet, so the first
        # real IDLE after it is news even if IDLE was the last state.
        key = (state, self.quiet)
        if key == self._last:
            return
        self._last = key

        # Being busy is not a size any more: every phase of a turn happens in
        # the resting overlay, which grows itself to fit whatever it is
        # showing (see Apollo.on_status and orb.Orb).
        self.on_status(state)

        if self.quiet:
            # Startup runs at sign-in, and it ends by speaking a greeting. A
            # full-screen takeover every time you log in is the opposite of an
            # ambient assistant, so while waking up the overlay stays a corner
            # orb whatever the backend reports. Notes still come through.
            self._call("status", STARTING)
            return

        if state in self.ENGAGED:
            self.overlay.raise_above()
        self._call("status", state)

    def turn(self, speaker, text, visual=None):
        # The design labels the assistant's side of the conversation "Apollo",
        # but the reporter protocol keys off "You" vs. anything else.
        self.on_turn(speaker, text, visual)
        self._call("turn", speaker, text)

    def partial(self, text):
        """Words heard so far, mid-sentence.

        Native layer only, like `level` and for the same reason: this fires
        while you are still talking, and the page is not on screen to receive
        it anyway unless the full display happens to be open.
        """
        self.on_partial(text)

    def visual(self, visual):
        """A chart or cards from a tool. Native overlay only, like `partial`."""
        if self.on_visual is not None and visual:
            self.on_visual(visual)

    def activity(self, text):
        """What Apollo is doing right now, in a few words ("fetching NVDA").

        Native overlay only. This can be called on Gemini's event-loop thread
        (a search is noticed there), and a page call blocks until the page
        answers - which would stall the loop that is receiving the voice.
        """
        if self.on_activity is not None and text:
            self.on_activity(text)

    def stream_reply(self, text):
        """Apollo's answer so far, while it is being spoken.

        Native overlay only, for the same reason as `activity`: fragments
        arrive on Gemini's event-loop thread. The page gets the finished
        answer through `turn` once the turn is over.
        """
        self.on_turn("Apollo", text, None)

    def panels(self, state):
        """Which panels the display should be showing."""
        self._call("panels", state)

    def refresh(self, *keys):
        """Have the data service read these again (everything, if none) and
        push them. True if there is a service to ask.

        It asks and returns. It used to read the lot on the tool's own
        thread - every stock with its valuation, four news topics, the
        posts, the weather - and the tool's answer waited for all of it.
        """
        service = getattr(self._app, "data", None) if self._app is not None else None
        if service is None:
            return False
        try:
            service.poke(*keys)
        except Exception:  # noqa: BLE001 - a refresh is not worth a failed turn
            return False
        return True

    def data(self, snapshot):
        """The world, for the full display. Only worth sending while it is up."""
        self._call("data", snapshot)

    def live(self, batch):
        """Trades since the last batch, {symbol: (price, seconds)}: the cards
        and an opened stock move with them."""
        self._call("live", {symbol: {"price": price, "time": seconds}
                            for symbol, (price, seconds) in batch.items()})

    def note(self, text):
        self._call("note", text)

    def fatal(self, text):
        self._call("fatal", text)

    def level(self, value):
        """Live mic loudness, 0-1, straight from the recording thread.

        Deliberately never reaches the page: this arrives every audio block,
        and an `evaluate_js` per block would queue faster than WebView2 could
        drain it. It goes to the native orb, which is a float assignment.
        """
        self.on_level(value)

    def mode(self, name):
        self._call("mode", name)

    def sleep(self, on):
        """Asleep: the display is the idle screen. Awake: it is itself."""
        self._call("sleep", bool(on))

    def states(self, states):
        """Which of Apollo's own modes are on - away, hands-free - for the
        display's bar to light."""
        self._call("states", dict(states))

    def agent(self, event):
        """A step of an agent's run - LYLA's, for now - for her pipeline card
        on the display: received, asking, done or error."""
        self._call("agent", dict(event))

    def intro(self):
        """Play the word, as Apollo comes up."""
        self._call("intro")

    def boot(self, step):
        """A line of the boot screen: one check, or one part of Apollo up."""
        self._call("boot", dict(step))

    def boot_done(self, summary):
        """The checks and the start are done: {issues, fails}."""
        self._call("bootDone", dict(summary))

    def issues(self, items):
        """What is wrong, for the System panel (issues.py)."""
        self._call("issues", list(items))

    def checked(self, summary):
        """The checks, run again from the System panel, are done."""
        self._call("checked", dict(summary))

    def scan(self, event):
        """The scanner: {state: scanning|step|done|error, name, text, report}."""
        self._call("scan", dict(event))

    def story(self, number):
        """Open story `number` on the display's feed (0 closes it).

        Answers with what the page opened - its title, source and summary -
        so Apollo can talk about the story he just put up, or None if there
        is no such story or no page to ask.
        """
        if not self.alive:
            return None
        number = int(number)
        app = self._app
        # A story asked for is a story to be seen: if the display is not up,
        # it comes up with the story open on it.
        if (number and app is not None
                and getattr(app.overlay, "mode", None) != Overlay.FULL):
            app.toggle_peek()
        try:
            return self.window.evaluate_js(
                f"window.apollo.story && window.apollo.story({number})")
        except Exception:
            return None

    def tab(self, name):
        """Show one tab of the side panel; the display comes up if it is not."""
        app = self._app
        if app is not None and getattr(app.overlay, "mode", None) != Overlay.FULL:
            app.toggle_peek()
        self._call("tab", str(name))
        return True

    def osiris(self, on):
        """OSIRIS mode on the page, or off: Apollo in its colours, with the
        frame the map's window is laid into (or without it)."""
        self._call("osiris", bool(on))

    def ask_osiris(self, on):
        """OSIRIS asked for by voice. The watcher brings the display up if it
        has to and tells the page (Apollo.check_osiris)."""
        app = self._app
        if app is None:
            return False
        log.info("OSIRIS %s, you said", "open" if on else "closed")
        app.request_osiris(bool(on))
        return True

    def display(self, request):
        """Ultra mode's displays: on or off, one expanded, one shown or
        hidden - or the layout kept from last time, as the display opens."""
        self._call("display", request)

    def ask_display(self, request):
        """Something asked of ultra mode by voice. Like OSIRIS, the watcher
        does it - bringing the display up first if it has to be seen - so
        a mode never changes on the voice's own thread (check_displays)."""
        app = self._app
        if app is None:
            return False
        log.info("displays: %s, you said", request)
        app.request_display(request)
        return True

    def going_out(self):
        """You said you are going out."""
        app = self._app
        if app is None:
            return False
        log.info("going out, you said")
        app.request_away()
        return True

    def idle(self):
        """You asked for idle mode by voice."""
        app = self._app
        if app is None:
            return False
        log.info("idle mode asked for")
        app.request_idle()
        return True

    def stock(self, symbol):
        """Open `symbol` out of its card on the display ("" closes it).

        Answers with what the card shows - price, move, target - or None if
        the stock is not on the display. Like a story, a stock asked for
        brings the display up.
        """
        if not self.alive:
            return None
        symbol = str(symbol or "")
        app = self._app
        if (symbol and app is not None
                and getattr(app.overlay, "mode", None) != Overlay.FULL):
            app.toggle_peek()
        try:
            # Quoted, not spliced: the symbol came back from a market search.
            return self.window.evaluate_js(
                f"window.apollo.stock && window.apollo.stock({json.dumps(symbol)})")
        except Exception:
            return None


class Api:
    """What the page can call back into. Just the one thing it needs.

    Keep every attribute here private except the methods themselves. pywebview
    builds the JS bridge by walking `dir()` over this object and recursing into
    any attribute that is not callable, so holding the app would hand it the
    whole graph - app, window, and the entire WinForms/WebView2 tree behind
    `window.native`. It probes that tree off the UI thread, and every COM
    property that objects to being read from there gets logged to stderr -
    hundreds of lines of "maximum recursion depth exceeded" and
    E_NOINTERFACE before the window even opens. A leading underscore is
    what keeps it out.
    """

    def __init__(self, quit, open_link=None, desk=None, poke=None, osiris=None, app=None):
        self._quit = quit
        self._open_link = open_link
        self._desk = desk or stockdesk.StockDesk()
        self._poke = poke or (lambda *keys: None)
        self._osiris = osiris
        self._app = app

    def quit(self):
        self._quit()

    def open_link(self, url):
        """A story's "Read" button: the article, in your browser."""
        if self._open_link is not None:
            return self._open_link(url)
        return False

    # The stock panel: a chart over a span, and the watchlist changed by hand.

    def chart(self, symbol, period):
        return self._desk.chart(symbol, period)

    def watch(self, symbol):
        return self._desk.watch(symbol)

    def unwatch(self, symbol):
        return self._desk.unwatch(symbol)

    def suggestions(self):
        return stockdesk.suggestions()

    def rate_find(self, find_id, useful):
        """A Private Eye find marked useful or not, from the display."""
        if private_eye.rate(str(find_id or ""), bool(useful)) is None:
            return False
        self._poke("finds")
        return True

    def open_folder(self, path):
        """A project folder from the Projects tab, in VS Code."""
        return projects.open_folder(str(path or ""))

    def drop_idea(self, idea_id):
        """An idea taken off the Ideas tab."""
        if not ideas.remove(str(idea_id or "")):
            return False
        self._poke("ideas")
        return True

    def noted(self, what, title, source=""):
        """A story or a stock you opened on the display, for the record."""
        journal.opened(str(what or ""), str(title or ""), str(source or ""))
        return True

    def osiris_open(self, rect):
        """The display has gone into OSIRIS mode and laid out the frame for the
        map, at `rect` ({x, y, w, h}, device pixels): the map's window goes
        there. Called again when the frame moves."""
        if self._osiris is None:
            return False
        return self._osiris.open(rect)

    def osiris_close(self):
        """The display has left OSIRIS mode: the map's window goes."""
        if self._osiris is None:
            return False
        self._osiris.close()
        return True

    # Apollo's own modes, from the display's bar: the idle screen now, away
    # mode, and hands-free listening. Each is asked of the app, which does it
    # on its watcher the way it does when you say it.

    def idle(self):
        if self._app is None:
            return False
        self._app.request_idle(grace=CLICK_GRACE)
        return True

    def away(self):
        if self._app is None:
            return False
        self._app.request_away(grace=CLICK_GRACE)
        return True

    def listen(self, on):
        if self._app is None:
            return False
        self._app.set_listening(bool(on))
        return True

    def states(self):
        """Which of them are on, for the bar to light."""
        return self._app.mode_states() if self._app is not None else {}

    def trading(self):
        """Trading mode is up: its board is read now, and kept fresh for the
        next half hour (the page asks again while it stays up)."""
        if self._app is None:
            return False
        self._app.want_trading()
        return True

    def pick_file(self):
        """Choose file, on the scanner: File Explorer opens over the display
        and what you pick is scanned (Apollo.choose_and_scan)."""
        return self._app.choose_and_scan() if self._app is not None else False

    def lyla_reports(self):
        """LYLA's latest reports and what she is on now, for agents mode to
        list when the page comes up (it hears of each new one as it lands)."""
        working = lyla.DESK.current
        return {"reports": lyla.DESK.reports[:8],
                "working": {"task": working["task"], "symbol": working["symbol"]} if working else None}

    def crew_status(self):
        """Every agent: its role, what it is on, what waits, its reports."""
        return crew.status()

    def set_panel(self, name, shown):
        """A panel shown or hidden from the display itself - LYLA's room, by
        the button along the bottom - and kept that way, as if it had been
        asked for out loud."""
        return (panels.show if shown else panels.hide)(str(name or ""))

    def save_layout(self, layout):
        """Ultra mode's layout as the page has it now, after a drag, a resize,
        a display hidden or expanded: kept, so the screen you set up is the
        one you get tomorrow. Cleaned first - it came over the bridge."""
        displays.save(layout)
        return True

    def save_hud(self, layout):
        """The normal display as you arranged it - a panel moved, resized,
        scaled or hidden - kept for tomorrow (hud.py). Cleaned first - it
        came over the bridge."""
        hud.save(layout)
        return True

    def osiris_park(self):
        """Ultra mode wants the map off the screen for now - minimized, under
        a display being dragged or set up, or while Apollo answers - but kept
        loaded for when it is back."""
        if self._osiris is None:
            return False
        self._osiris.park()
        return True

    def dismiss_issue(self, key):
        """An issue on the System panel dismissed: fixed, or not worth it."""
        return issues.resolve(str(key or ""))

    def run_checks(self):
        """The checks run again from the System panel; the page hears each
        one and then `checked`."""
        if self._app is None:
            return False
        threading.Thread(target=self._app.run_checks, daemon=True, name="checks").start()
        return True

    def osiris_layers(self, layers):
        """The map's layers, switched in its settings. Only its own layers'
        names are taken; the map's address is never the page's to give."""
        if self._osiris is None:
            return []
        return self._osiris.set_layers(layers)


class Apollo:
    def __init__(self):
        self.stopping = threading.Event()
        self.overlay = Overlay()
        self.tray = None
        # The two reasons Apollo becomes the full display. A turn is no longer
        # one of them: answering happens in the overlay itself now.
        self.watcher = None
        self.orb = None
        self.voice = None          # the Gemini Live session, once connected
        self.clips = None          # the replay buffer, once recording
        self.data = None           # the world, refreshed on a timer
        self.ticker = None         # prices as they trade, with a Finnhub key
        self.learner = None        # learns your interests from the record
        self.eye = None            # Private Eye, the scout
        self.away = away_mode.Away()        # out of the house? (away.py)
        self.keeper = away_mode.Keeper()    # ...then the PC stays up with Claude open
        self.away_requested = False
        self.intro_wanted = False  # the word, once; see `check_intro`
        self.intro_until = 0.0     # ...playing until then (monotonic)
        self._scan_lock = threading.Lock()   # one file scanned at a time
        self.boot_done_at = None   # when the checks and the start were both done
        self._boot_parts = set()
        self._boot_results = []
        self._boot_lock = threading.Lock()
        self.schedule = briefing.Schedule()   # has today's recap happened?
        self.briefing_thread = None
        self.prayer_thread = None
        self.listen_toggle = None  # ...and the CTRL+1 watcher over it
        self.turn_busy = False     # listening, thinking, or speaking
        self.last_engaged = 0.0    # when a turn last ran; the recap waits it out
        self.prayers = prayer.Watch()
        self.presence = presence.Presence(AFK_SECONDS)
        self.wake = presence.VoiceWake()    # asleep, a voice wakes it
        self.asleep_shown = False           # what the page was last told
        self.last_status = None    # the phase the overlay last acted on
        self.view = turnview.TurnView()   # what this turn adds up to on screen
        # OSIRIS, laid into the display in a window of its own (osiris.py).
        self.osiris = osiris_module.Osiris(origin=self._display_origin,
                                           owner=lambda: self.overlay.hwnd,
                                           on_gone=self.osiris_gone,
                                           layers=displays.state()["layers"])
        self.osiris_requested = None
        self.display_requests = collections.deque()   # ultra mode, asked by voice
        self.window = webview.create_window(
            "Apollo",
            INDEX,
            width=1280,
            height=800,
            resizable=False,
            frameless=True,
            easy_drag=False,      # the overlay is not something you drag
            shadow=False,
            focus=False,          # sets WS_EX_NOACTIVATE: never steal focus
            on_top=True,
            transparent=True,
            background_color="#000000",
            js_api=Api(self.quit, open_link=self.open_link,
                       desk=stockdesk.StockDesk(poke=self.poke_data),
                       poke=self.poke_data, osiris=self.osiris, app=self),
        )
        self.window.events.shown += self.on_shown
        self.window.events.loaded += self.on_loaded
        self.window.events.closed += self.on_closed

    # -- lifecycle ----------------------------------------------------------

    def toggle_clips(self):
        """Tray: pause or resume the replay buffer. True if it is recording.
        Paused here, it stays paused - `keep_clips` does not bring it back."""
        if self.clips is None:
            return False
        self.clips_wanted = not self.clips.running
        if self.clips_wanted:
            self._clips_paused = False
            self.clips.start()
        else:
            self.clips.stop()
        return self.clips_wanted

    def on_shown(self):
        """Only the tray. The window is deliberately left completely alone.

        pywebview shows a transparent window, hides it again, and re-shows it
        on the Navigating event. Touching the window here lands in the middle
        of that dance: `attach` hides the window to apply WS_EX_TOOLWINDOW, and
        if pywebview's Hide follows ours the window stays hidden, never
        navigates, and `loaded` never fires - so the orb and the backend never
        start and Apollo is a process with nothing on screen. Everything to do
        with this window therefore waits for `on_loaded`.
        """
        self.tray = Tray(on_quit=self.quit, on_toggle_clips=self.toggle_clips)

    def start_orb(self):
        """Bring up the native orb, positioned where `Overlay.rect_for` puts it.

        Read through `self.overlay` rather than recomputing the position here,
        so there is exactly one place that decides where the orb sits.
        """
        if self.orb is not None:
            return
        x, y, w, _h = self.overlay.box_for(Overlay.ORB)
        self.orb = orb_module.Orb(size=w, position=(x, y),
                                  overhang=self.overlay.orb_overhang())
        self.orb.start_on(self.window.native)

    def start_watcher(self):
        """Start the chord/presence watcher once, from whichever event got here
        first. `shown` is the natural place, but it is exactly the event whose
        timing cannot be relied on - and the watcher carries the watchdog that
        repairs a window left hidden, so it must not depend on that timing."""
        if getattr(self, "watcher", None) is None:
            self.watcher = Watcher(self)
            self.watcher.start()

    def blacken_form(self):
        """Paint the WinForms host black instead of the default Control grey.

        pywebview skips setting `BackColor` entirely when `transparent=True`,
        so the form keeps the system Control colour - a near-white #F0F0F0 -
        and that is what shows through wherever the page draws nothing. It is
        the light square that appears around the orb. Black is not
        transparency, but it is the difference between a pale tile on your
        wallpaper and something you have to look for.
        """
        try:
            import clr
            clr.AddReference("System.Drawing")
            import System.Drawing as D
            from System import Action

            form = self.window.native
            form.Invoke(Action(lambda: setattr(form, "BackColor", D.Color.Black)))
        except Exception:
            pass   # cosmetic only; never worth failing startup over

    def on_loaded(self):
        """The page is up, so it can be talked to. Start the backend.

        This, not `shown`, is where the geometry is made to stick. For a
        transparent window pywebview shows the form, hides it again, and
        re-shows it on the Navigating event - and that re-show restores the
        form's own stale WinForms Bounds, undoing anything `shown` did. By the
        time the document has loaded that dance is over, so an attach here
        holds. The watcher re-checks anyway, because the ordering is pywebview's
        to change, not ours.
        """
        self.blacken_form()
        self.start_orb()
        if not self.overlay.attach(tries=8, gap=0.15):
            # Without the Win32 side this is a plain window sitting on top of
            # everything - worse than not starting.
            self.ui_fatal_startup("Could not attach the overlay window.")
            return
        self.apply_mode()
        self.start_watcher()
        self.ui = WebReporter(self.window, self.overlay,
                              on_status=self.on_status, on_turn=self.on_turn,
                              on_level=self.on_level,
                              on_partial=self.on_partial,
                              on_visual=self.on_visual,
                              on_activity=self.on_activity,
                              app=self)
        issues.set_listener(self.tell_issues)
        self.listen_for_drops()
        self.want_intro()
        threading.Thread(target=self.worker, daemon=True).start()

    def on_closed(self):
        self.stopping.set()
        log.info("the window closed: quitting")
        self.close_live()
        if getattr(self, "ui", None):
            self.ui.alive = False

    def ui_fatal_startup(self, message):
        die(message)

    def quit(self):
        if self.stopping.is_set():
            return
        self.stopping.set()
        log.info("quitting")
        self.close_live()
        if self.clips is not None:
            self.clips.stop()
        if self.data is not None:
            self.data.stop()
        if self.ticker is not None:
            self.ticker.stop()
        if self.learner is not None:
            self.learner.stop()
        if self.eye is not None:
            self.eye.stop()
        if self.orb:
            self.orb.close()
        if self.tray:
            self.tray.close()
        try:
            self.window.destroy()
        except Exception:
            pass

    # -- how big Apollo is, and why ------------------------------------------

    def desired_mode(self):
        """The one place that decides which window Apollo is.

        Only two answers left, and a turn is not one of them. Listening,
        thinking and answering all happen in the resting overlay now: the mesh
        stays exactly where it is and the native layer grows downward under it
        to hold your words and then the reply, so there is nothing for this
        method to decide when a turn starts. It decides between the ambient
        overlay and the full display, and that is all.
        """
        # Set while the intro plays; only `check_intro` clears it, on the
        # watcher's thread, so this needs no clock of its own.
        if getattr(self, "intro_until", 0.0):
            return Overlay.FULL
        return Overlay.FULL if self.presence.full else Overlay.ORB

    def _boot_ready(self, now):
        """The loading screen has shown its last line long enough."""
        done = getattr(self, "boot_done_at", None)
        if done is None:
            return False
        started = getattr(self, "intro_started", now)
        return now >= max(started + INTRO_SECONDS, done + INTRO_TAIL)

    # -- the boot: the checks, the start, and the issues they find ---------

    def boot_step(self, step, keep=True):
        """A line of the boot screen - and, kept, an issue for the System
        panel when it is wrong, or one resolved when it is right again."""
        step = {"id": str(step.get("id", "")), "label": str(step.get("label", "")),
                "status": step.get("status", "ok"), "detail": str(step.get("detail", "")),
                "total": BOOT_TOTAL}
        if keep:
            key = "check:" + step["id"]
            if step["status"] in ("warn", "fail"):
                issues.record(key, step["label"], step["detail"], step["status"])
            else:
                issues.resolve(key)
        with self._boot_lock:
            self._boot_results.append(step)
        ui = getattr(self, "ui", None)
        tell = getattr(ui, "boot", None) if ui is not None and ui.alive else None
        if tell is not None:
            tell(step)

    @staticmethod
    def _summary(steps):
        return {"issues": sum(1 for s in steps if s["status"] != "ok"),
                "fails": sum(1 for s in steps if s["status"] == "fail")}

    def run_checks(self, boot=False):
        """Every check (diagnostics.py), each a line as it lands. At the boot
        it is half of what the loading screen waits for; from the System
        panel, the page is told when they are all in."""
        results = diagnostics.run(report=self.boot_step)
        if boot:
            self.boot_part_done("checks")
        else:
            ui = getattr(self, "ui", None)
            if ui is not None and ui.alive:
                ui.checked(self._summary(results))
        return results

    def boot_part_done(self, part):
        """"checks" or "startup" finished; both, and the boot is done."""
        with self._boot_lock:
            self._boot_parts.add(part)
            if not {"checks", "startup"} <= self._boot_parts or self.boot_done_at is not None:
                return
            self.boot_done_at = time.monotonic()
            summary = self._summary(self._boot_results)
        log.info("boot done: %d issue(s), %d failing", summary["issues"], summary["fails"])
        ui = getattr(self, "ui", None)
        if ui is not None and ui.alive:
            ui.boot_done(summary)

    # -- the scanner: files dropped on the display --------------------------

    def listen_for_drops(self):
        """Files dropped anywhere on the display come here with their full
        paths (pywebview's drop event) - and the drop is kept from the
        WebView, which would otherwise open the file in place of the page."""
        try:
            from webview.dom import DOMEventHandler
            self.window.dom.document.events.drop += DOMEventHandler(self.on_drop, prevent_default=True)
        except Exception:  # noqa: BLE001 - no scanner is survivable; no display is not
            log.warning("files dropped on the display cannot be scanned", exc_info=True)

    def on_drop(self, event):
        files = ((event or {}).get("dataTransfer") or {}).get("files") or []
        paths = [f.get("pywebviewFullPath") for f in files if isinstance(f, dict)]
        paths = [p for p in paths if p]
        ui = getattr(self, "ui", None)
        if not paths:
            if ui is not None and ui.alive:
                ui.scan({"state": "error", "name": "",
                         "text": "That did not come with a file - drop a file from File Explorer."})
            return
        threading.Thread(target=self._scan_all, args=(paths[:10],), daemon=True, name="scan").start()

    def choose_and_scan(self):
        """File Explorer's own open dialog, over the display, and what you
        pick scanned like a drop. The display fills the screen, so there is
        nothing behind it to drag a file from. True if a file was chosen."""
        window = getattr(self, "window", None)
        if window is None:
            return False
        kind = getattr(getattr(webview, "FileDialog", None), "OPEN", None)
        if kind is None:
            kind = getattr(webview, "OPEN_DIALOG", 10)
        try:
            chosen = window.create_file_dialog(kind, allow_multiple=True)
        except Exception:  # noqa: BLE001 - no dialog is a note, not a crash
            log.warning("the file dialog would not open", exc_info=True)
            return False
        paths = [p for p in (chosen or ()) if p]
        if not paths:
            return False
        threading.Thread(target=self._scan_all, args=(paths[:10],), daemon=True, name="scan").start()
        return True

    def _scan_all(self, paths):
        for path in paths:
            self.scan_file(path)

    def scan_file(self, path):
        """Scan one file (scanner.py), telling the page as it goes."""
        ui = getattr(self, "ui", None)

        def tell(event):
            if ui is not None and ui.alive:
                ui.scan(event)

        name = os.path.basename(path)
        with self._scan_lock:
            tell({"state": "scanning", "name": name})
            report = scanner.scan(path, on_step=lambda text: tell({"state": "step", "name": name,
                                                                    "text": text}))
            log.info("scanned %s: %s", name, report.get("verdict"))
            tell({"state": "done", "name": name, "report": report})
        return report

    def tell_issues(self, items):
        """The System panel's list, whenever it changes (issues.py)."""
        ui = getattr(self, "ui", None)
        tell = getattr(ui, "issues", None) if ui is not None and ui.alive else None
        if tell is not None:
            tell(items)

    def want_intro(self):
        """Ask for the intro. The watcher plays it on its next tick."""
        self.intro_wanted = True

    def check_intro(self, now=None):
        """APOLLO in lit cells, on the whole screen, as Apollo comes up.

        The display holds the screen for INTRO_SECONDS while the page plays
        it - the boot lines type out, the name settles, and the picture blurs
        away into the display under it - and then the display stays: open,
        as if Ctrl+` had been pressed, and closed the same way. Not over a
        full-screen program: a game or a film that was up first is left
        alone, and Apollo stays in the overlay.

        On the watcher's thread, start and end, like every other change of
        mode. The first version ended on a timer thread, which raced the
        watcher's own check of the window: it saw the window halfway between
        two modes and "repaired" it, and that is how the deadlock described
        in `user32_releasing_gil` was found.
        """
        now = time.monotonic() if now is None else now
        if self.intro_wanted:
            self.intro_wanted = False
            if screen_busy():
                log.info("intro skipped: a full-screen program has the screen")
                return
            log.info("intro")
            self.intro_started = now
            self.intro_until = now + INTRO_MOST
            # Told first, while the page is still hidden, so the display is
            # never seen for a frame on its way to the intro.
            self.ui.intro()
            self.apply_mode()
            return
        if self.intro_until and (now >= self.intro_until or self._boot_ready(now)):
            self.intro_until = 0.0
            # The intro blurs away into the display, so the display is what
            # is left: open it, unless Ctrl+` already did.
            if not self.presence.full:
                self.presence.toggle_peek()
            self.apply_mode()

    def apply_mode(self):
        """Swap between the overlay and the full display, and take OSIRIS's
        window along: it is only ever on screen with the display, awake."""
        self._apply_mode()
        self.osiris_follow()

    def osiris_follow(self):
        osiris = getattr(self, "osiris", None)
        if osiris is not None:
            osiris.follow(self.overlay.mode == Overlay.FULL and not self.presence.asleep)

    @staticmethod
    def _display_origin():
        left, top, _right, _bottom = Overlay.work_area()
        return (left, top)

    def osiris_gone(self):
        """The map's window was closed from its own side: the display takes
        off OSIRIS's colours."""
        ui = getattr(self, "ui", None)
        if ui is not None and ui.alive:
            ui.osiris(False)

    def request_osiris(self, on):
        """OSIRIS open or closed, by voice. The watcher does it (check_osiris)."""
        self.osiris_requested = bool(on)

    def check_osiris(self):
        """A voice request for OSIRIS, on the watcher's thread like every other
        change of mode: the display comes up first if it has to, then the page
        goes into OSIRIS mode and says where the map goes (Api.osiris_open)."""
        wanted = getattr(self, "osiris_requested", None)
        if wanted is None:
            return
        self.osiris_requested = None
        ui = getattr(self, "ui", None)
        if ui is None or not ui.alive:
            return
        if wanted and not self.presence.full:
            self.presence.toggle_peek()
            self.apply_mode()
        ui.osiris(wanted)
        if not wanted:
            osiris = getattr(self, "osiris", None)
            if osiris is not None:
                osiris.close()

    def request_display(self, request):
        """Ultra mode asked for by voice. The watcher does it (check_displays)."""
        queue = getattr(self, "display_requests", None)
        if queue is None:
            queue = self.display_requests = collections.deque()
        queue.append(dict(request))

    @staticmethod
    def _to_be_seen(request):
        """A request that wants the display up: ultra mode on, a display put
        on the screen or shown, or a mode asked for by name - every one of
        them is something to look at. Hiding one, or leaving ultra mode,
        leaves the screen as it is."""
        action = request.get("action")
        return (action in ("focus", "show", "mode", "scan")
                or (action == "hud_edit" and request.get("do") in ("edit", "reset"))
                or (action == "ultra" and bool(request.get("on"))))

    def check_displays(self):
        """Voice requests for ultra mode, in the order they were made, on the
        watcher's thread like every other change of mode: the display comes
        up first if the request wants to be seen, then the page does it."""
        queue = getattr(self, "display_requests", None)
        if not queue:
            return
        ui = getattr(self, "ui", None)
        if ui is None or not ui.alive:
            queue.clear()
            return
        while queue:
            request = queue.popleft()
            if self._to_be_seen(request) and not self.presence.full:
                self.presence.toggle_peek()
                self.apply_mode()
            show = getattr(ui, "display", None)
            if show is not None:
                show(request)

    def _apply_mode(self):
        """Swap between the overlay and the full display.

        A cut, not an animation: the full display is a different thing
        arriving rather than the overlay growing, and the growing is now the
        overlay's own business (see `orb.Orb._advance_box`). Exactly one of
        the two windows is on screen at any moment.
        """
        self.apply_sleep()
        mode = self.desired_mode()
        if mode == self.overlay.mode:
            return
        self.overlay.mode = mode
        orb = self.orb

        ui = getattr(self, "ui", None)
        if ui is not None and ui.alive:
            ui.mode(mode)
            if mode == Overlay.FULL:
                # on_data only reaches the page while the display is up, so
                # without this the first thing it shows after a quiet stretch
                # is the last snapshot it happened to catch - or nothing.
                data = getattr(self, "data", None)
                if data is not None:
                    ui.data(data.snapshot)
                # ...and the panels the way they were left: hidden by voice or
                # by the button, and still hidden after a restart.
                shown = getattr(ui, "panels", None)
                if shown is not None:
                    shown(panels.state())
                # ...and ultra mode's displays the way you laid them out.
                laid_out = getattr(ui, "display", None)
                if laid_out is not None:
                    # ...with the normal display's HUD the way you arranged it.
                    laid_out({"action": "layout", "layout": displays.state(), "hud": hud.state()})
                # ...and which of Apollo's own modes are on, for the bar.
                self._tell_states()
                # ...and what is wrong, for the System panel.
                self.tell_issues(issues.current())

        if orb is None:                   # no native layer yet: just cut
            self.overlay.show_page(mode)
            return

        if mode == Overlay.ORB:
            # Back from the full display, which had the whole screen: the
            # overlay starts again from its resting footprint, with nothing
            # under the mesh.
            orb.place(self.overlay.box_for(Overlay.ORB), self.overlay.orb_overhang())
            orb.set_visible(True)
            self.overlay.hide_page()
        else:
            orb.set_visible(False)
            self.overlay.show_page(mode)

    def apply_sleep(self):
        """Tell the page whether it is the idle screen, and listen if it is.

        Before the window is shown, never after: told late, the page would put
        the whole dashboard up for a frame on its way to the idle screen.
        """
        asleep = self.presence.asleep
        if asleep == self.asleep_shown:
            return
        self.asleep_shown = asleep
        log.info("asleep" if asleep else "awake again")
        ui = getattr(self, "ui", None)
        if ui is not None and ui.alive:
            ui.sleep(asleep)
        voice = getattr(self, "voice", None)
        if voice is not None:
            self.wake = presence.VoiceWake()
            voice.listen(self.on_wake_level if asleep else None)

    def on_wake_level(self, level):
        """Asleep, every mic block's loudness. PortAudio's thread: it only
        leaves a note, and the watcher's next tick does the waking."""
        if self.wake.feed(level):
            self.presence.touch(time.monotonic())

    def poke_data(self, *keys):
        """Have the data service read these again soon, if it is running."""
        if self.data is not None:
            self.data.poke(*keys)

    def open_link(self, url):
        """Open an article from the feed, and get the display out of its way.

        Only web addresses: the page is handed feed data, and a feed that
        slipped a `file:` or `ms-settings:` link into a story must not get to
        run it by being clicked.
        """
        url = str(url or "")
        if not url.startswith(("https://", "http://")):
            return False
        import webbrowser
        webbrowser.open(url)
        if self.presence.peek_open:
            self.presence.toggle_peek()
        self.apply_mode()
        return True

    def on_level(self, value):
        """Mic loudness while you are speaking. Called from the audio thread."""
        if self.orb is not None:
            self.orb.set_level(value)

    # How long an answer stays up once Apollo has stopped speaking. Long
    # enough to finish reading a figure you only half caught, short enough
    # that the desktop is your own again by the time you have looked away.
    LINGER = 4.0

    def on_status(self, state):
        """A phase change from the backend: listening, thinking, speaking, idle."""
        # Only a change of phase touches the words on screen (see
        # `presence.content_action`): a fresh turn clears the last answer
        # at once, settling back after one lets it linger, and a repeat of
        # the same phase does nothing at all.
        delay = presence.content_action(self.last_status, state, self.LINGER)
        self.last_status = state
        if delay == 0.0:
            self.view.reset()          # a fresh turn: nothing carries over
            if self.orb is not None:
                self.orb.set_activity("")
        if delay is not None and self.orb is not None:
            self.orb.clear_content(after=delay)
        self.turn_busy = state in WebReporter.ENGAGED
        if self.turn_busy:
            self.last_engaged = time.monotonic()
            # A conversation is someone being here, keyboard or no keyboard.
            self.presence.touch(self.last_engaged)
        if self.orb is not None:
            self.orb.set_state(self.overlay_state_for(state))
        self.apply_mode()

        # The ring can lose topmost status to any other window that asserts
        # it after ours did - that cost real debugging time to track down
        # (see the module docstring) - and it can happen mid-conversation, not
        # only on a mode change apply_mode() would already catch. Reassert
        # whenever a turn is actively under way.
        if self.turn_busy and self.overlay.mode == Overlay.ORB and self.orb is not None:
            self.orb.raise_above()

    def _render(self, frame):
        """Put a turn frame from `self.view` on the overlay."""
        if self.orb is None:
            return
        role, text, visual = frame
        if text or visual:
            self.orb.set_content(role, text, visual)

    def overlay_state_for(self, phase):
        """Which face the overlay wears for a phase of the turn.

        Speaking is two different pictures: an answer that is a row of
        readouts is the RESULT state, and one that is words (with or without
        a chart) is the REPLY state.
        """
        if phase == assistant.LISTENING:
            return overlay_state.LISTENING
        if phase == assistant.THINKING:
            return overlay_state.SEARCHING
        if phase == assistant.SPEAKING:
            visual = self.view.visual or {}
            if visual.get("cards") and not self.view.reply:
                return overlay_state.RESULT
            return overlay_state.REPLY
        return overlay_state.REST

    def on_turn(self, speaker, text, visual=None):
        """A line of the transcript arrived: yours, or Apollo's reply.

        Both now stream - yours from Gemini's transcript while you talk, the
        reply as it is spoken - and `turnview.TurnView` decides what they add
        up to: your final line never wipes an answer already up, and a chart
        a tool drew stays with the answer as it grows.
        """
        if not text:
            return
        if speaker == "You":
            self._render(self.view.heard(text, final=True))
        else:
            if visual:
                self.view.show(visual)
            self._render(self.view.replied(text))

    def on_partial(self, text):
        """Your words so far, while you are still talking."""
        if text:
            self._render(self.view.heard(text))

    def on_visual(self, visual):
        """A chart or cards a tool drew for this turn."""
        self._render(self.view.show(visual))

    def on_activity(self, text):
        """What Apollo is doing ("fetching NVDA"), under your words."""
        self.view.doing(text)
        if self.orb is not None:
            self.orb.set_activity(text)

    def request_away(self, grace=None):
        """You said you are going out, or pressed Away. The watcher does it
        (check_presence)."""
        self.away_requested = True
        self.away_grace = grace

    def request_idle(self, grace=None):
        """Idle mode, because you asked or pressed Idle. The watcher does it
        (check_presence)."""
        self.idle_requested = time.monotonic()
        self.idle_grace = grace

    def want_trading(self):
        """Trading mode wants its board: read it now, and keep it fresh."""
        data = getattr(self, "data", None)
        if data is not None:
            data.want_trading()

    def mode_states(self):
        """Which of Apollo's own modes are on, for the display's bar."""
        gone = getattr(self, "away", None)
        toggle = getattr(self, "listen_toggle", None)
        return {"away": bool(gone is not None and gone.away),
                "listening": bool(toggle is not None and toggle.enabled.is_set())}

    def _tell_states(self):
        ui = getattr(self, "ui", None)
        states = getattr(ui, "states", None) if ui is not None else None
        if states is not None:
            states(self.mode_states())

    def set_listening(self, on):
        """Hands-free on or off from the display's bar: the same switch as
        Ctrl+1, read by the run loop between turns."""
        toggle = getattr(self, "listen_toggle", None)
        if toggle is None:
            return
        if on:
            toggle.enabled.set()
        else:
            toggle.enabled.clear()
        self.on_listen_toggle(bool(on))

    def toggle_peek(self):
        """CTRL+`: open the full display by hand, or put it away."""
        if getattr(self, "ui", None) is None:
            return   # the page is not up yet; nothing to open
        # Stays open until the chord is pressed again - using the machine in
        # between no longer closes it (see `presence.Presence`).
        self.presence.toggle_peek()
        self.apply_mode()

    def on_data(self, snapshot):
        """A fresh world snapshot. The page only wants it while it is visible."""
        ui = getattr(self, "ui", None)
        if ui is not None and ui.alive and self.overlay.mode == Overlay.FULL:
            # With the streamed prices over the minute-old ones, or the next
            # snapshot would put every card back a minute.
            ui.data(live.overlay_snapshot(snapshot, getattr(self, "ticker", None)))

    def on_ticks(self, batch):
        """Trades from the stream, about once a second. Only for the page."""
        ui = getattr(self, "ui", None)
        if ui is not None and ui.alive and self.overlay.mode == Overlay.FULL:
            ui.live(batch)

    def morning(self):
        """The day's first recap: open the display, say it, put it away."""
        opened = not self.presence.full
        if opened:
            self.presence.toggle_peek()
            self.apply_mode()
        try:
            assistant.brief_now(self.ui, self.voice)
        except Exception:
            pass          # a failed briefing must not take the day with it
        finally:
            if opened and self.presence.peek_open:
                self.presence.toggle_peek()
                self.apply_mode()

    def check_briefing(self, idle):
        """Once a day, the first time you are actually at the machine.

        "At the machine" has to mean idle at it, not touching it. The talk
        chord makes you present, so the first Ctrl+Alt of the day used to
        satisfy every condition here and the recap started over the top of
        the turn that press was opening - `turn_busy` could not catch it,
        because that flag comes from Gemini's status and the status arrives
        after the press.
        """
        if not DAILY_RECAP:
            return
        ui = getattr(self, "ui", None)
        if (ui is None or ui.quiet or self.voice is None
                or self.briefing_thread is not None and self.briefing_thread.is_alive()):
            return
        busy = (self.turn_busy
                or assistant.talk_held()          # the chord is down right now
                or time.monotonic() - self.last_engaged < BRIEF_SETTLE)
        if not self.schedule.due(idle_seconds=idle, busy=busy):
            return
        self.schedule.done()
        log.info("day's recap starting")
        self.briefing_thread = threading.Thread(target=self.morning, daemon=True,
                                                name="apollo-briefing")
        self.briefing_thread.start()

    def check_prayer(self):
        """Fifteen minutes before each prayer, once.

        It waits for a turn the way a reminder does, rather than talking over
        one: TURN_GATE is what `announce` blocks on.
        """
        ui = getattr(self, "ui", None)
        if ui is None or ui.quiet or self.voice is None:
            return
        if self.prayer_thread is not None and self.prayer_thread.is_alive():
            return
        found = self.prayers.due()
        if found is None:
            return
        name, when = found
        log.info("prayer reminder: %s at %s", name, when.strftime("%H:%M"))
        self.prayer_thread = threading.Thread(
            target=assistant.fire_prayer, daemon=True, name="apollo-prayer",
            args=(ui, self.voice, name, when, prayer.LEAD_MINUTES))
        self.prayer_thread.start()

    def check_presence(self, idle):
        """Open the display when you are away; put it away when you come back.

        `idle` is seconds since the last input anywhere in Windows, so this
        follows you rather than following Apollo's own window.
        """
        now = time.monotonic()
        # Locking the PC is asking for idle mode: once per lock, so waking it
        # on the lock screen does not put it straight back to sleep.
        locked = pc_locked()
        if locked and not getattr(self, "_was_locked", False):
            log.info("the PC was locked: idle mode")
            self.request_idle()
        self._was_locked = locked
        # Away mode (away.py): out by what you say - once the answer is over,
        # or Apollo's own voice would count as you being here - and back at a
        # touch or a word.
        # Here, on the watcher's thread, because keeping the PC up holds only
        # as long as the thread that asked for it.
        if getattr(self, "away", None) is not None:
            if getattr(self, "away_requested", False) and not getattr(self, "turn_busy", False):
                self.away_requested = False
                if self.away.leaving(now, getattr(self, "away_grace", None)):
                    self.keeper.apply(True)
                    self._tell_states()
            touched = self.presence._touched
            here = idle if touched is None else min(idle, max(0.0, now - touched))
            if self.away.update(now, here):
                self.keeper.apply(self.away.away)
                self._tell_states()
        # Asked for by voice: once Apollo has finished saying it will, or his
        # own voice would be the thing that wakes him.
        if (getattr(self, "idle_requested", None) is not None
                and not getattr(self, "turn_busy", False)):
            self.idle_requested = None
            self.presence.sleep_now(now, getattr(self, "idle_grace", None))
            self.apply_mode()
        # Only asked on the way to sleep; see `screen_busy`.
        busy = (idle >= self.presence.afk_seconds and not self.presence.asleep
                and screen_busy())
        if self.presence.check(idle, now=now, screen_busy=busy):
            self.apply_mode()
        self.keep_clips(now, locked)
        self.check_briefing(idle)
        self.check_prayer()

    def keep_clips(self, now, locked):
        """The replay buffer records while you are here to be recorded.

        It is the heaviest thing Apollo does - the whole screen captured and
        encoded thirty times a second, most of a core - and it ran day and
        night: asleep, with Apollo's own display over the screen, it was
        recording Apollo's display. So it is paused while Apollo is asleep or
        the PC is locked (where Windows allows no capture anyway, and it used
        to die and stay dead), and back the moment you are - unless you
        paused it yourself from the tray. One that dies with you here is tried
        again, a minute later, then less and less often if it keeps dying.
        """
        recorder = getattr(self, "clips", None)
        if recorder is None:
            return
        wanted = getattr(self, "clips_wanted", True)
        if not (wanted and not locked and not self.presence.asleep):
            if recorder.running:
                recorder.stop()
            self._clips_paused = wanted
            return
        if recorder.running:
            return
        if getattr(self, "_clips_paused", False):
            self._clips_paused = False
            self._clips_retry = CLIPS_RETRY
        else:
            last = getattr(self, "_clips_started", None)
            retry = getattr(self, "_clips_retry", CLIPS_RETRY)
            if last is not None and now - last < retry:
                return
            if last is not None:
                self._clips_retry = min(retry * 2, CLIPS_RETRY_MOST)
            log.info("the replay buffer had stopped; recording again")
            issues.record("clips", "REPLAY BUFFER",
                          f"stopped and restarted: {getattr(recorder, 'error', None) or 'no reason given'}",
                          "warn")
        self._clips_started = now
        recorder.start()

    def check_overlay_alive(self):
        """Keep the window the shape it is supposed to be.

        Both a startup repair and a running watchdog: pywebview can re-show the
        form with its own bounds after we have sized it, and nothing else would
        notice.
        """
        now = time.monotonic()
        if now - getattr(self, "_last_check", 0) < 2:
            return
        self._last_check = now
        # Nothing to wait for any more: the overlay resizing itself to fit an
        # answer is not a disagreement between the two windows, because at
        # rest the page window is supposed to be hidden whatever size the
        # native layer has grown to.
        #
        # Every couple of seconds is often enough to catch the orb's Z-order
        # being stolen without it ever costing a visibly missed frame - see
        # `Orb.raise_above` for why this can happen even with no mode change.
        if self.orb is not None and self.overlay.mode == Overlay.ORB:
            self.orb.raise_above()
        if self.overlay.hwnd and self.overlay.verify():
            return
        # Two seconds rather than something lazier because this is also what
        # repairs a startup where pywebview's show/hide/re-show dance landed
        # after our geometry did. It is two Win32 calls; it can afford to run
        # often, and a window left the wrong size is very visible.
        self.overlay.attach(tries=2, gap=0.1)
        self.apply_mode()

    # -- the backend, off the UI thread -------------------------------------

    def worker(self):
        # pyttsx3 drives SAPI through COM, which has to be initialised per
        # thread. On the main thread that happens for us; here it doesn't.
        try:
            import comtypes
            comtypes.CoInitialize()
        except Exception:
            pass  # not fatal - only matters if the TTS driver needs it

        ui = self.ui
        ui.status(STARTING)
        # The checks run beside the start, each a line on the loading screen.
        threading.Thread(target=self.run_checks, kwargs={"boot": True}, daemon=True,
                         name="checks").start()

        # Patient about the network: at sign-in it is usually a few seconds
        # away, and giving up here used to leave Apollo running but empty for
        # the whole session. A bad key is still fatal at once.
        try:
            if not assistant.wait_for_api(ui, stop=self.stopping.is_set):
                return                        # quitting while it waited
        except RuntimeError as e:
            log.error("startup check failed: %s", e)
            self.boot_step({"id": "claude", "label": "CLAUDE API", "status": "fail", "detail": str(e)})
            self.boot_part_done("startup")
            ui.fatal(str(e))
            return
        log.info("API reachable")
        self.boot_step({"id": "claude", "label": "CLAUDE API", "status": "ok", "detail": "reachable"})

        # The backup transcriber loads behind everything else - Gemini's own
        # transcript is the one in use - so it no longer holds up waking.
        whisper = assistant.load_whisper()

        # Before the greeting, so the first-run voice download shows a note
        # instead of silently stalling it.
        assistant.load_voice(ui)

        # Apollo's voice. Connected before the greeting so that its microphone
        # stream is the one that is open by the time you can press the chord -
        # it owns the device for the life of the session, and the local
        # fallback recorder must never be holding it at the same time.
        # Push-to-talk, always: always-listening is turned on with CTRL+1, not
        # arrived at.
        self.voice = assistant.Voice(
            ui, on_level=self.on_level,
            on_user_text=assistant.agent_interrupt(ui),
            on_heard=ui.partial,
            on_reply=ui.stream_reply,
            on_activity=ui.activity,
            run_tool=assistant.tool_runner(ui))
        self.voice.open(auto_vad=False)
        log.info("voice session opened")
        # The voice's own issue is kept by Voice.open, for every reconnect too.
        self.boot_step({"id": "voice", "label": "VOICE LINK",
                        "status": "ok" if self.voice.ready else "fail",
                        "detail": gemini_live_model(self.voice) or "would not open"}, keep=False)

        # The replay buffer: the last minute of the screen, in memory only, so
        # "clip that" has something to save. Nothing reaches the disk until
        # you ask. A machine that cannot record says so once and Apollo
        # carries on without clips.
        self.clips = clips.ReplayBuffer().start()
        tools.set_clip_buffer(self.clips)
        self.boot_step({"id": "clips", "label": "REPLAY BUFFER", "status": "ok",
                        "detail": "recording"}, keep=False)

        # Everything the display and the briefing read - prices, headlines,
        # posts, weather, the machine - refreshed on a timer rather than
        # inside a turn, where it would be latency you could hear.
        self.data = dataservice.DataService(on_snapshot=self.on_data).start()
        log.info("data service started")
        self.boot_step({"id": "data", "label": "DATA SERVICE", "status": "ok",
                        "detail": "running"}, keep=False)

        # Prices as they trade, over the minute-by-minute reading, for the
        # stocks the stream carries. No key, no stream: the minute will do.
        key = live.api_key()
        if key:
            self.ticker = live.LiveFeed(key, symbols=watchlist.current,
                                        on_tick=self.on_ticks).start()
            live.set_feed(self.ticker)
            log.info("live prices on")
            self.boot_step({"id": "prices", "label": "LIVE PRICES", "status": "ok",
                            "detail": "streaming"}, keep=False)
        else:
            log.info("no %s; prices refresh once a minute", live.KEY_NAME)
            self.boot_step({"id": "prices", "label": "LIVE PRICES", "status": "warn",
                            "detail": "once a minute - no key"}, keep=False)

        # What you care about, learned from each finished day of the record
        # (journal.py) by one question to Claude, and read by Gemini at the
        # start of every session.
        self.learner = interests.Learner(assistant.ask_once).start()
        log.info("learning from the record")

        # Private Eye: every few hours, the free sources searched for what you
        # care about; the best few finds go on the display and into the recap.
        self.eye = private_eye.PrivateEye().start(on_found=lambda: self.poke_data("finds"))
        log.info("Private Eye on watch")
        self.boot_step({"id": "eye", "label": "PRIVATE EYE", "status": "ok",
                        "detail": "on watch"}, keep=False)
        self.boot_part_done("startup")

        # CTRL+1. A thread of its own so it answers during a turn as well as
        # between them; `run_loop` reads its flag and does the actual
        # switching, so a mode change never lands mid-sentence.
        self.listen_toggle = assistant.ListenToggle(
            on_toggle=self.on_listen_toggle, stop=self.stopping.is_set)
        self.listen_toggle.start()

        # Reminders you set by voice come back in Apollo's voice, and wait for
        # any turn in progress to finish first (see assistant.TURN_GATE).
        reminders.start_watcher(
            lambda reminder, late: assistant.fire_reminder(ui, self.voice, reminder, late),
            assistant.TURN_GATE, self.stopping.is_set)

        # LYLA's desk: the research Apollo hands her runs on her own thread,
        # her card shows each step, and when she is done Apollo says what she
        # found - after any turn in progress, like a reminder (lyla.py).
        crew.configure(
            tell=ui.agent,
            report=lambda job: assistant.report_agent(ui, self.voice, job),
            gate=assistant.TURN_GATE)
        youtube.DOWNLOADS.configure(
            report=lambda job: assistant.report_download(ui, self.voice, job),
            gate=assistant.TURN_GATE, tell=ui.agent)

        # Say hello, so you know the mic is live before you ever press a key.
        assistant.greet(ui)

        # Waking is over: from here a turn is allowed to take the screen.
        ui.quiet = False
        ui.status(assistant.IDLE)
        log.info("awake")

        # Quitting is the Hotkeys thread's job, so that it answers during a
        # turn as well as between them.
        try:
            assistant.run_loop(ui, whisper, stop=self.stopping.is_set,
                               voice=self.voice, toggle=self.listen_toggle)
        finally:
            self.close_live()
        self.quit()

    def on_listen_toggle(self, listening):
        """CTRL+1 was pressed. Report it; `run_loop` does the switching.

        Deliberately does nothing but tell you: the session is replaced to
        change mode, and doing that from the hotkey thread would tear the
        microphone out from under a turn that is still running.
        """
        ui = getattr(self, "ui", None)
        if ui is not None and ui.alive:
            ui.note("Always-listening ON" if listening else "Always-listening OFF")
            states = getattr(ui, "states", None)
            if states is not None:
                states({**self.mode_states(), "listening": bool(listening)})

    def close_live(self):
        """Shut the Gemini session down, once, from whichever path got here.

        Both `quit` and the end of `worker` call this, because either can come
        first: the tray quits while a turn is in flight, or the loop stops on
        its own. It has to happen while the session's event loop is still
        running - see the shutdown note in `gemini_live` - so it cannot be
        left to interpreter teardown.

        `Voice` is itself idempotent and locked, which is what makes calling
        this from two threads safe: the toggle may be replacing the session at
        the very moment the tray quits.
        """
        voice = getattr(self, "voice", None)
        if voice is not None:
            voice.close()


def gemini_live_model(voice):
    live = getattr(voice, "live", None)
    return getattr(live, "model", None) if live is not None else None


def die(message):
    """Report a failure that happens before there is a page to report it on.

    Launched via pythonw.exe there is no console, so stderr goes nowhere and a
    plain SystemExit would exit silently. 0x10 is MB_ICONERROR.
    """
    ctypes.windll.user32.MessageBoxW(None, message, "Apollo", 0x10)
    raise SystemExit(message)


def main():
    if not os.path.exists(INDEX):
        # Not a build step any more - this page is written by hand and lives
        # in the repository, so a missing one means a broken checkout.
        die("Missing front end: " + INDEX)

    lock = single_instance()
    if lock is None:
        # Silent on purpose: the usual cause is launching it by hand when the
        # Startup copy is already resident, and a dialog for that is noise.
        sys.exit(0)

    # After the lock: the copy that exits because one is already running
    # must not write "started" into the running one's log.
    start_log()
    try:
        _crashes = watch_crashes()  # noqa: F841 - held open while Apollo runs
    except OSError:
        log.warning("no crash file; native crashes will go unrecorded")
    log.info("started, pid %s", os.getpid())

    Apollo()
    # http_server serves ui/ over localhost instead of file://, which is what
    # lets the page fetch() its own sound effects and load the fonts.
    webview.start(http_server=True)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # Nothing is watching stderr under pythonw.exe, so a crash would
        # otherwise just make the window vanish with no explanation.
        die(traceback.format_exc())
