"""Trading mode's board: who is buying their own stock, what Congress is
trading, the filings and headlines that move a price, what traders are
piling into - and a read of what they are likely to pick next.

Every source here is public and was chosen after looking at what is
actually reachable (September 2026):

  insiders     OpenInsider's screens of SEC Form 4 filings: the latest
               open-market purchases of $25k and up, and "cluster buys" -
               several insiders of one company buying at once, the
               strongest of the insider signals. Market-wide, no key.
  congress     STOCK Act disclosures of House and Senate trades, from the
               CongressInvests API (free, no key, 100 requests a day - read
               at most every half hour).
  filings      The SEC's own feed of 8-K "current reports" - the material
               events a company must disclose within four business days:
               bankruptcy, restatements, delisting notices, a change of
               control, deals signed or ended, executives leaving. The SEC
               only answers requests that name a contact email: yours
               (SEC_CONTACT below, or the SEC_CONTACT variable).
  news         Market-moving headlines: Finnhub's market news with the key
               Apollo already has, and a news search for the words that
               move prices (halted, FDA, merger, probe, guidance cut...).
  traders      StockTwits - the trading floor of social media - for what is
               trending, why (its own summary of the chatter) and how
               bullish the messages about each are; and Reddit's finance
               communities through ApeWisdom, for mentions and how fast
               they are rising. Neither needs a key.
  x            Traders on X, if you give Apollo an X API bearer token
               (X_BEARER_TOKEN) and the accounts to follow (X_TRADERS). X
               has no free tier any more - reads are pay-per-use, about half
               a cent a post - so it is off without a token and capped at
               X_DAILY_READS posts a day (100 by default) with one.

`conclude` puts them together into the next picks: the tickers where the
signals agree - trending with traders, bullish messages, mentions rising,
insiders or members of Congress buying - each with its reasons. It is a
read of where the crowd and the insiders are heading, not advice, and the
display says so.

Nothing here raises: a source that fails is empty, and says so in
`board()["sources"]`.
"""

import datetime
import html
import json
import logging
import math
import os
import re
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import feeds
import live

log = logging.getLogger("apollo.trading")

HERE = os.path.dirname(os.path.abspath(__file__))
UA = "Apollo/1.0 (personal desktop assistant)"
TIMEOUT = 15          # OpenInsider's pages are large and it is not always quick

OPENINSIDER = {"buys": "http://openinsider.com/latest-insider-purchases-25k",
               "clusters": "http://openinsider.com/latest-cluster-buys"}
CONGRESS_URL = ("https://congressinfor-production.up.railway.app/trades/recent?"
                + urllib.parse.urlencode({"limit": 40, "days": 30}))
SEC_8K = ("https://www.sec.gov/cgi-bin/browse-edgar?"
          + urllib.parse.urlencode({"action": "getcurrent", "type": "8-K",
                                    "count": 60, "output": "atom"}))
SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"
FINNHUB_NEWS = "https://finnhub.io/api/v1/news?category=general"
STOCKTWITS_TRENDING = "https://api.stocktwits.com/api/2/trending/symbols.json"
STOCKTWITS_STREAM = "https://api.stocktwits.com/api/2/streams/symbol/{}.json"
APEWISDOM = "https://apewisdom.io/api/v1.0/filter/all-stocks/page/1"
X_SEARCH = "https://api.x.com/2/tweets/search/recent"

# How long each source is worth keeping, in seconds.
TTL = {"buys": 900, "clusters": 900, "congress": 1800, "filings": 300,
       "tickers": 86400, "news": 300, "trending": 600, "stream": 900,
       "reddit": 600, "x": 7200}

# The words that make a headline one to read now.
MOVING_QUERY = ('stock (halted OR "FDA approval" OR "FDA rejects" OR merger OR acquisition '
                'OR "to acquire" OR buyout OR "SEC investigation" OR "guidance cut" OR '
                'bankruptcy OR downgrade OR upgrade OR recall OR lawsuit)')

# The 8-K items worth a line, most serious first, and how serious each is.
ITEMS = {
    "1.03": ("Bankruptcy", 5), "4.02": ("Restatement - past results unreliable", 5),
    "3.01": ("Delisting notice", 4), "5.01": ("Change in control", 4),
    "2.06": ("Impairment", 4), "2.05": ("Layoffs / exit costs", 3),
    "1.01": ("Material deal signed", 3), "1.02": ("Material deal ended", 3),
    "2.01": ("Acquisition or sale completed", 3), "5.02": ("Executive or director change", 2),
    "2.02": ("Results announced", 2), "3.02": ("Unregistered share sale", 2),
    "8.01": ("Other material event", 1), "7.01": ("Reg FD disclosure", 1),
}

# StockTwits classes that are companies, not coins or funds.
EQUITIES = {"Stock", "DepositoryReceipt"}
STREAMS = 8          # how many trending names get their messages read for sentiment
PICKS = 5

_cache = {}
_lock = threading.Lock()


# -- the network, once --------------------------------------------------------------

def _download(url, headers=None):
    """The one call that touches the network. Tests replace this."""
    request = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def _get(key, url, headers=None):
    """Bytes for `url`, kept for TTL[key]; the last good copy if it fails now,
    None if there never was one."""
    now = time.monotonic()
    with _lock:
        hit = _cache.get(url)
    if hit and hit[0] > now:
        return hit[1]
    try:
        body = _download(url, headers)
    except Exception as e:  # noqa: BLE001 - a source that is down is empty, not fatal
        log.info("%s unreachable: %s", url, e)
        return hit[1] if hit else None
    with _lock:
        _cache[url] = (now + TTL[key], body)
    return body


def _json(body):
    try:
        return json.loads(body) if body else None
    except ValueError:
        return None


def _money(text):
    """'+$130,300' -> 130300.0; '' -> 0."""
    digits = re.sub(r"[^\d.\-]", "", str(text or "").replace("+", ""))
    try:
        return float(digits) if digits not in ("", "-", ".") else 0.0
    except ValueError:
        return 0.0


# -- insiders -------------------------------------------------------------------------

def _cell(raw):
    """A table cell's text. Attribute values go first: OpenInsider's tooltips
    carry whole <img> tags inside them, and a '>' in there cuts a naive
    tag-stripper short."""
    text = re.sub(r'"[^"]*"', '""', raw)
    text = re.sub(r"<[^>]*>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_openinsider(page):
    """An OpenInsider screen -> [{filed, traded, ticker, company, insider,
    title, industry, insiders, price, qty, owned, value}], as listed."""
    text = page.decode("utf-8", "replace") if isinstance(page, bytes) else str(page or "")
    start = text.find('class="tinytable"')
    if start < 0:
        return []
    table = text[start:]
    table = table[:table.find("</table>")] if "</table>" in table else table
    heads = [_cell(h).replace("\xa0", " ").strip().lower()
             for h in re.findall(r"<th[^>]*>(.*?)</th>", table, re.S)]
    rows = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S):
        cells = [_cell(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) != len(heads):
            continue
        got = dict(zip(heads, cells))
        ticker = got.get("ticker", "").strip().upper()
        if not re.fullmatch(r"[A-Z][A-Z.\-]{0,6}", ticker):
            continue
        rows.append({
            "filed": got.get("filing date", "")[:10],
            "traded": got.get("trade date", ""),
            "ticker": ticker,
            "company": got.get("company name", ""),
            "insider": got.get("insider name", ""),
            "title": got.get("title", ""),
            "industry": got.get("industry", ""),
            "insiders": int(_money(got.get("ins", "")) or 1),
            "price": _money(got.get("price", "")),
            "qty": _money(got.get("qty", "")),
            "owned": got.get("δown", got.get("Δown", "")),
            "value": _money(got.get("value", "")),
        })
    return rows


def insider_buys(limit=10):
    return parse_openinsider(_get("buys", OPENINSIDER["buys"]))[:limit]


def cluster_buys(limit=8):
    return parse_openinsider(_get("clusters", OPENINSIDER["clusters"]))[:limit]


# -- Congress --------------------------------------------------------------------------

def parse_congress(body):
    data = _json(body) or {}
    trades = []
    for t in data.get("trades") or []:
        ticker = str(t.get("ticker") or "").strip().upper()
        if not ticker or ticker in ("--", "N/A"):
            continue
        trades.append({"member": str(t.get("member") or ""), "chamber": str(t.get("chamber") or ""),
                       "side": "buy" if str(t.get("trade_type", "")).lower().startswith("buy")
                       or str(t.get("trade_type", "")).lower().startswith("purchase") else "sell",
                       "amount": str(t.get("amount") or ""), "traded": str(t.get("tx_date") or ""),
                       "disclosed": str(t.get("disclosed") or ""), "ticker": ticker,
                       "asset": str(t.get("asset") or ""), "link": str(t.get("link") or "")})
    trades.sort(key=lambda t: t["disclosed"], reverse=True)
    return trades


def congress_trades(limit=14):
    return parse_congress(_get("congress", CONGRESS_URL))[:limit]


# -- the filings and headlines that move a price ------------------------------------------

ATOM = "{http://www.w3.org/2005/Atom}"


def parse_8k(body, tickers=None):
    """The SEC's current 8-K feed -> [{company, cik, ticker, filed, items:
    [{code, label}], weight, link}], the most serious first."""
    tickers = tickers or {}
    try:
        root = ET.fromstring(body)
    except (ET.ParseError, TypeError):
        return []
    seen, filings = set(), []
    for entry in root.findall(f"{ATOM}entry"):
        title = entry.findtext(f"{ATOM}title") or ""
        match = re.match(r"\s*8-K[^-]*-\s*(.*?)\s*\((\d{4,10})\)", title)
        if not match:
            continue
        company, cik = match.group(1).strip(), str(int(match.group(2)))
        summary = html.unescape(entry.findtext(f"{ATOM}summary") or "")
        codes = re.findall(r"Item\s+(\d\.\d\d)", summary)
        items = [{"code": c, "label": ITEMS[c][0]} for c in dict.fromkeys(codes) if c in ITEMS]
        if not items:
            continue
        key = (cik, tuple(i["code"] for i in items))
        if key in seen:
            continue
        seen.add(key)
        link = entry.find(f"{ATOM}link")
        filings.append({"company": company.title() if company.isupper() else company,
                        "cik": cik, "ticker": tickers.get(cik, ""),
                        "filed": (entry.findtext(f"{ATOM}updated") or "")[:16].replace("T", " "),
                        "items": items, "weight": max(ITEMS[i["code"]][1] for i in items),
                        "link": link.get("href", "") if link is not None else ""})
    filings.sort(key=lambda f: (f["weight"], f["filed"]), reverse=True)
    return filings


# The contact the SEC is given: yours, as you said to use it (26 September
# 2026). SEC_CONTACT overrides it; set it to "off" to stop asking the SEC.
SEC_CONTACT = "youcancallmeobad@gmail.com"


def sec_contact():
    given = (os.environ.get("SEC_CONTACT") or SEC_CONTACT or "").strip()
    return "" if given.lower() == "off" else given


def _sec_tickers(headers):
    """CIK -> ticker. A company with several (its warrants, its units) is
    known by its common stock: the ticker with no suffix, the shortest."""
    data = _json(_get("tickers", SEC_TICKERS, headers)) or {}
    return pick_tickers(data)


def pick_tickers(data):
    best = {}
    for v in (data or {}).values():
        if not isinstance(v, dict):
            continue
        cik, ticker = str(v.get("cik_str")), str(v.get("ticker", "")).upper()
        if not ticker:
            continue
        rank = ("-" in ticker, len(ticker))
        if cik not in best or rank < best[cik][0]:
            best[cik] = (rank, ticker)
    return {cik: ticker for cik, (_, ticker) in best.items()}


def sensitive_filings(limit=10):
    """None when there is no contact to give the SEC; else the filings."""
    contact = sec_contact()
    if not contact:
        return None
    headers = {"User-Agent": f"Apollo personal assistant {contact}"}
    body = _get("filings", SEC_8K, headers)
    return parse_8k(body, _sec_tickers(headers))[:limit] if body else []


def parse_finnhub_news(body, limit=10):
    items = []
    for n in _json(body) or []:
        if not isinstance(n, dict) or not n.get("headline"):
            continue
        when = float(n.get("datetime") or 0)
        items.append({"title": str(n["headline"]), "source": str(n.get("source") or ""),
                      "link": str(n.get("url") or ""), "when": when,
                      "age": feeds.age_words(time.time() - when) if when else "",
                      "tickers": [t for t in str(n.get("related") or "").split(",") if t]})
    items.sort(key=lambda i: i["when"], reverse=True)
    return items[:limit]


def moving_news(limit=10):
    """Market-moving headlines: Finnhub's market news where there is a key,
    and a search for the words that move prices, merged, newest first."""
    found = []
    key = live.api_key()
    if key:
        found += parse_finnhub_news(_get("news", FINNHUB_NEWS, {"X-Finnhub-Token": key}))
    try:
        for story in feeds.search(MOVING_QUERY + " when:1d", limit=limit):
            found.append({"title": story.get("title", ""), "source": story.get("source", ""),
                          "link": story.get("link", ""), "when": story.get("when", 0),
                          "age": story.get("age", ""), "tickers": []})
    except Exception:  # noqa: BLE001
        log.debug("moving headlines failed", exc_info=True)
    seen, merged = set(), []
    for item in sorted(found, key=lambda i: i.get("when") or 0, reverse=True):
        key_ = re.sub(r"\W+", " ", item["title"].lower()).strip()[:60]
        if key_ and key_ not in seen:
            seen.add(key_)
            item["moving"] = feeds.is_market_moving(item["title"])
            merged.append(item)
    return merged[:limit]


# -- traders -------------------------------------------------------------------------------

def parse_trending(body):
    """StockTwits' trending -> companies only: [{symbol, name, score,
    watchers, summary, sector}], in its order."""
    out = []
    for s in (_json(body) or {}).get("symbols") or []:
        if s.get("instrument_class") not in EQUITIES:
            continue
        trends = s.get("trends") or {}
        out.append({"symbol": str(s.get("symbol") or "").upper(), "name": str(s.get("title") or ""),
                    "score": float(s.get("trending_score") or 0),
                    "watchers": int(s.get("watchlist_count") or 0),
                    "summary": str(trends.get("summary") or ""),
                    "sector": str(s.get("sector") or "")})
    return out


def parse_stream(body):
    """One symbol's recent StockTwits messages -> bullish and bearish counts
    among those that say which they are."""
    bull = bear = 0
    for m in (_json(body) or {}).get("messages") or []:
        mood = ((m.get("entities") or {}).get("sentiment") or {}).get("basic")
        bull += mood == "Bullish"
        bear += mood == "Bearish"
    return {"bull": bull, "bear": bear}


def parse_apewisdom(body, limit=15):
    out = []
    for r in (_json(body) or {}).get("results") or []:
        ticker = str(r.get("ticker") or "").upper()
        if not ticker:
            continue
        now, before = int(r.get("mentions") or 0), int(r.get("mentions_24h_ago") or 0)
        out.append({"ticker": ticker, "name": html.unescape(str(r.get("name") or "")),
                    "mentions": now, "before": before,
                    "rise": now / before if before else float(now > 0) * 3.0,
                    "rank": int(r.get("rank") or 0), "rank_before": int(r.get("rank_24h_ago") or 0)})
    return out[:limit]


def traders():
    """What traders are on: StockTwits' trending names with their sentiment,
    and Reddit's most mentioned."""
    trending = parse_trending(_get("trending", STOCKTWITS_TRENDING))
    for name in trending[:STREAMS]:
        mood = parse_stream(_get("stream", STOCKTWITS_STREAM.format(urllib.parse.quote(name["symbol"]))))
        said = mood["bull"] + mood["bear"]
        name["bull"] = mood["bull"] / said if said >= 5 else None
        name["votes"] = said
    for name in trending[STREAMS:]:
        name["bull"], name["votes"] = None, 0
    return {"trending": trending, "reddit": parse_apewisdom(_get("reddit", APEWISDOM))}


def parse_messages(body, limit=6):
    """One symbol's recent StockTwits messages -> the latest few, each with
    what it says and whether it calls itself bullish or bearish."""
    out = []
    for m in (_json(body) or {}).get("messages") or []:
        text = " ".join(str(m.get("body") or "").split())
        if not text:
            continue
        mood = ((m.get("entities") or {}).get("sentiment") or {}).get("basic") or ""
        out.append({"text": text[:280], "mood": mood.lower(),
                    "who": str((m.get("user") or {}).get("username") or "")})
    return out[:limit]


def chatter(symbol):
    """What traders are saying about one ticker on StockTwits right now:
    bullish and bearish counts, the share bullish, and the latest messages."""
    body = _get("stream", STOCKTWITS_STREAM.format(urllib.parse.quote(symbol.upper())))
    mood = parse_stream(body)
    said = mood["bull"] + mood["bear"]
    return {"bull": mood["bull"], "bear": mood["bear"],
            "bullish": round(mood["bull"] / said, 2) if said >= 5 else None,
            "messages": parse_messages(body)}


def on_the_desk(symbol, board):
    """Everywhere one ticker turns up on a board: as a pick and why,
    trending, on Reddit, bought by insiders, traded by Congress, in a
    filing or a headline. Empty lists where it does not."""
    ticker = symbol.upper()
    word = re.compile(rf"\b{re.escape(ticker)}\b")
    return {
        "pick": next(({"rank": i + 1, "reasons": p["reasons"], "why": p.get("summary", "")}
                      for i, p in enumerate(board.get("picks") or []) if p["ticker"] == ticker), None),
        "trending": next(({"rank": i + 1, "bullish": t.get("bull"), "why": t.get("summary", "")}
                          for i, t in enumerate(board.get("trending") or []) if t["symbol"] == ticker), None),
        "reddit": next(({"mentions": r["mentions"], "yesterday": r["before"]}
                        for r in board.get("reddit") or [] if r["ticker"] == ticker), None),
        "insider_clusters": [c for c in board.get("clusters") or [] if c["ticker"] == ticker],
        "insider_buys": [b for b in board.get("buys") or [] if b["ticker"] == ticker],
        "congress": [t for t in board.get("congress") or [] if t["ticker"] == ticker],
        "filings": [{"company": f["company"], "filed": f["filed"],
                     "what": [i["label"] for i in f["items"]]}
                    for f in board.get("filings") or [] if f["ticker"] == ticker],
        "headlines": [n["title"] for n in board.get("news") or [] if word.search(n.get("title", ""))],
    }


# -- X, when there is a token and the reads to spend --------------------------------------

X_STATE = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Apollo", "x_reads.json")


def x_settings():
    token = (os.environ.get("X_BEARER_TOKEN") or "").strip()
    handles = [h.strip().lstrip("@") for h in (os.environ.get("X_TRADERS") or "").split(",") if h.strip()]
    try:
        cap = int(os.environ.get("X_DAILY_READS") or 100)
    except ValueError:
        cap = 100
    return token, handles, max(0, cap)


def _x_spent(today):
    try:
        with open(X_STATE, encoding="utf-8") as f:
            state = json.load(f)
        return int(state.get("reads", 0)) if state.get("day") == today else 0
    except (OSError, ValueError):
        return 0


def _x_spend(today, reads):
    try:
        os.makedirs(os.path.dirname(X_STATE), exist_ok=True)
        with open(X_STATE, "w", encoding="utf-8") as f:
            json.dump({"day": today, "reads": _x_spent(today) + reads}, f)
    except OSError:
        pass


def parse_x(body):
    """Recent posts -> {tickers: {TICKER: posts that name it}, posts: [...]}."""
    data = _json(body) or {}
    users = {u.get("id"): u.get("username", "") for u in (data.get("includes") or {}).get("users") or []}
    counts, posts = {}, []
    for p in data.get("data") or []:
        text = str(p.get("text") or "")
        tags = sorted({t.upper() for t in re.findall(r"\$([A-Za-z]{1,5})\b", text)})
        for t in tags:
            counts[t] = counts.get(t, 0) + 1
        posts.append({"who": users.get(p.get("author_id"), ""), "text": text[:220], "tickers": tags})
    return {"tickers": counts, "posts": posts}


def x_traders():
    """None when X is not set up; else what the followed traders named."""
    token, handles, cap = x_settings()
    if not token or not handles:
        return None
    today = datetime.date.today().isoformat()
    left = cap - _x_spent(today)
    wanted = 50
    url = X_SEARCH + "?" + urllib.parse.urlencode({
        "query": "(" + " OR ".join(f"from:{h}" for h in handles[:20]) + ") has:cashtags -is:retweet",
        "max_results": wanted, "expansions": "author_id", "user.fields": "username"})
    with _lock:
        hit = _cache.get(url)
    fresh = hit and hit[0] > time.monotonic()
    if not fresh and left < wanted:
        # Out of today's reads: what was read last, or nothing.
        return parse_x(hit[1]) if hit else {"tickers": {}, "posts": [], "capped": True}
    body = _get("x", url, {"Authorization": f"Bearer {token}"})
    if body is not None and not fresh:
        _x_spend(today, len((_json(body) or {}).get("data") or []))
    return parse_x(body) if body else {"tickers": {}, "posts": []}


# -- the read -------------------------------------------------------------------------------

def conclude(trending=(), reddit=(), clusters=(), buys=(), congress=(), x=None, limit=PICKS):
    """The next picks: tickers scored by how many of the signals agree, each
    with why. [{ticker, name, score, bull, reasons, summary}], best first."""
    board = {}

    def pick(ticker, name="", signal=""):
        entry = board.setdefault(ticker, {"ticker": ticker, "name": name, "score": 0.0,
                                          "bull": None, "reasons": [], "summary": "",
                                          "signals": set()})
        if name and not entry["name"]:
            entry["name"] = name
        entry["signals"].add(signal)
        return entry

    count = max(1, len(trending))
    for i, t in enumerate(trending):
        p = pick(t["symbol"], t.get("name", ""), "crowd")
        p["score"] += 3.0 * (1 - i / count)
        p["summary"] = t.get("summary", "")
        reason = f"#{i + 1} trending on StockTwits"
        bull = t.get("bull")
        if bull is not None:
            p["bull"] = bull
            p["score"] += 4.0 * (bull - 0.5)
            reason += f", {round(bull * 100)}% bullish"
        p["reasons"].append(reason)
    for r in reddit:
        if r["mentions"] < 10:
            continue
        p = pick(r["ticker"], r.get("name", ""), "reddit")
        rise = r["rise"]
        p["score"] += 0.6 + min(2.0, max(0.0, math.log2(max(rise, 1e-9)))) if rise > 1 else 0.6
        p["reasons"].append(f"{r['mentions']} Reddit mentions"
                            + (f", {rise:.1f}x yesterday's" if rise >= 1.5 and r["before"] else ""))
    for c in clusters:
        p = pick(c["ticker"], c.get("company", ""), "insiders")
        p["score"] += 2.0 + min(1.5, c["value"] / 2_000_000)
        p["reasons"].append(f"{c['insiders']} insiders bought ${c['value'] / 1e6:.1f}M")
    for b in buys:
        if b["value"] < 100_000:
            continue
        p = pick(b["ticker"], b.get("company", ""), "insiders")
        p["score"] += 1.0 + min(1.0, b["value"] / 5_000_000)
        p["reasons"].append(f"{b['title'] or 'Insider'} {b['insider']} bought ${b['value'] / 1e6:.2f}M"
                            if b["value"] >= 1e6 else
                            f"{b['title'] or 'Insider'} {b['insider']} bought ${b['value'] / 1e3:.0f}k")
    # Congress: one line per member and stock however many filings it took,
    # weighted by the size of the range they disclosed.
    bought = {}
    for t in congress:
        if t["side"] == "buy":
            bought.setdefault((t["ticker"], t["member"]), []).append(t)
    for (ticker, member), trades in bought.items():
        p = pick(ticker, trades[0].get("asset", ""), "congress")
        floor = max(_money(t["amount"].split("-")[0]) for t in trades)
        p["score"] += 0.5 + min(1.5, math.log10(max(floor, 1000) / 1000) / 2)
        times = f" ({len(trades)} filings)" if len(trades) > 1 else ""
        p["reasons"].append(f"{member} ({trades[0]['chamber']}) bought {trades[0]['amount']}{times}")
    if x:
        total = sum(x.get("tickers", {}).values()) or 1
        for ticker, n in x.get("tickers", {}).items():
            p = pick(ticker, "", "x")
            p["score"] += 1.0 + 2.0 * n / total
            p["reasons"].append(f"named in {n} posts by the traders you follow on X")
    picks = [p for p in board.values() if p["reasons"] and p["score"] > 0]
    # Agreement first - two kinds of signal beat one strong one - then weight.
    picks.sort(key=lambda p: (min(len(p["signals"]), 3), p["score"]), reverse=True)
    for p in picks:
        p["score"] = round(p["score"], 2)
        p["reasons"] = p["reasons"][:4]
        p["signals"] = sorted(p["signals"])
    return picks[:limit]


def verdict(picks):
    """One line of it, for the display's head and for Apollo to say."""
    if not picks:
        return "Nothing stands out yet - the sources are quiet or unreachable."
    names = [p["ticker"] for p in picks[:3]]
    lead = picks[0]
    return (f"Traders and insiders are leaning into {', '.join(names)}"
            + (f" - {lead['ticker']} most of all: {lead['reasons'][0]}." if lead["reasons"] else "."))


def board():
    """Everything trading mode shows, read now (each source on its own clock)."""
    sources = {}

    def attempt(name, read, empty):
        try:
            value = read()
        except Exception as e:  # noqa: BLE001 - one source never takes the board down
            log.info("trading source %s failed: %s", name, e)
            sources[name] = "down"
            return empty
        sources[name] = "off" if value is None else ("ok" if value else "empty")
        return empty if value is None else value

    crowd = attempt("traders", traders, {"trending": [], "reddit": []})
    buys = attempt("insiders", insider_buys, [])
    clusters = attempt("clusters", cluster_buys, [])
    congress = attempt("congress", congress_trades, [])
    filings = attempt("filings", sensitive_filings, [])
    news = attempt("news", moving_news, [])
    x = attempt("x", x_traders, None)
    picks = conclude(crowd["trending"], crowd["reddit"], clusters, buys, congress, x)
    return {"picks": picks, "verdict": verdict(picks), "trending": crowd["trending"][:12],
            "reddit": crowd["reddit"][:10], "buys": buys, "clusters": clusters,
            "congress": congress, "filings": filings, "news": news, "x": x,
            "sources": sources, "sec_contact": bool(sec_contact()), "updated": time.time()}
