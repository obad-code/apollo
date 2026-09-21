"""Prayer times for Riyadh, and the reminder before each one.

Times come from Aladhan with method 4 - Umm al-Qura, which is what Saudi
Arabia actually uses. The method matters: another one moves Fajr and Isha by
up to twenty minutes, and a reminder that is twenty minutes out is worse than
no reminder.

A day is fetched once and kept on disk, so the machine can be offline for the
rest of it. Nothing here raises: no times means no reminder, never a failed
turn.
"""

import datetime
import json
import logging
import os
import threading
import urllib.parse
import urllib.request

log = logging.getLogger("apollo.prayer")

CITY = "Riyadh"
COUNTRY = "Saudi Arabia"
METHOD = 4                   # Umm al-Qura University, Makkah
ENDPOINT = "https://api.aladhan.com/v1/timingsByCity"
HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")}
TIMEOUT = 8

CACHE = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                     "Apollo", "prayer.json")

# The five. Sunrise comes back in the same payload and is not one of them.
PRAYERS = ("Fajr", "Dhuhr", "Asr", "Maghrib", "Isha")

LEAD_MINUTES = 15            # how long before a prayer the reminder comes
WINDOW_MINUTES = 6           # how late a missed tick may still announce it

_memo = {}                   # date -> {name: datetime}
_lock = threading.Lock()


def _download(day):
    """Aladhan's timings for one day, as {name: "HH:MM"}."""
    query = urllib.parse.urlencode({"city": CITY, "country": COUNTRY,
                                    "method": METHOD,
                                    "date": day.strftime("%d-%m-%Y")})
    request = urllib.request.Request(f"{ENDPOINT}?{query}", headers=HEADERS)
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        data = json.load(response)
    return data["data"]["timings"]


def _read_cache(key):
    try:
        with open(CACHE, encoding="utf-8") as handle:
            return json.load(handle).get(key)
    except (OSError, ValueError):
        return None


def _write_cache(key, timings):
    try:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        try:
            with open(CACHE, encoding="utf-8") as handle:
                kept = json.load(handle)
        except (OSError, ValueError):
            kept = {}
        # Only today and tomorrow are worth keeping; the rest is history.
        kept = {k: v for k, v in kept.items() if k >= key}
        kept[key] = timings
        with open(CACHE, "w", encoding="utf-8") as handle:
            json.dump(kept, handle)
    except OSError as e:
        log.info("could not save prayer times: %s", e)


def times(day=None):
    """The five prayers for `day`, as datetimes. Empty if they cannot be had."""
    day = day or datetime.date.today()
    key = day.isoformat()
    with _lock:
        if key in _memo:
            return dict(_memo[key])

    timings = _read_cache(key)
    if timings is None:
        try:
            timings = _download(day)
            _write_cache(key, timings)
        except Exception as e:  # noqa: BLE001 - a reminder, not the day
            log.info("prayer times unavailable: %s", e)
            return {}

    out = {}
    for name in PRAYERS:
        raw = (timings or {}).get(name) or ""
        # Aladhan appends the zone, as in "17:51 (+03)".
        clock = raw.split(" ")[0].strip()
        try:
            hour, minute = (int(part) for part in clock.split(":")[:2])
            out[name] = datetime.datetime.combine(day, datetime.time(hour, minute))
        except (ValueError, TypeError):
            continue
    if out:
        with _lock:
            _memo[key] = dict(out)
    return out


def next_prayer(now=None):
    """The next prayer and when it is, looking into tomorrow if it has to."""
    now = now or datetime.datetime.now()
    today = times(now.date())
    for name in PRAYERS:
        when = today.get(name)
        if when is not None and when > now:
            return name, when
    tomorrow = times(now.date() + datetime.timedelta(days=1))
    for name in PRAYERS:
        when = tomorrow.get(name)
        if when is not None:
            return name, when
    return None, None


class Watch:
    """Whether a prayer reminder is due, and whether it has been given.

    Kept in memory: a reminder missed because Apollo was restarted is a
    reminder missed, and saying it twice would be worse than saying it late.
    """

    def __init__(self, lead_minutes=LEAD_MINUTES, window_minutes=WINDOW_MINUTES):
        self.lead = datetime.timedelta(minutes=lead_minutes)
        self.window = datetime.timedelta(minutes=window_minutes)
        self.given = set()

    def due(self, now=None):
        """`(name, when)` if it is time to say one, else None.

        The window exists because this is polled: a tick that lands a minute
        late must still announce, and one that lands after the prayer has
        begun must not - fifteen minutes late is not a reminder.
        """
        now = now or datetime.datetime.now()
        for name, when in sorted(times(now.date()).items(), key=lambda kv: kv[1]):
            if when <= now:
                continue                       # already begun
            remaining = when - now
            if remaining > self.lead:
                continue                       # not yet
            if remaining < self.lead - self.window:
                continue                       # too late to call it a warning
            key = (now.date().isoformat(), name)
            if key in self.given:
                continue
            self.given.add(key)
            return name, when
        return None
