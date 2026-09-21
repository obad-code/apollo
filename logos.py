"""Company marks for the stock cards.

They come from a public endpoint one symbol at a time, and they are cached on
disk because they never change and because a card must not wait on a network
fetch to paint. The cache lives under the display's own directory so
pywebview's HTTP server can serve them to the page - it roots at the page,
and nothing above it is reachable - and it is kept out of git: these are
other companies' trademarks, not Apollo's to redistribute.

Nothing here raises. A mark that will not come is a card without a mark.
"""

import logging
import os
import re
import threading

import urllib.request

log = logging.getLogger("apollo.logos")

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "ui", "full", "logos")
SOURCE = "https://financialmodelingprep.com/image-stock/{symbol}.png"
HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")}
TIMEOUT = 6
MAX_BYTES = 512 * 1024

# A symbol arrives off a feed and is about to name a file. Letters, digits,
# a dot and a dash are every real ticker; anything else is refused rather
# than sanitised, because a symbol that needs sanitising is not a symbol.
SAFE = re.compile(r"^[A-Za-z0-9.\-^]{1,12}$")

# PNG, JPEG, GIF and SVG. The endpoint answers 200 with an HTML page for some
# symbols, and an HTML file written as NVDA.png is worse than no file.
MAGIC = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF8", b"<svg", b"<?xml")

_misses = set()          # symbols the source has no mark for
_lock = threading.Lock()


def _download(url):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read(MAX_BYTES)


def _looks_like_an_image(data):
    return bool(data) and any(data.startswith(magic) for magic in MAGIC)


def path_for(symbol):
    """The mark's file on disk, fetching it the first time. None if there is none."""
    if not symbol or not SAFE.match(symbol):
        return None
    name = symbol.upper() + ".png"
    destination = os.path.join(CACHE, name)
    if os.path.exists(destination):
        return destination
    with _lock:
        if symbol.upper() in _misses:
            return None
    try:
        data = _download(SOURCE.format(symbol=symbol.upper()))
        if not _looks_like_an_image(data):
            raise ValueError("not an image")
        os.makedirs(CACHE, exist_ok=True)
        # Written beside and renamed, so a half-written file is never read as
        # a mark by the next call.
        partial = destination + ".part"
        with open(partial, "wb") as handle:
            handle.write(data)
        os.replace(partial, destination)
        return destination
    except Exception as exc:  # noqa: BLE001 - a missing mark is not a failure
        log.debug("no mark for %s: %s", symbol, exc)
        with _lock:
            _misses.add(symbol.upper())
        return None


def url_for(symbol):
    """What the display asks for, relative to the page that loads it."""
    path = path_for(symbol)
    return f"logos/{os.path.basename(path)}" if path else None
