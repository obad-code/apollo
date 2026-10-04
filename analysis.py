"""A stock looked at whole: what the company does, its numbers, its news, and
a call - Strong Buy, Buy, Hold or Avoid - with the green flags and the red
flags that make it.

The call is counted, not guessed: each flag is a plain rule on a number
Yahoo gives (growth, margins, debt, cash, the analysts, the target), so the
same numbers always give the same call, and every flag says why. Not advice;
the reasons are there to be checked.
"""

import logging
import time

import feeds
import market

log = logging.getLogger("apollo.analysis")

MODULES = ("assetProfile,price,financialData,summaryDetail,defaultKeyStatistics,"
           "calendarEvents")
TTL = 900
_cache = {}

# A STRONG BUY has to be rare: strong on the business, on price and on trend all at once.
# (The first version gave it from +4, and over half of the big names got it - analysts' own
# optimism and a few easy greens were enough. Now it takes +6, and a price already above the
# analysts' target can never be better than HOLD.)
# Six grades, so a good stock is not lumped in with a merely decent one, nor a weak one with a broken one.
VERDICTS = [(6, "STRONG BUY", "BUY"), (4, "GOOD", "BUY"), (2, "DECENT", "BUY"), (0, "HOLD", "HOLD"), (-2, "WEAK", "HOLD")]
ORDER = ["AVOID", "WEAK", "HOLD", "DECENT", "GOOD", "STRONG BUY"]
RULES = 3          # bumped whenever the rules change, so a new rule is never told as a stock's "call changed"


def call(score):
    """The call for a score (greens less reds), and its tone."""
    for floor, words, tone in VERDICTS:
        if score >= floor:
            return words, tone
    return "AVOID", "SELL"


def verdict(score, n):
    """The call after the limits that no score can buy past: (words, tone, why it was held back)."""
    words, tone = call(score)
    notes = []

    def cap(top, why):
        nonlocal words, tone
        if ORDER.index(words) > ORDER.index(top):
            words, tone = top, ("HOLD" if top in ("HOLD", "WEAK") else "BUY")
            notes.append(f"Held at {top}: {why}")

    if (n.get("upside") is not None) and n["upside"] < 0:
        cap("HOLD", "the price is already above the analysts' target")
    pe, fpe = n.get("pe"), n.get("forward_pe")
    if (pe is not None and pe > 100) or (fpe is not None and fpe > 60):
        cap("GOOD", "the price assumes years of perfect growth")
    return words, tone, notes


def _pct(x):
    return f"{x * 100:.0f}%"


def flags(n):
    """Green and red flags from the numbers `n` (fractions as Yahoo gives
    them; any may be None). Pure, so it is tested without the network."""
    green, red = [], []

    def rule(value, good, bad, good_text, bad_text):
        if value is None:
            return
        if good(value):
            green.append(good_text(value))
        elif bad(value):
            red.append(bad_text(value))

    rule(n.get("revenue_growth"), lambda v: v >= .10, lambda v: v < 0,
         lambda v: f"Sales growing fast: +{_pct(v)} a year",
         lambda v: f"Sales shrinking: {_pct(v)} a year")
    rule(n.get("earnings_growth"), lambda v: v >= .10, lambda v: v < 0,
         lambda v: f"Profits growing: +{_pct(v)}",
         lambda v: f"Profits falling: {_pct(v)}")
    rule(n.get("margin"), lambda v: v >= .15, lambda v: v < 0,
         lambda v: f"Very profitable: keeps {_pct(v)} of every sale",
         lambda v: f"Losing money: {_pct(v)} margin")
    rule(n.get("free_cash"), lambda v: v > 0, lambda v: v < 0,
         lambda v: "Makes real cash (positive free cash flow)",
         lambda v: "Burning cash (negative free cash flow)")
    rule(n.get("debt_equity"), lambda v: v < 50, lambda v: v > 200,
         lambda v: f"Little debt (debt/equity {v:.0f}%)",
         lambda v: f"Heavy debt (debt/equity {v:.0f}%)")
    # The analysts count ONCE, however many of their numbers agree: their ratings and targets lean
    # bullish as a rule, so they must not be allowed to carry a call by themselves.
    up, rating = n.get("upside"), n.get("rating")
    if up is not None and up < 0:
        red.append(f"Price is already {abs(up):.0f}% above the analysts' target")
    elif rating is not None and rating >= 3.0:
        red.append(f"Analysts are cool on it ({rating:.1f} of 5)")
    elif (up is not None and up >= 15) or (rating is not None and rating <= 2.0):
        said = []
        if rating is not None and rating <= 2.0:
            said.append(f"rating {rating:.1f} of 5, 1 = strong buy")
        if up is not None and up >= 15:
            said.append(f"target {up:.0f}% above the price")
        green.append("Analysts lean positive (" + ", ".join(said) + ")")
    price, a200 = n.get("price"), n.get("avg200")
    if price and a200:
        gap = (price - a200) / a200
        if gap > 0:
            green.append(f"Trending up: {gap * 100:.0f}% above its 200-day average")
        elif gap < -0.05:
            red.append(f"Downtrend: {abs(gap) * 100:.0f}% below its 200-day average")
    beta = n.get("beta")
    if beta is not None and beta > 1.8:
        red.append(f"Very jumpy: beta {beta:.1f} (swings {beta:.1f}x the market)")
    pe, fpe = n.get("pe"), n.get("forward_pe")
    if pe is not None and pe > 60:
        red.append(f"Expensive: P/E {pe:.0f}")
    elif pe is not None and 0 < pe < 20:
        green.append(f"Cheap for its profits: P/E {pe:.0f}")
    if fpe is not None and fpe > 35 and not (pe is not None and pe > 60):
        red.append(f"Priced for perfection: forward P/E {fpe:.0f}")
    if pe and fpe and 0 < fpe < pe * .85:
        green.append(f"Earnings expected to grow (forward P/E {fpe:.0f} < {pe:.0f})")
    return green, red


def _numbers(block, price):
    fin = block.get("financialData") or {}
    summ = block.get("summaryDetail") or {}
    raw = market._raw
    target = raw(fin, "targetMeanPrice", 2)
    return {
        "revenue_growth": raw(fin, "revenueGrowth"),
        "earnings_growth": raw(fin, "earningsGrowth"),
        "margin": raw(fin, "profitMargins"),
        "free_cash": raw(fin, "freeCashflow"),
        "debt_equity": raw(fin, "debtToEquity"),
        "rating": raw(fin, "recommendationMean"),
        "target": target,
        "upside": market.upside(target, price),
        "pe": raw(summ, "trailingPE", 2),
        "forward_pe": raw(summ, "forwardPE", 2),
        "cap": raw(summ, "marketCap"),
        "price": price,
        "avg200": raw(summ, "twoHundredDayAverage", 2),
        "beta": raw(summ, "beta", 2),
    }


def news(name, symbol, limit=5):
    try:
        return [{"title": s.get("title", ""), "source": s.get("source", ""),
                 "link": s.get("link", ""), "age": s.get("age", "")}
                for s in feeds.search(f'"{name}" OR {symbol} stock when:7d', limit=limit)]
    except Exception:  # noqa: BLE001
        return []


def analyse(symbol):
    """The whole look at `symbol`, or {"ok": False, "error": ...}."""
    symbol = str(symbol or "").strip().upper()
    if not symbol:
        return {"ok": False, "error": "No stock named."}
    hit = _cache.get(symbol)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    try:
        data = market._summary_json(symbol, modules=MODULES)
        block = (((data or {}).get("quoteSummary") or {}).get("result") or [{}])[0]
    except Exception as e:  # noqa: BLE001
        log.info("analysis of %s failed: %s", symbol, e)
        return {"ok": False, "error": "The market data didn't answer. Try again in a minute."}
    profile = block.get("assetProfile") or {}
    price_block = block.get("price") or {}
    price = market._raw(price_block, "regularMarketPrice", 2)
    name = price_block.get("shortName") or price_block.get("longName") or symbol
    n = _numbers(block, price)
    green, red = flags(n)
    words, tone, held = verdict(len(green) - len(red), n)
    about = str(profile.get("longBusinessSummary") or "")
    result = {"ok": True, "symbol": symbol, "name": name, "price": price,
              "sector": profile.get("sector") or "", "industry": profile.get("industry") or "",
              "about": about[:600] + ("…" if len(about) > 600 else ""),
              "numbers": n, "verdict": words, "tone": tone,
              "score": len(green) - len(red), "green": green, "red": red, "held": held,
              "news": news(name, symbol)}
    _cache[symbol] = (time.monotonic() + TTL, result)
    return result
