# P4 Data and the Daily Recap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apollo knows what is happening: headlines on your interests, Trump's latest posts with the market-moving ones flagged, Riyadh's weather, your machine's load, and what Apollo's own APIs have cost today — and it can brief you on all of it, once a day by itself and any time you ask.

**Architecture:** Four small readers (`feeds`, `weather`, `sysinfo`, `usage`) each own one source and cache it. `dataservice` refreshes them on a schedule and keeps one snapshot for tools and (in P6) the display. `briefing` composes the snapshot into something speakable, and `presence` decides when the day's first recap is due.

**Tech Stack:** Python standard library for HTTP and XML, psutil, NVML through ctypes, pytest.

**Spec:** `docs/superpowers/specs/2026-09-19-apollo-jarvis-design.md` (§4 P4)

## Probe results this plan rests on (2026-09-20)

| Source | Result |
|---|---|
| Google News RSS per topic | 200, ~1.0 s, ~100 items each for gaming / Marvel / movies |
| trumpstruth.org/feed | 200, 0.8 s, 100 posts, newest ~6 h old; image-only posts come through as `[No Title] - Post from ...` and must be dropped |
| Open-Meteo, Riyadh | 200, 0.9 s, now 32.5 °C, today 29.7–42.0 °C, code 0 |
| NVML via `ctypes.CDLL("nvml.dll")` | works, 1.7 ms: GPU 5%, 8.6 GB total, name "NVIDIA GeForce RTX 4060 Ti" |

## Global Constraints

- Interests are Gaming (PlayStation, GTA 6), Marvel, Movies, Markets; watchlist AAPL MSFT NVDA TSLA AMZN GOOGL META plus S&P 500 and Nasdaq (`market.WATCHLIST`, `market.INDICES`); weather is Riyadh.
- Every reader caches and every reader is total: a dead source returns its last value with an age, or nothing — never an exception into a turn.
- No test may touch the network: parsers take fixtures, the clock is injectable.
- The recap is spoken by Gemini through `assistant.announce`, so it is in the language you last used.
- Tests: `.venv/Scripts/python.exe -m pytest -q`. Commit per task with the `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` trailer.

## Review Focus

1. A source that is down must not blank the display or break a briefing — Task 1 (`test_failed_fetch_keeps_the_last_good_value`).
2. The day's recap must happen once, not on every wake — Task 4 (`test_briefing_is_due_once_a_day`).
3. A recap at 3am must not claim yesterday's close is "today" — Task 4 (`test_market_line_says_when_the_market_last_traded`).
4. Image-only posts ("[No Title]") must not be read out as posts — Task 1 (`test_empty_posts_are_dropped`).
5. Token costs shown as facts when they are estimates — Task 3 (`test_cost_is_marked_estimated`).

---

### Task 1: `feeds.py` — headlines and posts

**Files:**
- Create: `feeds.py`, `tests/test_feeds.py`, `tests/fixtures/news_gaming.xml`, `tests/fixtures/posts.xml`

**Interfaces:**
- Produces: `feeds.TOPICS` (dict name → query), `feeds.headlines(topic, limit=5) -> list[dict]` (`title`, `source`, `age`, `when`, `link`), `feeds.posts(hours=24, limit=5) -> list[dict]` (`text`, `when`, `age`, `market`), `feeds.MOVING_WORDS`, `feeds.is_market_moving(text) -> bool`, `feeds.parse_news(xml_bytes)`, `feeds.parse_posts(xml_bytes)`, `feeds.age_words(seconds) -> str`.

- [ ] **Step 1: Record fixtures** (network, once):

```bash
.venv/Scripts/python.exe - <<'EOF'
import urllib.parse, urllib.request
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/140.0 Safari/537.36"}
def save(name, url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=10) as r:
        open(f"tests/fixtures/{name}", "wb").write(r.read())
save("news_gaming.xml", "https://news.google.com/rss/search?q=" + urllib.parse.quote('PlayStation OR "GTA 6" OR gaming') + "&hl=en-US&gl=US&ceid=US:en")
save("posts.xml", "https://trumpstruth.org/feed")
print("ok")
EOF
```

- [ ] **Step 2: Failing tests** — `tests/test_feeds.py`:

```python
# FILE: tests/test_feeds.py
import os
import time

import pytest

import feeds

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture(name):
    with open(os.path.join(FIX, name), "rb") as f:
        return f.read()


def test_parse_news_gives_title_source_and_age():
    items = feeds.parse_news(fixture("news_gaming.xml"))
    assert len(items) > 10
    first = items[0]
    assert first["title"] and " - " not in first["title"][-30:]   # source split off
    assert first["source"] and first["when"] > 0
    assert isinstance(first["age"], str)


def test_parse_posts_reads_text_and_time():
    items = feeds.parse_posts(fixture("posts.xml"))
    assert len(items) > 10
    assert all(item["text"] for item in items)
    assert items[0]["when"] >= items[-1]["when"]                  # newest first


def test_empty_posts_are_dropped():
    items = feeds.parse_posts(fixture("posts.xml"))
    assert not any(item["text"].startswith("[No Title]") for item in items)


def test_market_moving_flag():
    assert feeds.is_market_moving("Tariffs on imported chips will be announced Monday")
    assert feeds.is_market_moving("The Fed must cut rates NOW")
    assert feeds.is_market_moving("NVIDIA is doing a great job")
    assert not feeds.is_market_moving("Happy Thanksgiving to all, including the haters")


def test_age_words():
    assert feeds.age_words(30) == "just now"
    assert feeds.age_words(400) == "6m ago"
    assert feeds.age_words(7200) == "2h ago"
    assert feeds.age_words(200000) == "2d ago"


def test_headlines_uses_the_cache_and_survives_failure(monkeypatch):
    calls = []

    def fake_fetch(url, ttl):
        calls.append(url)
        return fixture("news_gaming.xml")

    feeds._cache.clear()
    monkeypatch.setattr(feeds, "_fetch", fake_fetch)
    first = feeds.headlines("gaming", limit=3)
    second = feeds.headlines("gaming", limit=3)
    assert len(first) == 3 and first == second
    assert len(calls) == 1                                        # cached


def test_failed_fetch_keeps_the_last_good_value(monkeypatch):
    feeds._cache.clear()
    monkeypatch.setattr(feeds, "_fetch", lambda url, ttl: fixture("news_gaming.xml"))
    good = feeds.headlines("marvel", limit=2)

    def broken(url, ttl):
        raise OSError("offline")

    monkeypatch.setattr(feeds, "_fetch", broken)
    feeds._cache[feeds._url_for("marvel")] = (0, feeds._cache[feeds._url_for("marvel")][1])
    assert feeds.headlines("marvel", limit=2) == good              # last good value


def test_unknown_topic_is_searched_verbatim(monkeypatch):
    seen = []
    monkeypatch.setattr(feeds, "_fetch", lambda url, ttl: seen.append(url) or fixture("news_gaming.xml"))
    feeds._cache.clear()
    feeds.headlines("rocket lab", limit=1)
    assert "rocket" in seen[0].lower()
```

- [ ] **Step 3: Run** — Expected: `No module named 'feeds'`.

- [ ] **Step 4: Implement** `feeds.py`:

```python
# FILE: feeds.py
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


def _fetch(url, ttl):
    """Bytes for `url`, cached for `ttl` seconds. Raises if the fetch fails."""
    now = time.monotonic()
    with _lock:
        hit = _cache.get(url)
        if hit and hit[0] > now:
            return hit[1]
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        body = response.read()
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
```

- [ ] **Step 5: Run** — Expected: 8 passed. Then the full suite.
- [ ] **Step 6: Commit** `git add feeds.py tests/test_feeds.py tests/fixtures && git commit -m "Add news and posts feeds"`

---

### Task 2: `weather.py` and `sysinfo.py`

**Files:**
- Create: `weather.py`, `sysinfo.py`, `tests/test_weather.py`, `tests/test_sysinfo.py`

**Interfaces:**
- Produces: `weather.RIYADH`, `weather.now() -> dict` (`temp`, `high`, `low`, `text`, `code`, `age`) or `{}`; `weather.describe(code) -> str`; `sysinfo.snapshot() -> dict` (`cpu`, `ram`, `gpu`, `gpu_name`, `vram`), `sysinfo.gpu() -> dict|None`.

- [ ] **Step 1: Failing tests**

```python
# FILE: tests/test_weather.py
import json

import weather


PAYLOAD = {
    "current": {"temperature_2m": 32.5, "weather_code": 0},
    "daily": {"temperature_2m_max": [42.0], "temperature_2m_min": [29.7]},
}


def test_now_reads_the_payload(monkeypatch):
    weather._cache.clear()
    monkeypatch.setattr(weather, "_get", lambda url, ttl: PAYLOAD)
    reading = weather.now()
    assert reading["temp"] == 33 and reading["high"] == 42 and reading["low"] == 30
    assert reading["text"] == "clear"


def test_codes_have_words():
    assert weather.describe(0) == "clear"
    assert "rain" in weather.describe(61)
    assert weather.describe(999) == ""


def test_a_dead_service_is_empty_not_an_error(monkeypatch):
    weather._cache.clear()

    def boom(url, ttl):
        raise OSError("offline")

    monkeypatch.setattr(weather, "_get", boom)
    assert weather.now() == {}
```

```python
# FILE: tests/test_sysinfo.py
import sysinfo


def test_snapshot_has_cpu_and_ram():
    snap = sysinfo.snapshot()
    assert 0 <= snap["cpu"] <= 100
    assert 0 < snap["ram"] <= 100


def test_gpu_is_optional(monkeypatch):
    monkeypatch.setattr(sysinfo, "_nvml", lambda: None)
    sysinfo._handle = None
    snap = sysinfo.snapshot()
    assert snap["gpu"] is None and snap["gpu_name"] == ""


def test_gpu_reads_nvml_when_present():
    gpu = sysinfo.gpu()
    if gpu is None:
        return                      # no NVIDIA card here; nothing to assert
    assert 0 <= gpu["load"] <= 100 and gpu["name"]
```

- [ ] **Step 2: Run** — Expected: missing modules.

- [ ] **Step 3: Implement**

```python
# FILE: weather.py
"""Riyadh's weather, from Open-Meteo: no key, no account, about a second."""

import json
import threading
import time
import urllib.request

RIYADH = (24.7136, 46.6753)
TIMEZONE = "Asia/Riyadh"
TTL = 900
TIMEOUT = 6

# WMO weather codes, in the handful of words a voice would use.
CODES = {0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
         45: "fog", 48: "freezing fog", 51: "light drizzle", 53: "drizzle",
         55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
         71: "light snow", 73: "snow", 75: "heavy snow", 80: "rain showers",
         81: "rain showers", 82: "heavy rain showers", 95: "thunderstorms",
         96: "thunderstorms with hail", 99: "thunderstorms with hail"}

_cache = {}
_lock = threading.Lock()


def describe(code):
    return CODES.get(int(code), "") if code is not None else ""


def _get(url, ttl):
    now = time.monotonic()
    with _lock:
        hit = _cache.get(url)
        if hit and hit[0] > now:
            return hit[1]
    with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
        data = json.load(response)
    with _lock:
        _cache[url] = (now + ttl, data)
    return data


def now(place=RIYADH):
    """Temperature now, today's high and low, and a word for the sky."""
    url = ("https://api.open-meteo.com/v1/forecast"
           f"?latitude={place[0]}&longitude={place[1]}"
           "&current=temperature_2m,weather_code"
           "&daily=temperature_2m_max,temperature_2m_min"
           f"&timezone={urllib.parse.quote(TIMEZONE)}&forecast_days=1")
    try:
        data = _get(url, TTL)
    except Exception:  # noqa: BLE001 - weather is a nicety, never a failure
        return {}
    current = data.get("current") or {}
    daily = data.get("daily") or {}
    code = current.get("weather_code")
    highs, lows = daily.get("temperature_2m_max") or [], daily.get("temperature_2m_min") or []
    return {"temp": round(current.get("temperature_2m", 0)),
            "high": round(highs[0]) if highs else None,
            "low": round(lows[0]) if lows else None,
            "code": code, "text": describe(code)}
```
(add `import urllib.parse` at the top)

```python
# FILE: sysinfo.py
"""What the machine is doing: CPU, memory, and the NVIDIA card if there is one.

NVML is read through ctypes rather than by running nvidia-smi: measured at
1.7 ms against about 80 ms for spawning the tool, and the display asks every
few seconds.
"""

import ctypes
import logging

import psutil

log = logging.getLogger("apollo.sysinfo")

_nvml_lib = None
_handle = None
_tried = False


class _Utilization(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]


def _nvml():
    """The NVML library, loaded once. None on a machine without it."""
    global _nvml_lib, _tried
    if _tried:
        return _nvml_lib
    _tried = True
    for name in ("nvml.dll", r"C:\Windows\System32\nvml.dll", "libnvidia-ml.so.1"):
        try:
            library = ctypes.CDLL(name)
        except OSError:
            continue
        if library.nvmlInit_v2() == 0:
            _nvml_lib = library
            break
    return _nvml_lib


def gpu():
    """Load, memory and name for GPU 0, or None."""
    global _handle
    library = _nvml()
    if library is None:
        return None
    try:
        if _handle is None:
            handle = ctypes.c_void_p()
            if library.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(handle)) != 0:
                return None
            _handle = handle
        used = _Utilization()
        if library.nvmlDeviceGetUtilizationRates(_handle, ctypes.byref(used)) != 0:
            return None
        memory = (ctypes.c_ulonglong * 3)()
        library.nvmlDeviceGetMemoryInfo(_handle, ctypes.byref(memory))
        name = ctypes.create_string_buffer(96)
        library.nvmlDeviceGetName(_handle, name, 96)
        return {"load": int(used.gpu), "name": name.value.decode(errors="replace"),
                "vram": round(memory[2] / 1e9, 1), "vram_total": round(memory[0] / 1e9, 1)}
    except Exception:  # noqa: BLE001 - telemetry is never worth an exception
        return None


def snapshot():
    """One reading of the machine, for the display and the briefing."""
    card = gpu()
    return {"cpu": round(psutil.cpu_percent(interval=None)),
            "ram": round(psutil.virtual_memory().percent),
            "gpu": card["load"] if card else None,
            "gpu_name": card["name"] if card else "",
            "vram": card["vram"] if card else None}
```

- [ ] **Step 4: Run** — Expected: all pass.
- [ ] **Step 5: Commit** `git add weather.py sysinfo.py tests/test_weather.py tests/test_sysinfo.py && git commit -m "Add weather and machine telemetry"`

---

### Task 3: `usage.py` — what Apollo's APIs cost today

**Files:**
- Create: `usage.py`, `tests/test_usage.py`
- Modify: `gemini_live.py` (record `usage_metadata`), `assistant.py` (record Claude's `usage`)

**Interfaces:**
- Produces: `usage.record(provider, model, prompt=0, response=0, seconds=0.0)`, `usage.today() -> dict` (`gemini`, `claude`, `cost`, `estimated: True`, `turns`), `usage.PRICES`, `usage.reset()`, `usage.PATH`.

- [ ] **Step 1: Failing tests**

```python
# FILE: tests/test_usage.py
import json
import os

import usage


def test_records_tokens_per_provider(tmp_path, monkeypatch):
    monkeypatch.setattr(usage, "PATH", str(tmp_path / "usage.json"))
    usage.reset()
    usage.record("gemini", "native-audio", prompt=1000, response=500)
    usage.record("gemini", "native-audio", prompt=200, response=100)
    usage.record("claude", "opus", prompt=3000, response=700)
    today = usage.today()
    assert today["gemini"]["prompt"] == 1200 and today["gemini"]["response"] == 600
    assert today["claude"]["prompt"] == 3000
    assert today["turns"] == 3


def test_cost_is_marked_estimated(tmp_path, monkeypatch):
    monkeypatch.setattr(usage, "PATH", str(tmp_path / "usage.json"))
    usage.reset()
    usage.record("claude", "opus", prompt=1_000_000, response=1_000_000)
    today = usage.today()
    assert today["estimated"] is True
    assert today["cost"] == round(usage.PRICES["claude"]["prompt"] + usage.PRICES["claude"]["response"], 2)


def test_survives_a_corrupt_file(tmp_path, monkeypatch):
    path = tmp_path / "usage.json"
    path.write_text("{ this is not json")
    monkeypatch.setattr(usage, "PATH", str(path))
    usage.reset()
    usage.record("gemini", "m", prompt=10)
    assert usage.today()["gemini"]["prompt"] == 10


def test_a_new_day_starts_at_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(usage, "PATH", str(tmp_path / "usage.json"))
    usage.reset()
    monkeypatch.setattr(usage, "_today_key", lambda: "2026-09-19")
    usage.record("gemini", "m", prompt=100)
    monkeypatch.setattr(usage, "_today_key", lambda: "2026-09-20")
    assert usage.today()["gemini"]["prompt"] == 0
```

- [ ] **Step 2: Run** — Expected: missing module.

- [ ] **Step 3: Implement** `usage.py`:

```python
# FILE: usage.py
"""What Apollo's APIs have cost today, counted on this machine.

Neither provider will tell an ordinary API key what it has spent, so Apollo
keeps its own ledger: tokens as they are reported on each response, totalled
per day in %LOCALAPPDATA%\\Apollo\\usage.json, and a cost worked out from the
table below. The prices are the published list ones and they change, so every
figure this module produces is marked `estimated` - the display says "approx"
and the voice says "about".
"""

import json
import logging
import os
import threading
from datetime import date

log = logging.getLogger("apollo.usage")

PATH = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                    "Apollo", "usage.json")

# Dollars per million tokens. Edit to match what you are actually billed.
PRICES = {
    "gemini": {"prompt": 3.00, "response": 12.00},    # native-audio in/out
    "claude": {"prompt": 5.00, "response": 25.00},    # Opus 5
}

_lock = threading.Lock()


def _today_key():
    return date.today().isoformat()


def _load():
    try:
        with open(PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(data):
    try:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError as e:
        log.info("could not write the usage ledger: %s", e)


def reset():
    """Forget today's totals (used by tests, and by a deliberate wipe)."""
    with _lock:
        data = _load()
        data.pop(_today_key(), None)
        _save(data)


def record(provider, model="", prompt=0, response=0, seconds=0.0):
    """Add one exchange to today's ledger. Never raises."""
    try:
        with _lock:
            data = _load()
            day = data.setdefault(_today_key(), {"turns": 0})
            entry = day.setdefault(provider, {"prompt": 0, "response": 0, "seconds": 0.0})
            entry["prompt"] += int(prompt or 0)
            entry["response"] += int(response or 0)
            entry["seconds"] = round(entry.get("seconds", 0.0) + float(seconds or 0.0), 1)
            day["turns"] = day.get("turns", 0) + 1
            day["model_" + provider] = model or day.get("model_" + provider, "")
            _save(data)
    except Exception:  # noqa: BLE001 - a ledger must never break a turn
        log.debug("usage not recorded", exc_info=True)


def today():
    """Today's totals and an estimated cost."""
    with _lock:
        day = _load().get(_today_key(), {})
    out = {"turns": day.get("turns", 0), "estimated": True}
    cost = 0.0
    for provider, price in PRICES.items():
        entry = day.get(provider) or {"prompt": 0, "response": 0, "seconds": 0.0}
        out[provider] = {"prompt": entry.get("prompt", 0),
                         "response": entry.get("response", 0),
                         "seconds": entry.get("seconds", 0.0)}
        cost += (entry.get("prompt", 0) * price["prompt"]
                 + entry.get("response", 0) * price["response"]) / 1_000_000
    out["cost"] = round(cost, 2)
    out["tokens"] = sum(out[p]["prompt"] + out[p]["response"] for p in PRICES)
    return out
```

- [ ] **Step 4: Wire it in.**
  - `gemini_live.py`, in `_receive_loop`, after the content handling:
    ```python
                meta = getattr(response, "usage_metadata", None)
                if meta is not None:
                    self._note_usage(meta)
    ```
    and on the class:
    ```python
        def _note_usage(self, meta):
            """Tokens as the server reports them, for the day's ledger."""
            if self._on_usage is None:
                return
            try:
                self._on_usage(int(getattr(meta, "prompt_token_count", 0) or 0),
                               int(getattr(meta, "response_token_count", 0) or 0))
            except Exception:
                pass
    ```
    with `on_usage=None` in `__init__` (`self._on_usage = on_usage`).
  - `assistant.py`: `Voice` passes `on_usage=lambda p, r: usage.record("gemini", gemini_live.MODEL, prompt=p, response=r)`; in `ask_claude`, after each `_send`, `usage.record("claude", CLAUDE_MODEL, prompt=response.usage.input_tokens, response=response.usage.output_tokens)` guarded by `getattr`.

- [ ] **Step 5: Run** the suite — Expected: all pass.
- [ ] **Step 6: Commit** `git add usage.py tests/test_usage.py gemini_live.py assistant.py && git commit -m "Count what Apollo's APIs cost each day"`

---

### Task 4: `briefing.py` — the recap, and when it is due

**Files:**
- Create: `briefing.py`, `tests/test_briefing.py`
- Modify: `tools.py` (`get_news`, `get_posts`, `daily_briefing`)

**Interfaces:**
- Produces: `briefing.compose(now=None) -> dict` (`date`, `hijri`, `weather`, `market`, `headlines`, `posts`, `reminders`, `usage`), `briefing.spoken(payload) -> str` (what Gemini is asked to say), `briefing.Schedule(state_path)` with `.due(now, idle_seconds) -> bool`, `.done(now)`, `.last`; `briefing.STATE_PATH`; `briefing.hijri(date) -> str`.

- [ ] **Step 1: Failing tests**

```python
# FILE: tests/test_briefing.py
import datetime

import pytest

import briefing


@pytest.fixture
def quiet(monkeypatch):
    monkeypatch.setattr(briefing.feeds, "headlines",
                        lambda topic, limit=5: [{"title": f"{topic} story", "source": "IGN",
                                                 "age": "2h ago", "when": 1, "link": ""}])
    monkeypatch.setattr(briefing.feeds, "posts",
                        lambda hours=24, limit=5: [{"text": "Tariffs on chips Monday",
                                                    "age": "3h ago", "when": 1, "market": True}])
    monkeypatch.setattr(briefing.weather, "now", lambda: {"temp": 33, "high": 42, "low": 30, "text": "clear"})
    monkeypatch.setattr(briefing.market, "quote", lambda symbol: {
        "symbol": symbol, "name": symbol, "price": 100.0, "change": 1.0, "change_pct": 1.0,
        "currency": "USD", "exchange": "NMS", "points": [], "previous_close": 99.0, "time": 0})
    monkeypatch.setattr(briefing.market, "market_status", lambda now=None: {
        "open": False, "next": None, "label": "NYSE opens in 8h 00m"})


def test_compose_has_every_section(quiet):
    payload = briefing.compose(now=datetime.datetime(2026, 9, 20, 8, 30))
    assert payload["date"] == "Sunday 20 September 2026"
    assert payload["weather"]["temp"] == 33
    assert payload["market"]["indices"] and payload["market"]["movers"]
    assert payload["headlines"]["gaming"][0]["title"] == "gaming story"
    assert payload["posts"][0]["market"] is True


def test_market_line_says_when_the_market_last_traded(quiet):
    payload = briefing.compose(now=datetime.datetime(2026, 9, 20, 3, 0))
    assert "opens in" in payload["market"]["status"].lower()
    said = briefing.spoken(payload)
    assert "closed" in said.lower() or "opens" in said.lower()


def test_spoken_is_an_instruction_not_a_script(quiet):
    said = briefing.spoken(briefing.compose(now=datetime.datetime(2026, 9, 20, 8, 30)))
    assert "language" in said.lower()
    assert len(said) < 4000


def test_briefing_is_due_once_a_day(tmp_path):
    state = briefing.Schedule(str(tmp_path / "briefing.json"))
    morning = datetime.datetime(2026, 9, 20, 8, 0)
    assert state.due(morning, idle_seconds=0.0) is True
    state.done(morning)
    assert state.due(datetime.datetime(2026, 9, 20, 9, 0), idle_seconds=0.0) is False
    assert state.due(datetime.datetime(2026, 9, 21, 7, 0), idle_seconds=0.0) is True


def test_not_due_while_you_are_away(tmp_path):
    state = briefing.Schedule(str(tmp_path / "briefing.json"))
    assert state.due(datetime.datetime(2026, 9, 20, 8, 0), idle_seconds=600.0) is False


def test_hijri_date():
    assert briefing.hijri(datetime.date(2026, 9, 20)).endswith("1448")
```

- [ ] **Step 2: Run** — Expected: missing module.

- [ ] **Step 3: Implement** `briefing.py`:

```python
# FILE: briefing.py
"""The day, as Apollo tells it.

One composer that gathers what the readers already cache - weather, the
watchlist, headlines on what you follow, Trump's last day of posts, your
reminders, and what the APIs have cost - and one schedule that decides when
the day's first recap is due. The words are Gemini's: `spoken` hands it the
facts and asks for a short read in whatever language you last used, because a
briefing written here would always sound like a form letter.
"""

import datetime
import json
import logging
import os

import feeds
import market
import reminders
import usage
import weather

log = logging.getLogger("apollo.briefing")

STATE_PATH = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                          "Apollo", "briefing.json")

# You are at the machine, not walking past it.
PRESENT_SECONDS = 120

HIJRI_MONTHS = ("Muharram", "Safar", "Rabi I", "Rabi II", "Jumada I", "Jumada II",
                "Rajab", "Shaban", "Ramadan", "Shawwal", "Dhul-Qadah", "Dhul-Hijjah")


def hijri(day):
    """The Umm al-Qura date, for a user who reads both calendars."""
    try:
        from datetime import date as _date  # noqa: F401
        import calendar  # noqa: F401
        # Kuwaiti algorithm: good to a day, and needs no dependency.
        jd = day.toordinal() + 1721425
        n = jd - 1948440 + 10632
        n2 = n // 10631
        n = n % 10631
        j = ((n - 1) // 354) if n else 0
        year = 30 * n2 + j + 1
        days = n - (j * 354 + (3 + 11 * j) // 30)
        month = min(12, int((days + 28.5001) / 29.5))
        day_of = int(days - int(29.5001 * month - 29))
        return f"{max(1, day_of)} {HIJRI_MONTHS[max(0, month - 1)]} {year}"
    except Exception:  # noqa: BLE001
        return ""


def compose(now=None):
    """Everything the recap draws on. Every part is optional and may be empty."""
    now = now or datetime.datetime.now()
    indices, movers = [], []
    for symbol in market.INDICES:
        try:
            indices.append(_small(market.quote(symbol)))
        except Exception:  # noqa: BLE001 - a dead feed costs a line, not the recap
            continue
    for symbol in market.WATCHLIST:
        try:
            movers.append(_small(market.quote(symbol)))
        except Exception:  # noqa: BLE001
            continue
    movers.sort(key=lambda q: abs(q["change_pct"]), reverse=True)

    try:
        status = market.market_status(now.astimezone() if now.tzinfo else None)["label"]
    except Exception:  # noqa: BLE001
        status = ""

    return {
        "date": now.strftime("%A %-d %B %Y") if os.name != "nt" else now.strftime("%A %#d %B %Y"),
        "time": now.strftime("%H:%M"),
        "hijri": hijri(now.date()),
        "day_of_year": now.timetuple().tm_yday,
        "week": now.isocalendar().week,
        "weather": weather.now(),
        "market": {"indices": indices, "movers": movers[:4], "status": status},
        "headlines": {topic: feeds.headlines(topic, limit=2) for topic in feeds.TOPICS},
        "posts": feeds.posts(hours=24, limit=3),
        "reminders": reminders.pending()[:3],
        "usage": usage.today(),
    }


def _small(quote):
    return {"symbol": quote["symbol"], "name": quote["name"], "price": quote["price"],
            "change_pct": round(quote["change_pct"], 2), "currency": quote["currency"]}


def spoken(payload):
    """The instruction Gemini is given: the facts, and how to read them."""
    lines = [f"Brief the user on their day. It is {payload['date']}, {payload['time']} in Riyadh."]
    if payload.get("hijri"):
        lines.append(f"Hijri date: {payload['hijri']}.")
    sky = payload.get("weather") or {}
    if sky:
        lines.append(f"Riyadh: {sky.get('temp')}C now, {sky.get('text')}, "
                     f"high {sky.get('high')} low {sky.get('low')}.")
    market_part = payload.get("market") or {}
    if market_part.get("status"):
        lines.append(f"Market: {market_part['status']}.")
    for quote in market_part.get("indices", []) + market_part.get("movers", []):
        lines.append(f"{quote['symbol']} {quote['price']:.2f} {quote['change_pct']:+.2f}%.")
    for topic, items in (payload.get("headlines") or {}).items():
        for item in items:
            lines.append(f"{topic}: {item['title']} ({item['source']}, {item['age']}).")
    for post in payload.get("posts") or []:
        flag = " [market-moving]" if post.get("market") else ""
        lines.append(f"Trump posted{flag} {post['age']}: {post['text'][:200]}")
    for reminder in payload.get("reminders") or []:
        lines.append(f"Reminder: {reminder['text']} ({reminder['due']}).")
    lines.append(
        "Read this as a short spoken briefing - about 30 to 45 seconds, in the "
        "language the user last spoke to you in, their dialect if it was Arabic. "
        "Lead with the date and weather in one sentence, then the market, then "
        "the two or three stories that actually matter to them, then anything "
        "market-moving in the posts, then their reminders. Give real numbers. "
        "Skip anything the facts above do not cover, and never invent a figure.")
    return "\n".join(lines)


class Schedule:
    """Whether today's recap has happened yet.

    Once a day, the first time you are actually at the machine. The state is a
    date in a file, so a restart - or a crash halfway through a briefing -
    cannot give you the same recap twice.
    """

    def __init__(self, path=None):
        self.path = path or STATE_PATH
        self.last = self._read()

    def _read(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f).get("last", "")
        except (OSError, ValueError):
            return ""

    def due(self, now=None, idle_seconds=0.0):
        now = now or datetime.datetime.now()
        if idle_seconds > PRESENT_SECONDS:
            return False              # you are not here yet
        return self.last != now.date().isoformat()

    def done(self, now=None):
        now = now or datetime.datetime.now()
        self.last = now.date().isoformat()
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"last": self.last}, f)
        except OSError as e:
            log.info("could not save the briefing date: %s", e)
```

- [ ] **Step 4: Tools.** In `tools.py`:

```python
@_tool("get_news", "reading the news",
       "Headlines on a topic the user follows (gaming, marvel, movies, markets) or any "
       "phrase. Speak only what this returns.",
       _obj({"topic": _str("Topic or search phrase"),
             "limit": {"type": "integer", "description": "How many, 1-8 (default 4)"}},
            ["topic"]))
def _get_news(ctx, topic, limit=4):
    ctx.activity(f"reading {topic} news")
    items = feeds.headlines(topic, limit=max(1, min(8, int(limit))))
    if not items:
        return {"ok": False, "error": f"No headlines came back for {topic}."}
    return {"ok": True, "topic": topic,
            "headlines": [{k: item[k] for k in ("title", "source", "age")} for item in items]}


@_tool("get_posts", "checking posts",
       "Donald Trump's recent Truth Social posts, market-moving ones first. Use when the "
       "user asks what he posted or said.",
       _obj({"hours": {"type": "integer", "description": "How far back, 1-72 (default 24)"}}))
def _get_posts(ctx, hours=24):
    ctx.activity("checking posts")
    items = feeds.posts(hours=max(1, min(72, int(hours))), limit=5)
    if not items:
        return {"ok": False, "error": "Nothing has been posted in that window."}
    return {"ok": True, "posts": [{"text": p["text"][:400], "age": p["age"],
                                   "market_moving": p["market"]} for p in items]}


@_tool("daily_briefing", "putting the briefing together",
       "The user's daily recap: date, Riyadh weather, their watchlist, headlines on what "
       "they follow, recent posts, reminders. Use for 'brief me', 'what did I miss', "
       "'catch me up'.",
       _obj({}))
def _daily_briefing(ctx):
    ctx.activity("putting the briefing together")
    payload = briefing.compose()
    ctx.show(overlay_content.clean_visual({"cards": _briefing_cards(payload)}))
    return {"ok": True, "brief": briefing.spoken(payload)}


def _briefing_cards(payload):
    cards = []
    sky = payload.get("weather") or {}
    if sky:
        cards.append({"label": "Riyadh", "value": f"{sky.get('temp')}C {sky.get('text', '')}"[:14]})
    for quote in (payload.get("market") or {}).get("indices", [])[:2]:
        cards.append({"label": quote["symbol"].lstrip("^"),
                      "value": f"{quote['change_pct']:+.1f}%"})
    posts = payload.get("posts") or []
    if posts:
        cards.append({"label": "Posts", "value": f"{len(posts)} new"})
    return cards
```
with `import briefing`, `import feeds` added beside the other tool imports.

- [ ] **Step 5: Run** — Expected: all pass.
- [ ] **Step 6: Commit** `git add briefing.py tests/test_briefing.py tools.py && git commit -m "Compose the daily recap, and decide when it is due"`

---

### Task 5: `dataservice.py`, and Apollo asking for the recap

**Files:**
- Create: `dataservice.py`, `tests/test_dataservice.py`
- Modify: `apollo.py` (start the service; trigger the day's recap), `assistant.py` (`brief_now`)

**Interfaces:**
- Produces: `dataservice.DataService(on_snapshot=None)` with `.start()`, `.stop()`, `.snapshot` (dict), `.refresh(force=False)`, `.INTERVALS`; `assistant.brief_now(ui, voice)`.

- [ ] **Step 1: Failing tests**

```python
# FILE: tests/test_dataservice.py
import time

import dataservice


def test_snapshot_gathers_every_reader(monkeypatch):
    monkeypatch.setattr(dataservice.market, "quote", lambda s: {
        "symbol": s, "name": s, "price": 10.0, "change": 0.1, "change_pct": 1.0,
        "currency": "USD", "exchange": "NMS", "points": [(1, 10.0)], "previous_close": 9.9, "time": 0})
    monkeypatch.setattr(dataservice.market, "history", lambda s, p: {
        "symbol": s, "name": s, "price": 10.0, "change_pct": 1.0, "currency": "USD",
        "exchange": "NMS", "points": [(i, 10.0 + i) for i in range(8)], "previous_close": 9.9, "time": 0})
    monkeypatch.setattr(dataservice.feeds, "headlines", lambda topic, limit=5: [{"title": "x", "source": "y", "age": "1h ago", "when": 1, "link": ""}])
    monkeypatch.setattr(dataservice.feeds, "posts", lambda hours=24, limit=5: [])
    monkeypatch.setattr(dataservice.weather, "now", lambda: {"temp": 30, "text": "clear", "high": 40, "low": 25})

    service = dataservice.DataService()
    service.refresh(force=True)
    snap = service.snapshot
    assert snap["market"]["indices"] and snap["market"]["watchlist"]
    assert snap["market"]["watchlist"][0]["spark"]          # a sparkline's points
    assert snap["news"] and snap["weather"]["temp"] == 30
    assert snap["system"]["cpu"] >= 0 and "updated" in snap


def test_a_broken_reader_leaves_the_rest(monkeypatch):
    def boom(*a, **kw):
        raise OSError("offline")
    monkeypatch.setattr(dataservice.market, "quote", boom)
    monkeypatch.setattr(dataservice.market, "history", boom)
    monkeypatch.setattr(dataservice.feeds, "headlines", lambda topic, limit=5: [])
    monkeypatch.setattr(dataservice.feeds, "posts", lambda hours=24, limit=5: [])
    monkeypatch.setattr(dataservice.weather, "now", lambda: {})
    service = dataservice.DataService()
    service.refresh(force=True)
    assert service.snapshot["market"]["watchlist"] == []
    assert service.snapshot["system"]["cpu"] >= 0


def test_it_tells_the_page_only_when_asked():
    seen = []
    service = dataservice.DataService(on_snapshot=seen.append)
    service.refresh(force=True)
    assert len(seen) == 1
```

- [ ] **Step 2: Run** — Expected: missing module.
- [ ] **Step 3: Implement** `dataservice.py`:

```python
# FILE: dataservice.py
"""One background thread that keeps Apollo's world up to date.

Every reader below caches on its own, so this exists for two reasons: to pay
for the slow parts (a dozen quotes, four news queries) on a timer instead of
inside a turn, and to keep one snapshot that both the tools and the display
read. The intervals are what the sources are worth: prices while New York is
open, headlines every ten minutes, the machine every few seconds.
"""

import logging
import threading
import time

import feeds
import market
import sysinfo
import usage
import weather

log = logging.getLogger("apollo.data")

INTERVALS = {"market": 60, "news": 600, "posts": 300, "weather": 900, "system": 5}
SPARK_POINTS = 24


class DataService:
    def __init__(self, on_snapshot=None):
        self.on_snapshot = on_snapshot
        self.snapshot = {"market": {"indices": [], "watchlist": [], "status": ""},
                         "news": {}, "posts": [], "weather": {}, "system": {},
                         "usage": {}, "updated": 0.0}
        self._due = {key: 0.0 for key in INTERVALS}
        self._thread = None
        self._stopping = threading.Event()

    def start(self):
        if self._thread is None or not self._thread.is_alive():
            self._stopping.clear()
            self._thread = threading.Thread(target=self._run, daemon=True, name="apollo-data")
            self._thread.start()
        return self

    def stop(self):
        self._stopping.set()

    def _run(self):
        while not self._stopping.is_set():
            try:
                self.refresh()
            except Exception:  # noqa: BLE001 - the loop outlives any one failure
                log.debug("refresh failed", exc_info=True)
            self._stopping.wait(2.0)

    def refresh(self, force=False):
        """Update whatever is due. `force` updates everything."""
        now = time.monotonic()
        changed = False
        for key, every in INTERVALS.items():
            if not force and now < self._due[key]:
                continue
            self._due[key] = now + every
            getattr(self, "_read_" + key)()
            changed = True
        if changed:
            self.snapshot["updated"] = time.time()
            self.snapshot["usage"] = usage.today()
            if self.on_snapshot is not None:
                try:
                    self.on_snapshot(self.snapshot)
                except Exception:  # noqa: BLE001
                    log.debug("snapshot listener failed", exc_info=True)

    # -- one reader each; none of them may raise ---------------------------

    def _read_market(self):
        indices, watchlist = [], []
        for symbol in market.INDICES:
            quote = self._quote(symbol, spark=False)
            if quote:
                indices.append(quote)
        for symbol in market.WATCHLIST:
            quote = self._quote(symbol, spark=True)
            if quote:
                watchlist.append(quote)
        status = ""
        try:
            status = market.market_status()["label"]
        except Exception:  # noqa: BLE001
            pass
        self.snapshot["market"] = {"indices": indices, "watchlist": watchlist,
                                   "status": status}

    def _quote(self, symbol, spark):
        try:
            data = market.history(symbol, "1d") if spark else market.quote(symbol)
        except Exception:  # noqa: BLE001
            return None
        points = [round(price, 2) for _, price in data.get("points", [])][-SPARK_POINTS:]
        return {"symbol": data["symbol"], "name": data["name"],
                "price": round(data["price"], 2),
                "change_pct": round(data["change_pct"], 2),
                "currency": data["currency"], "spark": points}

    def _read_news(self):
        self.snapshot["news"] = {topic: feeds.headlines(topic, limit=4)
                                 for topic in feeds.TOPICS}

    def _read_posts(self):
        self.snapshot["posts"] = feeds.posts(hours=24, limit=4)

    def _read_weather(self):
        self.snapshot["weather"] = weather.now()

    def _read_system(self):
        self.snapshot["system"] = sysinfo.snapshot()
```

- [ ] **Step 4: Apollo.** In `assistant.py`:

```python
def brief_now(ui, voice):
    """Say the day's recap, in Apollo's voice."""
    payload = briefing.compose()
    visual = overlay_content.clean_visual({"cards": tools._briefing_cards(payload)})
    if visual is not None and hasattr(ui, "visual"):
        ui.visual(visual)
    announce(ui, voice, briefing.spoken(payload),
             "Here is your briefing. The data services are not answering right now.")
```
(with `import briefing` at the top).

In `apollo.py`: `import briefing`, `import dataservice`; in `__init__`, `self.data = None`, `self.schedule = briefing.Schedule()`; in `worker`, after the clips buffer:
```python
        # Everything the display and the briefing read, refreshed on a timer
        # rather than inside a turn.
        self.data = dataservice.DataService(on_snapshot=self.on_data).start()
```
with
```python
    def on_data(self, snapshot):
        """A fresh world snapshot. The page only wants it when it is visible."""
        ui = getattr(self, "ui", None)
        if ui is not None and ui.alive and self.overlay.mode == Overlay.FULL:
            ui.data(snapshot)
```
and `WebReporter.data(snapshot)` → `self._call("data", snapshot)`.

The day's recap, in `check_presence` (which the watcher already calls with the idle time):
```python
        if (self.ui is not None and not self.ui.quiet and not self.turn_busy
                and self.voice is not None and self.schedule.due(idle_seconds=idle)):
            self.schedule.done()
            threading.Thread(target=self.morning, daemon=True, name="briefing").start()
```
and
```python
    def morning(self):
        """The day's first recap: open the display and say it."""
        self.presence.toggle_peek()          # show the world while it talks
        self.apply_mode()
        try:
            assistant.brief_now(self.ui, self.voice)
        finally:
            self.presence.toggle_peek()
            self.apply_mode()
```

- [ ] **Step 5: Run** the suite — Expected: all pass.
- [ ] **Step 6: Commit** `git add dataservice.py tests/test_dataservice.py apollo.py assistant.py && git commit -m "Keep the world up to date, and give the day's recap once"`

---

### Task 6: Live check and README

- [ ] **Step 1:** `probes/probe_briefing.py` — compose a real briefing and print `spoken(payload)` plus the snapshot's shape and timings. Expected: real prices, four topics of headlines, today's posts, Riyadh weather, and a plausible instruction under 4000 characters.
- [ ] **Step 2:** With `GEMINI_API_KEY` set, have a real `LiveSession` speak it (`prompt(spoken)`), in English and after an Arabic turn. Expected: a 30–45 s read, in the right language. (If the Live API is still refusing tool turns, record that and check the text path only.)
- [ ] **Step 3:** README: a "What Apollo knows" section — the feeds, the once-a-day recap and "brief me", where the ledger lives, and that costs are estimates.
- [ ] **Step 4: Commit** `git add -A && git commit -m "Live briefing check and README"`
