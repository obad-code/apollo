"""Prayer times for Riyadh, and the reminder fifteen minutes before each.

The times come from Aladhan using Umm al-Qura, which is the method Saudi
Arabia actually uses - a different method moves Fajr and Isha by up to twenty
minutes, which is the difference between a useful reminder and a wrong one.
"""
import datetime

import pytest

import prayer


TIMINGS = {"Fajr": "04:23", "Sunrise": "05:47", "Dhuhr": "11:46",
           "Asr": "15:14", "Maghrib": "17:51", "Isha": "19:21"}


@pytest.fixture(autouse=True)
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(prayer, "CACHE", str(tmp_path / "prayer.json"))
    prayer._memo.clear()


def test_times_are_read_for_the_day(monkeypatch):
    monkeypatch.setattr(prayer, "_download", lambda day: TIMINGS)
    day = datetime.date(2026, 9, 21)
    times = prayer.times(day)

    assert set(times) == set(prayer.PRAYERS)
    assert times["Maghrib"] == datetime.datetime(2026, 9, 21, 17, 51)
    assert "Sunrise" not in times, "sunrise is not a prayer"


def test_the_day_is_fetched_once(monkeypatch):
    calls = []
    monkeypatch.setattr(prayer, "_download", lambda day: calls.append(day) or TIMINGS)
    day = datetime.date(2026, 9, 21)
    prayer.times(day)
    prayer.times(day)
    assert len(calls) == 1


def test_the_next_prayer_is_the_next_one(monkeypatch):
    monkeypatch.setattr(prayer, "_download", lambda day: TIMINGS)
    now = datetime.datetime(2026, 9, 21, 12, 30)
    name, when = prayer.next_prayer(now)
    assert name == "Asr"
    assert when == datetime.datetime(2026, 9, 21, 15, 14)


def test_after_isha_the_next_one_is_tomorrow_s_fajr(monkeypatch):
    monkeypatch.setattr(prayer, "_download", lambda day: TIMINGS)
    now = datetime.datetime(2026, 9, 21, 21, 0)
    name, when = prayer.next_prayer(now)
    assert name == "Fajr"
    assert when.date() == datetime.date(2026, 9, 22)


def test_the_reminder_is_due_fifteen_minutes_before(monkeypatch):
    monkeypatch.setattr(prayer, "_download", lambda day: TIMINGS)
    watch = prayer.Watch(lead_minutes=15)

    assert watch.due(datetime.datetime(2026, 9, 21, 17, 30)) is None
    due = watch.due(datetime.datetime(2026, 9, 21, 17, 36))
    assert due is not None and due[0] == "Maghrib"


def test_a_reminder_is_given_once(monkeypatch):
    monkeypatch.setattr(prayer, "_download", lambda day: TIMINGS)
    watch = prayer.Watch(lead_minutes=15)
    assert watch.due(datetime.datetime(2026, 9, 21, 17, 36)) is not None
    assert watch.due(datetime.datetime(2026, 9, 21, 17, 38)) is None, (
        "the same prayer was announced twice")


def test_a_prayer_already_begun_is_not_announced_as_coming(monkeypatch):
    """Fifteen minutes late is not a reminder, it is a contradiction."""
    monkeypatch.setattr(prayer, "_download", lambda day: TIMINGS)
    watch = prayer.Watch(lead_minutes=15)
    assert watch.due(datetime.datetime(2026, 9, 21, 17, 55)) is None


def test_a_feed_that_will_not_answer_costs_the_reminder_not_the_day(monkeypatch):
    def boom(day):
        raise OSError("no network")

    monkeypatch.setattr(prayer, "_download", boom)
    assert prayer.times(datetime.date(2026, 9, 21)) == {}
    assert prayer.next_prayer(datetime.datetime(2026, 9, 21, 12, 0)) == (None, None)
    assert prayer.Watch().due(datetime.datetime(2026, 9, 21, 17, 36)) is None
