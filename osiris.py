"""OSIRIS inside Apollo: the open-source intelligence map at osirisai.live -
flights, ships, CCTV, live news, earthquakes, incidents, undersea cables -
laid into the full display, with Apollo dressed the way OSIRIS is while it
is open (the page does the dressing; see `setOsiris` in ui/full/app.js).

Why a window of its own rather than a frame in the page: the site answers
every request with `X-Frame-Options: SAMEORIGIN`, so no browser will draw it
inside somebody else's page, and taking that header off would be taking
apart a protection the site chose for itself. A window pointed at the site
is just a browser. The display leaves a frame for it and says where the
frame is; the window is put exactly there, owned by the display so it stays
above it, and goes whenever the display goes - to the overlay, or to sleep.

Sealed off from Apollo: the window gets no bridge into Apollo (`js_api`),
so nothing on the page can ask Apollo for anything, and it browses privately
like every Apollo window. Links that open new windows go to the browser.

What it is, checked before it went in (2026-09-25): a Next.js app served
from osirisai.live itself behind Cloudflare, with map tiles, markets and
news fetched through its own server. No ads, no third-party trackers, no
miner, nothing that touches a wallet. It does carry tools that look at the
machine they run on - a scan of your own PC's local ports and addresses
(WebRTC and 127.0.0.1), a Bluetooth scanner, live location - and each of
them runs only when you open that tool; Bluetooth and location still ask.
"""

import ctypes
import logging
import threading
from ctypes import wintypes

log = logging.getLogger("apollo.osiris")

LAYERS = ("maritime", "cctv", "cctv_previews", "live_news", "earthquakes",
          "global_incidents", "day_night", "cables", "sdk_sea", "sdk_air", "sdk_naval")
SITE = "https://osirisai.live/"
TITLE = "Apollo · OSIRIS"
SMALLEST = 200            # a frame narrower or shorter than this is not a frame


def layers_of(wanted):
    """The map's own layers out of `wanted`, once each, in the order given.
    Anything else - anything that is not one of its layers' names - is left
    out: the page chooses layers, never an address."""
    if not isinstance(wanted, (list, tuple)):
        return list(LAYERS)
    kept = []
    for layer in wanted:
        if isinstance(layer, str) and layer in LAYERS and layer not in kept:
            kept.append(layer)
    return kept


def url_for(layers):
    """The map with these layers on. Always osirisai.live: only a layer's
    name gets into the address, and with none on it is the site's own view."""
    kept = layers_of(layers)
    return SITE + "?layers=" + ",".join(kept) if kept else SITE


URL = url_for(LAYERS)


def _frame(rect):
    """(x, y, w, h) in whole device pixels, or None for anything that is not
    a frame the display could have laid out."""
    try:
        x, y, w, h = (int(round(float(rect[k]))) for k in ("x", "y", "w", "h"))
    except (TypeError, KeyError, ValueError):
        return None
    if w < SMALLEST or h < SMALLEST:
        return None
    return (x, y, w, h)


class Osiris:
    """The OSIRIS window: opened over the display's frame for it, hidden while
    the display is away, closed when you close it.

    The native side comes in as functions, so the deciding can be tested
    without a window: `create(rect, on_ready, on_closed)` makes the window,
    calls `on_ready` once it can be moved and `on_closed` if it is closed
    from its own side; `place(window, rect)` puts it on a screen rectangle;
    `show`, `hide` and `destroy` do what they say, and `navigate(window,
    url)` loads the map again with other layers. `origin()` is where the
    display's top left corner is on the screen, and `on_gone()` is told
    when the window closed without Apollo closing it (Alt+F4 on the map),
    so the display can take off OSIRIS's colours.

    In ultra mode the map is one display among several, and it is parked -
    off the screen but still loaded - while it is minimized, while another
    display is expanded, while one is being dragged or set up over it, and
    while Apollo answers: a window can only be laid over the page, never
    under it, so whatever the page drew where the map is would be hidden.
    """

    def __init__(self, create=None, place=None, show=None, hide=None, destroy=None,
                 navigate=None, origin=None, owner=None, on_gone=None, layers=None):
        self._owner = owner or (lambda: None)
        self._on_gone = on_gone or (lambda: None)
        self._create = create or self._create_window
        self._place = place or self._place_window
        self._show = show or _show_window
        self._hide = hide or _hide_window
        self._destroy = destroy or _destroy_window
        self._navigate = navigate or _navigate_window
        self._origin = origin or (lambda: (0, 0))
        self._lock = threading.RLock()
        self.window = None
        self.frame = None         # where it goes on the display, device pixels
        self.ready = False        # the window exists and can be moved
        self.shown = True         # the display is up and awake
        self.wanted = True        # ...and the page wants the map seen, not parked
        self.url = url_for(LAYERS if layers is None else layers)

    def _on_screen(self):
        left, top = self._origin()
        x, y, w, h = self.frame
        return (left + x, top + y, w, h)

    def open(self, rect):
        """The display has laid out the frame: open the window over it, or
        move it there. False, and nothing done, for a frame that is not one."""
        frame = _frame(rect)
        if frame is None:
            return False
        with self._lock:
            self.frame = frame
            self.wanted = True
            if self.window is None:
                log.info("OSIRIS opening")
                self.ready = False
                self.window = self._create(self._on_screen(), self._on_ready, self._on_closed)
            elif self.ready and self.shown:
                self._place(self.window, self._on_screen())
                self._show(self.window)
        return True

    def park(self):
        """Off the screen, still loaded: back where it was, or wherever the
        next `open` says, without loading the whole map again."""
        with self._lock:
            was = self.wanted
            self.wanted = False
            if self.window is not None and self.ready and self.shown and was:
                self._hide(self.window)

    def set_layers(self, layers):
        """The map with these of its layers on; an open map loads them now.
        Returns the layers kept."""
        kept = layers_of(layers)
        with self._lock:
            url = url_for(kept)
            changed = url != self.url
            self.url = url
            if changed and self.window is not None and self.ready:
                log.info("OSIRIS layers: %s", ",".join(kept) or "the site's own")
                self._navigate(self.window, url)
        return kept

    def _on_ready(self, *_):
        with self._lock:
            if self.window is None:
                return
            self.ready = True
            self._place(self.window, self._on_screen())
            if not (self.shown and self.wanted):
                self._hide(self.window)

    def _on_closed(self, *_):
        with self._lock:
            if self.window is None:
                return                 # Apollo closed it; nobody to tell
            self.window, self.ready = None, False
        log.info("OSIRIS closed from its own window")
        self._on_gone()

    def follow(self, shown):
        """The display is up and awake (True) or not: the window goes with it."""
        with self._lock:
            shown = bool(shown)
            changed = shown != self.shown
            self.shown = shown
            if self.window is None or not self.ready or not changed or not self.wanted:
                return
            if shown:
                self._place(self.window, self._on_screen())
                self._show(self.window)
            else:
                self._hide(self.window)

    def close(self):
        with self._lock:
            window, self.window, self.ready = self.window, None, False
        if window is not None:
            log.info("OSIRIS closed")
            self._destroy(window)

    # -- the real window --------------------------------------------------------

    def _create_window(self, rect, on_ready, on_closed):
        import webview
        x, y, w, h = rect
        # No js_api: the page gets no way into Apollo.
        window = webview.create_window(
            TITLE, self.url, x=x, y=y, width=w, height=h,
            frameless=True, easy_drag=False, on_top=True, resizable=False,
            background_color="#04040a", text_select=True)
        window.events.shown += on_ready
        window.events.closed += on_closed
        return window

    def _place_window(self, window, rect):
        hwnd = _hwnd()
        if not hwnd:
            return
        owner = self._owner()
        if owner:
            # Owned by the display: always above it, and never behind it.
            _user32.SetWindowLongPtrW(hwnd, GWLP_HWNDPARENT, owner)
        x, y, w, h = rect
        _user32.SetWindowPos(hwnd, HWND_TOPMOST, x, y, w, h, SWP_NOACTIVATE | SWP_SHOWWINDOW)


# -- Win32, through ctypes: it lets go of the GIL while it waits (see
# apollo.user32_releasing_gil for why that matters with WebView2) -------------

GWLP_HWNDPARENT = -8
HWND_TOPMOST = wintypes.HWND(-1)
SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x0010, 0x0040
SW_HIDE, SW_SHOWNOACTIVATE = 0, 4


def _load_user32():
    try:
        lib = ctypes.WinDLL("user32", use_last_error=True)
    except (AttributeError, OSError):
        return None
    lib.SetWindowLongPtrW.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t)
    lib.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    lib.SetWindowPos.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, ctypes.c_uint)
    lib.SetWindowPos.restype = wintypes.BOOL
    lib.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
    lib.ShowWindow.restype = wintypes.BOOL
    lib.FindWindowW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
    lib.FindWindowW.restype = wintypes.HWND
    return lib


_user32 = _load_user32()


def _hwnd():
    return _user32.FindWindowW(None, TITLE) if _user32 is not None else None


def _show_window(window):
    hwnd = _hwnd()
    if hwnd:
        _user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)


def _hide_window(window):
    hwnd = _hwnd()
    if hwnd:
        _user32.ShowWindow(hwnd, SW_HIDE)


def _navigate_window(window, url):
    try:
        window.load_url(url)
    except Exception as e:  # noqa: BLE001 - it may be closing
        log.info("OSIRIS would not load its new layers: %s", e)


def _navigate_window(window, url):
    try:
        window.load_url(url)
    except Exception as e:  # noqa: BLE001 - it may be closing
        log.info("OSIRIS would not load its new layers: %s", e)


def _destroy_window(window):
    try:
        window.destroy()
    except Exception as e:  # noqa: BLE001 - it may already be gone
        log.info("OSIRIS window would not close: %s", e)
