"""Ideas for new projects, said to Apollo and kept for later.

"Idea: a Discord bot for the clan" - kept in %LOCALAPPDATA%\\Apollo\\ideas.json,
newest first, on the display's Ideas tab beside your reminders, and read
back when you ask. Nothing here raises.
"""

import json
import logging
import os
import threading
import time
import uuid

import feeds
import journal

log = logging.getLogger("apollo.ideas")

PATH = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                    "Apollo", "ideas.json")
MOST = 100

_lock = threading.Lock()


def _read():
    try:
        with open(PATH, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    return [i for i in data if isinstance(i, dict) and i.get("text")] if isinstance(data, list) else []


def _write(items):
    try:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        temporary = PATH + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(items, handle, ensure_ascii=False)
        os.replace(temporary, PATH)
    except OSError as e:
        log.info("could not save the ideas: %s", e)


def all():  # noqa: A001 - read as ideas.all()
    """Every idea, newest first, with how long ago it was had."""
    now = time.time()
    with _lock:
        items = _read()
    return [dict(i, age=feeds.age_words(now - i.get("at", now)))
            for i in sorted(items, key=lambda i: -i.get("at", 0))]


def add(text):
    idea = {"id": uuid.uuid4().hex[:10], "text": str(text).strip()[:400], "at": time.time()}
    with _lock:
        items = _read()
        items.append(idea)
        _write(items[-MOST:])
    journal.write("idea", text=idea["text"])
    return idea


def remove(idea_id):
    with _lock:
        items = _read()
        kept = [i for i in items if i.get("id") != idea_id]
        if len(kept) == len(items):
            return False
        _write(kept)
    return True
