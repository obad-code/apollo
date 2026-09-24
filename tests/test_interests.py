"""What Apollo knows about you: interests with how much each matters, what
you do not care for, a few facts - learned by Claude, a day at a time, from
the record of what you said and opened, and read by Gemini at the start of
every session."""
import datetime
import json

import pytest

import assistant
import gemini_live
import journal
import interests


@pytest.fixture(autouse=True)
def own_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(interests, "PATH", str(tmp_path / "profile.json"))


def names(p):
    return [i["name"] for i in p["interests"]]


def test_a_fresh_profile_starts_from_what_apollo_was_told():
    p = interests.load()
    assert {"Nvidia", "Marvel", "GTA 6"} <= set(names(p))
    assert "Riyadh" in " ".join(p["facts"])


def test_the_summary_puts_the_strongest_first_and_says_what_is_not_wanted():
    p = interests.load()
    p["interests"] = [{"name": "Tesla", "kind": "company", "weight": 0.2, "query": "Tesla"},
                      {"name": "Palantir", "kind": "company", "weight": 0.9, "query": "Palantir"}]
    p["dislikes"] = ["crypto"]
    text = interests.summary(p)
    assert text.index("Palantir") < text.index("Tesla")
    assert "crypto" in text
    assert len(text) < 1500


def reply(**changes):
    base = {"about": "Follows chips and games closely.",
            "interests": [{"name": "Palantir", "kind": "company", "weight": 0.7,
                           "query": "Palantir"}],
            "dislikes": [], "facts": ["Lives in Riyadh"]}
    base.update(changes)
    return "Here it is:\n```json\n" + json.dumps(base) + "\n```"


def test_a_day_is_learned_from():
    asked = []

    def ask(system, prompt):
        asked.append(prompt)
        return reply()

    entries = [{"kind": "you", "text": "how is palantir doing"},
               {"kind": "opened", "what": "stock", "title": "PLTR", "source": "Palantir"}]
    p = interests.learn(entries, interests.load(), ask)
    assert "Palantir" in names(p)
    assert p["about"] == "Follows chips and games closely."
    # Claude saw both the day and what was already known.
    assert "how is palantir doing" in asked[0] and "Nvidia" in asked[0]


def test_an_answer_that_is_not_a_profile_changes_nothing():
    before = interests.load()
    after = interests.learn([{"kind": "you", "text": "hi"}], before, lambda s, p: "sorry, no")
    assert after == before


def test_a_failed_call_changes_nothing():
    def ask(system, prompt):
        raise RuntimeError("offline")

    before = interests.load()
    assert interests.learn([{"kind": "you", "text": "hi"}], before, ask) == before


def test_weights_are_kept_between_nothing_and_everything_and_the_list_is_capped():
    many = [{"name": f"Thing {i}", "kind": "topic", "weight": 3.0 - i, "query": f"thing {i}"}
            for i in range(60)]
    p = interests.learn([{"kind": "you", "text": "x"}], interests.load(),
                      lambda s, pr: reply(interests=many))
    assert len(p["interests"]) <= interests.MOST
    assert all(0.0 <= i["weight"] <= 1.0 for i in p["interests"])


def test_what_is_not_mentioned_fades():
    p = interests.load()
    p["interests"] = [{"name": "Old game", "kind": "game", "weight": 0.5, "query": "old game"},
                      {"name": "Faint", "kind": "topic", "weight": 0.06, "query": "faint"}]
    faded = interests.decay(p, days=5)
    assert faded["interests"][0]["weight"] < 0.5
    assert "Faint" not in names(faded)


def test_a_find_you_liked_counts_and_one_you_did_not_counts_against():
    p = interests.load()
    p["interests"] = [{"name": "Marvel", "kind": "topic", "weight": 0.5, "query": "Marvel"}]
    up = interests.rate(p, "Marvel", useful=True)["interests"][0]["weight"]
    down = interests.rate(p, "Marvel", useful=False)["interests"][0]["weight"]
    assert up > 0.5 > down


def test_catching_up_learns_finished_days_only_and_remembers_where_it_got_to(tmp_path):
    today = datetime.date(2026, 9, 25)
    for back in (3, 2, 1, 0):
        day = today - datetime.timedelta(days=back)
        journal.os.makedirs(journal.ROOT, exist_ok=True)
        with open(journal._path(day), "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"kind": "you", "text": f"day {day}"}) + "\n")
    learned = []

    def ask(system, prompt):
        learned.append(prompt)
        return reply()

    interests.catch_up(ask, today=today)
    assert len(learned) == 3                             # not today: it is not over
    assert interests.load()["learned_through"] == (today - datetime.timedelta(days=1)).isoformat()
    interests.catch_up(ask, today=today)
    assert len(learned) == 3                             # nothing new to learn


def test_gemini_is_told_what_apollo_knows():
    p = interests.load()
    p["interests"] = [{"name": "Palantir", "kind": "company", "weight": 0.9, "query": "Palantir"}]
    interests.save(p)
    assert "Palantir" in gemini_live.system_instruction()


def test_one_plain_question_to_claude(monkeypatch):
    sent = []

    class Response:
        content = [type("B", (), {"type": "text", "text": "done"})()]

    def send(request, stream=False):
        sent.append(request)
        return Response()

    monkeypatch.setattr(assistant, "_send", send)
    assert assistant.ask_once("be brief", "hello") == "done"
    assert sent[0]["system"] == "be brief"
    assert sent[0]["messages"] == [{"role": "user", "content": "hello"}]
    assert "tools" not in sent[0]


def test_the_learner_catches_up_on_its_own_thread_until_stopped(monkeypatch):
    import threading
    import time

    calls = []
    ran = threading.Event()

    def catch_up(ask, today=None):
        calls.append(ask)
        ran.set()
        return []

    monkeypatch.setattr(interests, "catch_up", catch_up)
    ask = object()
    learner = interests.Learner(ask, first=0.0, every=0.05).start()
    try:
        assert ran.wait(2)
        time.sleep(0.2)
        assert len(calls) >= 2 and all(c is ask for c in calls)
    finally:
        learner.stop()
    assert not learner.alive()


def test_a_learner_that_fails_keeps_going(monkeypatch):
    import threading

    tries = []
    twice = threading.Event()

    def catch_up(ask, today=None):
        tries.append(1)
        if len(tries) >= 2:
            twice.set()
        raise RuntimeError("the API is down")

    monkeypatch.setattr(interests, "catch_up", catch_up)
    learner = interests.Learner(lambda s, p: "", first=0.0, every=0.05).start()
    try:
        assert twice.wait(2)
    finally:
        learner.stop()
