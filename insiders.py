"""What the people who run your companies do with their own shares.

Directors and officers have to file a Form 4 with the SEC within two
business days of trading their own company's stock. Finnhub carries those
filings with the key Apollo already has for live prices, so this asks
Finnhub and never the SEC directly.

Only open-market purchases (code P) and sales (code S) count. The rest of a
Form 4 - shares withheld for tax, options exercised, gifts, grants - happens
on a schedule, not on a view of the stock, and would drown the two that do
say something. Lots sold by one person on one day are one sale.

US stocks only, like the price stream. Nothing here raises.
"""

import datetime
import json
import logging
import urllib.parse
import urllib.request

import live

log = logging.getLogger("apollo.insiders")

URL = "https://finnhub.io/api/v1/stock/insider-transactions"
SIDES = {"P": "buy", "S": "sell"}
DAYS = 90            # the window the display and the tool look back over
RECENT_BUY = 30      # a buy this recent is worth a mark on the card
LATEST = 5


def api_key():
    return live.api_key()


def _today():
    return datetime.date.today()


def fetch(symbol, key, since):
    """Finnhub's Form 4 rows for one stock, filed since `since`."""
    query = urllib.parse.urlencode({"symbol": symbol, "from": since.isoformat()})
    request = urllib.request.Request(f"{URL}?{query}",
                                     headers={"X-Finnhub-Token": key, "User-Agent": "Apollo"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return (json.load(response) or {}).get("data") or []


def _person(raw):
    """"STEVENS MARK A" -> "Mark A Stevens": filings put the surname first."""
    parts = [p.capitalize() if len(p) > 1 else p for p in str(raw or "").split()]
    return " ".join(parts[1:] + parts[:1]) if len(parts) > 1 else " ".join(parts)


def _trades(rows, since):
    """Open-market buys and sells since `since`, one per person, day and side."""
    merged = {}
    for r in rows or []:
        side = SIDES.get(r.get("transactionCode"))
        day = str(r.get("transactionDate") or "")
        if not side or not day or day < since.isoformat():
            continue
        shares = abs(int(r.get("change") or 0))
        price = float(r.get("transactionPrice") or 0)
        key = (r.get("name"), day, side)
        trade = merged.setdefault(key, {"name": _person(r.get("name")), "side": side, "date": day,
                                        "filed": str(r.get("filingDate") or day),
                                        "shares": 0, "value": 0.0})
        trade["shares"] += shares
        trade["value"] += shares * price
        trade["filed"] = max(trade["filed"], str(r.get("filingDate") or day))
    return sorted(merged.values(), key=lambda t: (t["date"], t["value"]), reverse=True)


def summary(symbol, rows, today=None, days=DAYS):
    today = today or _today()
    trades = _trades(rows, today - datetime.timedelta(days=days))

    def total(side):
        picked = [t for t in trades if t["side"] == side]
        return {"count": len(picked), "shares": sum(t["shares"] for t in picked),
                "value": round(sum(t["value"] for t in picked), 2)}

    recent = (today - datetime.timedelta(days=RECENT_BUY)).isoformat()
    return {"symbol": symbol, "days": days, "buys": total("buy"), "sells": total("sell"),
            "recent_buy": any(t["side"] == "buy" and t["date"] >= recent for t in trades),
            "latest": [dict(t, value=round(t["value"], 2)) for t in trades[:LATEST]]}


def for_watchlist(symbols, key=None, fetch=None, today=None, days=DAYS):
    """{symbol: summary} for the US stocks in `symbols` Finnhub answers for."""
    if not key:
        return {}
    fetch = fetch or globals()["fetch"]
    today = today or _today()
    since = today - datetime.timedelta(days=days)
    found = {}
    for symbol in symbols:
        if not live.streamable(symbol):
            continue
        try:
            rows = fetch(symbol, key, since)
        except Exception as e:  # noqa: BLE001 - one stock's silence is not the rest's
            log.debug("insiders for %s failed: %s", symbol, type(e).__name__)
            continue
        found[symbol] = summary(symbol, rows, today=today, days=days)
    return found


def notable(symbols, key=None, fetch=None, today=None, days=2, least=1_000_000):
    """The big trades filed in the last `days` days: worth a line in the recap."""
    today = today or _today()
    filed_since = (today - datetime.timedelta(days=days)).isoformat()
    picked = []
    for symbol, s in for_watchlist(symbols, key=key, fetch=fetch, today=today).items():
        for trade in s["latest"]:
            if trade["filed"] >= filed_since and trade["value"] >= least:
                picked.append(dict(trade, symbol=symbol))
    return sorted(picked, key=lambda t: -t["value"])
