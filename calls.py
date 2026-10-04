"""Was MONEYPENNY right? Every stock call she makes is kept with the price it
was made at; a week and a month later the price is looked at again and the
call is marked right or wrong.

    BUY / STRONG BUY   right if the price went up
    AVOID / SELL       right if it went down
    HOLD               right if it stayed within 5% either way

The price at the mark is written down once, so a call's grade never changes
afterwards. One call per stock per source per day.
"""

import datetime as dt
import json
import logging
import os

log = logging.getLogger("apollo.calls")

PATH = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Apollo", "calls.json")
MARKS = (7, 30)
HOLD_BAND = 5.0
KEEP = 2000


def load(path=PATH):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save(rows, path=PATH):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rows[-KEEP:], f, ensure_ascii=False)
    except OSError:
        log.info("could not keep the calls", exc_info=True)


def side(verdict):
    v = str(verdict or "").upper()
    if "BUY" in v:
        return "up"
    if v in ("AVOID", "SELL", "TRIM", "PULL"):
        return "down"
    return "flat" if v else ""


def record(symbol, verdict, price, source="MONEYPENNY", when=None, path=PATH):
    """Keep one call. Returns False when it is a repeat for today or has no price."""
    symbol, verdict = str(symbol or "").upper(), str(verdict or "").upper()
    if not symbol or not side(verdict) or not price:
        return False
    when = when or dt.datetime.now()
    day = when.date().isoformat()
    rows = load(path)
    if any(r["symbol"] == symbol and r["source"] == source and r["day"] == day for r in rows):
        return False
    rows.append({"symbol": symbol, "verdict": verdict, "price": float(price), "source": source,
                 "day": day, "at": when.isoformat(timespec="minutes")})
    save(rows, path)
    return True


def right(row, later):
    move = (later - row["price"]) / row["price"] * 100
    s = side(row["verdict"])
    return move > 0 if s == "up" else move < 0 if s == "down" else abs(move) <= HOLD_BAND


def grade(today=None, price=None, path=PATH):
    """Write down the price at each mark that has come round. `price(symbol)` -> now."""
    today = today or dt.date.today()
    if price is None:
        import market
        price = lambda s: market.quote(s)["price"]  # noqa: E731
    rows, changed, cache = load(path), False, {}
    for r in rows:
        age = (today - dt.date.fromisoformat(r["day"])).days
        for mark in MARKS:
            key = f"p{mark}"
            if age >= mark and key not in r:
                if r["symbol"] not in cache:
                    try:
                        cache[r["symbol"]] = float(price(r["symbol"]))
                    except Exception:  # noqa: BLE001 - graded on a later day instead
                        cache[r["symbol"]] = None
                if cache[r["symbol"]]:
                    r[key] = cache[r["symbol"]]
                    changed = True
    if changed:
        save(rows, path)
    return rows


def scorecard(rows=None, path=PATH):
    """{marks: {7: {calls, right, rate}, 30: {...}}, recent: [...graded calls...], open}"""
    rows = load(path) if rows is None else rows
    out = {"marks": {}, "recent": [], "open": 0}
    for mark in MARKS:
        done = [r for r in rows if f"p{mark}" in r]
        hits = sum(1 for r in done if right(r, r[f"p{mark}"]))
        out["marks"][mark] = {"calls": len(done), "right": hits,
                              "rate": round(100 * hits / len(done)) if done else None}
    out["open"] = sum(1 for r in rows if "p7" not in r)
    for r in sorted((r for r in rows if "p7" in r), key=lambda r: r["day"], reverse=True)[:8]:
        move = round((r["p7"] - r["price"]) / r["price"] * 100, 1)
        out["recent"].append({"symbol": r["symbol"], "verdict": r["verdict"], "day": r["day"],
                              "move": move, "right": right(r, r["p7"])})
    return out
