"""Market alerts: what counts as big news, told once, by email and voice."""
import time

import pytest

import alerts
import emailer

NOW = 1_790_000_000.0


def story(title, minutes=3, source="Reuters", summary=""):
    return {"title": title, "summary": summary, "source": source, "link": "https://x/1",
            "when": NOW - minutes * 60}


def test_a_trillion_dollar_amd_is_big_news():
    rated = alerts.score(story("AMD market value tops $1 trillion as shares soar"),
                                 watch=("NVDA",), now=NOW)
    assert rated["score"] >= alerts.THRESHOLD and "AMD" in rated["tickers"]


def test_a_quiet_story_is_not():
    rated = alerts.score(story("Five things to watch this weekend", source="Blog"), now=NOW)
    assert rated["score"] < alerts.THRESHOLD


def test_an_old_story_is_not_breaking():
    rated = alerts.score(story("Nvidia beats earnings, shares surge", minutes=600), now=NOW)
    assert rated["score"] < alerts.THRESHOLD


def test_the_watchlist_counts_extra():
    plain = alerts.score(story("Rivian recalls 20,000 trucks"), now=NOW)
    watched = alerts.score(story("Rivian recalls 20,000 trucks"), watch=("RIVN", "RIVIAN"), now=NOW)
    assert watched["score"] > plain["score"]


def test_the_same_story_from_two_sources_is_one():
    assert alerts.key_of("Nvidia beats, shares surge") == alerts.key_of("Shares surge: Nvidia beats!")


def test_a_sharp_move_is_spotted_once():
    moves = alerts.Moves()
    assert moves.note({"NVDA": 100.0}, now=NOW) == []
    assert moves.note({"NVDA": 105.0}, now=NOW + 300) == []      # 5% is a normal day
    moved = moves.note({"NVDA": 110.0}, now=NOW + 330)
    assert moved == [("NVDA", 10.0, 100.0, 110.0)]
    assert moves.note({"NVDA": 110.2}, now=NOW + 360) == []


def watcher(tmp_path, stories, prices=None, **kw):
    told = {"email": [], "voice": []}
    w = alerts.Watcher(speak=told["voice"].append, email=told["email"].append,
                       watch=lambda: ["NVDA"], prices=lambda watch: dict(prices or {}),
                       sources=lambda watch: list(stories), explain=lambda s, t: "ACTION: BUY X\nSUMMARY: it matters\nCONFIDENCE: high\nMAJOR: yes",
                       path=str(tmp_path / "seen.json"), clock=lambda: NOW, **kw)
    return w, told


def test_the_first_round_only_learns_what_is_already_out(tmp_path):
    w, told = watcher(tmp_path, [story("Nvidia misses earnings, stock plunges")])
    assert w.check(quiet=True) == [] and told["email"] == []
    assert w.check() == []                       # ...and does not tell it later either


def test_a_new_story_is_emailed_and_said_once(tmp_path):
    stories = []
    w, told = watcher(tmp_path, stories)
    w.check(quiet=True)
    stories.append(story("Nvidia misses earnings, stock plunges"))
    first = w.check()
    assert len(first) == 1 and first[0]["call"]["summary"] == "it matters"
    assert len(told["email"]) == 1 and len(told["voice"]) == 1
    assert w.check() == []


def test_no_more_than_a_few_an_hour(tmp_path):
    stories = []
    w, told = watcher(tmp_path, stories)
    w.check(quiet=True)
    stories += [story(f"Nvidia {word} earnings, stock plunges after guidance cut")
                for word in ("misses", "botches", "fumbles", "blows", "flubs", "drops", "loses", "sinks")]
    w.check()
    assert len(told["email"]) == alerts.MOST_PER_HOUR


def test_one_channel_failing_does_not_stop_the_other(tmp_path):
    stories = []
    w, told = watcher(tmp_path, stories)
    w.email = lambda alert: (_ for _ in ()).throw(RuntimeError("no smtp"))
    w.check(quiet=True)
    stories.append(story("Apple to acquire a chipmaker in record buyout"))
    w.check()
    assert len(told["voice"]) == 1


def test_seen_stories_survive_a_restart(tmp_path):
    w, _ = watcher(tmp_path, [story("Tesla CEO steps down")])
    w.check(quiet=True)
    again, told = watcher(tmp_path, [story("Tesla CEO steps down")])
    again.check()
    assert told["email"] == []


def test_email_needs_settings(monkeypatch):
    monkeypatch.delenv("APOLLO_SMTP_USER", raising=False)
    with pytest.raises(RuntimeError, match="not set up"):
        emailer.send("s", "b")


def test_email_goes_to_you_by_default_and_refuses_lists(monkeypatch):
    monkeypatch.setenv("APOLLO_SMTP_USER", "me@gmail.com")
    monkeypatch.setenv("APOLLO_SMTP_PASSWORD", "abcd efgh ijkl mnop")
    monkeypatch.delenv("APOLLO_ALERT_TO", raising=False)
    sent = []
    monkeypatch.setattr(emailer, "_deliver", lambda found, message: sent.append((found, message)))
    assert emailer.send("Hi", "Body")["to"] == "me@gmail.com"
    found, message = sent[0]
    assert found["password"] == "abcdefghijklmnop" and message["To"] == "me@gmail.com"
    with pytest.raises(ValueError):
        emailer.send("Hi", "Body", to="a@x.com, b@y.com")


def test_the_alert_card_escapes_what_it_shows():
    html = emailer.card("<b>AMD</b> tops $1T", ["up & away"], "https://x/?a=1&b=2")
    assert "&lt;b&gt;AMD" in html and "up &amp; away" in html and "a=1&amp;b=2" in html


def test_the_call_is_read_off_the_desks_answer():
    call = alerts.parse_call("ACTION: SELL TSLA\nSUMMARY: Recall of 2M cars. Margins at risk.\n"
                             "WHY:\n- recall\n- margins\n- guidance cut\nCONFIDENCE: high")
    assert call == {"action": "SELL", "ticker": "TSLA", "summary": "Recall of 2M cars. Margins at risk.",
                    "why": ["recall", "margins", "guidance cut"], "confidence": "high",
                    "major": False}


def test_only_major_sure_calls_interrupt_you():
    assert alerts.major({"action": "SELL", "confidence": "high", "major": True})
    assert not alerts.major({"action": "SELL", "confidence": "medium", "major": True})
    assert not alerts.major({"action": "HOLD", "confidence": "high", "major": True})
    assert not alerts.major({"action": "BUY", "confidence": "high", "major": False})


def test_no_more_than_a_few_a_week_even_across_restarts(tmp_path):
    stories = []
    w, told = watcher(tmp_path, stories)
    w.check(quiet=True)
    for day, word in enumerate(("misses", "botches", "fumbles", "blows", "flubs", "sinks")):
        w.clock = lambda d=day: NOW + d * 86400
        stories.append(story(f"Nvidia {word} earnings, stock plunges", minutes=-day * 1440 + 3))
        w.check()
    assert len(told["email"]) == alerts.MOST_PER_WEEK
    again, _ = watcher(tmp_path, [])
    assert len(again.sent) == alerts.MOST_PER_WEEK


def test_ignored_news_is_not_sent(tmp_path):
    stories = []
    w, told = watcher(tmp_path, stories)
    w.explain = lambda s, t: "ACTION: IGNORE NVDA\nSUMMARY: Noise."
    w.check(quiet=True)
    stories.append(story("Nvidia misses earnings, stock plunges"))
    assert w.check() == [] and told["email"] == []


def test_a_hold_on_a_stock_you_do_not_watch_is_not_sent(tmp_path):
    stories = []
    w, told = watcher(tmp_path, stories)
    w.explain = lambda s, t: "ACTION: HOLD AAPL\nSUMMARY: Fine."
    w.check(quiet=True)
    stories.append(story("Apple to acquire a chipmaker in record buyout"))
    assert w.check() == []


def test_the_email_leads_with_the_call(tmp_path, monkeypatch):
    monkeypatch.setenv("APOLLO_SMTP_USER", "me@gmail.com")
    monkeypatch.setenv("APOLLO_SMTP_PASSWORD", "x")
    sent = []
    monkeypatch.setattr(emailer, "_deliver", lambda found, message: sent.append(message))
    alerts.Watcher._email({"story": story("Tesla recall"), "tickers": ["TSLA"], "why": [],
                           "explained": "ACTION: SELL TSLA\nSUMMARY: Bad.\nCONFIDENCE: high"})
    assert sent[0]["Subject"].startswith("SELL - TAKE YOUR MONEY OUT TSLA")
