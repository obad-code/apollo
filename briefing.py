"""The day, as Apollo tells it.

One composer that gathers what the readers already cache - weather, the
watchlist, headlines on what you follow, Trump's last day of posts, your
reminders, and what the APIs have cost - and one schedule that decides when
the day's first recap is due. The words are Gemini's: `spoken` hands it the
facts and asks for a short read in whatever language you last used, because a
briefing written here would always sound like a form letter.
"""

import datetime
import json
import logging
import os

import feeds
import market
import reminders
import usage
import watchlist
import weather

log = logging.getLogger("apollo.briefing")

STATE_PATH = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                          "Apollo", "briefing.json")

# You are at the machine, not walking past it.
PRESENT_SECONDS = 120

HIJRI_MONTHS = ("Muharram", "Safar", "Rabi I", "Rabi II", "Jumada I", "Jumada II",
                "Rajab", "Shaban", "Ramadan", "Shawwal", "Dhul-Qadah", "Dhul-Hijjah")


def hijri(day):
    """The Hijri date, by the Kuwaiti algorithm - good to a day, no dependency.

    Checked against known anchors: 2000-01-01 is 24 Ramadan 1420 and
    2026-09-20 is in Rabi II 1448.
    """
    try:
        jd = day.toordinal() + 1721425
        length = jd - 1948440 + 10632
        cycles = (length - 1) // 10631
        length = length - 10631 * cycles + 354
        j = (((10985 - length) // 5316) * ((50 * length) // 17719)
             + (length // 5670) * ((43 * length) // 15238))
        length = (length - ((30 - j) // 15) * ((17719 * j) // 50)
                  - (j // 16) * ((15238 * j) // 43) + 29)
        month = (24 * length) // 709
        day_of = length - (709 * month) // 24
        year = 30 * cycles + j - 30
        return f"{day_of} {HIJRI_MONTHS[max(0, min(11, month - 1))]} {year}"
    except Exception:  # noqa: BLE001 - a date is never worth a failed briefing
        return ""


def compose(now=None):
    """Everything the recap draws on. Every part is optional and may be empty."""
    now = now or datetime.datetime.now()
    indices, movers = [], []
    for symbol in market.INDICES:
        try:
            indices.append(_small(market.quote(symbol)))
        except Exception:  # noqa: BLE001 - a dead feed costs a line, not the recap
            continue
    for symbol in watchlist.current():
        try:
            movers.append(_small(market.quote(symbol)))
        except Exception:  # noqa: BLE001
            continue
    movers.sort(key=lambda q: abs(q["change_pct"]), reverse=True)

    try:
        status = market.market_status(now.astimezone() if now.tzinfo else None)["label"]
    except Exception:  # noqa: BLE001
        status = ""

    return {
        "date": now.strftime("%A %-d %B %Y") if os.name != "nt" else now.strftime("%A %#d %B %Y"),
        "time": now.strftime("%H:%M"),
        "hijri": hijri(now.date()),
        "day_of_year": now.timetuple().tm_yday,
        "week": now.isocalendar().week,
        "weather": weather.now(),
        "market": {"indices": indices, "movers": movers[:4], "status": status},
        "headlines": {topic: feeds.headlines(topic, limit=2) for topic in feeds.TOPICS},
        "posts": feeds.posts(hours=24, limit=3),
        "reminders": reminders.pending()[:3],
        "usage": usage.today(),
    }


def _small(quote):
    return {"symbol": quote["symbol"], "name": quote["name"], "price": quote["price"],
            "change_pct": round(quote["change_pct"], 2), "currency": quote["currency"]}


def spoken(payload):
    """The instruction Gemini is given: the facts, and how to read them."""
    lines = [f"Brief the user on their day. It is {payload['date']}, {payload['time']} in Riyadh."]
    if payload.get("hijri"):
        lines.append(f"Hijri date: {payload['hijri']}.")
    sky = payload.get("weather") or {}
    if sky:
        lines.append(f"Riyadh: {sky.get('temp')}C now, {sky.get('text')}, "
                     f"high {sky.get('high')} low {sky.get('low')}.")
    market_part = payload.get("market") or {}
    if market_part.get("status"):
        lines.append(f"Market: {market_part['status']}.")
    for quote in market_part.get("indices", []) + market_part.get("movers", []):
        lines.append(f"{quote['symbol']} {quote['price']:.2f} {quote['change_pct']:+.2f}%.")
    for topic, items in (payload.get("headlines") or {}).items():
        for item in items:
            lines.append(f"{topic}: {item['title']} ({item['source']}, {item['age']}).")
    for post in payload.get("posts") or []:
        flag = " [market-moving]" if post.get("market") else ""
        lines.append(f"Trump posted{flag} {post['age']}: {post['text'][:200]}")
    for reminder in payload.get("reminders") or []:
        lines.append(f"Reminder: {reminder['text']} ({reminder['due']}).")
    lines.append(
        "Read this as a short spoken briefing - about 30 to 45 seconds, in the "
        "language the user last spoke to you in, their dialect if it was Arabic. "
        "Lead with the date and weather in one sentence, then the market, then "
        "the two or three stories that actually matter to them, then anything "
        "market-moving in the posts, then their reminders. Give real numbers. "
        "Skip anything the facts above do not cover, and never invent a figure.")
    return "\n".join(lines)


class Schedule:
    """Whether today's recap has happened yet.

    Once a day, the first time you are actually at the machine. The state is a
    date in a file, so a restart - or a crash halfway through a briefing -
    cannot give you the same recap twice.
    """

    def __init__(self, path=None):
        self.path = path or STATE_PATH
        self.last = self._read()

    def _read(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f).get("last", "")
        except (OSError, ValueError):
            return ""

    def due(self, now=None, idle_seconds=0.0, busy=False):
        """Whether to give the day's recap now.

        `busy` is the important one and was missing. Pressing the talk chord
        makes you present, so the first Ctrl+Alt of the day satisfied every
        other condition here and the recap started talking over the turn that
        press was opening. Anything that means "they are mid-sentence with
        it" - the chord held, a turn in flight, a turn just finished - has to
        hold the recap back.
        """
        now = now or datetime.datetime.now()
        if busy:
            return False              # you are talking to it, not idle at it
        if idle_seconds > PRESENT_SECONDS:
            return False              # you are not here yet
        return self.last != now.date().isoformat()

    def done(self, now=None):
        now = now or datetime.datetime.now()
        self.last = now.date().isoformat()
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"last": self.last}, f)
        except OSError as e:
            log.info("could not save the briefing date: %s", e)
