"""Apollo's record of your days: what you said, what he answered, what you
opened. On this PC only, one file a day, so there is something to learn
what you care about from."""
import datetime
import json
import os

import journal


def test_what_is_written_is_read_back_the_same_day(tmp_path):
    journal.write("you", text="how is nvidia doing")
    journal.write("apollo", text="Up 2% today.")
    entries = journal.day(datetime.date.today())
    assert [(e["kind"], e["text"]) for e in entries] == [
        ("you", "how is nvidia doing"), ("apollo", "Up 2% today.")]
    assert all("at" in e for e in entries)


def test_one_file_a_day_in_apollos_own_folder():
    journal.write("you", text="hello")
    name = datetime.date.today().isoformat() + ".jsonl"
    assert os.path.exists(os.path.join(journal.ROOT, name))


def test_long_text_is_cut_short():
    journal.write("you", text="x" * 5000)
    (entry,) = journal.day(datetime.date.today())
    assert len(entry["text"]) <= journal.TRIM + 1


def test_it_never_raises_when_it_cannot_write(monkeypatch, tmp_path):
    blocked = tmp_path / "a-file-not-a-folder"
    blocked.write_text("")
    monkeypatch.setattr(journal, "ROOT", str(blocked / "journal"))
    journal.write("you", text="still fine")          # must not raise


def test_a_damaged_line_is_skipped_not_fatal():
    journal.write("you", text="one")
    path = os.path.join(journal.ROOT, datetime.date.today().isoformat() + ".jsonl")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("{ not json\n")
    journal.write("you", text="two")
    assert [e["text"] for e in journal.day(datetime.date.today())] == ["one", "two"]


def test_days_older_than_the_keep_are_let_go():
    os.makedirs(journal.ROOT, exist_ok=True)
    old = datetime.date.today() - datetime.timedelta(days=journal.KEEP_DAYS + 3)
    with open(os.path.join(journal.ROOT, old.isoformat() + ".jsonl"), "w") as handle:
        handle.write(json.dumps({"kind": "you", "text": "long ago"}) + "\n")
    journal.prune()
    assert old not in journal.days()


def test_forget_clears_it_all():
    journal.write("you", text="something private")
    journal.forget()
    assert journal.days() == []
