"""Was MONEYPENNY right? Every stock call she makes is kept with the price it
was made at; a week and a month later the price is looked at again and the
call is marked right or wrong.

    STRONG BUY / GOOD / DECENT   right if the price went up
    WEAK / AVOID / SELL          right if it went down
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
    if "BUY" in v or v in ("GOOD", "DECENT"):
        return "up"
    if v in ("AVOID", "SELL", "TRIM", "PULL", "WEAK"):
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


# -- learning from the ones she got wrong ----------------------------------------------------

REVIEW = (
    "You are MONEYPENNY, reviewing one of your own stock calls that turned out wrong. Be honest "
    "and specific - no excuses. Answer in exactly this shape:\n"
    "WHAT HAPPENED: one sentence, with the numbers.\n"
    "WHAT I MISSED: one or two sentences - the signal you over- or under-weighted.\n"
    "LESSON: one rule, under 25 words, you will follow on future calls.")


def review(think=None, path=PATH, most=3):
    """A post-mortem on each wrong call not reviewed yet (a few at a time). Returns how many."""
    rows = load(path)
    todo = [r for r in rows if "p7" in r and not right(r, r["p7"]) and "lesson" not in r][:most]
    if not todo:
        return 0
    if think is None:
        import lyla
        think = lambda prompt: lyla.ask_gemini(prompt, REVIEW)  # noqa: E731
    import re
    for r in todo:
        move = round((r["p7"] - r["price"]) / r["price"] * 100, 1)
        prompt = (f"Your call: {r['verdict']} on {r['symbol']} on {r['day']} at {r['price']}. "
                  f"A week later it was {r['p7']} ({move:+}%). Look up what happened to {r['symbol']} that week.")
        try:
            text = think(prompt) or ""
        except Exception:  # noqa: BLE001 - reviewed on a later day
            continue
        found = re.search(r"LESSON:\s*(.+)", text)
        r["review"] = text.strip()[:1200]
        r["lesson"] = (found.group(1).strip() if found else text.strip().splitlines()[-1])[:200]
    save(rows, path)
    return len(todo)


def lessons(most=8, path=PATH):
    """Her most recent lessons, newest first."""
    rows = [r for r in load(path) if r.get("lesson")]
    return [{"symbol": r["symbol"], "verdict": r["verdict"], "day": r["day"], "lesson": r["lesson"]}
            for r in sorted(rows, key=lambda r: r["day"], reverse=True)[:most]]


def lessons_prompt(path=PATH):
    """What goes in front of her next call, so the same mistake is not made twice."""
    got = lessons(path=path)
    if not got:
        return ""
    return ("\n\nLessons from your own past calls that went wrong - apply them:\n"
            + "\n".join(f"- ({g['symbol']} {g['verdict']}, {g['day']}) {g['lesson']}" for g in got))
