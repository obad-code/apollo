"""Headlines and posts, from feeds that need no key and no account.

Google News publishes an RSS search feed, and trumpstruth.org mirrors Truth
Social as RSS - Trump Media's own real-time API is a paid Wall Street product
(CNBC, August 2026), and this is the public alternative. Both answer in about
a second, so they are read on a timer and cached; every reader here is total,
because a dead feed should cost a line on the display, never a turn.
"""

import html
import logging
import re
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

log = logging.getLogger("apollo.feeds")

HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")}
TIMEOUT = 8
NEWS_TTL = 600         # ten minutes; headlines do not change faster than that
POSTS_TTL = 300
POSTS_URL = "https://trumpstruth.org/feed"

# What the user actually follows. A topic is a Google News query; anything not
# listed is searched as typed.
TOPICS = {
    "gaming": 'PlayStation OR "GTA 6" OR gaming',
    "marvel": "Marvel",
    "movies": "box office OR movies",
    "markets": "stock market OR Nasdaq OR S&P 500",
}

# Words that make a post worth flagging before the market opens. Deliberately
# blunt: a flag is a nudge to read it, not a trading signal.
MOVING_WORDS = (
    "tariff", "tariffs", "fed", "federal reserve", "rate", "rates", "interest",
    "inflation", "china", "trade", "sanction", "sanctions", "oil", "opec",
    "crypto", "bitcoin", "stock", "stocks", "market", "markets", "economy",
    "jobs", "tax", "taxes", "chip", "chips", "semiconductor", "tiktok",
    "nvidia", "apple", "tesla", "amazon", "microsoft", "meta", "google",
)

_cache = {}
_lock = threading.Lock()


def _download(url):
    """The one call that touches the network. Tests replace this."""
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def _fetch(url, ttl):
    """Bytes for `url`, cached for `ttl` seconds. Raises if the fetch fails."""
    now = time.monotonic()
    with _lock:
        hit = _cache.get(url)
        if hit and hit[0] > now:
            return hit[1]
    body = _download(url)
    with _lock:
        _cache[url] = (now + ttl, body)
    return body


def _cached_or_fetch(url, ttl):
    """`_fetch`, but a failure falls back to whatever was last read.

    A feed that is down is worth an old headline with an honest age on it;
    it is not worth an empty display or a broken turn.
    """
    try:
        return _fetch(url, ttl)
    except Exception as e:  # noqa: BLE001
        with _lock:
            hit = _cache.get(url)
        if hit:
            log.info("%s unreachable (%s); using the last copy", url, e)
            return hit[1]
        log.info("%s unreachable (%s) and nothing cached", url, e)
        return None


def age_words(seconds):
    """How long ago, the way a person would say it."""
    seconds = max(0, int(seconds))
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def _when(item):
    node = item.find("pubDate")
    if node is None or not node.text:
        return 0.0
    try:
        return parsedate_to_datetime(node.text).timestamp()
    except (TypeError, ValueError):
        return 0.0


def _clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_news(body):
    """Google News RSS -> [{title, source, link, when, age}], newest first."""
    items = []
    for item in ET.fromstring(body).findall(".//item"):
        raw = _clean((item.findtext("title") or ""))
        if not raw:
            continue
        # Google appends " - Publisher" to every headline.
        title, _, source = raw.rpartition(" - ")
        when = _when(item)
        items.append({"title": title or raw, "source": source or "",
                      "link": item.findtext("link") or "", "when": when,
                      "age": age_words(time.time() - when) if when else ""})
    items.sort(key=lambda i: i["when"], reverse=True)
    return items


def parse_posts(body):
    """trumpstruth.org RSS -> [{text, when, age, market}], newest first.

    Image-only posts arrive as "[No Title] - Post from ..."; there is nothing
    to read out, so they are dropped rather than announced as silence.
    """
    items = []
    for item in ET.fromstring(body).findall(".//item"):
        text = _clean(item.findtext("description") or "") or _clean(item.findtext("title") or "")
        if not text or text.startswith("[No Title]"):
            continue
        when = _when(item)
        items.append({"text": text, "when": when,
                      "age": age_words(time.time() - when) if when else "",
                      "market": is_market_moving(text)})
    items.sort(key=lambda i: i["when"], reverse=True)
    return items


def is_market_moving(text):
    low = (text or "").lower()
    return any(re.search(rf"\b{re.escape(word)}\b", low) for word in MOVING_WORDS)


def _url_for(topic):
    query = TOPICS.get(topic.lower(), topic)
    return ("https://news.google.com/rss/search?"
            + urllib.parse.urlencode({"q": query, "hl": "en-US", "gl": "US",
                                      "ceid": "US:en"}))


def headlines(topic, limit=5):
    """The newest `limit` headlines for a topic (or any phrase)."""
    body = _cached_or_fetch(_url_for(topic), NEWS_TTL)
    if not body:
        return []
    try:
        return parse_news(body)[:limit]
    except ET.ParseError:
        return []


def posts(hours=24, limit=5):
    """Trump's posts from the last `hours`, market-moving ones first."""
    body = _cached_or_fetch(POSTS_URL, POSTS_TTL)
    if not body:
        return []
    try:
        found = parse_posts(body)
    except ET.ParseError:
        return []
    cutoff = time.time() - hours * 3600
    recent = [p for p in found if p["when"] >= cutoff] or found[:limit]
    recent.sort(key=lambda p: (not p["market"], -p["when"]))
    return recent[:limit]
