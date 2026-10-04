"""The crew's standing jobs: work the agents do on their own, every day,
without being asked - aimed at money.

    MONEYPENNY  weekdays, before the US open: the whole watchlist - what to
                add to, hold, or pull money out of - and it is emailed.
    THEIA       every evening: your ideas, judged for which could earn, and
                the cheapest way to start the best one this week.
    LYLA        every morning: three concrete ways to make money this week
                that fit what you follow, with where to start.

A routine job is like any other (its card, its report) but Apollo does not
interrupt you to say it: it waits in crew_findings, and MONEYPENNY's goes to
your inbox. APOLLO_ROUTINES=0 turns them off. Each runs at most once a day.
"""

import datetime as dt
import json
import logging
import os
import threading

log = logging.getLogger("apollo.routines")

STATE = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                     "Apollo", "routines.json")

# (agent, hour from, weekdays only)
ROUTINES = {
    "MONEYPENNY": (15, True),
    "THEIA": (20, False),
    "SHORTS": (int(os.environ.get("SHORTS_HOUR") or 13), False),   # a Short a day at the peak hour
}


ON_POSTED = None    # Apollo says it when a Short goes up on its own


def enabled():
    return os.environ.get("APOLLO_ROUTINES", "1").strip().lower() not in ("0", "false", "no", "off")


def _load(path=STATE):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(data, path=STATE):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        log.info("routines: could not save state", exc_info=True)


def due(now, last):
    """The agents whose routine is due at `now`, given `last` {agent: date}."""
    out = []
    for agent, (hour, weekdays) in ROUTINES.items():
        if weekdays and now.weekday() >= 5:
            continue
        if now.hour >= hour and last.get(agent) != now.date().isoformat():
            out.append(agent)
    return out


def _ideas_text():
    try:
        import ideas
        return "; ".join(i.get("text", "") for i in ideas.all()[:15]) or ""
    except Exception:  # noqa: BLE001
        return ""


def _interests_text():
    try:
        import interests
        found = interests.load().get("interests", [])
        return ", ".join(i["name"] for i in sorted(found, key=lambda i: -i.get("weight", 0))[:10])
    except Exception:  # noqa: BLE001
        return ""


def start_job(agent):
    """Hand `agent` its routine. Returns the desk's answer, or None."""
    import crew
    if agent == "MONEYPENNY":
        symbols = crew.watchlist_symbols()
        if not symbols:
            return None
        return crew.MONEYPENNY_DESK.take(
            "Daily review of my watchlist: for each stock say BUY MORE, HOLD or PULL MONEY "
            "OUT, with the one reason that decides it. Lead with the single most important move today.",
            "", symbols=symbols, routine=True, email=True)
    if agent == "THEIA":
        ideas = _ideas_text()
        task = ("Which of my ideas could earn money soonest, and the cheapest way to start "
                "the best one this week, step by step." + (f" My ideas: {ideas}" if ideas else
                " I have no ideas saved: suggest three that a solo developer with an AI "
                "voice assistant project could earn from."))
        return crew.THEIA_DESK.take(task, routine=True)
    if agent == "SHORTS":
        import autopost
        if not autopost.due_today(dt.date.today(), autopost.load().get("asked", "")[:10]):
            return None
        return crew.desk("LYLA").take("Make today's Shorts from the trends", short=True,
                                      batch=autopost.COUNT)
    if agent == "LYLA":
        likes = _interests_text()
        return crew.desk("LYLA").take(
            "Find three concrete ways I can make money online this week - real platforms, "
            "real current demand, what it pays, and the first step."
            + (f" I follow: {likes}." if likes else ""), routine=True)
    return None


def tick(now=None, path=STATE):
    """Start whatever is due. Returns the agents started."""
    if not enabled():
        return []
    now = now or dt.datetime.now()
    last = _load(path)
    started = []
    for agent in due(now, last):
        try:
            if start_job(agent) is not None:
                started.append(agent)
        except Exception:  # noqa: BLE001 - one routine never stops the others
            log.warning("routine for %s failed to start", agent, exc_info=True)
        last[agent] = now.date().isoformat()
    if started or last:
        _save(last, path)
    try:
        import autopost
        posted = autopost.tick(now)
        if posted and ON_POSTED:
            ON_POSTED(posted)
    except Exception:  # noqa: BLE001
        log.warning("short auto-post failed", exc_info=True)
    return started


def start(stopping):
    """Check every ten minutes, on a thread, until `stopping()`."""
    def loop():
        while not stopping():
            try:
                tick()
            except Exception:  # noqa: BLE001
                log.warning("routines tick failed", exc_info=True)
            for _ in range(600):
                if stopping():
                    return
                threading.Event().wait(1)
    threading.Thread(target=loop, daemon=True, name="crew-routines").start()
