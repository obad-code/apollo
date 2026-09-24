"""The watcher owns the chords, presence, the recap and the prayer reminders.

It is one daemon thread polling in a loop, under pythonw, with no console.
An exception anywhere in a tick used to end that thread for the rest of the
session - taking Ctrl+`, the quit chord, the recap and the prayer reminders
with it - and nothing was written anywhere to say so.
"""
import logging
import threading

import apollo


class App:
    """Enough of Apollo for the watcher to poll."""

    def __init__(self, ticks_until_stop=6, fail_on=(1,)):
        self.stopping = threading.Event()
        self.ticks = 0
        self.fail_on = set(fail_on)
        self.ticks_until_stop = ticks_until_stop

    def quit(self):
        pass

    def toggle_peek(self):
        pass

    def check_intro(self):
        pass

    def check_presence(self, idle):
        self.ticks += 1
        if self.ticks >= self.ticks_until_stop:
            self.stopping.set()
        if self.ticks in self.fail_on:
            raise RuntimeError("a check that broke once")

    def check_overlay_alive(self):
        pass


def test_one_bad_tick_does_not_end_the_watcher(monkeypatch):
    monkeypatch.setattr(apollo, "chord_down", lambda chord: False)
    monkeypatch.setattr(apollo, "idle_seconds", lambda: 0.0)
    monkeypatch.setattr(apollo.time, "sleep", lambda s: None)
    app = App(ticks_until_stop=6, fail_on=(1, 3))

    watcher = apollo.Watcher(app)
    watcher.run()                       # in this thread, so it must return

    assert app.ticks == 6, f"the watcher stopped after tick {app.ticks}"


def test_a_bad_tick_is_written_down(monkeypatch, caplog):
    monkeypatch.setattr(apollo, "chord_down", lambda chord: False)
    monkeypatch.setattr(apollo, "idle_seconds", lambda: 0.0)
    monkeypatch.setattr(apollo.time, "sleep", lambda s: None)
    app = App(ticks_until_stop=3, fail_on=(1,))

    with caplog.at_level(logging.ERROR, logger="apollo"):
        apollo.Watcher(app).run()

    assert any("a check that broke once" in r.getMessage() or
               "a check that broke once" in (r.exc_text or "")
               for r in caplog.records), "the failure was not logged"


def test_the_same_failure_every_tick_is_not_logged_every_tick(monkeypatch, caplog):
    """Twenty-five ticks a second: a check that fails every time must not
    write twenty-five tracebacks a second into the log."""
    monkeypatch.setattr(apollo, "chord_down", lambda chord: False)
    monkeypatch.setattr(apollo, "idle_seconds", lambda: 0.0)
    monkeypatch.setattr(apollo.time, "sleep", lambda s: None)
    app = App(ticks_until_stop=200, fail_on=range(1, 201))

    with caplog.at_level(logging.ERROR, logger="apollo"):
        apollo.Watcher(app).run()

    assert app.ticks == 200
    assert len([r for r in caplog.records if r.levelno >= logging.ERROR]) <= 3
