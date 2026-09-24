"""Apollo's record of your days, kept on this PC and nowhere else.

What you said, what he answered, the tools he used, and the stories and
stocks you opened on the display - one JSON line each, in one file a day
under %LOCALAPPDATA%\\Apollo\\journal. It is what the nightly pass reads to
learn what you care about (profile.py), so that he knows you without being
told, and what Private Eye hunts for.

Nothing here leaves the machine by itself, nothing here raises, and the last
KEEP_DAYS days are all that is kept.
"""

import datetime
import json
import logging
import os
import shutil
import threading

log = logging.getLogger("apollo.journal")

ROOT = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                    "Apollo", "journal")
KEEP_DAYS = 60
# Long enough for any sentence you would say or a reply he would speak; a
# pasted essay does not need to be kept whole to be learned from.
TRIM = 400

_lock = threading.Lock()
_pruned_on = None


def _path(day):
    return os.path.join(ROOT, day.isoformat() + ".jsonl")


def _trim(value):
    if isinstance(value, str) and len(value) > TRIM:
        return value[:TRIM] + "…"
    if isinstance(value, dict):
        return {k: _trim(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_trim(v) for v in value][:20]
    return value


def write(kind, **fields):
    """Add one entry to today's record. Never raises."""
    global _pruned_on
    now = datetime.datetime.now()
    entry = {"at": now.isoformat(timespec="seconds"), "kind": kind}
    entry.update(_trim(fields))
    try:
        line = json.dumps(entry, ensure_ascii=False, default=str)
        with _lock:
            os.makedirs(ROOT, exist_ok=True)
            with open(_path(now.date()), "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
            first_today = _pruned_on != now.date()
            _pruned_on = now.date()
        if first_today:
            prune()
    except (OSError, TypeError, ValueError) as e:
        log.debug("could not write the journal: %s", e)


# The three things the rest of Apollo records, by name.

def said(text):
    if text:
        write("you", text=text)


def answered(text, who="Apollo"):
    if text:
        write("apollo", text=text, who=who)


def opened(what, title, source=""):
    if title:
        write("opened", what=what, title=title, source=source)


def day(date):
    """Every entry of one day, oldest first. A damaged line is skipped."""
    entries = []
    try:
        with open(_path(date), encoding="utf-8") as handle:
            for line in handle:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if isinstance(entry, dict):
                    entries.append(entry)
    except OSError:
        pass
    return entries


def days():
    """The days there is a record of, oldest first."""
    found = []
    try:
        for name in os.listdir(ROOT):
            if name.endswith(".jsonl"):
                try:
                    found.append(datetime.date.fromisoformat(name[:-6]))
                except ValueError:
                    continue
    except OSError:
        pass
    return sorted(found)


def prune(today=None):
    """Let go of the days past KEEP_DAYS."""
    today = today or datetime.date.today()
    cutoff = today - datetime.timedelta(days=KEEP_DAYS)
    for old in days():
        if old < cutoff:
            try:
                os.remove(_path(old))
            except OSError:
                pass


def forget():
    """Delete the whole record."""
    with _lock:
        shutil.rmtree(ROOT, ignore_errors=True)
