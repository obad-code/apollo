"""What Apollo found wrong with itself, kept for you to fix later.

The checks at startup (diagnostics.py) and the things that go wrong while
it runs - a voice session that would not open, a recorder that keeps dying
- each record an issue here, by a key of its own: the same problem again is
counted rather than listed twice, and it goes when it is fixed (the check
passing again resolves it) or when you dismiss it on the System panel.

Kept in %LOCALAPPDATA%\\Apollo\\issues.json, so an issue from the morning is
still there in the evening. A damaged file is an empty list, never a crash.
"""

import json
import logging
import os
import threading
import time

log = logging.getLogger("apollo.issues")

PATH = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                    "Apollo", "issues.json")

MOST = 30                  # the newest this many are kept
LEVELS = ("fail", "warn")  # a failure is something that does not work; a warning, something less

_lock = threading.Lock()
_listener = None


def set_listener(fn):
    """`fn(current())` after every change - the display's System panel."""
    global _listener
    _listener = fn


def _read():
    try:
        with open(PATH, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError, UnicodeDecodeError):
        return []
    return [i for i in data if isinstance(i, dict) and i.get("key")] if isinstance(data, list) else []


def _write(items):
    try:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        temporary = PATH + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(items, handle, ensure_ascii=False, indent=1)
        os.replace(temporary, PATH)
    except OSError as e:
        log.warning("could not keep the issues: %s", e)


def _ordered(items):
    return sorted(items, key=lambda i: (i.get("level") != "fail", -float(i.get("last") or 0)))


def _changed(items):
    listener = _listener
    if listener is not None:
        try:
            listener(_ordered(items))
        except Exception:  # noqa: BLE001 - a display that is not there must not lose the issue
            log.debug("issue listener failed", exc_info=True)


def current():
    """Every issue kept: failures first, then the newest."""
    with _lock:
        return _ordered(_read())


def record(key, title, detail="", level="warn", now=None):
    """Keep issue `key`, or count it again if it is already kept."""
    now = time.time() if now is None else now
    level = level if level in LEVELS else "warn"
    with _lock:
        items = _read()
        found = next((i for i in items if i["key"] == key), None)
        if found is None:
            found = {"key": key, "first": now, "count": 0}
            items.append(found)
        found.update(title=str(title), detail=str(detail or ""), level=level, last=now,
                     count=int(found.get("count") or 0) + 1)
        items = sorted(items, key=lambda i: -float(i.get("last") or 0))[:MOST]
        _write(items)
    _changed(items)
    return found


def resolve(key):
    """Issue `key` fixed, or dismissed. True if there was one."""
    with _lock:
        items = _read()
        kept = [i for i in items if i["key"] != key]
        if len(kept) == len(items):
            return False
        _write(kept)
    _changed(kept)
    return True
