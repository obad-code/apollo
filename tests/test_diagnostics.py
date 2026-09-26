"""Apollo's checks of itself as it comes up: quick, all at once, each one
said on the boot screen as it lands, and anything wrong kept as an issue
for the System panel.
"""
import threading
import time

import diagnostics as d


def test_every_check_is_reported_as_it_lands(monkeypatch):
    monkeypatch.setattr(d, "CHECKS", (("a", "ALPHA", lambda: (d.OK, "fine")),
                                      ("b", "BRAVO", lambda: (d.WARN, "meh"))))
    heard = []
    results = d.run(report=heard.append, timeout=2)
    assert {r["id"] for r in heard} == {"a", "b"}
    assert {r["id"]: r["status"] for r in results} == {"a": "ok", "b": "warn"}
    assert all(set(r) >= {"id", "label", "status", "detail"} for r in results)


def test_a_check_that_breaks_is_a_failure_not_a_crash(monkeypatch):
    def broken():
        raise RuntimeError("boom")
    monkeypatch.setattr(d, "CHECKS", (("x", "X", broken),))
    [result] = d.run(timeout=2)
    assert result["status"] == d.FAIL and "boom" in result["detail"]


def test_a_check_that_never_answers_does_not_hold_the_boot(monkeypatch):
    stuck = threading.Event()
    monkeypatch.setattr(d, "CHECKS", (("slow", "SLOW", lambda: stuck.wait(10) or (d.OK, "")),
                                      ("quick", "QUICK", lambda: (d.OK, ""))))
    began = time.monotonic()
    results = {r["id"]: r for r in d.run(timeout=0.5)}
    stuck.set()
    assert time.monotonic() - began < 2
    assert results["quick"]["status"] == d.OK
    assert results["slow"]["status"] == d.WARN and "no answer" in results["slow"]["detail"]


def test_no_gemini_key_is_a_failure_and_the_others_are_warnings():
    assert d.check_keys({})[0] == d.FAIL
    status, detail = d.check_keys({"GEMINI_API_KEY": "x"})
    assert status == d.WARN and "ANTHROPIC_API_KEY" in detail
    assert d.check_keys({"GEMINI_API_KEY": "x", "ANTHROPIC_API_KEY": "y",
                         "FINNHUB_API_KEY": "z"})[0] == d.OK


def test_a_damaged_saved_file_is_named(tmp_path):
    (tmp_path / "layout.json").write_text("{broken", encoding="utf-8")
    (tmp_path / "watchlist.json").write_text("[]", encoding="utf-8")
    status, detail = d.check_state(str(tmp_path))
    assert status == d.WARN and "layout.json" in detail and "watchlist" not in detail
    (tmp_path / "layout.json").write_text("{}", encoding="utf-8")
    assert d.check_state(str(tmp_path))[0] == d.OK


def test_the_disk(monkeypatch, tmp_path):
    def usage(gb):
        return lambda path: type("Usage", (), {"free": gb * 2**30})()
    monkeypatch.setattr(d.shutil, "disk_usage", usage(1))
    assert d.check_disk(str(tmp_path))[0] == d.FAIL
    monkeypatch.setattr(d.shutil, "disk_usage", usage(5))
    assert d.check_disk(str(tmp_path))[0] == d.WARN
    monkeypatch.setattr(d.shutil, "disk_usage", usage(80))
    assert d.check_disk(str(tmp_path)) == (d.OK, "80 GB free")


def write_log(path, *runs):
    lines = []
    for n, run in enumerate(runs):
        lines.append(f"2026-09-26 10:0{n}:00,000 INFO    apollo: started, pid {n}")
        lines.extend(run)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_a_crash_last_time_is_found_in_the_log(tmp_path):
    log = tmp_path / "apollo.log"
    write_log(log, ["2026-09-26 10:00:05,000 CRITICAL apollo: thread speaker crashed"], [])
    status, detail = d.check_last_run(str(log), str(tmp_path / "crash.log"),
                                      str(tmp_path / "seen.json"))
    assert status == d.FAIL and "speaker crashed" in detail


def test_a_native_crash_is_found_by_the_crash_file_growing(tmp_path):
    log, crash, seen = tmp_path / "apollo.log", tmp_path / "crash.log", tmp_path / "seen.json"
    write_log(log, [], [])
    crash.write_text("", encoding="utf-8")
    assert d.check_last_run(str(log), str(crash), str(seen))[0] == d.OK
    crash.write_text("Windows fatal exception: access violation\n", encoding="utf-8")
    assert d.check_last_run(str(log), str(crash), str(seen))[0] == d.FAIL
    # ...once: the next start has nothing new to say.
    assert d.check_last_run(str(log), str(crash), str(seen))[0] == d.OK


def test_the_self_test_names_what_broke(monkeypatch):
    def broken():
        raise ValueError("bad file")
    monkeypatch.setattr(d, "SELF_TESTS", (("layout", lambda: {}), ("ideas", broken)))
    status, detail = d.check_self()
    assert status == d.FAIL and "ideas" in detail and "layout" not in detail


def test_the_real_checks_are_all_listed():
    ids = [c[0] for c in d.CHECKS]
    for wanted in ("keys", "network", "mic", "speakers", "disk", "state", "encoder",
                   "lastrun", "self", "sources"):
        assert wanted in ids
    assert len(set(ids)) == len(ids)
