"""Which panels the full display is showing.

"Take the stocks off the screen" has to work, and has to still be true
tomorrow, so this is a file rather than a flag. Panels answer to the words
someone would actually say for them, in either language - the display is
read in Arabic as often as in English.

Nothing here raises. A panel nobody has heard of is refused with a sentence
that names the ones that exist, because "I don't know that one" on its own
is not an answer.
"""

import json
import logging
import os
import threading

log = logging.getLogger("apollo.panels")

PATH = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                    "Apollo", "panels.json")

# id -> every word that should find it. First entry is what Apollo calls it
# back when it is talking about it.
PANELS = {
    "markets": ("stocks", "stock", "market", "markets", "watchlist", "shares",
                "الأسهم", "الاسهم", "السوق", "سهم"),
    "feed": ("news", "feed", "headlines", "stories", "posts", "trump",
             "الأخبار", "الاخبار", "اخبار", "ترمب", "ترامب"),
    "clock": ("clock", "time", "date", "weather",
              "الساعة", "الوقت", "التاريخ", "الطقس"),
    "status": ("status", "dots", "indicators",
               "الحالة", "المؤشرات"),
    # Still "strip" on disk, so a choice saved before the strip became the
    # system gauges carries over.
    "strip": ("system gauges", "gauges", "meters", "system", "strip", "tokens",
              "usage", "cost", "clips", "العدادات", "الشريط", "الاستهلاك", "النظام"),
    "lyla": ("lyla", "lila", "robot", "ليلى", "ليلا", "الروبوت"),
    "core": ("core", "ring", "apollo", "wordmark",
             "الحلقة", "ابولو", "أبولو"),
}

_memo = None
_lock = threading.Lock()


def resolve(said):
    """The panel a spoken phrase means, or None."""
    text = (said or "").strip().lower()
    if not text:
        return None
    # Longest word first, so "the stock market" is not answered by "stock"
    # when a longer phrase would have matched something else.
    best = None
    for panel, words in PANELS.items():
        for word in words:
            if word in text and (best is None or len(word) > best[1]):
                best = (panel, len(word))
    return best[0] if best else None


def state():
    """Every panel and whether it is shown."""
    global _memo
    with _lock:
        if _memo is not None:
            return dict(_memo)
    hidden = []
    try:
        with open(PATH, encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, list):
            hidden = [p for p in loaded if p in PANELS]
    except (OSError, ValueError) as e:
        log.info("panel state unreadable, showing everything: %s", e)
    current = {panel: panel not in hidden for panel in PANELS}
    with _lock:
        _memo = dict(current)
    return dict(current)


def visible(panel):
    return state().get(panel, True)


def _save(current):
    global _memo
    with _lock:
        _memo = dict(current)
    try:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        with open(PATH, "w", encoding="utf-8") as handle:
            json.dump([p for p, shown in current.items() if not shown], handle)
    except OSError as e:
        log.info("could not save the panel state: %s", e)


def _unknown(said):
    names = ", ".join(words[0] for words in PANELS.values())
    return {"ok": False,
            "error": f"I don't have a panel called {said}. There's {names}."}


def _set(said, shown):
    panel = resolve(said)
    if panel is None:
        return _unknown(said)
    current = state()
    current[panel] = shown
    _save(current)
    return {"ok": True, "panel": panel, "shown": shown, "panels": current}


def hide(said):
    return _set(said, False)


def show(said):
    return _set(said, True)
