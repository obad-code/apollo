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


# -- THEIA's read of each idea ----------------------------------------------------------------

THEIA_TASK = ("Analyse this idea the user saved, properly: what it really is, how it could work, "
              "what it needs, the risks, and the best way to do it - concrete first steps. Their idea: {text}")


def send_to_theia(idea, take=None):
    """Hand a new idea to THEIA, quietly: no announcement when she is done - it waits on the idea."""
    try:
        if take is None:
            if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")):
                return False                     # nothing for her to think with
            import crew
            take = crew.desk("THEIA").take
        take(THEIA_TASK.format(text=idea["text"]), idea=idea["id"], routine=True)
        return True
    except Exception:  # noqa: BLE001 - the idea is kept either way
        log.info("idea not sent to THEIA", exc_info=True)
        return False


def attach(idea_id, summary, report):
    """THEIA's analysis, kept on the idea itself."""
    with _lock:
        items = _read()
        for i in items:
            if i.get("id") == idea_id:
                i["theia"] = {"summary": str(summary)[:600], "report": str(report)[:12000],
                              "at": time.time(), "seen": False}
                _write(items)
                return True
    return False


def unseen():
    """Ideas THEIA has analysed that you have not looked at yet."""
    with _lock:
        return [i for i in _read() if (i.get("theia") or {}).get("seen") is False]


def mark_seen():
    with _lock:
        items = _read()
        for i in items:
            if i.get("theia"):
                i["theia"]["seen"] = True
        _write(items)
    return True


def waiting():
    """Ideas THEIA has not analysed yet (for a catch-up at start)."""
    with _lock:
        return [i for i in _read() if not i.get("theia")]
