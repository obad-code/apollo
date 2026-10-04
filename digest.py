"""Your summary: the day on one quiet page - markets with their charts, your
stocks and their calls, how right MONEYPENNY has been, the weather, the news
that matters, earnings coming, reminders. Apollo never reads it out; the
button on the display lights up when a new one is ready.

A new summary is made twice a day while Apollo runs: in the morning (the
first time after 06:00) and after the US close (the first time after 16:30
New York). The page's refresh button makes one on demand.
"""

import datetime as dt
import json
import logging
import os

log = logging.getLogger("apollo.digest")

PATH = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Apollo", "digest.json")
MORNING = dt.time(6, 0)
US_CLOSE = dt.time(16, 30)
MOST_STOCKS = 8


def load(path=PATH):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data, path=PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def _new_york(now):
    try:
        from zoneinfo import ZoneInfo
        return now.astimezone(ZoneInfo("America/New_York"))
    except Exception:  # noqa: BLE001 - no tz database: Riyadh is NY + 7 most of the year
        return now - dt.timedelta(hours=7)


def due(now=None, last_iso=""):
    """Which edition is due now - "morning", "close" - or "" if none."""
    now = now or dt.datetime.now().astimezone()
    last = dt.datetime.fromisoformat(last_iso) if last_iso else None
    ny = _new_york(now)
    if ny.weekday() < 5 and ny.time() >= US_CLOSE:
        close_at = ny.replace(hour=US_CLOSE.hour, minute=US_CLOSE.minute, second=0, microsecond=0)
        if last is None or last < close_at:
            return "close"
    if now.time() >= MORNING:
        morning_at = now.replace(hour=MORNING.hour, minute=MORNING.minute, second=0, microsecond=0)
        if last is None or last < morning_at:
            return "morning"
    return ""


def _quote(symbol, spark=True):
    import market
    data = market.history(symbol, "1d") if spark else market.quote(symbol)
    points = [round(p, 2) for _, p in data.get("points", [])]
    if len(points) > 60:
        step = len(points) / 60
        points = [points[int(i * step)] for i in range(60)]
    return {"symbol": data["symbol"], "name": data.get("name", ""), "price": round(data["price"], 2),
            "change_pct": round(data["change_pct"], 2), "spark": points}


def _calls_now():
    """The last counted call per watched stock, from what the alerts keep."""
    import alerts
    try:
        with open(alerts.SEEN, encoding="utf-8") as f:
            seen = json.load(f)
    except (OSError, ValueError):
        return {}
    out = {}
    for key in seen:
        if key.startswith("verdict:"):
            _, symbol, verdict = key.split(":", 2)
            out[symbol] = verdict
    return out


def build(edition="", now=None):
    """Everything on the page. Every part may be empty; none can fail the rest."""
    now = now or dt.datetime.now().astimezone()
    out = {"made": now.isoformat(timespec="seconds"), "edition": edition or "now",
           "date": now.strftime("%A %d %B %Y"), "time": now.strftime("%H:%M")}

    def part(name, fn):
        try:
            out[name] = fn()
        except Exception as e:  # noqa: BLE001
            log.info("summary: %s unavailable (%s)", name, e)
            out[name] = None

    import briefing
    import feeds
    import market
    import reminders
    import watchlist
    import weather
    part("hijri", lambda: briefing.hijri(now.date()))
    part("weather", weather.now)
    part("status", lambda: market.market_status()["label"])
    part("indices", lambda: [_quote(s) for s in market.INDICES])
    part("verdicts", _calls_now)
    verdicts = out.get("verdicts") or {}

    def stocks():
        rows = []
        for s in watchlist.current()[:MOST_STOCKS]:
            try:
                q = _quote(s)
            except Exception:  # noqa: BLE001
                continue
            q["verdict"] = verdicts.get(q["symbol"], "")
            rows.append(q)
        return sorted(rows, key=lambda q: -abs(q["change_pct"]))
    part("stocks", stocks)

    def accuracy():
        import calls
        calls.grade()
        calls.review()                       # she looks at what she got wrong, and keeps the lesson
        return dict(calls.scorecard(), lessons=calls.lessons(4))
    part("accuracy", accuracy)
    part("earnings", lambda: _earnings(now))
    part("news", lambda: {t: [{"title": h["title"], "source": h.get("source", ""), "age": h.get("age", ""),
                               "link": h.get("link", "")} for h in feeds.headlines(t, limit=3)]
                          for t in feeds.TOPICS})
    if edition == "close":                         # THEIA's ideas are a morning thing; keep this morning's
        out["theia"] = load().get("theia")
    else:
        part("theia", theia_today)
    part("reminders", lambda: [{"text": r.get("text", ""), "due": r.get("due", "")} for r in reminders.pending()[:4]])
    return out


def _earnings(now):
    import market
    import watchlist
    rows = []
    for s in watchlist.current():
        try:
            when = market.fundamentals(s, timeout=market.TURN_TIMEOUT).get("earnings")
        except Exception:  # noqa: BLE001
            continue
        if when:
            days = (dt.date.fromisoformat(when) - now.date()).days
            if 0 <= days <= 7:
                rows.append({"symbol": s, "date": when, "days": days})
    return sorted(rows, key=lambda r: r["days"])


def make(edition="", path=PATH):
    data = build(edition)
    data["seen"] = False
    save(data, path)
    return data


def mark_seen(path=PATH):
    data = load(path)
    if data:
        data["seen"] = True
        save(data, path)
    return True


THEIA_DAY = (
    "You are THEIA, the user's analyst. From what you know of them below, give them three things for "
    "today that would genuinely help: a concrete idea for their day or one of their projects, a next "
    "step on one of their saved ideas, or a question about their plans that would help them decide "
    "something. Specific to them - never generic advice. In the language of their ideas (Gulf Arabic "
    "if they wrote Arabic). Answer ONLY with JSON: [{\"kind\": \"idea\" or \"next step\" or "
    "\"question\", \"text\": \"under 40 words\"}]")


def theia_today(think=None):
    """THEIA's three things for today: ideas, next steps, questions about your plans."""
    import re
    import ideas
    import reminders
    kept = ideas.all()[:12]
    lines = [f"- idea: {i['text']}" + (f" (your read: {i['theia']['summary'][:200]})" if i.get("theia") else "")
             for i in kept]
    lines += [f"- reminder: {r.get('text', '')} ({r.get('due', '')})" for r in reminders.pending()[:5]]
    try:
        import interests
        lines.append("- what they care about: " + json.dumps(interests.load(), ensure_ascii=False)[:1500])
    except Exception:  # noqa: BLE001 - no profile yet
        pass
    if think is None:
        import lyla
        think = lambda prompt: lyla.ask_gemini(prompt, THEIA_DAY)  # noqa: E731
    text = think("Today is " + dt.date.today().strftime("%A %d %B") + ".\n" + "\n".join(lines or ["(nothing saved yet)"]))
    found = re.search(r"\[.*\]", text or "", re.S)
    rows = json.loads(found.group(0)) if found else []
    return [{"kind": str(r.get("kind", "idea"))[:20], "text": str(r.get("text", ""))[:300]}
            for r in rows if isinstance(r, dict) and r.get("text")][:3]
