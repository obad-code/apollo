import queue
import time

import gemini_live


def session():
    return gemini_live.LiveSession(api_key="test")


def test_new_session_is_not_playing():
    assert session().playing is False


def test_recent_write_counts_as_playing():
    s = session()
    s._last_write = time.monotonic()
    assert s.playing is True


def test_queued_audio_counts_as_playing():
    s = session()
    s._play_q = queue.Queue()
    s._play_q.put(b"\0\0")
    assert s.playing is True


def test_wait_until_quiet_returns_once_tail_passes():
    s = session()
    s._last_write = time.monotonic()
    t0 = time.monotonic()
    assert s.wait_until_quiet(timeout=2) is True
    assert time.monotonic() - t0 >= s.PLAY_TAIL - 0.06


def test_wait_until_quiet_times_out_on_stuck_queue():
    s = session()
    s._play_q = queue.Queue()
    s._play_q.put(b"\0\0")
    assert s.wait_until_quiet(timeout=0.2) is False
