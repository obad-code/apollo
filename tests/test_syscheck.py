import json
import os
import time

import syscheck


def test_broken_files_are_moved_aside_and_kept(tmp_path):
    (tmp_path / "good.json").write_text("{}", encoding="utf-8")
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    old = tmp_path / "x.json.tmp"
    old.write_text("half", encoding="utf-8")
    os.utime(old, (time.time() - 3600, time.time() - 3600))
    fresh = tmp_path / "y.json.tmp"
    fresh.write_text("being written", encoding="utf-8")
    rows = syscheck.fix_files(str(tmp_path))
    names = sorted(os.listdir(tmp_path))
    assert "good.json" in names and "bad.json" not in names
    assert any(n.startswith("bad.json.broken-") for n in names)          # kept, not deleted
    assert "x.json.tmp" not in names and "y.json.tmp" in names           # only old leftovers go
    assert {r["fixed"] for r in rows} == {"moved aside", "cleaned"}


def test_nothing_outside_apollos_folder_is_touched(tmp_path):
    inside, outside = tmp_path / "apollo", tmp_path / "yours"
    inside.mkdir(), outside.mkdir()
    (outside / "private.json").write_text("{broken", encoding="utf-8")
    try:
        os.symlink(outside / "private.json", inside / "link.json")
    except OSError:
        pass
    syscheck.fix_files(str(inside))
    assert (outside / "private.json").read_text(encoding="utf-8") == "{broken"


def test_quota_comes_back_and_spent_models_are_named():
    now = time.time()
    spent = {"a": now - 5, "b": now + 7200}
    assert syscheck.fix_quota(spent, now)[0]["fixed"] == "reset" and "a" not in spent
    row = syscheck.check_quota(spent, now)[0]
    assert row["status"] == "warn" and "b" in row["detail"]
    assert syscheck.check_quota({}, now)[0]["status"] == "ok"


def test_log_counts_only_never_the_text(tmp_path):
    log = tmp_path / "apollo.log"
    log.write_text("2026-10-04 10:00:00,1 ERROR   apollo.lyla: secret words here\n"
                   "2026-10-04 10:01:00,1 ERROR   apollo.lyla: more\n"
                   "2026-10-03 10:01:00,1 ERROR   apollo.crew: yesterday\n"
                   "2026-10-04 10:02:00,1 INFO    apollo.crew: fine\n", encoding="utf-8")
    import datetime as dt
    row = syscheck.check_log(str(log), dt.date(2026, 10, 4))[0]
    assert "lyla 2" in row["detail"] and "secret" not in row["detail"] and "crew" not in row["detail"]


def test_brains_and_agents_and_a_broken_part():
    rows = syscheck.check_brains(lambda: {"Gemini": {"ok": False, "why": "429"}, "Claude": {"ok": False, "why": "not set up"},
                                          "Hermes": {"ok": True}})
    assert [r["status"] for r in rows] == ["fail", "warn", "ok"]

    def load(name):
        if name == "lyla":
            raise ImportError("gone")
    agents = syscheck.check_agents(load)
    assert next(r for r in agents if r["id"] == "agent:lyla")["status"] == "fail"


def test_run_keeps_going_and_saves(tmp_path):
    def boom():
        raise RuntimeError("x")
    out = syscheck.run(str(tmp_path / "s.json"), parts=(boom, lambda: [syscheck._row("a", "A", "ok", "fine")]))
    assert out["fail"] == 1 and out["ok"] == 1
    assert json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))["rows"][1]["id"] == "a"
    assert syscheck.last(str(tmp_path / "s.json"))["fail"] == 1
