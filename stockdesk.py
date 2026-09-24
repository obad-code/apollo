"""What the display's stock panel can ask for with the mouse.

Open a stock and its chart can be read over a day, a week, a month, six
months or a year; take it off the watchlist; put another on from a short
list of suggestions. The voice tools change the same list (tools.py) - this
is the other hand on it.

Nothing here raises: every answer is a dict the page can show.
"""

import journal
import market
import watchlist

# The spans the stock view offers, in the order its chips run.
PERIODS = ("1d", "5d", "1mo", "6mo", "1y")

# What "Add a stock" offers, by the name it goes by. The built-in list is in
# it too, so one you took off can be put back with a click.
SUGGESTED = (
    ("AAPL", "Apple"), ("MSFT", "Microsoft"), ("NVDA", "NVIDIA"),
    ("TSLA", "Tesla"), ("AMZN", "Amazon"), ("GOOGL", "Alphabet"),
    ("META", "Meta"), ("PLTR", "Palantir"), ("AMD", "AMD"),
    ("AVGO", "Broadcom"), ("TSM", "TSMC"), ("MRVL", "Marvell"),
    ("NFLX", "Netflix"), ("INTC", "Intel"), ("SONY", "Sony"),
    ("TTWO", "Take-Two"), ("DIS", "Disney"), ("2222.SR", "Aramco"),
    ("1120.SR", "Al Rajhi"), ("BTC-USD", "Bitcoin"), ("GC=F", "Gold"),
)


def suggestions():
    """The suggested stocks not on the watchlist, as {symbol, name}."""
    watched = set(watchlist.current())
    return [{"symbol": symbol, "name": name}
            for symbol, name in SUGGESTED if symbol not in watched]


class StockDesk:
    """`poke(*keys)` asks the data service to read those again, without
    waiting: a stock put on shows up on the display a moment later."""

    def __init__(self, poke=None):
        self._poke = poke or (lambda *keys: None)

    def watch(self, symbol):
        result = watchlist.add(str(symbol or ""))
        if result.get("ok") and not result.get("already"):
            journal.write("watch", symbol=result["symbol"])
            self._poke("market")
        return result

    def unwatch(self, symbol):
        result = watchlist.remove(str(symbol or ""))
        if result.get("ok"):
            journal.write("unwatch", symbol=result["symbol"])
            self._poke("market")
        return result

    def chart(self, symbol, period):
        """The closes over `period`, for a stock the page is showing."""
        symbol, period = str(symbol or ""), str(period or "")
        # Only what the page shows and offers: it is handed feed data, and
        # this reaches the network on its say-so.
        if period not in PERIODS or symbol not in watchlist.current():
            return {"ok": False, "error": "That chart isn't on offer."}
        try:
            data = market.history(symbol, period)
        except Exception as e:  # noqa: BLE001 - the page says it, whatever it was
            return {"ok": False, "error": str(e) or type(e).__name__}
        points = data.get("points", [])
        closes = [round(float(price), 4) for _, price in points]
        return {"ok": True, "symbol": symbol, "period": period, "points": closes,
                "times": [int(stamp) for stamp, _ in points],
                "price": data.get("price"), "change_pct": data.get("change_pct"),
                "high": max(closes) if closes else None,
                "low": min(closes) if closes else None}
