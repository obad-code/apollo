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
