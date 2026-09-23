"""Apollo's log file, when it cannot have it.

The log is the only place a failure under pythonw shows up. It was opened
once at startup, and if that open failed - the file still held by a copy
that was being shut down as this one started - `start_log` returned None
and every line after it went nowhere. Apollo ran fully awake for minutes
with an empty log, which looks exactly like Apollo not running.
"""
import logging
import os

import pytest
import win32con
import win32file

import apollo


@pytest.fixture
def clean_logger():
    logger = logging.getLogger("apollo")
    before = list(logger.handlers)
    yield logger
    for handler in list(logger.handlers):
        if handler not in before:
            logger.removeHandler(handler)
            handler.close()


def locked(path):
    """Hold `path` open with no sharing at all, the way a dying process can."""
    return win32file.CreateFile(path, win32con.GENERIC_WRITE, 0, None,
                                win32con.OPEN_ALWAYS, 0, None)


def test_the_log_is_written_where_it_belongs(tmp_path, clean_logger):
    path = tmp_path / "apollo.log"
    assert apollo.start_log(str(path)) is not None
    clean_logger.info("a line")
    for handler in clean_logger.handlers:
        handler.flush()
    assert "a line" in path.read_text(encoding="utf-8")


def test_a_locked_log_falls_back_rather_than_going_silent(tmp_path, clean_logger):
    path = tmp_path / "apollo.log"
    handle = locked(str(path))
    try:
        handler = apollo.start_log(str(path))
        assert handler is not None, "a locked log left Apollo with no log at all"
        clean_logger.info("still heard")
        handler.flush()
        written = handler.baseFilename
        assert written != str(path)
        assert os.path.dirname(written) == str(tmp_path), "the fallback went elsewhere"
        text = open(written, encoding="utf-8").read()
        assert "still heard" in text
        # ...and it says why it is not in the usual place.
        assert "apollo.log" in text
    finally:
        handle.Close()


def test_a_second_start_does_not_double_every_line(tmp_path, clean_logger):
    """start_log attaches to a module-level logger; calling it twice (a probe,
    a test, a restart inside one process) must not write each line twice."""
    path = tmp_path / "apollo.log"
    apollo.start_log(str(path))
    apollo.start_log(str(path))
    clean_logger.info("once")
    for handler in clean_logger.handlers:
        handler.flush()
    assert path.read_text(encoding="utf-8").count("once") == 1


def test_the_router_and_the_voice_reach_the_file(tmp_path, clean_logger):
    """Which backend a turn went to, and whether Gemini connected, are the
    two most useful lines Apollo writes - and they were kept to the console,
    which under pythonw does not exist."""
    import assistant  # noqa: F401 - sets up those two loggers on import

    path = tmp_path / "apollo.log"
    apollo.start_log(str(path))
    logging.getLogger("apollo.router").info("routed to gemini")
    logging.getLogger("apollo.gemini").info("connected")
    for handler in clean_logger.handlers:
        handler.flush()
    text = path.read_text(encoding="utf-8")
    assert "routed to gemini" in text and "connected" in text
