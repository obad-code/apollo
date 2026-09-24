"""Private Eye: Apollo's scout. Every few hours it searches free sources for
what you care about, keeps the best few finds you have not seen, and learns
from what you make of them."""
import datetime
import json
import time
import threading

import pytest

import dataservice
import interests
import journal
import private_eye
import tools
from tools import Context

NOW = 1_790_300_000.0


@pytest.fixture(autouse=True)
def own_files(tmp_path, monkeypatch):
    monkeypatch.setattr(private_eye, "PATH", str(tmp_path / "finds.json"))
    profile = interests.load()
    profile["interests"] = [
        {"name": "GTA 6", "kind": "game", "weight": 0.9, "query": "GTA 6"},
        {"name": "Nvidia", "kind": "company", "weight": 0.5, "query": "Nvidia"},
        {"name": "Tesla", "kind": "company", "weight": 0.1, "query": "Tesla"},
    ]
    profile["dislikes"] = ["crypto"]
    interests.save(profile)


def item(title, hours_old=1, link=None, source="Example", summary=""):
    return {"title": title, "source": source, "link": link or f"https://example.com/{hash(title)}",
            "summary": summary, "image": "", "when": NOW - hours_old * 3600}


def eye(results, fail=()):
    """A Private Eye whose one source answers from `results` by query."""
    def source(query):
        if query in fail:
            raise OSError("down")
        return list(results.get(query, []))
    return private_eye.PrivateEye(sources=(source,), clock=lambda: NOW)


def titles(finds):
    return [f["title"] for f in finds]


def test_it_searches_for_the_strongest_interests():
    asked = []
    scout = private_eye.PrivateEye(sources=(lambda q: asked.append(q) or [],), clock=lambda: NOW)
    scout.run()
    assert asked[:2] == ["GTA 6", "Nvidia"]


def test_the_stronger_interest_and_the_fresher_find_come_first():
    finds = eye({"GTA 6": [item("GTA 6 trailer three", hours_old=2)],
                 "Nvidia": [item("Nvidia earnings beat", hours_old=2)],
                 "Tesla": [item("Tesla recall", hours_old=1)]}).run()
    assert titles(finds)[0] == "GTA 6 trailer three"
    assert titles(finds).index("Nvidia earnings beat") < titles(finds).index("Tesla recall")
    assert finds[0]["interest"] == "GTA 6"


def test_what_you_do_not_care_for_and_what_is_old_are_left_out():
    finds = eye({"Nvidia": [item("Nvidia and crypto miners", 1),
                            item("Nvidia three weeks ago", hours_old=24 * 21),
                            item("Nvidia new GPU", 1)]}).run()
    assert titles(finds) == ["Nvidia new GPU"]


def test_the_same_story_twice_is_one_find():
    finds = eye({"GTA 6": [item("GTA 6 delayed again", link="https://a.com/1"),
                           item("GTA 6 Delayed Again!", link="https://b.com/2")]}).run()
    assert len(finds) == 1


def test_a_find_is_not_found_twice():
    results = {"GTA 6": [item("GTA 6 map leak")]}
    scout = eye(results)
    assert titles(scout.run()) == ["GTA 6 map leak"]
    results["GTA 6"].append(item("GTA 6 price announced"))
    again = scout.run()
    assert titles(again).count("GTA 6 map leak") <= 1
    assert "GTA 6 price announced" in titles(again)


def test_a_dead_source_does_not_stop_the_others():
    finds = eye({"Nvidia": [item("Nvidia new GPU")]}, fail=("GTA 6",)).run()
    assert titles(finds) == ["Nvidia new GPU"]


def test_only_the_best_few_are_kept_and_they_are_saved():
    many = {"GTA 6": [item(f"GTA 6 story {i}", hours_old=i + 1) for i in range(12)]}
    finds = eye(many).run()
    assert len(finds) == private_eye.KEEP
    assert titles(private_eye.load()) == titles(finds)


def test_a_useful_find_raises_its_interest_and_a_useless_one_lowers_it_and_goes():
    scout = eye({"GTA 6": [item("GTA 6 map leak")], "Nvidia": [item("Nvidia new GPU")]})
    finds = scout.run()
    gta = next(f for f in finds if f["interest"] == "GTA 6")
    nv = next(f for f in finds if f["interest"] == "Nvidia")
    private_eye.rate(gta["id"], useful=True)
    private_eye.rate(nv["id"], useful=False)
    weights = {i["name"]: i["weight"] for i in interests.load()["interests"]}
    assert weights["GTA 6"] > 0.9 - 1e-9 and weights["Nvidia"] < 0.5
    assert nv["id"] not in [f["id"] for f in private_eye.load()]
    rated = [e for e in journal.day(datetime.date.today()) if e["kind"] == "rated"]
    assert {(e["interest"], e["useful"]) for e in rated} == {("GTA 6", True), ("Nvidia", False)}


def test_hacker_news_and_reddit_are_read():
    hn = {"hits": [{"title": "Show HN: a GPU trick", "url": "https://x.dev/gpu",
                    "created_at_i": NOW - 3600, "points": 120, "objectID": "1"}]}
    reddit = {"data": {"children": [{"data": {
        "title": "GTA 6 screenshot", "url": "https://i.redd.it/a.png",
        "permalink": "/r/GTA6/comments/1/x/", "subreddit": "GTA6",
        "created_utc": NOW - 7200, "score": 900}}]}}
    (a,) = private_eye.parse_hn(json.dumps(hn))
    (b,) = private_eye.parse_reddit(json.dumps(reddit))
    assert a["title"] == "Show HN: a GPU trick" and a["source"] == "Hacker News"
    assert b["source"] == "r/GTA6" and b["link"] == "https://www.reddit.com/r/GTA6/comments/1/x/"
    assert private_eye.parse_hn("garbage") == [] and private_eye.parse_reddit("{}") == []


def test_the_display_is_given_the_finds(monkeypatch):
    eye({"GTA 6": [item("GTA 6 map leak")]}).run()
    service = dataservice.DataService()
    assert service._read_finds() is True
    assert titles(service.snapshot["finds"]) == ["GTA 6 map leak"]


def test_asked_out_loud_it_says_what_it_found():
    eye({"GTA 6": [item("GTA 6 map leak")], "Nvidia": [item("Nvidia new GPU")]}).run()
    result = tools.run("private_eye_finds", {}, Context())
    assert result["ok"] is True
    assert [f["number"] for f in result["finds"]] == [1, 2]
    assert result["finds"][0]["title"] == "GTA 6 map leak"


def test_a_find_is_rated_by_its_number():
    eye({"GTA 6": [item("GTA 6 map leak")], "Nvidia": [item("Nvidia new GPU")]}).run()
    result = tools.run("rate_find", {"number": 2, "useful": False}, Context())
    assert result["ok"] is True
    assert "Nvidia new GPU" not in titles(private_eye.load())
    spec = tools.REGISTRY["rate_find"].description
    assert "مهم" in spec


def test_the_scout_runs_on_its_own_and_says_when_it_has_found_something(monkeypatch):
    found = threading.Event()
    scout = eye({"GTA 6": [item("GTA 6 map leak")]})
    scout.start(first=0.0, every=60.0, on_found=found.set)
    try:
        assert found.wait(3)
    finally:
        scout.stop()


def test_the_morning_briefing_mentions_what_it_found(monkeypatch):
    import briefing

    monkeypatch.setattr(briefing.feeds, "headlines", lambda topic, limit=5: [])
    monkeypatch.setattr(briefing.feeds, "posts", lambda hours=24, limit=5: [])
    monkeypatch.setattr(briefing.weather, "now", lambda: {})
    monkeypatch.setattr(briefing.market, "quote", lambda symbol: (_ for _ in ()).throw(OSError()))
    monkeypatch.setattr(briefing.market, "market_status", lambda now=None: {"label": ""})
    eye({"GTA 6": [item("GTA 6 map leak", source="IGN")]}).run()
    payload = briefing.compose(now=datetime.datetime(2026, 9, 25, 8, 30))
    assert [f["title"] for f in payload["finds"]] == ["GTA 6 map leak"]
    said = briefing.spoken(payload)
    assert "Private Eye" in said and "GTA 6 map leak" in said


def test_a_find_is_rated_from_the_display():
    import apollo

    eye({"GTA 6": [item("GTA 6 map leak")]}).run()
    (find,) = private_eye.load()
    poked = []
    api = apollo.Api(lambda: None, poke=lambda *keys: poked.append(keys))
    assert api.rate_find(find["id"], False) is True
    assert private_eye.load() == []
    assert poked == [("finds",)]
