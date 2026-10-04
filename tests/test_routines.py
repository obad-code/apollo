import datetime as dt

import routines


def test_moneypenny_only_on_weekdays_after_three():
    saturday = dt.datetime(2026, 10, 3, 16)
    monday = dt.datetime(2026, 10, 5, 16)
    assert "MONEYPENNY" not in routines.due(saturday, {})
    assert "MONEYPENNY" in routines.due(monday, {})
    assert "MONEYPENNY" not in routines.due(dt.datetime(2026, 10, 5, 9), {})


def test_each_routine_runs_once_a_day(tmp_path, monkeypatch):
    started = []
    monkeypatch.setattr(routines, "start_job", lambda a: started.append(a) or {"job": 1})
    monkeypatch.setenv("APOLLO_ROUTINES", "1")
    path = str(tmp_path / "r.json")
    now = dt.datetime(2026, 10, 5, 21)
    assert sorted(routines.tick(now, path)) == ["MONEYPENNY", "SHORTS", "THEIA"]
    assert routines.tick(now, path) == []


def test_routines_can_be_turned_off(monkeypatch):
    monkeypatch.setenv("APOLLO_ROUTINES", "0")
    assert routines.tick(dt.datetime(2026, 10, 5, 21)) == []
