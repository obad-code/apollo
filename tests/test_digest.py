import datetime as dt

import digest

RIYADH = dt.timezone(dt.timedelta(hours=3))


def test_a_morning_and_an_after_close_edition_once_each():
    morning = dt.datetime(2026, 10, 5, 7, 0, tzinfo=RIYADH)                 # a Monday
    assert digest.due(morning, "") == "morning"
    assert digest.due(morning, morning.isoformat()) == ""
    after_close = dt.datetime(2026, 10, 5, 23, 45, tzinfo=RIYADH)          # 16:45 in New York
    assert digest.due(after_close, morning.isoformat()) == "close"
    assert digest.due(after_close, after_close.isoformat()) == ""


def test_no_close_edition_at_the_weekend():
    saturday = dt.datetime(2026, 10, 10, 23, 45, tzinfo=RIYADH)
    assert digest.due(saturday, dt.datetime(2026, 10, 10, 7, 0, tzinfo=RIYADH).isoformat()) == ""


def test_seen_is_kept(tmp_path):
    path = str(tmp_path / "d.json")
    digest.save({"made": "x", "seen": False}, path)
    digest.mark_seen(path)
    assert digest.load(path)["seen"] is True
