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


def by_source(url):
    """Bing's feed for Bing's URLs, Google's for Google's."""
    return fixture("news_bing.xml" if "bing.com" in url else "news_gaming.xml")


def test_headlines_uses_the_cache_and_survives_failure(monkeypatch):
    calls = []

    def fake_download(url):
        calls.append(url)
        return by_source(url)

    feeds._cache.clear()
    monkeypatch.setattr(feeds, "_download", fake_download)
    first = feeds.headlines("gaming", limit=3)
    second = feeds.headlines("gaming", limit=3)
    assert len(first) == 3 and first == second
    assert len(calls) == 1                                        # cached


def test_failed_fetch_keeps_the_last_good_value(monkeypatch):
    feeds._cache.clear()
    monkeypatch.setattr(feeds, "_download", by_source)
    good = feeds.headlines("marvel", limit=2)

    def broken(url):
        raise OSError("offline")

    monkeypatch.setattr(feeds, "_download", broken)
    url = feeds._bing_url_for("marvel")
    feeds._cache[url] = (0, feeds._cache[url][1])              # expire it
    assert feeds.headlines("marvel", limit=2) == good              # last good value


def test_unknown_topic_is_searched_verbatim(monkeypatch):
    seen = []
    monkeypatch.setattr(feeds, "_download", lambda url: seen.append(url) or by_source(url))
    feeds._cache.clear()
    feeds.headlines("rocket lab", limit=1)
    assert "rocket" in seen[0].lower()


# -- Bing News: the display's pictures and summaries come from here ----------

def test_parse_bing_gives_summary_image_and_the_publishers_link():
    items = feeds.parse_bing(fixture("news_bing.xml"))
    assert [item["title"] for item in items] == [
        "Studio moves its winter release up by a month",           # newest first
        "A sequel opens to a record weekend at the global box office",
        "Streaming numbers for the summer's biggest release",
    ]                                                              # blank dropped
    record = items[1]
    assert record["source"] == "Example Trade"
    assert record["summary"].startswith("The film took $108M")
    # Bing's click-tracking wrapper is unwrapped to the article itself.
    assert record["link"] == "https://www.example.com/news/record-weekend"
    # Served over https, so the page never asks for a mixed-content image,
    # and asked for at a size the original has: past it, Bing pads the
    # picture out with white. 16:9 inside the feed's 1024x576, capped at 800.
    assert record["image"] == "https://www.bing.com/th?id=ORMS.0001&pid=News&w=800&h=450&c=14"
    assert record["when"] > 0 and record["age"]


def test_parse_bing_story_without_a_picture_has_an_empty_image():
    items = feeds.parse_bing(fixture("news_bing.xml"))
    winter = items[0]
    assert winter["image"] == ""
    assert winter["summary"] == "The date change clears the way for a holiday run."
    assert winter["link"] == "https://news.example.org/2026/09/winter"


def test_bing_is_asked_with_its_own_or():
    # Bing's RSS answers `a OR b` with nothing at all; `a | b` is its OR.
    url = feeds._bing_url_for("movies")
    assert "bing.com/news/search" in url and "format=rss" in url
    assert "%7C" in url and "OR" not in url
    assert "setmkt=en-US" in url


def test_headlines_prefer_bing_and_carry_pictures(monkeypatch):
    feeds._cache.clear()
    monkeypatch.setattr(feeds, "_download", by_source)
    stories = feeds.headlines("movies", limit=5)
    assert stories and any(story["image"] for story in stories)
    assert all("summary" in story for story in stories)


def test_headlines_fall_back_to_google_when_bing_has_nothing(monkeypatch):
    feeds._cache.clear()

    def bing_down(url):
        if "bing.com" in url:
            raise OSError("bing unreachable")
        return fixture("news_gaming.xml")

    monkeypatch.setattr(feeds, "_download", bing_down)
    stories = feeds.headlines("gaming", limit=3)
    assert len(stories) == 3
    # Google has no picture or summary to give; the keys are there, empty.
    assert all(story["image"] == "" and "summary" in story for story in stories)


POST_WITH_LINK = b"""<?xml version="1.0"?><rss><channel><item>
<description>&lt;p&gt;Netanyahu Bloc Takes Lead in Latest Israeli Election Poll: &lt;a href="https://www.example.com/newsfront/poll/2026/09/17/" rel="nofollow"&gt;&lt;span class="invisible"&gt;https://www.&lt;/span&gt;&lt;span class="ellipsis"&gt;example.com/newsfront/poll&lt;/span&gt;&lt;span class="invisible"&gt;/2026/09/17/&lt;/span&gt;&lt;/a&gt;&lt;/p&gt;</description>
<pubDate>Tue, 22 Sep 2026 13:29:00 GMT</pubDate></item>
<item><description>&lt;p&gt;RT &lt;span class="h-card"&gt;&lt;a href="https://truthsocial.com/@someone" rel="nofollow"&gt;@&lt;span&gt;someone&lt;/span&gt;&lt;/a&gt;&lt;/span&gt; A great day for the Economy!&lt;/p&gt;</description>
<pubDate>Tue, 22 Sep 2026 12:00:00 GMT</pubDate></item></channel></rss>"""


def test_a_posted_link_is_taken_out_of_the_words_and_kept_as_the_link():
    """A post that shares an article reads "Headline: https://www. example.com/..."
    once its markup is stripped - the address, broken with spaces, is most of
    the line. It comes out of the text and becomes the post's link."""
    shared, retweet = feeds.parse_posts(POST_WITH_LINK)
    assert shared["text"] == "Netanyahu Bloc Takes Lead in Latest Israeli Election Poll"
    assert shared["link"] == "https://www.example.com/newsfront/poll/2026/09/17/"
    # A mention is words, not an address: it stays.
    assert retweet["text"] == "RT @someone A great day for the Economy!"
    assert retweet["link"] == ""


def test_a_picture_with_no_stated_size_is_asked_for_small():
    """Without the feed's maximum, a small size is the one that is never padded."""
    streaming = feeds.parse_bing(fixture("news_bing.xml"))[2]
    assert streaming["image"] == "https://www.bing.com/th?id=OVFT.0002&pid=News&w=400&h=225&c=14"
