"""Reminder storage, scheduling, and the background watcher that fires them.

Knows about the clock and the disk; knows nothing about Claude. The watcher
runs on its own thread and calls back into whoever started it when something
comes due, so this module never speaks or draws anything itself.

Times are naive local datetimes throughout. An ISO string that arrives with a
timezone is converted to local time and flattened, so everything downstream can
compare datetimes without worrying about which are aware.
"""

import json
import os
import threading
import time
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(HERE, "reminders.json")

CHECK_SECONDS = 5        # how often the watcher looks for due reminders
MAX_HORIZON_DAYS = 365   # refuse anything further out than this
LATE_AFTER_SECONDS = 120  # past this, a reminder announces itself as late

# Guards both the in-memory list and the file behind it.
_lock = threading.RLock()
_reminders = None  # None until first load
_next_id = 1


# --- storage ---------------------------------------------------------------


def _load():
    """Read the store from disk. Corrupt or missing file means start empty."""
    global _reminders, _next_id

    if _reminders is not None:
        return _reminders

    _reminders = []
    try:
        with open(STORE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            _reminders = [r for r in data if isinstance(r, dict) and "due" in r]
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError):
        # A damaged store must not stop the assistant from starting. Losing
        # pending reminders is bad; refusing to boot is worse.
        _reminders = []

    _next_id = max((r.get("id", 0) for r in _reminders), default=0) + 1
    return _reminders


def _save():
    """Write the store out atomically, so a crash mid-write can't corrupt it."""
    tmp = STORE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_reminders, f, indent=2)
        os.replace(tmp, STORE)
    except OSError:
        pass  # can't persist; the in-memory copy still fires this session


# --- time handling ---------------------------------------------------------


def _to_local_naive(dt):
    """Flatten an aware datetime to naive local time; leave naive ones alone."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone().replace(tzinfo=None)


def parse_when(when=None, in_minutes=None, now=None):
    """Work out when a reminder is due.

    Raises ValueError with a message written to be handed straight back to
    Claude as a tool result - it says what was wrong *and* what the time is
    now, so a wrong guess can be corrected without another round trip.
    """
    now = now or datetime.now()

    if in_minutes is not None:
        try:
            minutes = float(in_minutes)
        except (TypeError, ValueError):
            raise ValueError(f"in_minutes must be a number, got {in_minutes!r}.")
        if minutes <= 0:
            raise ValueError("in_minutes must be greater than zero.")
        if minutes > MAX_HORIZON_DAYS * 24 * 60:
            raise ValueError(f"That is further out than {MAX_HORIZON_DAYS} days.")
        return now + timedelta(minutes=minutes)

    if not when:
        raise ValueError("Give either in_minutes or when.")

    try:
        due = _to_local_naive(datetime.fromisoformat(str(when).strip()))
    except ValueError:
        raise ValueError(
            f"Could not read {when!r} as an ISO 8601 time. Use a form like "
            f"2026-09-13T15:00:00. It is now {now.isoformat(timespec='seconds')}."
        )

    if due <= now:
        raise ValueError(
            f"{due.isoformat(timespec='seconds')} is in the past. It is now "
            f"{now.isoformat(timespec='seconds')} - work the time out from that."
        )
    if due > now + timedelta(days=MAX_HORIZON_DAYS):
        raise ValueError(f"That is further out than {MAX_HORIZON_DAYS} days.")

    return due


def say_when(due, now=None):
    """A spoken-friendly description of when something is due."""
    now = now or datetime.now()
    delta = due - now
    minutes = delta.total_seconds() / 60

    if minutes < 1:
        return "in less than a minute"
    if minutes < 60:
        return f"in {round(minutes)} minutes"
    if due.date() == now.date():
        return f"today at {due.strftime('%I:%M %p').lstrip('0')}"
    if due.date() == (now + timedelta(days=1)).date():
        return f"tomorrow at {due.strftime('%I:%M %p').lstrip('0')}"
    return f"on {due.strftime('%A %d %B')} at {due.strftime('%I:%M %p').lstrip('0')}"


# --- the operations Claude drives ------------------------------------------


def add(text, when=None, in_minutes=None):
    """Store a reminder. Returns a status string for the tool result."""
    global _next_id

    text = (text or "").strip()
    if not text:
        return "Failed: no reminder text was given."

    try:
        due = parse_when(when, in_minutes)
    except ValueError as e:
        return f"Failed: {e}"

    with _lock:
        _load()
        reminder = {
            "id": _next_id,
            "text": text,
            "due": due.isoformat(timespec="seconds"),
            "created": datetime.now().isoformat(timespec="seconds"),
        }
        _next_id += 1
        _reminders.append(reminder)
        _save()

    return f"Reminder set for {say_when(due)}: {text}"


def pending():
    """Every reminder still waiting, soonest first."""
    with _lock:
        _load()
        return sorted(_reminders, key=lambda r: r["due"])


def describe_pending():
    """A spoken-friendly list of what's outstanding, for the tool result."""
    items = pending()
    if not items:
        return "There are no reminders set."

    lines = [f"{len(items)} reminder(s):"]
    for r in items:
        lines.append(f"- {r['text']} ({say_when(_due_of(r))})")
    return "\n".join(lines)


def cancel(which):
    """Cancel by 'all', by id, or by a substring of the reminder text."""
    which = (which or "").strip()
    if not which:
        return "Failed: say which reminder to cancel."

    with _lock:
        _load()
        if which.lower() == "all":
            count = len(_reminders)
            _reminders.clear()
            _save()
            return f"Cancelled all {count} reminder(s)." if count else "Nothing to cancel."

        matches = [r for r in _reminders if str(r["id"]) == which]
        if not matches:
            needle = which.lower()
            matches = [r for r in _reminders if needle in r["text"].lower()]

        if not matches:
            return f"Failed: no reminder matching '{which}'."
        if len(matches) > 1:
            listed = ", ".join(r["text"] for r in matches)
            return f"Failed: '{which}' matches several - {listed}. Be more specific."

        _reminders.remove(matches[0])
        _save()
        return f"Cancelled: {matches[0]['text']}"


# --- the watcher -----------------------------------------------------------


def _due_of(reminder):
    try:
        return datetime.fromisoformat(reminder["due"])
    except (ValueError, KeyError):
        # An unreadable due time would otherwise wedge the watcher forever,
        # so treat it as due now and let it fire and clear itself.
        return datetime.min


def take_due(now=None):
    """Remove and return everything that has come due.

    Removing before firing is deliberate: if speaking throws, the reminder is
    gone rather than repeating every five seconds forever.
    """
    now = now or datetime.now()
    with _lock:
        _load()
        due = [r for r in _reminders if _due_of(r) <= now]
        if due:
            for r in due:
                _reminders.remove(r)
            _save()
    return sorted(due, key=lambda r: r["due"])


def start_watcher(fire, gate, stop):
    """Run the background watcher until `stop()` says otherwise.

    `fire(reminder, late)` speaks and displays one reminder. `gate` is a lock
    held for the duration of a user's turn - the watcher takes it before firing
    so a reminder can never talk over a question, an answer, or the microphone.
    It waits its turn instead, which is the right trade: a reminder five
    seconds late is fine, a reminder shouted over your sentence is not.
    """

    def loop():
        # SAPI drives COM, which needs initialising per thread. Piper doesn't,
        # but the fallback path might get used from here.
        try:
            import comtypes
            comtypes.CoInitialize()
        except Exception:
            pass

        while not stop():
            try:
                for reminder in take_due():
                    if stop():
                        return
                    late = (
                        datetime.now() - _due_of(reminder)
                    ).total_seconds() > LATE_AFTER_SECONDS
                    with gate:
                        if stop():
                            return
                        fire(reminder, late)
            except Exception:
                # The watcher outliving one bad reminder matters more than
                # surfacing why it failed - it has no channel to report on.
                pass
            time.sleep(CHECK_SECONDS)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    return thread
