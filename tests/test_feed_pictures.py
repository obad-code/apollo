"""The feed's stories each with a picture: Bing's where it gives one, and
otherwise the one the article's own page names for sharing (og:image) -
read once and kept, never asked of a page again for hours."""
import feeds


PAGE = """<html><head>
<meta name="twitter:image" content="https://cdn.example.com/tw.jpg">
<meta content="https://cdn.example.com/og.jpg?a=1&amp;b=2" property="og:image" />
</head><body>...</body></html>"""


def test_a_page_s_own_picture_is_found():
    assert feeds.page_picture(PAGE) == "https://cdn.example.com/og.jpg?a=1&b=2"
    assert feeds.page_picture('<meta property="og:image" content="//img.example.com/a.png">') == \
        "https://img.example.com/a.png"
    assert feeds.page_picture('<meta name="twitter:image" content="http://x.example.com/b.png">') == \
        "https://x.example.com/b.png"
    assert feeds.page_picture('<meta property="og:image" content="/relative.png">') == ""
    assert feeds.page_picture("") == ""


def test_a_page_is_read_once_and_its_answer_kept(monkeypatch):
    read = []
    monkeypatch.setattr(feeds, "_pictures", {})
    monkeypatch.setattr(feeds, "_page_head", lambda url: read.append(url) or PAGE)
    assert feeds.picture_for("https://news.example.com/a") == "https://cdn.example.com/og.jpg?a=1&b=2"
    assert feeds.picture_for("https://news.example.com/a") == "https://cdn.example.com/og.jpg?a=1&b=2"
    assert read == ["https://news.example.com/a"]


def test_a_page_that_will_not_answer_has_no_picture(monkeypatch):
    def down(url):
        raise OSError("refused")
    monkeypatch.setattr(feeds, "_pictures", {})
    monkeypatch.setattr(feeds, "_page_head", down)
    assert feeds.picture_for("https://news.example.com/b") == ""
    assert feeds.picture_for("javascript:alert(1)") == ""


def test_only_the_stories_without_one_are_filled(monkeypatch):
    asked = []
    monkeypatch.setattr(feeds, "picture_for", lambda link: asked.append(link) or "https://p/x.jpg")
    stories = [{"link": "https://a", "image": "https://bing/th"}, {"link": "https://b", "image": ""}]
    feeds.fill_pictures(stories)
    assert asked == ["https://b"] and stories[1]["image"] == "https://p/x.jpg"
    assert stories[0]["image"] == "https://bing/th"


def test_headlines_come_with_their_pictures(monkeypatch):
    monkeypatch.setattr(feeds, "_read", lambda url, parse: [{"title": "t", "link": "https://a", "image": ""}]
                        if "bing" in url else [])
    monkeypatch.setattr(feeds, "picture_for", lambda link: "https://p/y.jpg")
    assert feeds.headlines("gaming")[0]["image"] == "https://p/y.jpg"
