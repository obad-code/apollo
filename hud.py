"""The normal display as a HUD you arrange: where each panel is, how big,
how large what is inside it is drawn, and whether it is hidden - kept, so
the screen you set up is the one you get tomorrow.

The page does the arranging (ui/full/hud.js) and sends the result over the
bridge; this cleans it by the same rules, keeps it beside the ultra layout
and hands it back as the display opens. tests/test_hud.py runs both
cleaners on the same input.

Each panel is kept as fractions of the stage - x, y, w, h - with `s` its
scale and `hidden`. `free` is whether there is an arrangement at all: until
you first move something the display lays itself out.
"""

import json
import logging
import math
import os
import threading

log = logging.getLogger("apollo.hud")

PATH = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                    "Apollo", "hud.json")

PANELS = ("today", "markets", "system", "core", "lyla", "feed", "scan",
          "console-left", "console-right")
MIN_W = 0.08
MIN_H = 0.04
SCALE_MIN = 0.6
SCALE_MAX = 1.6

_memo = None
_lock = threading.Lock()


def empty():
    return {"free": False, "items": {}}


def _finite(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _fixed(value):
    # Four places, halves up - the way hud.js rounds, so both keep the same.
    return math.floor(value * 10000 + 0.5) / 10000


def _clamp(value, low, high):
    return min(high, max(low, value))


def _item(raw):
    if not isinstance(raw, dict) or not all(_finite(raw.get(k)) for k in ("x", "y", "w", "h")):
        return None
    w = _fixed(_clamp(raw["w"], MIN_W, 1))
    h = _fixed(_clamp(raw["h"], MIN_H, 1))
    return {"x": _fixed(_clamp(raw["x"], 0, 1 - w)), "y": _fixed(_clamp(raw["y"], 0, 1 - h)),
            "w": w, "h": h,
            "s": _fixed(_clamp(raw["s"], SCALE_MIN, SCALE_MAX)) if _finite(raw.get("s")) else 1,
            "hidden": raw.get("hidden") is True}


def sanitize(raw):
    """A HUD made safe to keep and lay out, exactly as hud.sanitize does."""
    out = empty()
    if not isinstance(raw, dict):
        return out
    given = raw.get("items") if isinstance(raw.get("items"), dict) else {}
    for panel in PANELS:
        item = _item(given.get(panel))
        if item is not None:
            out["items"][panel] = item
    out["free"] = raw.get("free") is True and all(p in out["items"] for p in PANELS)
    return out


def state():
    """The HUD as the page last left it - none arranged if nothing is kept."""
    global _memo
    with _lock:
        if _memo is not None:
            return json.loads(json.dumps(_memo))
    try:
        with open(PATH, encoding="utf-8") as handle:
            loaded = sanitize(json.load(handle))
    except (OSError, ValueError):
        loaded = empty()
    with _lock:
        _memo = loaded
    return json.loads(json.dumps(loaded))


def save(layout):
    """Keep what the page arranged. Returns it, cleaned."""
    global _memo
    clean = sanitize(layout)
    with _lock:
        _memo = clean
    try:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        with open(PATH, "w", encoding="utf-8") as handle:
            json.dump(clean, handle)
    except OSError as e:
        log.info("could not keep the HUD: %s", e)
    return json.loads(json.dumps(clean))
