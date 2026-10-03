"""Market alerts: big news, told to you the moment Apollo sees it.

AMD crosses a trillion, Nvidia misses, the Fed cuts, a CEO quits: a story
that moves a big stock. Apollo watches for these all the time he is running
and, when one lands:

  - emails you (emailer.py) with what happened, why it matters and which way
    it is likely to push the stock - a read, not advice;
  - says it out loud if he is up, after any sentence in progress.

What he watches, every CHECK_EVERY seconds:

  News     Finnhub's market news (FINNHUB_API_KEY, which the live prices
           already use) and Google News for the big names and your
           watchlist, from the last hour.
  Moves    the live prices (live.py): a watchlist stock that moves
           MOVE_PCT or more inside MOVE_WINDOW is news in itself, and Apollo
           looks up why.

A story is scored - a big company or one you watch, words that move prices,
a fresh time stamp, a serious source - and only one at or over THRESHOLD is
told. Each is told once, and never more than MOST_PER_HOUR in an hour, so a
busy day is a few emails, not a flood.

How fast: as fast as the sources. Polling every minute, a story is usually
with you a minute or two after it is published; seconds-level needs a paid
real-time news stream (Benzinga, Finnhub's premium news, Polygon), which
slots in as another source here.
"""

import collections
import hashlib
import json
import logging
import os
import re
import threading
import time
import urllib.parse

log = logging.getLogger("apollo.alerts")

CHECK_EVERY = int(os.environ.get("APOLLO_ALERT_EVERY") or 60)
THRESHOLD = int(os.environ.get("APOLLO_ALERT_THRESHOLD") or 7)
MOST_PER_HOUR = 6
FRESH_MINUTES = 90          # a story older than this is not breaking
MOVE_PCT = 4.0
MOVE_WINDOW = 15 * 60
LANGUAGE = os.environ.get("APOLLO_ALERT_LANGUAGE") or "Arabic (Saudi dialect), then the same in English"
SEEN = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                    "Apollo", "alerts_seen.json")

# The companies whose news moves markets, by ticker and the names they go by.
BIG = {
    "AAPL": ("apple",), "MSFT": ("microsoft",), "NVDA": ("nvidia",),
    "AMZN": ("amazon",), "GOOGL": ("alphabet", "google"), "META": ("meta platforms", "meta"),
    "TSLA": ("tesla",), "AVGO": ("broadcom",), "AMD": ("amd", "advanced micro devices"),
    "TSM": ("tsmc", "taiwan semiconductor"), "NFLX": ("netflix",), "ORCL": ("oracle",),
    "INTC": ("intel",), "PLTR": ("palantir",), "JPM": ("jpmorgan",), "LLY": ("eli lilly",),
    "BRK.B": ("berkshire",), "WMT": ("walmart",), "XOM": ("exxon",), "COIN": ("coinbase",),
    "MSTR": ("microstrategy", "strategy inc"), "2222.SR": ("aramco",), "ARM": ("arm holdings",),
    "SMCI": ("supermicro", "super micro"), "MU": ("micron",), "QCOM": ("qualcomm",),
}

# Words that move a stock, and how much they count.
STRONG = (
    "trillion", "acquire", "acquires", "acquisition", "merger", "buyout", "takeover",
    "bankruptcy", "chapter 11", "guidance", "beats", "misses", "earnings", "revenue",
    "fda approv", "antitrust", "sec charges", "lawsuit", "recall", "resigns", "steps down",
    "fired", "layoffs", "record high", "all-time high", "plunge", "plunges", "soar", "soars",
    "surge", "surges", "tumble", "tumbles", "crash", "halted", "downgrade", "upgrade",
    "stock split", "buyback", "tariff", "export ban", "export curbs", "sanction",
    "rate cut", "rate hike", "fed cuts", "fed raises", "delist", "short seller",
    "investigation", "probe", "default", "dividend cut", "outage", "breach", "hack",
)
SERIOUS = ("reuters", "bloomberg", "cnbc", "wall street journal", "wsj", "financial times",
           "associated press", "ap news", "marketwatch", "barron", "the information", "axios")

FINNHUB_NEWS = "https://finnhub.io/api/v1/news"


def _norm(text):
    return re.sub(r"[^a-z0-9 ]+", " ", str(text or "").lower())


def key_of(title):
    """The same story from two sources is one story."""
    words = [w for w in _norm(title).split() if len(w) > 2][:10]
    return hashlib.sha1(" ".join(sorted(words)).encode()).hexdigest()[:16]


def companies_in(text, watch=()):
    """The tickers a headline is about: big names and the watchlist's own."""
    said = f" {_norm(text)} "
    found = []
    for ticker, names in BIG.items():
        if any(f" {name} " in said for name in names) or f" {ticker.lower()} " in said:
            found.append(ticker)
    for ticker in watch:
        bare = ticker.split(".")[0].lower()
        if len(bare) > 1 and f" {bare} " in said and ticker not in found:
            found.append(ticker)
    return found


def score(story, watch=(), now=None):
    """How much a story matters, and why. ({score, why, tickers})"""
    now = now or time.time()
    text = f"{story.get('title', '')} {story.get('summary', '')}"
    said = _norm(text)
    tickers = companies_in(text, watch)
    points, why = 0, []
    if tickers:
        points += 3
        why.append("about " + ", ".join(tickers[:3]))
        if any(t in watch for t in tickers):
            points += 2
            why.append("on your watchlist")
    hits = [w for w in STRONG if w in said]
    if hits:
        points += min(6, 3 * len(hits))
        why.append("says " + ", ".join(hits[:3]))
    age = now - float(story.get("when") or 0)
    if story.get("when") and age < 15 * 60:
        points += 2
        why.append("minutes old")
    elif story.get("when") and age > FRESH_MINUTES * 60:
        points -= 10
    if any(s in str(story.get("source", "")).lower() for s in SERIOUS):
        points += 1
    return {"score": points, "why": why, "tickers": tickers}


# -- the sources ------------------------------------------------------------------

def finnhub_news(key, fetch=None):
    """Finnhub's general market news, newest first."""
    import feeds
    fetch = fetch or feeds._download
    url = FINNHUB_NEWS + "?" + urllib.parse.urlencode({"category": "general", "token": key})
    try:
        rows = json.loads(fetch(url))
    except Exception as e:  # noqa: BLE001 - a source that is down is left out
        log.info("Finnhub news unavailable: %s", type(e).__name__)
        return []
    return [{"title": r.get("headline", ""), "summary": r.get("summary", ""),
             "source": r.get("source", ""), "link": r.get("url", ""),
             "when": float(r.get("datetime") or 0), "image": r.get("image", "")}
            for r in rows if isinstance(r, dict) and r.get("headline")]


def google_news(names, fetch=None):
    """Google News for these names, from the last hour."""
    import feeds
    fetch = fetch or feeds._download
    stories = []
    for start in range(0, len(names), 8):
        group = names[start:start + 8]
        query = " OR ".join(f'"{n}"' for n in group) + " stock when:1h"
        try:
            stories += feeds.parse_news(fetch(feeds._url_for(query)))
        except Exception as e:  # noqa: BLE001
            log.info("Google News unavailable: %s", type(e).__name__)
    return stories


class Moves:
    """Remembers each watched stock's recent prices to spot a sharp move."""

    def __init__(self):
        self.seen = collections.defaultdict(collections.deque)

    def note(self, prices, now=None):
        """`prices` {symbol: price}. Returns [(symbol, pct, then, now_price)]."""
        now = now or time.time()
        moved = []
        for symbol, price in prices.items():
            if not price:
                continue
            history = self.seen[symbol]
            history.append((now, float(price)))
            while history and now - history[0][0] > MOVE_WINDOW:
                history.popleft()
            first = history[0][1]
            pct = (float(price) - first) / first * 100 if first else 0
            if abs(pct) >= MOVE_PCT:
                moved.append((symbol, round(pct, 1), first, float(price)))
                history.clear()
                history.append((now, float(price)))
        return moved


# -- telling you -----------------------------------------------------------------

EXPLAIN = (
    "You are Apollo's market alert desk. A story just broke. Check the facts "
    "with search, then decide what the user should DO. The user knows this is "
    "not financial advice and wants a straight call, so give one. Answer in "
    "exactly this shape, in the language asked for:\n"
    "ACTION: one of BUY, SELL, HOLD or IGNORE, then the ticker. SELL means take "
    "money out - use it when the news is genuinely dangerous for a stock the user "
    "watches. IGNORE means it does not matter enough to act on.\n"
    "SUMMARY: two short sentences - what happened, and why that is the call.\n"
    "WHY:\n- three short bullets: the facts the call rests on.\n"
    "CONFIDENCE: low, medium or high.")

ACTIONS = ("BUY", "SELL", "HOLD", "IGNORE")


def parse_call(text):
    """The desk's answer -> {action, ticker, summary, why, confidence}.
    Anything it did not say is left empty; no ACTION reads as HOLD."""
    import re
    out = {"action": "HOLD", "ticker": "", "summary": "", "why": [], "confidence": ""}
    text = str(text or "")
    found = re.search(r"ACTION:\s*\**\s*(BUY|SELL|HOLD|IGNORE)\b\s*\**\s*([A-Z0-9.\-]{1,10})?", text, re.I)
    if found:
        out["action"] = found.group(1).upper()
        out["ticker"] = (found.group(2) or "").upper()
    summary = re.search(r"SUMMARY:\s*(.+?)(?:\n\s*WHY:|\n\s*CONFIDENCE:|$)", text, re.S | re.I)
    if summary:
        out["summary"] = " ".join(summary.group(1).split())
    why = re.search(r"WHY:\s*(.+?)(?:\n\s*CONFIDENCE:|$)", text, re.S | re.I)
    if why:
        out["why"] = [line.strip(" -•*\t") for line in why.group(1).splitlines() if line.strip(" -•*\t")][:4]
    confidence = re.search(r"CONFIDENCE:\s*(low|medium|high)", text, re.I)
    if confidence:
        out["confidence"] = confidence.group(1).lower()
    if not out["summary"] and not found:
        out["summary"] = " ".join(text.split())[:300]
    return out


def explain(story, tickers, language=LANGUAGE, think=None):
    """A few sentences on the story, from Gemini. Falls back to its summary."""
    prompt = (f"Language: {language}.\nTickers: {', '.join(tickers) or 'none named'}.\n"
              f"Headline: {story.get('title')}\nSource: {story.get('source')}\n"
              f"Summary: {story.get('summary', '')}\nLink: {story.get('link', '')}")
    try:
        if think is None:
            import lyla
            return lyla.ask_gemini(prompt, EXPLAIN)
        return think(prompt)
    except Exception as e:  # noqa: BLE001 - an alert still goes without the explanation
        log.info("alert explanation failed: %s", e)
        return story.get("summary") or ""


class Watcher:
    """The loop. `speak(alert)` says one out loud (Apollo, if he is up);
    `email(alert)` mails it; `watch()` is the watchlist; `prices()` the live
    prices; `sources()` the stories. All replaceable in tests."""

    def __init__(self, speak=None, email=None, watch=None, prices=None, sources=None,
                 explain=explain, path=SEEN, clock=time.time):
        self.speak = speak
        self.email = email or self._email
        self.watch = watch or _watchlist
        self.prices = prices or _live_prices
        self.sources = sources or _sources
        self.explain = explain
        self.path = path
        self.clock = clock
        self.moves = Moves()
        self.seen = self._load()
        self.sent = collections.deque()
        self._stop = threading.Event()
        self._thread = None

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as handle:
                data = json.load(handle)
            return dict(data) if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self):
        cutoff = self.clock() - 3 * 86400
        self.seen = {k: v for k, v in self.seen.items() if v >= cutoff}
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as handle:
                json.dump(self.seen, handle)
        except OSError:
            log.debug("could not keep the alerts seen", exc_info=True)

    def start(self, stopping=None):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, args=(stopping,), daemon=True,
                                            name="alerts")
            self._thread.start()
        return self

    def stop(self):
        self._stop.set()

    def _run(self, stopping):
        self._stop.wait(20)                   # let Apollo finish waking first
        first = True
        while not self._stop.is_set() and not (stopping and stopping()):
            try:
                self.check(quiet=first)
            except Exception:  # noqa: BLE001 - the watcher outlives a bad round
                log.warning("alert round failed", exc_info=True)
            first = False
            self._stop.wait(CHECK_EVERY)

    def _room(self):
        now = self.clock()
        while self.sent and now - self.sent[0] > 3600:
            self.sent.popleft()
        return len(self.sent) < MOST_PER_HOUR

    def check(self, quiet=False):
        """One round. `quiet` (the first) only learns what is already out, so
        starting Apollo does not replay the morning's news. Returns alerts."""
        watch = tuple(self.watch())
        now = self.clock()
        found = []
        for story in self.sources(watch):
            key = key_of(story.get("title"))
            if key in self.seen:
                continue
            self.seen[key] = now
            rated = score(story, watch, now)
            if rated["score"] >= THRESHOLD and not quiet:
                found.append({"kind": "news", "story": story, **rated})
        for symbol, pct, then, price in self.moves.note(self.prices(watch), now):
            key = f"move:{symbol}:{int(now // 1800)}"
            if key in self.seen:
                continue
            self.seen[key] = now
            story = {"title": f"{symbol} {'up' if pct > 0 else 'down'} {abs(pct)}% in minutes",
                     "summary": f"{symbol} went from {then:.2f} to {price:.2f}.",
                     "source": "live prices", "link": "", "when": now}
            if not quiet:
                found.append({"kind": "move", "story": story, "score": THRESHOLD,
                              "why": [f"moved {pct:+.1f}%"], "tickers": [symbol]})
        self._save()
        told = []
        for alert in sorted(found, key=lambda a: -a["score"]):
            if not self._room():
                log.info("alert held back - %d already this hour", MOST_PER_HOUR)
                break
            alert["explained"] = self.explain(alert["story"], alert["tickers"])
            alert["call"] = parse_call(alert["explained"])
            # Only news worth acting on is told: the desk's IGNORE is not, and
            # nor is a HOLD on a stock you do not watch - that was the spam.
            if alert["call"]["action"] == "IGNORE" or (
                    alert["call"]["action"] == "HOLD"
                    and not any(t in watch for t in alert["tickers"])):
                log.info("alert not told (%s): %s", alert["call"]["action"], alert["story"]["title"])
                continue
            self.sent.append(now)
            self._tell(alert)
            told.append(alert)
        return told

    def _tell(self, alert):
        for name, send in (("email", self.email), ("voice", self.speak)):
            if send is None:
                continue
            try:
                send(alert)
            except Exception as e:  # noqa: BLE001 - one channel failing never stops the other
                log.warning("alert by %s failed: %s", name, e)

    @staticmethod
    def _email(alert):
        import emailer
        if not emailer.ready():
            return
        story = alert["story"]
        call = alert.get("call") or parse_call(alert.get("explained"))
        ticker = call["ticker"] or ", ".join(alert.get("tickers", [])[:2])
        verb = {"BUY": "BUY", "SELL": "SELL - TAKE YOUR MONEY OUT", "HOLD": "HOLD"}.get(call["action"], call["action"])
        head = f"{verb} {ticker}".strip()
        lines = [call["summary"] or story.get("summary", ""),
                 *[f"• {reason}" for reason in call["why"]],
                 f"Confidence: {call['confidence'] or 'not given'} · Source: {story.get('source', '')}"]
        emailer.send(f"{head} — {story['title']}"[:180],
                     "\n".join([head, ""] + lines + ["", story.get("link", "")]),
                     rich=emailer.card(story["title"], lines, story.get("link", ""), action=head,
                                       tone=call["action"]))


def _watchlist():
    try:
        import watchlist
        return watchlist.current()
    except Exception:  # noqa: BLE001
        return []


def _live_prices(watch):
    import live
    feed = live.current_feed()
    if feed is None:
        return {}
    out = {}
    for symbol in watch:
        tick = feed.latest(symbol)
        if tick:
            out[symbol] = tick[0] if isinstance(tick, (tuple, list)) else tick
    return out


def _sources(watch):
    import live
    stories = []
    key = live.api_key()
    if key:
        stories += finnhub_news(key)
    names = [BIG[t][0] for t in BIG] + [t for t in watch if t not in BIG]
    stories += google_news(names[:32])
    return stories


WATCHER = None


def start(speak=None, stopping=None):
    """Start watching, once. `speak(alert)` is Apollo saying it."""
    global WATCHER
    if WATCHER is None:
        WATCHER = Watcher(speak=speak).start(stopping)
    return WATCHER
