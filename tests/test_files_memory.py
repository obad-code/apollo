import datetime
import os

import pytest

import files
import journal
import memory


def test_write_read_append_in_apollo_folder():
    done = files.write("notes", "سطر اول")
    assert done["path"].endswith(os.path.join("Apollo", "notes.txt"))
    files.write("notes.txt", "second", append=True)
    assert files.read("notes.txt")["text"] == "سطر اول\nsecond"


@pytest.mark.parametrize("bad", ["../escape.txt", "/etc/passwd/..", "..", "", "run.exe"])
def test_names_cannot_leave_the_folder_or_be_programs(bad):
    with pytest.raises(ValueError):
        files.path_of(bad)


def test_subfolders_are_allowed():
    done = files.write("projects/apollo.md", "# hi")
    assert os.path.isfile(done["path"])
    assert [f[0] for f in files.listing()] == [os.path.join("projects", "apollo.md")]


def test_problem_log_is_dated_and_appended():
    when = datetime.datetime(2026, 10, 3, 9, 30)
    files.log_problem("he typed dddd", now=when)
    files.log_problem("voice cut out", now=when)
    text = files.read(files.PROBLEMS)["text"]
    assert text.startswith("# Apollo problems")
    assert "- [ ] 2026-10-03 09:30 — he typed dddd\n- [ ] 2026-10-03 09:30 — voice cut out" in text


def test_remember_recall_forget():
    memory.remember("My car is a Tahoe")
    memory.remember("my car is a tahoe")          # the same, kept once
    memory.remember("موعد الدكتور يوم الاحد")
    assert len(memory.all_memories()) == 2
    assert [m["text"] for m in memory.recall("car")] == ["My car is a Tahoe"]
    assert memory.forget("tahoe")
    assert [m["text"] for m in memory.all_memories()] == ["موعد الدكتور يوم الاحد"]


def test_summary_carries_memories_and_recent_talk():
    memory.remember("Prefers answers in Saudi dialect")
    journal.said("حلل لي انفيديا")
    journal.answered("تمام", who="Apollo")
    text = memory.summary(datetime.datetime.now() + datetime.timedelta(seconds=5))
    assert "Prefers answers in Saudi dialect" in text
    assert "User: حلل لي انفيديا" in text and "Apollo: تمام" in text


def test_summary_is_empty_with_nothing_kept():
    assert memory.summary() == ""
