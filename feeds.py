"""Headlines and posts, from feeds that need no key and no account.

Bing News publishes an RSS search feed with a picture and a paragraph for most
stories, which is what the display's feed shows when you open one; Google
News's feed has neither, and is kept as the fallback for when Bing has
nothing. trumpstruth.org mirrors Truth Social as RSS - Trump Media's own real-time API is a paid Wall Street product
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

# The same topics as Bing asks them. Its RSS answers `a OR b` with an empty
# feed, which is easy to mistake for a quiet news day; `|` is its OR.
BING_TOPICS = {
    "gaming": 'PlayStation | "GTA 6" | gaming',
    "marvel": "Marvel",
    "movies": "box office | movies",
    "markets": "stock market | Nasdaq | S&P 500",
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
    # Inline tags sit inside words ("@<span>name</span>"), so they go without
    # a trace; every other tag is a break between words.
    text = re.sub(r"</?(?:span|a)\b[^>]*>", "", text or "")
    text = re.sub(r"<[^>]+>", " ", text)
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


def _child(item, name):
    """A `News:` element's text, whatever namespace this query was given.

    Bing sets the namespace to the query's own URL, so it differs per topic
    and cannot be spelled once.
    """
    for node in item:
        if node.tag.rpartition("}")[2] == name and node.text:
            return node.text.strip()
    return ""


def _unwrap(link):
    """Bing's click-tracking redirect -> the article it points at."""
    parsed = urllib.parse.urlparse(link)
    if parsed.netloc.endswith("bing.com") and parsed.path.endswith("apiclick.aspx"):
        target = urllib.parse.parse_qs(parsed.query).get("url", [""])[0]
        if target.startswith(("https://", "http://")):
            return target
    return link


THUMB_MAX_W = 800        # the widest the display ever shows a story's picture
THUMB_SMALL = (400, 225)  # when the feed does not say how big the original is


def _thumbnail_size(max_w, max_h):
    """Bing's size parameters for the largest 16:9 picture the original has.

    Asked for more than that, Bing does not refuse - it centres the picture
    on white and hands that back, which on this display is a white frame.
    """
    try:
        width, height = int(max_w), int(max_h)
    except (TypeError, ValueError):
        width, height = THUMB_SMALL
    width = min(width, THUMB_MAX_W, height * 16 // 9)
    if width <= 0:
        width = THUMB_SMALL[0]
    return f"&w={width}&h={width * 9 // 16}&c=14"


def parse_bing(body):
    """Bing News RSS -> [{title, source, link, when, age, summary, image}].

    `image` is Bing's own thumbnail service, asked for over https; the page
    adds the size it wants. A story without one has an empty string there,
    which is what Google's stories carry too.
    """
    items = []
    for item in ET.fromstring(body).findall(".//item"):
        title = _clean(item.findtext("title") or "")
        if not title:
            continue
        image = _child(item, "Image")
        if image.startswith("http://"):
            image = "https://" + image[len("http://"):]
        if image.startswith("https://"):
            image += _thumbnail_size(_child(item, "ImageMaxWidth"),
                                     _child(item, "ImageMaxHeight"))
        when = _when(item)
        items.append({"title": title, "source": _clean(_child(item, "Source")),
                      "link": _unwrap(item.findtext("link") or ""),
                      "summary": _clean(item.findtext("description") or ""),
                      "image": image if image.startswith("https://") else "",
                      "when": when,
                      "age": age_words(time.time() - when) if when else ""})
    items.sort(key=lambda i: i["when"], reverse=True)
    return items


# A shared article, as Truth Social marks it up: an anchor whose text is the
# address itself, split into spans. A mention (@someone) is an anchor too,
# but its text is a name, so it is left alone.
_SHARED = re.compile(r'<a\b[^>]*href="(https?://[^"]+)"[^>]*>\s*<span class="invisible">'
                     r'.*?</a>', re.S)


def _unlink(description):
    """(description without its shared links, the first link it shared)."""
    found = _SHARED.search(description)
    cut = _SHARED.sub(" ", description)
    # "Headline: <link>" leaves the colon hanging once the link is gone.
    cut = re.sub(r"[\s:]+(</p>)", r"\1", cut)
    cut = re.sub(r"[\s:]+$", "", cut)
    return cut, html.unescape(found.group(1)) if found else ""


def parse_posts(body):
    """trumpstruth.org RSS -> [{text, when, age, market}], newest first.

    Image-only posts arrive as "[No Title] - Post from ..."; there is nothing
    to read out, so they are dropped rather than announced as silence.
    """
    items = []
    for item in ET.fromstring(body).findall(".//item"):
        description, link = _unlink(item.findtext("description") or "")
        text = _clean(description) or _clean(item.findtext("title") or "")
        if not text or text.startswith("[No Title]"):
            continue
        when = _when(item)
        items.append({"text": text, "link": link, "when": when,
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


def _bing_url_for(topic):
    query = BING_TOPICS.get(topic.lower(), topic)
    return ("https://www.bing.com/news/search?"
            + urllib.parse.urlencode({"q": query, "format": "rss", "setmkt": "en-US",
                                      "setlang": "en-US", "cc": "US"}))


def _read(url, parse):
    body = _cached_or_fetch(url, NEWS_TTL)
    if not body:
        return []
    try:
        return parse(body)
    except ET.ParseError:
        return []


# -- a picture for a story that came without one ------------------------------------

PICTURE_TTL = 24 * 3600      # a page's picture does not change
NO_PICTURE_TTL = 6 * 3600    # ...and one that had none, or would not answer, is asked again later
PAGE_MOST = 400_000          # the page's head is at the top; its body is not needed
_pictures = {}
_META = re.compile(r"<meta\b[^>]*>", re.I)
_ATTR = re.compile(r'([\w:-]+)\s*=\s*("([^"]*)"|\'([^\']*)\')')


def _page_head(url):
    """The first PAGE_MOST bytes of an article, as text. Tests replace this."""
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read(PAGE_MOST).decode("utf-8", "replace")


def page_picture(page):
    """The picture a page names for itself when it is shared - og:image, or
    twitter:image - over https, or ""."""
    wanted = {}
    for tag in _META.findall(page or ""):
        attrs = {m.group(1).lower(): html.unescape(m.group(3) if m.group(3) is not None else m.group(4))
                 for m in _ATTR.finditer(tag)}
        name = (attrs.get("property") or attrs.get("name") or "").lower()
        if name in ("og:image", "og:image:secure_url", "twitter:image", "twitter:image:src"):
            wanted.setdefault(name, attrs.get("content", "").strip())
    for name in ("og:image:secure_url", "og:image", "twitter:image", "twitter:image:src"):
        url = wanted.get(name, "")
        if url.startswith("//"):
            url = "https:" + url
        if url.startswith("http://"):
            url = "https://" + url[len("http://"):]
        if url.startswith("https://"):
            return url
    return ""


def picture_for(link):
    """A story's own picture, read off its page and kept - "" if it has none."""
    if not link.startswith(("https://", "http://")):
        return ""
    now = time.monotonic()
    with _lock:
        hit = _pictures.get(link)
    if hit and hit[0] > now:
        return hit[1]
    try:
        found = page_picture(_page_head(link))
    except Exception as e:  # noqa: BLE001 - a page that will not answer has no picture
        log.debug("no picture from %s: %s", link, e)
        found = ""
    with _lock:
        _pictures[link] = (now + (PICTURE_TTL if found else NO_PICTURE_TTL), found)
    return found


def fill_pictures(stories):
    """Every story without a picture given its page's own, the pages read at
    once. The feed shows a picture beside each story; about half come from
    Bing without one."""
    wanting = [story for story in stories if not story.get("image") and story.get("link")]
    if not wanting:
        return stories
    threads = [threading.Thread(target=lambda s=story: s.__setitem__("image", picture_for(s["link"])),
                                daemon=True) for story in wanting]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(TIMEOUT + 2)
    return stories


def headlines(topic, limit=5):
    """The newest `limit` headlines for a topic (or any phrase).

    Bing first, for the pictures and summaries; Google when Bing has nothing,
    with the same keys left empty so a reader never has to ask which it got.
    Bing's terms allow its results in an RSS reader for personal,
    non-commercial use, which is what this is.
    """
    found = _read(_bing_url_for(topic), parse_bing)
    if not found:
        found = [dict(story, summary="", image="")
                 for story in _read(_url_for(topic), parse_news)]
    return fill_pictures([dict(story) for story in found[:limit]])


def search(query, limit=10):
    """Google News for any query, newest first. Its search takes OR and
    quotes and `when:1d`, which Bing's RSS does not: asked for market-moving
    words, Bing answers with evergreen explainers."""
    return [dict(story, summary="", image="")
            for story in _read(_url_for(query), parse_news)][:limit]


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
