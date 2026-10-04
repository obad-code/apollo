import datetime as dt
import autopost


def test_pick_topics_pads_and_cleans():
    out = autopost.pick_topics(3, found=["x"], think=lambda p: '[{"kind":"story","world":"sea","topic":"Moon"},{"kind":"fact","world":"sea","topic":"B"}]')
    assert out[0] == {"kind": "story", "world": "sea", "topic": "Moon"} and len(out) == 3
    assert len({p["world"] for p in out}) == 3          # every Short gets its own world


def test_choose_and_deadline(tmp_path, monkeypatch):
    monkeypatch.setattr(autopost, "AUTOPOST", True)
    path = str(tmp_path / "p.json")
    made = [{"title": "A", "path": "a.mp4", "notes": ""}, {"title": "B", "path": "b.mp4", "notes": ""}]
    now = dt.datetime(2026, 1, 1, 13)
    autopost.offer(made, now, path)
    assert autopost.tick(now, path, upload=lambda v, n: "L") is None
    r = autopost.tick(now + dt.timedelta(hours=5), path, upload=lambda v, n: "L/" + v)
    assert r["ok"] and r["link"] == "L/a.mp4, L/b.mp4"      # both go up when nobody answers
    assert not autopost.choose(2, path, upload=lambda v, n: "x")["ok"]   # already posted
    autopost.offer(made, now, path)
    assert autopost.choose(2, path, upload=lambda v, n: v)["link"] == "b.mp4"
    autopost.offer(made, now, path)
    assert autopost.choose(0, path)["ok"] and autopost.load(path)["status"] == "skipped"


def test_due_every():
    assert autopost.due_today(dt.date(2026, 1, 2), "")
    assert autopost.due_today(dt.date(2026, 1, 2), "2026-01-01")
    assert not autopost.due_today(dt.date(2026, 1, 1), "2026-01-01")


def test_nothing_posts_by_itself_unless_asked(tmp_path, monkeypatch):
    path = str(tmp_path / "p.json")
    now = dt.datetime(2026, 1, 1, 13)
    autopost.offer([{"title": "A", "path": "a.mp4", "notes": ""}], now, path)
    monkeypatch.setattr(autopost, "AUTOPOST", False)
    assert autopost.tick(now + dt.timedelta(hours=9), path, upload=lambda v, n: 1 / 0) is None


def test_a_single_short_waits_for_your_word_and_can_be_a_private_draft(tmp_path):
    path = str(tmp_path / "p.json")
    made = [{"title": "A", "path": "a.mp4", "notes": "n"}]
    autopost.offer(made, dt.datetime(2026, 1, 1), path)
    assert "private draft" in autopost.question(made)
    seen = []
    r = autopost.choose(1, path, upload=lambda v, n, privacy=None: seen.append(privacy) or "L", privacy="private")
    assert seen == ["private"] and "private draft" in r["result"]
    autopost.offer(made, dt.datetime(2026, 1, 1), path)
    assert autopost.choose(0, path)["result"].startswith("Kept as a file")


def test_an_email_heads_up_goes_when_a_short_is_posted(tmp_path, monkeypatch):
    import emailer
    sent = []
    monkeypatch.setattr(emailer, "notify", lambda subject, text, attachments=None: sent.append((subject, text)) or True)
    path = str(tmp_path / "p.json")
    autopost.offer([{"title": "A", "path": "a.mp4", "notes": ""}], dt.datetime(2026, 1, 1), path)
    autopost.choose(1, path, upload=lambda v, n: "https://y/1")
    assert sent == [("Posted on YouTube: A", "https://y/1")]
