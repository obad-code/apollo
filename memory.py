"""What Apollo remembers because you told him to, and what was just said.

Two kinds of remembering, and both go into every voice session's
instructions when it opens:

  Memories   Things you asked him to keep - "remember that my car is a
             Tahoe", "تذكر ان موعدي مع الدكتور الاحد". Kept until you tell
             him to forget them, in %LOCALAPPDATA%\\Apollo\\memory.json.

  Recent     The last few exchanges from today's journal. A voice session
             does not outlive a reconnect - switching to always-listening,
             a dropped socket, the service's own time limit - and each new one
             used to start knowing nothing about the conversation it was in
             the middle of. This is what makes "and what about the other
             one?" still mean something after a reconnect.

Nothing here raises: a damaged file is an empty memory.
"""

import datetime
import json
import logging
import os
import threading
import time
import uuid

import journal

log = logging.getLogger("apollo.memory")

PATH = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                    "Apollo", "memory.json")
MOST = 200             # memories kept; the oldest go first past this
LONGEST = 500          # characters in one memory
RECENT_TURNS = 16      # journal lines carried into a new session
RECENT_HOURS = 6       # ...from no further back than this

_lock = threading.Lock()


def _read():
    try:
        with open(PATH, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError, UnicodeDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [m for m in data if isinstance(m, dict) and m.get("text")]


def _write(items):
    try:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        temporary = PATH + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(items, handle, ensure_ascii=False, indent=1)
        os.replace(temporary, PATH)
    except OSError as e:
        log.warning("could not keep the memories: %s", e)


def all_memories():
    """Every memory, oldest first."""
    with _lock:
        return _read()


def remember(text, now=None):
    """Keep `text`. The same thing twice is kept once. Returns the memory."""
    text = " ".join(str(text or "").split())[:LONGEST]
    if not text:
        raise ValueError("There was nothing to remember.")
    now = time.time() if now is None else now
    with _lock:
        items = _read()
        for item in items:
            if item["text"].casefold() == text.casefold():
                item["at"] = now
                _write(items)
                return item
        item = {"id": uuid.uuid4().hex[:8], "text": text, "at": now}
        items.append(item)
        _write(items[-MOST:])
        return item


def forget(query):
    """Drop the memories that `query` names: an id, or words they contain.
    Returns what was dropped."""
    query = str(query or "").strip().casefold()
    if not query:
        return []
    with _lock:
        items = _read()
        gone = [m for m in items
                if m.get("id") == query or query in m["text"].casefold()]
        if gone:
            _write([m for m in items if m not in gone])
        return gone


def recall(query=""):
    """The memories that mention `query` (all of them with none given)."""
    query = str(query or "").strip().casefold()
    items = all_memories()
    if not query:
        return items
    words = [w for w in query.split() if len(w) > 1]
    return [m for m in items
            if query in m["text"].casefold()
            or (words and all(w in m["text"].casefold() for w in words))]


def recent(now=None, turns=RECENT_TURNS, hours=RECENT_HOURS):
    """The last exchanges from the journal, oldest first, as (who, text)."""
    now = now or datetime.datetime.now()
    since = now - datetime.timedelta(hours=hours)
    lines = []
    for day in sorted({since.date(), now.date()}):
        for entry in journal.day(day):
            if entry.get("kind") not in ("you", "apollo") or not entry.get("text"):
                continue
            try:
                at = datetime.datetime.fromisoformat(entry.get("at", ""))
            except ValueError:
                continue
            if since <= at <= now:
                who = "User" if entry["kind"] == "you" else entry.get("who") or "Apollo"
                lines.append((who, entry["text"]))
    return lines[-turns:]


def summary(now=None):
    """Lines for a session's instructions: the memories, then the recent talk."""
    parts = []
    kept = all_memories()
    if kept:
        parts.append("Things the user asked you to remember (they are true until "
                     "the user says otherwise; use them without being asked):\n"
                     + "\n".join(f"- {m['text']}" for m in kept[-60:]))
    talk = recent(now)
    if talk:
        parts.append("The conversation so far today (you may have reconnected; "
                     "carry on from it naturally, do not repeat it back):\n"
                     + "\n".join(f"{who}: {text}" for who, text in talk))
    return "\n\n".join(parts)
