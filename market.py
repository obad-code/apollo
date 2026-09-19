"""Live prices and price history for Apollo's market tools and dashboard.

The source is Yahoo Finance's public chart endpoint: no key, no account, and
it answers in about 0.3 s from here. It is unofficial, so it is used with
care - two hosts serving the same data are tried in turn, answers are cached
(a minute while New York is trading, fifteen otherwise), and any failure
surfaces as a MarketError whose message is safe to speak. Nothing here ever
invents a number: no data means an error, not a guess.
"""

import json
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import overlay_content

HOSTS = ("https://query1.finance.yahoo.com", "https://query2.finance.yahoo.com")
HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")}
TIMEOUT = 6
NY = ZoneInfo("America/New_York")

PERIODS = {"1d": "5m", "5d": "30m", "1mo": "1d", "6mo": "1d", "1y": "1wk", "5y": "1mo"}
MAX_POINTS = 64

WATCHLIST = ("AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META")
INDICES = ("^GSPC", "^IXIC")

NAMES = {
    "apple": "AAPL", "microsoft": "MSFT", "nvidia": "NVDA", "tesla": "TSLA",
    "amazon": "AMZN", "google": "GOOGL", "alphabet": "GOOGL", "meta": "META",
    "facebook": "META", "netflix": "NFLX", "amd": "AMD", "intel": "INTC",
    "sony": "SONY", "disney": "DIS", "take two": "TTWO", "take-two": "TTWO",
    "rockstar": "TTWO", "palantir": "PLTR",
    "s&p 500": "^GSPC", "s&p": "^GSPC", "sp500": "^GSPC", "s and p": "^GSPC",
    "nasdaq": "^IXIC", "dow": "^DJI", "dow jones": "^DJI",
    "bitcoin": "BTC-USD", "ethereum": "ETH-USD", "gold": "GC=F", "oil": "CL=F",
    "crude": "CL=F", "brent": "BZ=F", "aramco": "2222.SR", "saudi aramco": "2222.SR",
    "tasi": "^TASI.SR", "al rajhi": "1120.SR",
    "ابل": "AAPL", "آبل": "AAPL", "أبل": "AAPL", "انفيديا": "NVDA", "إنفيديا": "NVDA",
    "تسلا": "TSLA", "مايكروسوفت": "MSFT", "امازون": "AMZN", "أمازون": "AMZN",
    "جوجل": "GOOGL", "قوقل": "GOOGL", "ميتا": "META", "ارامكو": "2222.SR",
    "أرامكو": "2222.SR", "بيتكوين": "BTC-USD", "الذهب": "GC=F", "ذهب": "GC=F",
    "النفط": "CL=F", "ناسداك": "^IXIC",
}

TV_SPECIAL = {"^GSPC": "SP:SPX", "^IXIC": "NASDAQ:IXIC", "^DJI": "DJ:DJI",
              "^NDX": "NASDAQ:NDX", "BTC-USD": "BITSTAMP:BTCUSD",
              "ETH-USD": "BITSTAMP:ETHUSD", "GC=F": "COMEX:GC1!", "CL=F": "NYMEX:CL1!",
              "BZ=F": "NYMEX:BB1!", "^TASI.SR": "TADAWUL:TASI"}
TV_EXCHANGE = {"NMS": "NASDAQ", "NGM": "NASDAQ", "NCM": "NASDAQ", "NAS": "NASDAQ",
               "NYQ": "NYSE", "NYS": "NYSE", "ASE": "AMEX", "PCX": "AMEX", "SAU": "TADAWUL"}


class MarketError(Exception):
    """A market lookup failed. The message is written to be spoken."""

    speakable = True    # tools.run passes the message through as-is


_cache = {}
_lock = threading.Lock()


def _open(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS),
                                timeout=TIMEOUT) as r:
        return json.load(r)


def _get_json(path, ttl):
    now = time.monotonic()
    with _lock:
        hit = _cache.get(path)
        if hit and hit[0] > now:
            return hit[1]
    last = None
    for host in HOSTS:
        try:
            data = _open(host + path)
        except Exception as e:  # noqa: BLE001 - any failure means try the other host
            last = e
            continue
        with _lock:
            _cache[path] = (now + ttl, data)
        return data
    raise MarketError(f"The market feed didn't answer ({type(last).__name__}).")


def _ttl():
    return 60 if market_status()["open"] else 900


def resolve(text):
    """A name or ticker as spoken -> a Yahoo symbol."""
    raw = (text or "").strip().strip("[]").strip().strip("'\"").strip()
    if not raw:
        raise MarketError("No stock was named.")
    key = raw.lower().removeprefix("the ").strip()
    for suffix in (" stock", " shares", " index", " price"):
        key = key.removesuffix(suffix)
    if key in NAMES:
        return NAMES[key]
    if re.fullmatch(r"\^?[A-Z0-9]{1,6}([.=-][A-Z0-9]{1,4})?", raw):
        return raw
    data = _get_json("/v1/finance/search?" + urllib.parse.urlencode(
        {"q": raw, "quotesCount": 5, "newsCount": 0}), ttl=86400)
    for q in data.get("quotes", []):
        if q.get("symbol") and q.get("quoteType") in (
                "EQUITY", "ETF", "INDEX", "CRYPTOCURRENCY", "FUTURE", "MUTUALFUND", "CURRENCY"):
            return q["symbol"]
    raise MarketError(f"I couldn't find a ticker for {raw}.")


def parse_chart(data):
    """Yahoo's chart JSON -> the handful of numbers Apollo uses."""
    try:
        result = data["chart"]["result"][0]
    except (KeyError, IndexError, TypeError):
        error = (((data or {}).get("chart") or {}).get("error") or {})
        raise MarketError(error.get("description") or "The market feed had nothing for that symbol.")
    meta = result.get("meta") or {}
    stamps = result.get("timestamp") or []
    closes = (((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or [])
    points = [(int(t), float(c)) for t, c in zip(stamps, closes) if c is not None]
    price = meta.get("regularMarketPrice") or (points[-1][1] if points else None)
    if price is None:
        raise MarketError("The feed has no price for that symbol right now.")
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    change = float(price) - float(prev) if prev else 0.0
    return {
        "symbol": meta.get("symbol") or "",
        "name": meta.get("shortName") or meta.get("longName") or meta.get("symbol") or "",
        "currency": meta.get("currency") or "",
        "exchange": meta.get("exchangeName") or "",
        "price": float(price),
        "previous_close": float(prev) if prev else None,
        "change": change,
        "change_pct": (change / float(prev) * 100.0) if prev else 0.0,
        "points": points,
        "time": int(meta.get("regularMarketTime") or (points[-1][0] if points else 0)),
    }


def _chart(symbol, period):
    path = (f"/v8/finance/chart/{urllib.parse.quote(symbol, safe='')}?"
            + urllib.parse.urlencode({"range": period, "interval": PERIODS[period]}))
    return parse_chart(_get_json(path, _ttl()))


def quote(symbol):
    """Today: price, change against yesterday's close, intraday points."""
    return _chart(symbol, "1d")


def history(symbol, period="5d"):
    """Over a period: change across it, and at most MAX_POINTS points."""
    data = _chart(symbol, period)
    data["points"] = downsample(data["points"], MAX_POINTS)
    return data


def downsample(points, n):
    if len(points) <= n:
        return list(points)
    step = (len(points) - 1) / (n - 1)
    return [points[round(i * step)] for i in range(n)]


def _span(delta):
    minutes = max(0, int(delta.total_seconds() // 60))
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


def market_status(now=None):
    """The NYSE regular session. Weekends are modelled; exchange holidays are not."""
    now = now.astimezone(NY) if now else datetime.now(NY)
    opens = now.replace(hour=9, minute=30, second=0, microsecond=0)
    closes = now.replace(hour=16, minute=0, second=0, microsecond=0)
    if now.weekday() < 5 and opens <= now < closes:
        return {"open": True, "next": closes, "label": "NYSE closes in " + _span(closes - now)}
    if now.weekday() < 5 and now < opens:
        nxt = opens
    else:
        day = now + timedelta(days=1)
        while day.weekday() >= 5:
            day += timedelta(days=1)
        nxt = day.replace(hour=9, minute=30, second=0, microsecond=0)
    return {"open": False, "next": nxt, "label": "NYSE opens in " + _span(nxt - now)}


def tradingview_symbol(symbol, exchange=""):
    if symbol in TV_SPECIAL:
        return TV_SPECIAL[symbol]
    if symbol.endswith(".SR"):
        return "TADAWUL:" + symbol[:-3]
    prefix = TV_EXCHANGE.get((exchange or "").upper())
    return f"{prefix}:{symbol}" if prefix else symbol


def tradingview_url(symbol, exchange=""):
    return ("https://www.tradingview.com/chart/?symbol="
            + urllib.parse.quote(tradingview_symbol(symbol, exchange), safe=""))


def fmt_price(x):
    return f"{x:,.2f}"


def visual_for(data, period):
    """Chart + cards for the overlay, from `quote` or `history` output."""
    closes = [c for _, c in data["points"]] or [data["price"]]
    label = "Today" if period == "1d" else period.upper()
    return overlay_content.clean_visual({
        "chart": {"points": closes, "label": f"{data['symbol']} · {period.upper()}",
                  "unit": "$" if data["currency"] == "USD" else ""},
        "cards": [{"label": "Last", "value": fmt_price(data["price"])},
                  {"label": label, "value": f"{data['change_pct']:+.1f}%"},
                  {"label": "High", "value": fmt_price(max(closes))},
                  {"label": "Low", "value": fmt_price(min(closes))}],
    })
