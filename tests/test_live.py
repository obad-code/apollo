"""Prices as they trade: Finnhub's stream, folded into what the display shows.

The display's own reading is Yahoo's, once a minute. The stream sends every
trade as it happens; the feed keeps the latest price per stock and hands a
batch on about once a second, and the snapshot takes a live price over the
minute-old one while it is fresh.
"""
import asyncio
import json
import logging
import threading
import time

import pytest

import live

KEY = "k" * 40


def trade(symbol, price, ms):
    return {"s": symbol, "p": price, "t": ms, "v": 1}


def message(*trades):
    return json.dumps({"type": "trade", "data": list(trades)})


# -- reading the stream ---------------------------------------------------------

def test_a_trade_message_gives_symbol_price_and_seconds():
    got = live.parse(message(trade("AAPL", 336.23, 1790265159123)))
    assert got == [("AAPL", 336.23, 1790265159.123)]


@pytest.mark.parametrize("text", ['{"type":"ping"}', '{"type":"error","msg":"no"}',
                                  "not json", '{"type":"trade"}', '{"type":"trade","data":[{}]}'])
def test_anything_else_gives_nothing(text):
    assert live.parse(text) == []


@pytest.mark.parametrize("symbol, ok", [("AAPL", True), ("NVDA", True), ("GOOGL", True),
                                        ("2222.SR", False), ("^GSPC", False), ("GC=F", False),
                                        ("BTC-USD", False), ("", False)])
def test_only_us_stocks_are_streamed(symbol, ok):
    """The free stream carries US stocks; Tadawul, indices, futures and
    crypto stay on the minute-by-minute reading."""
    assert live.streamable(symbol) is ok


# -- the price the display shows ----------------------------------------------------

def market(price=100.0, previous=80.0, spark=(90.0, 95.0, 100.0)):
    return {"indices": [], "status": "", "watchlist": [
        {"symbol": "NVDA", "price": price, "previous": previous, "change_pct": 25.0,
         "spark": list(spark)}]}


def test_a_fresh_trade_is_the_price():
    now = 1000.0
    out = live.overlay(market(), {"NVDA": (110.0, now - 2)}, now=now)
    quote = out["watchlist"][0]
    assert quote["price"] == 110.0
    assert quote["change_pct"] == pytest.approx(37.5)        # against yesterday's close
    assert quote["spark"][-1] == 110.0                        # the curve ends where it trades
    assert quote["live"] is True


def test_a_stale_trade_is_not():
    now = 1000.0
    out = live.overlay(market(), {"NVDA": (110.0, now - live.FRESH - 1)}, now=now)
    assert out["watchlist"][0]["price"] == 100.0
    assert not out["watchlist"][0].get("live")


def test_the_snapshot_it_was_given_is_left_alone():
    given = market()
    live.overlay(given, {"NVDA": (110.0, 999.0)}, now=1000.0)
    assert given["watchlist"][0]["price"] == 100.0


def test_no_previous_close_keeps_the_move_it_had():
    out = live.overlay(market(previous=None), {"NVDA": (110.0, 999.0)}, now=1000.0)
    assert out["watchlist"][0]["change_pct"] == 25.0


# -- the feed ---------------------------------------------------------------------

class Socket:
    """A stream that says what it is scripted to, then waits."""

    def __init__(self, script):
        self.script = list(script)
        self.sent = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def send(self, text):
        self.sent.append(json.loads(text))

    async def recv(self):
        if self.script:
            item = self.script.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item
        await asyncio.sleep(3600)


class Connector:
    def __init__(self, *sockets):
        self.sockets = list(sockets)
        self.urls = []

    def __call__(self, url, **kwargs):
        self.urls.append(url)
        return self.sockets.pop(0) if self.sockets else Socket([])


def wait_for(condition, seconds=3.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return False


def feed_with(connector, symbols, ticks=None):
    batches = ticks if ticks is not None else []
    made = live.LiveFeed(KEY, symbols=lambda: list(symbols), on_tick=batches.append,
                         connect=connector, flush_every=0.05, backoff=(0.05,))
    made.batches = batches
    return made


def subscribed(socket):
    return [m["symbol"] for m in socket.sent if m["type"] == "subscribe"]


def test_it_subscribes_to_the_watchlist_it_can_stream():
    socket = Socket([])
    feed = feed_with(Connector(socket), ["AAPL", "2222.SR", "NVDA"]).start()
    try:
        assert wait_for(lambda: len(socket.sent) >= 2)
        assert sorted(subscribed(socket)) == ["AAPL", "NVDA"]
    finally:
        feed.stop()


def test_trades_arrive_as_one_batch_with_the_latest_price():
    socket = Socket([message(trade("AAPL", 1.0, 1000), trade("AAPL", 2.0, 2000)),
                     message(trade("NVDA", 5.0, 3000))])
    feed = feed_with(Connector(socket), ["AAPL", "NVDA"]).start()
    try:
        assert wait_for(lambda: feed.batches)
        merged = {}
        for batch in feed.batches:
            merged.update(batch)
        assert merged["AAPL"] == (2.0, 2.0) and merged["NVDA"] == (5.0, 3.0)
        assert feed.latest("AAPL") == (2.0, 2.0)
    finally:
        feed.stop()


def test_a_stock_put_on_the_list_is_subscribed_and_one_taken_off_is_dropped():
    symbols = ["AAPL"]
    socket = Socket([])
    feed = live.LiveFeed(KEY, symbols=lambda: list(symbols), on_tick=lambda batch: None,
                         connect=Connector(socket), flush_every=0.05, backoff=(0.05,)).start()
    try:
        assert wait_for(lambda: subscribed(socket) == ["AAPL"])
        symbols[:] = ["PLTR"]
        assert wait_for(lambda: "PLTR" in subscribed(socket))
        assert {"type": "unsubscribe", "symbol": "AAPL"} in socket.sent
    finally:
        feed.stop()


def test_a_dropped_stream_is_opened_again_and_subscribed_again():
    first = Socket([ConnectionError("gone")])
    second = Socket([])
    connector = Connector(first, second)
    feed = feed_with(connector, ["AAPL"]).start()
    try:
        assert wait_for(lambda: subscribed(second) == ["AAPL"])
        assert len(connector.urls) == 2
    finally:
        feed.stop()


def test_the_key_never_reaches_the_log(caplog):
    caplog.set_level(logging.DEBUG, logger="apollo.live")
    connector = Connector(Socket([ConnectionError(f"wss://ws.finnhub.io?token={KEY} refused")]),
                          Socket([]))
    feed = feed_with(connector, ["AAPL"]).start()
    try:
        assert wait_for(lambda: len(connector.urls) == 2)
    finally:
        feed.stop()
    assert KEY not in caplog.text


def test_stop_ends_its_thread():
    feed = feed_with(Connector(Socket([])), ["AAPL"]).start()
    feed.stop()
    assert wait_for(lambda: not feed.alive())


# -- a price asked for out loud -------------------------------------------------------

def test_an_answer_takes_the_streamed_price_when_there_is_one():
    feed = live.LiveFeed(KEY, symbols=lambda: [], on_tick=lambda b: None)
    feed._latest["NVDA"] = (110.0, time.time())
    data = {"symbol": "NVDA", "price": 100.0, "previous_close": 80.0, "change": 20.0,
            "change_pct": 25.0}
    live.freshen(data, feed=feed, key=KEY, fetch=lambda *a, **k: pytest.fail("no fetch"))
    assert data["price"] == 110.0 and data["change_pct"] == pytest.approx(37.5)
    assert data["change"] == pytest.approx(30.0)


def test_one_not_streamed_is_asked_for_once():
    asked = []

    def fetch(symbol, key):
        asked.append(symbol)
        return {"c": 123.0, "d": 3.0, "dp": 2.5, "t": 1}

    data = {"symbol": "PLTR", "price": 100.0, "previous_close": 120.0, "change": -20.0,
            "change_pct": -16.7}
    live.freshen(data, feed=None, key=KEY, fetch=fetch)
    assert asked == ["PLTR"]
    assert data["price"] == 123.0 and data["change_pct"] == 2.5


def test_without_a_key_or_for_tadawul_nothing_changes():
    data = {"symbol": "2222.SR", "price": 27.0, "previous_close": 27.5, "change": -0.5,
            "change_pct": -1.8}
    live.freshen(data, feed=None, key=KEY, fetch=lambda *a: pytest.fail("no fetch"))
    live.freshen(dict(data, symbol="AAPL"), feed=None, key=None,
                 fetch=lambda *a: pytest.fail("no fetch"))
    assert data["price"] == 27.0


def test_a_failed_lookup_leaves_the_price_it_had():
    def fetch(symbol, key):
        raise OSError("offline")

    data = {"symbol": "PLTR", "price": 100.0, "previous_close": 120.0, "change": -20.0,
            "change_pct": -16.7}
    live.freshen(data, feed=None, key=KEY, fetch=fetch)
    assert data["price"] == 100.0


def test_the_key_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "abc")
    assert live.api_key() == "abc"


def test_no_key_anywhere_is_none(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    monkeypatch.setattr(live, "_saved_key", lambda: None)
    assert live.api_key() is None
