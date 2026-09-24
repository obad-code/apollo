"""Prices as they trade, from Finnhub's stream.

The display's own reading comes from Yahoo once a minute (dataservice). This
is the second hand: one WebSocket to Finnhub, subscribed to whichever of the
watchlist's stocks it carries, keeping the latest trade per stock and handing
a batch on about once a second. While a trade is fresh it is the price - on
the cards, in the stock opened out of its card, and in a spoken answer.

The free stream carries US stocks only. Tadawul, the indices, futures and
crypto stay on the minute-by-minute reading, and so does everything when the
stream is down or the market is shut: this adds to that reading, it never
replaces it.

The key rides in the stream's address, so neither the address nor an
exception's text (which can quote it) is ever logged - only the kind of
failure.
"""

import asyncio
import copy
import json
import logging
import os
import re
import threading
import time
import urllib.parse
import urllib.request

log = logging.getLogger("apollo.live")

KEY_NAME = "FINNHUB_API_KEY"
STREAM = "wss://ws.finnhub.io"
QUOTE = "https://finnhub.io/api/v1/quote"

# How long a trade counts as the price. Past this - the market shut, the
# stream stalled - the minute-by-minute reading is the better number.
FRESH = 120
# The free stream takes this many symbols at once.
MOST = 50
BACKOFF = (1, 2, 4, 8, 15, 30, 60)

_feed = None


def set_feed(feed):
    global _feed
    _feed = feed


def current_feed():
    return _feed


# -- the key ------------------------------------------------------------------

def _saved_key():
    """The key `setx` saved, for a process started before it was saved."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as handle:
            return winreg.QueryValueEx(handle, KEY_NAME)[0]
    except OSError:
        return None


def api_key():
    key = (os.environ.get(KEY_NAME) or _saved_key() or "").strip().strip('"')
    return key or None


# -- reading the stream ---------------------------------------------------------

def streamable(symbol):
    """Whether the free stream carries it: a plain US ticker."""
    return re.fullmatch(r"[A-Z]{1,5}", symbol or "") is not None


def parse(text):
    """A stream message -> [(symbol, price, seconds)]; anything else, []."""
    try:
        msg = json.loads(text)
    except (TypeError, ValueError):
        return []
    if not isinstance(msg, dict) or msg.get("type") != "trade":
        return []
    trades = []
    for item in msg.get("data") or []:
        try:
            trades.append((str(item["s"]), float(item["p"]), float(item["t"]) / 1000.0))
        except (KeyError, TypeError, ValueError):
            continue
    return trades


# -- the price the display shows ----------------------------------------------------

def _apply(quote, price):
    quote["price"] = price
    previous = quote.get("previous")
    if previous:
        quote["change_pct"] = (price - previous) / previous * 100.0
    spark = quote.get("spark")
    if spark:
        spark[-1] = price
    if quote.get("high") is not None:
        quote["high"] = max(quote["high"], price)
    if quote.get("low") is not None:
        quote["low"] = min(quote["low"], price)
    quote["live"] = True


def overlay(market, ticks, now=None):
    """The market snapshot with fresh trades as the prices. A new dict; the
    one given is left as the service read it."""
    now = time.time() if now is None else now
    out = dict(market or {})
    watched = []
    for quote in (market or {}).get("watchlist") or []:
        tick = ticks.get(quote.get("symbol"))
        if tick and now - tick[1] <= FRESH:
            quote = copy.deepcopy(quote)
            _apply(quote, tick[0])
        watched.append(quote)
    out["watchlist"] = watched
    return out


def overlay_snapshot(snapshot, feed):
    if feed is None or not snapshot.get("market"):
        return snapshot
    return dict(snapshot, market=overlay(snapshot["market"], feed.ticks()))


# -- a price asked for out loud -------------------------------------------------------

def quote_now(symbol, key, timeout=2.5):
    """Finnhub's quote for one stock: c (price), d (change), dp (change %)."""
    request = urllib.request.Request(
        QUOTE + "?" + urllib.parse.urlencode({"symbol": symbol}),
        headers={"X-Finnhub-Token": key, "User-Agent": "Apollo"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


_UNSET = object()


def freshen(data, feed=_UNSET, key=_UNSET, fetch=quote_now):
    """Bring a quote from `market.quote` up to the trade: the stream's price
    if it has a fresh one, else Finnhub's quote for a US stock. Anything that
    fails leaves the quote as it was."""
    feed = _feed if feed is _UNSET else feed
    symbol = data.get("symbol") or ""
    tick = feed.latest(symbol) if feed is not None else None
    if tick and time.time() - tick[1] <= FRESH:
        price = tick[0]
        data["price"] = price
        previous = data.get("previous_close")
        if previous:
            data["change"] = price - previous
            data["change_pct"] = (price - previous) / previous * 100.0
        return data
    key = api_key() if key is _UNSET else key
    if not key or not streamable(symbol):
        return data
    try:
        quote = fetch(symbol, key)
    except Exception as e:  # noqa: BLE001 - the minute-old price will do
        log.debug("quote for %s failed: %s", symbol, type(e).__name__)
        return data
    if quote and quote.get("c"):
        data["price"] = float(quote["c"])
        if quote.get("d") is not None:
            data["change"] = float(quote["d"])
        if quote.get("dp") is not None:
            data["change_pct"] = float(quote["dp"])
    return data


# -- the stream -------------------------------------------------------------------

class LiveFeed:
    """One stream for the watchlist. `symbols()` says what to follow, and is
    asked again every flush, so a stock put on or taken off is picked up
    within a second. `on_tick(batch)` gets {symbol: (price, seconds)}."""

    def __init__(self, key, symbols, on_tick, connect=None, flush_every=1.0,
                 backoff=BACKOFF):
        self._key = key
        self._symbols = symbols
        self._on_tick = on_tick
        self._connect = connect
        self._flush_every = flush_every
        self._backoff = backoff
        self._latest = {}
        self._lock = threading.Lock()
        self._stopping = threading.Event()
        self._thread = None
        self._loop = None
        self._task = None

    # -- what it knows

    def latest(self, symbol):
        with self._lock:
            return self._latest.get(symbol)

    def ticks(self):
        with self._lock:
            return dict(self._latest)

    # -- its thread

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True, name="apollo-live")
        self._thread.start()
        return self

    def stop(self):
        self._stopping.set()
        loop, task = self._loop, self._task
        if loop is not None and task is not None:
            try:
                loop.call_soon_threadsafe(task.cancel)
            except RuntimeError:
                pass              # the loop has already closed

    def alive(self):
        return self._thread is not None and self._thread.is_alive()

    def _run(self):
        loop = asyncio.new_event_loop()
        self._loop = loop
        try:
            self._task = loop.create_task(self._main())
            loop.run_until_complete(self._task)
        except asyncio.CancelledError:
            pass
        finally:
            loop.close()

    def _open(self):
        url = STREAM + "?" + urllib.parse.urlencode({"token": self._key})
        if self._connect is not None:
            return self._connect(url)
        import websockets
        return websockets.connect(url, open_timeout=10, ping_interval=20, ping_timeout=20)

    async def _main(self):
        failures = 0
        while not self._stopping.is_set():
            try:
                async with self._open() as stream:
                    failures = 0
                    log.info("live prices connected")
                    await self._session(stream)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 - the kind only: the text can hold the key
                wait = self._backoff[min(failures, len(self._backoff) - 1)]
                failures += 1
                log.info("live prices dropped (%s); again in %ss", type(e).__name__, wait)
                await asyncio.sleep(wait)

    async def _session(self, stream):
        subscribed = set()
        pending = {}
        await self._sync(stream, subscribed)
        flushed = time.monotonic()
        while not self._stopping.is_set():
            try:
                text = await asyncio.wait_for(stream.recv(), timeout=self._flush_every)
            except asyncio.TimeoutError:
                text = None
            for symbol, price, seconds in parse(text) if text is not None else ():
                pending[symbol] = (price, seconds)
            if time.monotonic() - flushed >= self._flush_every:
                flushed = time.monotonic()
                if pending:
                    self._flush(pending)
                    pending = {}
                await self._sync(stream, subscribed)

    def _flush(self, batch):
        with self._lock:
            self._latest.update(batch)
        try:
            self._on_tick(dict(batch))
        except Exception:  # noqa: BLE001 - a listener's fault is not the stream's
            log.debug("tick listener failed", exc_info=True)

    async def _sync(self, stream, subscribed):
        try:
            wanted = {s for s in self._symbols() if streamable(s)}
        except Exception:  # noqa: BLE001
            return
        wanted = set(sorted(wanted)[:MOST])
        for symbol in sorted(wanted - subscribed):
            await stream.send(json.dumps({"type": "subscribe", "symbol": symbol}))
        for symbol in sorted(subscribed - wanted):
            await stream.send(json.dumps({"type": "unsubscribe", "symbol": symbol}))
        subscribed.clear()
        subscribed.update(wanted)
