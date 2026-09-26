"""The issues Apollo found with itself, kept for you to fix later.

What the checks at startup found wrong, and what went wrong while it ran -
a voice session that would not open, a recorder that kept dying - each
kept once however often it happens, on the System panel until it is fixed
(the check passing again resolves it) or you dismiss it. Kept on disk, so
an issue from this morning is still there this evening.
"""
import json

import pytest

import issues


@pytest.fixture
def own(tmp_path, monkeypatch):
    monkeypatch.setattr(issues, "PATH", str(tmp_path / "issues.json"))
    monkeypatch.setattr(issues, "_listener", None)
    return tmp_path / "issues.json"


def test_an_issue_is_kept(own):
    issues.record("check:mic", "No microphone", "the device is gone", "fail", now=100.0)
    [one] = issues.current()
    assert (one["key"], one["title"], one["detail"], one["level"]) == \
        ("check:mic", "No microphone", "the device is gone", "fail")
    assert one["count"] == 1 and one["first"] == one["last"] == 100.0


def test_the_same_issue_again_is_counted_not_repeated(own):
    issues.record("voice", "Voice would not open", "", "fail", now=100.0)
    issues.record("voice", "Voice would not open", "timed out", "fail", now=160.0)
    [one] = issues.current()
    assert one["count"] == 2 and one["first"] == 100.0 and one["last"] == 160.0
    assert one["detail"] == "timed out"


def test_fixed_it_goes(own):
    issues.record("check:disk", "Disk nearly full", "", "warn", now=1.0)
    assert issues.resolve("check:disk") is True
    assert issues.current() == []
    assert issues.resolve("check:disk") is False


def test_failures_first_then_the_newest(own):
    issues.record("a", "A", "", "warn", now=1.0)
    issues.record("b", "B", "", "fail", now=2.0)
    issues.record("c", "C", "", "warn", now=3.0)
    assert [i["key"] for i in issues.current()] == ["b", "c", "a"]


def test_they_are_kept_on_disk(own):
    issues.record("a", "A", "", "warn", now=1.0)
    assert json.loads(own.read_text(encoding="utf-8"))[0]["key"] == "a"


def test_a_damaged_file_is_an_empty_list_not_a_crash(own):
    own.write_text("{not json", encoding="utf-8")
    assert issues.current() == []
    issues.record("a", "A", "", "warn", now=1.0)
    assert len(issues.current()) == 1


def test_a_level_it_does_not_know_is_a_warning(own):
    issues.record("a", "A", "", "catastrophic", now=1.0)
    assert issues.current()[0]["level"] == "warn"


def test_only_so_many_are_kept(own):
    for n in range(issues.MOST + 5):
        issues.record(f"k{n}", "K", "", "warn", now=float(n))
    kept = issues.current()
    assert len(kept) == issues.MOST
    assert kept[0]["key"] == f"k{issues.MOST + 4}"          # the newest stay


def test_whoever_is_listening_hears_every_change(own):
    heard = []
    issues.set_listener(heard.append)
    issues.record("a", "A", "", "warn", now=1.0)
    issues.resolve("a")
    assert [len(h) for h in heard] == [1, 0]
