"""Private Eye: Apollo's scout.

Every few hours it takes your strongest interests (interests.py) and
searches free sources for each - Bing News (through feeds.py), Hacker News
and Reddit - then keeps the few best finds you have not been shown before:
the ones about what you care about most, freshest, and not about anything
you have said you do not care for. They go on the display (a Private Eye
row in the feed), into the morning briefing, and to Apollo when you ask
what it found. Say a find is useful or not - or click it - and its interest
moves up or down (interests.rate), which is what the next search goes by.

Nothing here costs anything: every source is free. Nothing here raises.
"""

import hashlib
import json
import logging
import math
import os
import re
import threading
import time
import urllib.parse
import urllib.request

import feeds
import interests
import journal

log = logging.getLogger("apollo.private_eye")

PATH = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                    "Apollo", "finds.json")

KEEP = 5                 # finds kept at a time
SEARCHES = 6             # interests searched each run, strongest first
PER_SOURCE = 6           # results taken from each source for each search
MAX_AGE = 3 * 86400      # older than this, it is not news to anyone
KEEP_FOUND = 2 * 86400   # a find stays on the list this long, if still among the best
SEEN = 500               # finds remembered, so none is found twice
HALF_LIFE_HOURS = 36     # how fast a find goes stale in the ranking

_lock = threading.Lock()


# -- the sources: each takes a search and returns what it found ---------------

def _get(url, timeout=8):
    request = urllib.request.Request(url, headers=feeds.HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def news(query):
    return [{"title": s["title"], "source": s.get("source", ""), "link": s.get("link", ""),
             "summary": s.get("summary", ""), "image": s.get("image", ""),
             "when": s.get("when") or 0.0}
            for s in feeds.headlines(query, limit=PER_SOURCE)]


def parse_hn(body):
    try:
        hits = json.loads(body).get("hits") or []
    except (ValueError, AttributeError):
        return []
    found = []
    for hit in hits:
        if not isinstance(hit, dict) or not hit.get("title"):
            continue
        link = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
        found.append({"title": hit["title"], "source": "Hacker News", "link": link,
                      "summary": "", "image": "", "when": float(hit.get("created_at_i") or 0),
                      "points": int(hit.get("points") or 0)})
    return found


def hacker_news(query):
    return parse_hn(_get("https://hn.algolia.com/api/v1/search_by_date?"
                         + urllib.parse.urlencode({"query": query, "tags": "story",
                                                   "hitsPerPage": PER_SOURCE})))


def parse_reddit(body):
    try:
        children = ((json.loads(body).get("data") or {}).get("children")) or []
    except (ValueError, AttributeError):
        return []
    found = []
    for child in children:
        post = (child or {}).get("data") or {}
        if not post.get("title") or not post.get("permalink"):
            continue
        found.append({"title": post["title"], "source": f"r/{post.get('subreddit', '')}",
                      "link": "https://www.reddit.com" + post["permalink"],
                      "summary": "", "image": "", "when": float(post.get("created_utc") or 0),
                      "points": int(post.get("score") or 0)})
    return found


def reddit(query):
    return parse_reddit(_get("https://www.reddit.com/search.json?"
                             + urllib.parse.urlencode({"q": query, "sort": "top", "t": "day",
                                                       "limit": PER_SOURCE})))


SOURCES = (news, hacker_news, reddit)


# -- what is kept -------------------------------------------------------------------

def _read():
    try:
        with open(PATH, encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return {"finds": list(data.get("finds") or []), "seen": list(data.get("seen") or [])}
    except (OSError, ValueError):
        pass
    return {"finds": [], "seen": []}


def _write(data):
    try:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        temporary = PATH + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False)
        os.replace(temporary, PATH)
    except OSError as e:
        log.info("could not save the finds: %s", e)


def load():
    """The finds, best first, each with how long ago it happened."""
    with _lock:
        finds = _read()["finds"]
    now = time.time()
    return [dict(f, age=feeds.age_words(now - f["when"]) if f.get("when") else "")
            for f in finds]


def rate(find_id, useful):
    """You said a find was useful, or it was not. Its interest moves; a find
    that was not useful goes. Returns the find, or None."""
    with _lock:
        data = _read()
        find = next((f for f in data["finds"] if f.get("id") == find_id), None)
        if find is None:
            return None
        if not useful:
            data["finds"] = [f for f in data["finds"] if f.get("id") != find_id]
        else:
            find["rated"] = True
        _write(data)
    interests.save(interests.rate(interests.load(), find.get("interest", ""), useful))
    journal.write("rated", interest=find.get("interest", ""), useful=bool(useful),
                  title=find.get("title", ""))
    return find


# -- the scout ----------------------------------------------------------------------

def _key(title):
    """A title with the noise taken out: the same story from two places matches."""
    return re.sub(r"[^a-z0-9؀-ۿ]+", " ", str(title).lower()).strip()


def _id(candidate):
    basis = candidate.get("link") or _key(candidate.get("title", ""))
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]


class PrivateEye:
    def __init__(self, sources=SOURCES, clock=time.time):
        self._sources = sources
        self._clock = clock
        self._stopping = threading.Event()
        self._thread = None

    def _score(self, find, weight, others, now):
        hours = max(0.0, (now - (find.get("when") or now)) / 3600)
        fresh = 0.5 ** (hours / HALF_LIFE_HOURS)
        title = find.get("title", "").lower()
        also = sum(1 for name in others if name.lower() in title)
        popular = 1 + 0.08 * math.log10(1 + max(0, find.get("points", 0)))
        return weight * fresh * (1 + 0.25 * min(2, also)) * popular

    def run(self):
        """One search, start to finish. Returns the finds now kept."""
        now = self._clock()
        profile = interests.load()
        wanted = sorted(profile.get("interests", []), key=lambda i: -i["weight"])[:SEARCHES]
        weights = {i["name"]: i["weight"] for i in profile.get("interests", [])}
        dislikes = [d.lower() for d in profile.get("dislikes", []) if d]
        names = [i["name"] for i in wanted]
        with _lock:
            data = _read()
        seen = set(data["seen"])
        candidates = {}
        for interest in wanted:
            for source in self._sources:
                try:
                    results = source(interest["query"]) or []
                except Exception as e:  # noqa: BLE001 - one dead source is not all of them
                    log.debug("%s failed for %r: %s", getattr(source, "__name__", "source"),
                              interest["query"], type(e).__name__)
                    continue
                for result in results:
                    title = str(result.get("title") or "").strip()
                    when = float(result.get("when") or 0)
                    if not title or not when or now - when > MAX_AGE:
                        continue
                    if any(d in title.lower() for d in dislikes):
                        continue
                    find = dict(result, title=title, when=when, interest=interest["name"])
                    find["id"] = _id(find)
                    if find["id"] in seen:
                        continue
                    others = [n for n in names if n != interest["name"]]
                    find["score"] = self._score(find, interest["weight"], others, now)
                    key = _key(title)
                    if key not in candidates or find["score"] > candidates[key]["score"]:
                        candidates[key] = find
        # What was already found stays while it is fresh and still earns its place.
        for old in data["finds"]:
            if now - old.get("found_at", 0) > KEEP_FOUND:
                continue
            key = _key(old.get("title", ""))
            others = [n for n in names if n != old.get("interest")]
            rescored = dict(old, score=self._score(old, weights.get(old.get("interest"), 0.2),
                                                   others, now))
            if key not in candidates or rescored["score"] >= candidates[key]["score"]:
                candidates[key] = rescored
        best = sorted(candidates.values(), key=lambda f: -f["score"])[:KEEP]
        for find in best:
            find.setdefault("found_at", now)
            find.pop("points", None)
        with _lock:
            data = _read()
            data["finds"] = best
            data["seen"] = (data["seen"] + [f["id"] for f in best if f["id"] not in seen])[-SEEN:]
            _write(data)
        log.info("Private Eye kept %d finds", len(best))
        return best

    # -- on its own

    def start(self, first=180.0, every=3 * 3600.0, on_found=None):
        def loop():
            if self._stopping.wait(first):
                return
            while not self._stopping.is_set():
                try:
                    if self.run() and on_found is not None:
                        on_found()
                except Exception:  # noqa: BLE001 - next time
                    log.info("Private Eye failed; trying again later", exc_info=True)
                self._stopping.wait(every)

        self._thread = threading.Thread(target=loop, daemon=True, name="apollo-private-eye")
        self._thread.start()
        return self

    def stop(self):
        self._stopping.set()
