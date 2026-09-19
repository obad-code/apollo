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

    def fake_download(url):
        calls.append(url)
        return fixture("news_gaming.xml")

    feeds._cache.clear()
    monkeypatch.setattr(feeds, "_download", fake_download)
    first = feeds.headlines("gaming", limit=3)
    second = feeds.headlines("gaming", limit=3)
    assert len(first) == 3 and first == second
    assert len(calls) == 1                                        # cached


def test_failed_fetch_keeps_the_last_good_value(monkeypatch):
    feeds._cache.clear()
    monkeypatch.setattr(feeds, "_download", lambda url: fixture("news_gaming.xml"))
    good = feeds.headlines("marvel", limit=2)

    def broken(url):
        raise OSError("offline")

    monkeypatch.setattr(feeds, "_download", broken)
    url = feeds._url_for("marvel")
    feeds._cache[url] = (0, feeds._cache[url][1])              # expire it
    assert feeds.headlines("marvel", limit=2) == good              # last good value


def test_unknown_topic_is_searched_verbatim(monkeypatch):
    seen = []
    monkeypatch.setattr(feeds, "_download", lambda url: seen.append(url) or fixture("news_gaming.xml"))
    feeds._cache.clear()
    feeds.headlines("rocket lab", limit=1)
    assert "rocket" in seen[0].lower()
