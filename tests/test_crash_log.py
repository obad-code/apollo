"""A crash, and a quit, each leave a line.

Under pythonw there is no console: an exception nobody catches on a thread,
and a native crash inside a DLL, both vanished without a word - and so did
a plain quit. On 26 September 2026 the log simply stopped mid-morning, and
there was no telling from it whether Apollo had been closed or had died;
only Windows' own crash report said the day before's stop was a crash (in
libportaudio64bit.dll).
"""
import faulthandler
import logging
import threading
import types

import pytest

import apollo


@pytest.fixture
def records():
    caught = []

    class Keep(logging.Handler):
        def emit(self, record):
            caught.append(record)

    logger = logging.getLogger("apollo")
    handler = Keep(level=logging.DEBUG)
    logger.addHandler(handler)
    level = logger.level
    logger.setLevel(logging.INFO)
    yield caught
    logger.removeHandler(handler)
    logger.setLevel(level)


@pytest.fixture
def watched(tmp_path):
    before = (threading.excepthook, faulthandler.is_enabled())
    handle = apollo.watch_crashes(str(tmp_path / "crash.log"))
    yield handle
    threading.excepthook = before[0]
    faulthandler.disable()
    if before[1]:
        faulthandler.enable()
    handle.close()


def test_an_exception_on_a_thread_is_logged_with_its_traceback(watched, records):
    def boom():
        raise ValueError("the sound card went away")

    worker = threading.Thread(target=boom, name="speaker")
    worker.start()
    worker.join()
    crashed = [r for r in records if r.levelno == logging.CRITICAL]
    assert crashed, "a thread died and the log never heard"
    assert "speaker" in crashed[0].getMessage()
    assert crashed[0].exc_info and crashed[0].exc_info[0] is ValueError


def test_native_crashes_are_written_to_the_crash_file(watched, tmp_path):
    assert faulthandler.is_enabled()
    assert watched.name == str(tmp_path / "crash.log")


def test_quitting_says_so(records):
    app = types.SimpleNamespace(
        stopping=threading.Event(), close_live=lambda: None, clips=None, data=None,
        ticker=None, learner=None, eye=None, orb=None, tray=None, window=None)
    apollo.Apollo.quit(app)
    assert any("quitting" in r.getMessage() for r in records)


def test_the_window_closing_says_so_too(records):
    """Closing the display's window ends Apollo by another road than quit."""
    app = types.SimpleNamespace(stopping=threading.Event(), close_live=lambda: None, ui=None)
    apollo.Apollo.on_closed(app)
    assert any("closed" in r.getMessage() for r in records)
