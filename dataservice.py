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
import market
import sysinfo
import usage
import weather

log = logging.getLogger("apollo.data")

INTERVALS = {"market": 60, "news": 600, "posts": 300, "weather": 900, "system": 5}
SPARK_POINTS = 24


class DataService:
    def __init__(self, on_snapshot=None):
        self.on_snapshot = on_snapshot
        self.snapshot = {"market": {"indices": [], "watchlist": [], "status": ""},
                         "news": {}, "posts": [], "weather": {}, "system": {},
                         "usage": {}, "updated": 0.0}
        self._due = {key: 0.0 for key in INTERVALS}
        self._thread = None
        self._stopping = threading.Event()

    def start(self):
        if self._thread is None or not self._thread.is_alive():
            self._stopping.clear()
            self._thread = threading.Thread(target=self._run, daemon=True, name="apollo-data")
            self._thread.start()
        return self

    def stop(self):
        self._stopping.set()

    def _run(self):
        while not self._stopping.is_set():
            try:
                self.refresh()
            except Exception:  # noqa: BLE001 - the loop outlives any one failure
                log.debug("refresh failed", exc_info=True)
            self._stopping.wait(2.0)

    def refresh(self, force=False):
        """Update whatever is due. `force` updates everything."""
        now = time.monotonic()
        changed = False
        for key, every in INTERVALS.items():
            if not force and now < self._due[key]:
                continue
            self._due[key] = now + every
            getattr(self, "_read_" + key)()
            changed = True
        if changed:
            self.snapshot["updated"] = time.time()
            self.snapshot["usage"] = usage.today()
            if self.on_snapshot is not None:
                try:
                    self.on_snapshot(self.snapshot)
                except Exception:  # noqa: BLE001
                    log.debug("snapshot listener failed", exc_info=True)

    # -- one reader each; none of them may raise ---------------------------

    def _read_market(self):
        indices, watchlist = [], []
        for symbol in market.INDICES:
            quote = self._quote(symbol, spark=False)
            if quote:
                indices.append(quote)
        for symbol in market.WATCHLIST:
            quote = self._quote(symbol, spark=True)
            if quote:
                watchlist.append(quote)
        status = ""
        try:
            status = market.market_status()["label"]
        except Exception:  # noqa: BLE001
            pass
        self.snapshot["market"] = {"indices": indices, "watchlist": watchlist,
                                   "status": status}

    def _quote(self, symbol, spark):
        try:
            data = market.history(symbol, "1d") if spark else market.quote(symbol)
        except Exception:  # noqa: BLE001
            return None
        points = [round(price, 2) for _, price in data.get("points", [])][-SPARK_POINTS:]
        return {"symbol": data["symbol"], "name": data["name"],
                "price": round(data["price"], 2),
                "change_pct": round(data["change_pct"], 2),
                "currency": data["currency"], "spark": points}

    def _read_news(self):
        self.snapshot["news"] = {topic: feeds.headlines(topic, limit=4)
                                 for topic in feeds.TOPICS}

    def _read_posts(self):
        self.snapshot["posts"] = feeds.posts(hours=24, limit=4)

    def _read_weather(self):
        self.snapshot["weather"] = weather.now()

    def _read_system(self):
        self.snapshot["system"] = sysinfo.snapshot()
