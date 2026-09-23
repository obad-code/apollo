"""One background thread that keeps Apollo's world up to date.

Every reader below caches on its own, so this exists for two reasons: to pay
for the slow parts (a dozen quotes, four news queries) on a timer instead of
inside a turn, and to keep one snapshot that both the tools and the display
read. The intervals are what the sources are worth: prices while New York is
open, headlines every ten minutes, the machine every few seconds.
"""

import logging
import threading
import time

import feeds
import logos
import market
import prayer
import sysinfo
import usage
import watchlist
import weather

log = logging.getLogger("apollo.data")

# The display reads ages off the snapshot, and the snapshot comes from here;
# re-exported so a caller that has the service does not also need the feeds.
age_words = feeds.age_words

INTERVALS = {"market": 60, "news": 600, "posts": 300, "weather": 900, "system": 5,
             "prayer": 300}
SPARK_POINTS = 24


class DataService:
    def __init__(self, on_snapshot=None):
        self.on_snapshot = on_snapshot
        self.snapshot = {"market": {"indices": [], "watchlist": [], "status": ""},
                         "news": {}, "posts": [], "weather": {}, "system": {},
                         "usage": {}, "prayer": {}, "updated": 0.0,
                         # When each reader last came back with something. A
                         # reader that fails keeps its last good value, and the
                         # display says how old that value is rather than
                         # showing a blank panel and implying the world stopped.
                         "stamps": {key: 0.0 for key in INTERVALS}}
        self._due = {key: 0.0 for key in INTERVALS}
        self._thread = None
        self._stopping = threading.Event()
        self._wake = threading.Event()      # see `poke`

    def start(self):
        if self._thread is None or not self._thread.is_alive():
            self._stopping.clear()
            self._thread = threading.Thread(target=self._run, daemon=True, name="apollo-data")
            self._thread.start()
        return self

    def stop(self):
        self._stopping.set()
        self._wake.set()

    def poke(self, *keys):
        """Have the loop read these (all of them, with none named) now.

        Returns at once: the reading happens on the service's own thread,
        so whoever asked - a tool call, with Apollo silent until it answers -
        does not wait on Yahoo.
        """
        for key in keys or tuple(INTERVALS):
            self._due[key] = 0.0
        self._wake.set()

    def _run(self):
        while not self._stopping.is_set():
            self._wake.clear()
            try:
                self.refresh()
            except Exception:  # noqa: BLE001 - the loop outlives any one failure
                log.debug("refresh failed", exc_info=True)
            self._wake.wait(2.0)

    def refresh(self, force=False):
        """Update whatever is due. `force` updates everything."""
        now = time.monotonic()
        changed = False
        for key, every in INTERVALS.items():
            if not force and now < self._due[key]:
                continue
            self._due[key] = now + every
            if getattr(self, "_read_" + key)():
                self.snapshot["stamps"][key] = time.time()
            changed = True
        if changed:
            self.snapshot["updated"] = time.time()
            self.snapshot["usage"] = usage.today()
            if self.on_snapshot is not None:
                try:
                    self.on_snapshot(self.snapshot)
                except Exception:  # noqa: BLE001
                    log.debug("snapshot listener failed", exc_info=True)

    # -- one reader each; none of them may raise, and each returns whether it
    #    actually brought something back, so a failure ages rather than blanks.

    def _read_market(self):
        # Named `watched`, not `watchlist`: the latter is the module this
        # reads the symbols from, and shadowing it here is how the list
        # stopped being a list.
        indices, watched = [], []
        for symbol in market.INDICES:
            quote = self._quote(symbol, spark=False)
            if quote:
                indices.append(quote)
        for symbol in watchlist.current():
            quote = self._quote(symbol, spark=True)
            if quote:
                watched.append(quote)
        status = ""
        try:
            status = market.market_status()["label"]
        except Exception:  # noqa: BLE001
            pass
        if not indices and not watched:
            return False
        self.snapshot["market"] = {"indices": indices, "watchlist": watched,
                                   "status": status}
        return True

    def _quote(self, symbol, spark):
        try:
            data = market.history(symbol, "1d") if spark else market.quote(symbol)
        except Exception:  # noqa: BLE001
            return None
        points = [round(price, 2) for _, price in data.get("points", [])][-SPARK_POINTS:]
        quote = {"symbol": data["symbol"], "name": data["name"],
                 "price": round(data["price"], 2),
                 "change_pct": round(data["change_pct"], 2),
                 "currency": data["currency"], "spark": points}
        if not spark:
            return quote
        # What the stock cards show beyond the price: the company's mark, what
        # analysts think it is worth, and what it costs per unit of earnings.
        # Each is allowed to be missing; a card without them is still a card.
        quote["logo"] = logos.url_for(data["symbol"])
        quote["high"] = round(max(points), 2) if points else None
        quote["low"] = round(min(points), 2) if points else None
        quote["average"] = round(sum(points) / len(points), 2) if points else None
        valuation = market.fundamentals(data["symbol"])
        quote.update(valuation)
        quote["upside"] = market.upside(valuation.get("target"), quote["price"])
        return quote

    def _read_news(self):
        # Per topic, so one dead feed does not take the other three with it.
        fresh = {topic: feeds.headlines(topic, limit=4) for topic in feeds.TOPICS}
        if not any(fresh.values()):
            return False
        kept = dict(self.snapshot["news"])
        kept.update({topic: stories for topic, stories in fresh.items() if stories})
        self.snapshot["news"] = kept
        return True

    def _read_posts(self):
        posts = feeds.posts(hours=24, limit=4)
        if not posts:
            return False
        self.snapshot["posts"] = posts
        return True

    def _read_weather(self):
        reading = weather.now()
        if not reading:
            return False
        self.snapshot["weather"] = reading
        return True

    def _read_prayer(self):
        # The day's times are fetched once and remembered by `prayer`, which
        # the reminders already rely on, so asking again every few minutes is
        # a dictionary lookup; the few minutes are what keep "next" honest.
        name, when = prayer.next_prayer()
        if name is None:
            self.snapshot["prayer"] = {}
            return False
        self.snapshot["prayer"] = {"name": name, "at": when.timestamp()}
        return True

    def _read_system(self):
        reading = sysinfo.snapshot()
        if not reading:
            return False
        self.snapshot["system"] = reading
        return True
