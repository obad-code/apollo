"""Ultra mode's displays: where each one is on the screen, how big, whether it
is shown or minimized, which one is expanded - and the words that find each
one by voice, in either language. And whether the stocks and the feed are
folded away to a few, which the normal display shares.

The page lays them out and changes them as you drag, resize and hide them
(ui/full/tiles.js); this keeps what it last said, so the screen you set up
is the one you get tomorrow, and it is how "put the projects on my screen"
knows which display you meant. The two clean a layout the same way -
tests/test_displays.py runs both on the same input.

Nothing here raises: a layout that is not one is the default, and a display
nobody has heard of is refused with a sentence that names the ones there are.
"""

import json
import logging
import math
import os
import threading

log = logging.getLogger("apollo.displays")

PATH = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                    "Apollo", "layout.json")

COLUMNS = 12
ROWS = 12
MIN_W = 2

# The order they are packed in by default (tiles.DISPLAYS), each with its
# columns and rows.
ORDER = ("today", "osiris", "feed", "markets", "projects", "ideas", "core", "system", "talks")
SPANS = {"today": (3, 4), "osiris": (6, 8), "feed": (3, 8), "markets": (3, 8),
         "projects": (2, 4), "ideas": (2, 4), "core": (2, 4), "system": (3, 4),
         "talks": (3, 4)}

# osiris.LAYERS, each one a switch in the map's settings.
LAYERS = ("maritime", "cctv", "cctv_previews", "live_news", "earthquakes",
          "global_incidents", "day_night", "cables", "sdk_sea", "sdk_air", "sdk_naval")

# What Apollo calls each one when it talks about it.
NAMES = {"today": "today", "osiris": "OSIRIS", "feed": "the feed", "markets": "the stocks",
         "projects": "projects", "ideas": "ideas", "core": "Apollo",
         "system": "the system", "talks": "talks"}

# id -> every word that should find it.
WORDS = {
    "today": ("today", "clock", "time", "date", "weather", "prayer", "calendar",
              "اليوم", "الساعة", "الوقت", "التاريخ", "الطقس", "الصلاة"),
    "osiris": ("osiris", "world map", "intelligence map", "map",
               "اوزيرس", "أوزيرس", "اوزريس", "الخريطة", "الخريطه"),
    "feed": ("feed", "news", "headlines", "stories", "posts", "trump",
             "private eye", "الأخبار", "الاخبار", "اخبار", "ترمب", "ترامب"),
    "markets": ("stocks", "stock", "markets", "market", "watchlist", "shares",
                "الأسهم", "الاسهم", "السوق", "سهم"),
    "projects": ("projects", "project", "repos", "github", "claude code", "sessions",
                 "folders", "المشاريع", "مشاريع", "المشروع", "مشروع"),
    "ideas": ("ideas", "idea", "reminders", "الأفكار", "الافكار", "أفكار", "افكار",
              "فكرة", "التذكيرات"),
    "core": ("the ring", "ring", "core", "wordmark", "الحلقة"),
    "system": ("system", "gauges", "meters", "usage", "tokens", "status",
               "gemini", "claude", "cpu", "gpu", "النظام", "العدادات", "الاستهلاك",
               "الحالة", "جيميني", "كلود"),
    "talks": ("talks", "conversations", "history", "chats", "المحادثات", "محادثات",
              "السوالف"),
}

# Apollo's own name finds Apollo's display only when it is all that was said:
# in "Apollo, put the news up" it is who is being asked, not what for.
ONLY_ALONE = {"apollo": "core", "ابولو": "core", "أبولو": "core"}

_memo = None
_lock = threading.Lock()


def default():
    """The layout with nothing saved: every cell of the screen used once."""
    items = {d: {"shown": d != "talks", "w": SPANS[d][0], "h": SPANS[d][1], "min": False}
             for d in ORDER}
    return {"ultra": False, "focus": None, "order": list(ORDER), "items": items,
            "layers": list(LAYERS), "folded": False, "feedFolded": False}


def _whole(value, low, high, fallback):
    # Numbers only - the page writes nothing else - and rounded the way
    # JavaScript's Math.round does, halves up, so both sides agree.
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return fallback
    return max(low, min(high, math.floor(value + 0.5)))


def sanitize(raw):
    """A layout made safe to keep and lay out, exactly as tiles.sanitize does."""
    fresh = default()
    if not isinstance(raw, dict):
        return fresh
    order, seen = [], set()
    for display in raw.get("order") if isinstance(raw.get("order"), list) else []:
        if isinstance(display, str) and display in ORDER and display not in seen:
            seen.add(display)
            order.append(display)
    order += [d for d in ORDER if d not in seen]
    given = raw.get("items") if isinstance(raw.get("items"), dict) else {}
    items = {}
    for display in ORDER:
        was = fresh["items"][display]
        item = given.get(display) if isinstance(given.get(display), dict) else {}
        shown = item.get("shown")
        items[display] = {"shown": shown if isinstance(shown, bool) else was["shown"],
                          "w": _whole(item.get("w"), MIN_W, COLUMNS, was["w"]),
                          "h": _whole(item.get("h"), 1, ROWS, was["h"]),
                          "min": item.get("min") is True}
    layers = fresh["layers"]
    if isinstance(raw.get("layers"), list):
        wanted = raw["layers"]
        layers = [layer for i, layer in enumerate(wanted)
                  if isinstance(layer, str) and layer in LAYERS and wanted.index(layer) == i]
    focus = raw.get("focus")
    if not (isinstance(focus, str) and focus in ORDER
            and items[focus]["shown"] and not items[focus]["min"]):
        focus = None
    return {"ultra": raw.get("ultra") is True, "focus": focus, "order": order,
            "items": items, "layers": layers, "folded": raw.get("folded") is True,
            "feedFolded": raw.get("feedFolded") is True}


def state():
    """The layout as the page last left it."""
    global _memo
    with _lock:
        if _memo is not None:
            return json.loads(json.dumps(_memo))
    try:
        with open(PATH, encoding="utf-8") as handle:
            loaded = sanitize(json.load(handle))
    except (OSError, ValueError) as e:
        log.info("no layout kept, using the default: %s", e)
        loaded = default()
    with _lock:
        _memo = loaded
    return json.loads(json.dumps(loaded))


def ultra():
    return state()["ultra"]


def save(layout):
    """Keep what the page laid out. Returns it, cleaned."""
    global _memo
    clean = sanitize(layout)
    with _lock:
        _memo = clean
    try:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        with open(PATH, "w", encoding="utf-8") as handle:
            json.dump(clean, handle)
    except OSError as e:
        log.info("could not keep the layout: %s", e)
    return json.loads(json.dumps(clean))


def resolve(said):
    """The display a spoken phrase means, or None."""
    text = (said or "").strip().lower()
    if not text:
        return None
    alone = text.strip(" .,!?؟،").removeprefix("the ").strip()
    if alone in ONLY_ALONE:
        return ONLY_ALONE[alone]
    # The longest word that is in it: "claude code sessions" is the
    # projects, though "claude" alone would be the system.
    best = None
    for display, words in WORDS.items():
        for word in words:
            word = word.lower()
            if word in text and (best is None or len(word) > best[1]):
                best = (display, len(word))
    return best[0] if best else None


def name(display):
    """What Apollo calls a display when it talks about it."""
    return NAMES.get(display, display)


def unknown(said):
    names = ", ".join(name(d) for d in ORDER)
    return {"ok": False, "error": f"I don't have a display called {said}. There's {names}."}
