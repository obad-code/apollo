"""The speaker is one PortAudio stream used from three threads.

The reply is written to it from a worker thread (a blocking write, kept off
the event loop); `hush` stops and restarts it from whichever thread you
interrupted on - the receive loop, or the chord's; and a reconnect or a
change of listening mode closes it from the loop. PortAudio does not allow
any of those at once: a write that meets an abort comes back "Stream is
stopped" and ends the session, and one that meets a close reads freed
memory and takes Apollo down with an access violation in
libportaudio64bit.dll - which is what the log and Windows' crash report
showed on 25 September 2026, in always-listening, where the model is cut
off, and so hushed, most often.
"""
import threading
import time

import gemini_live

SLICE = 0.03          # how long the fake takes over one write


class Speaker:
    """A stream that notices being used by two threads at once."""

    def __init__(self):
        self.busy = threading.Lock()
        self.overlaps = []
        self.written = 0
        self.closed = False
        self.aborts = 0

    def _enter(self, what):
        if not self.busy.acquire(blocking=False):
            self.overlaps.append(what)
            return False
        return True

    def write(self, data):
        held = self._enter("write")
        if self.closed:
            self.overlaps.append("write after close")
        time.sleep(SLICE)
        self.written += len(data)
        if held:
            self.busy.release()

    def _quick(self, what):
        held = self._enter(what)
        if held:
            self.busy.release()

    def abort(self, ignore_errors=False):
        self._quick("abort")
        self.aborts += 1

    def start(self):
        self._quick("start")

    def close(self, ignore_errors=False):
        self._quick("close")
        self.closed = True


def session_with(speaker):
    s = gemini_live.LiveSession(api_key="test")
    s._speaker = speaker
    return s


def writing(s, chunk):
    worker = threading.Thread(target=s._write, args=(chunk,))
    worker.start()
    time.sleep(SLICE / 2)          # well inside the first slice
    return worker


# A second of reply: long enough to be cut into many slices.
SECOND = b"\0\0" * gemini_live.OUTPUT_RATE


def test_hush_never_touches_the_stream_mid_write():
    speaker = Speaker()
    s = session_with(speaker)
    worker = writing(s, SECOND)
    s.hush()
    worker.join(2)
    assert speaker.overlaps == []
    assert speaker.aborts == 1


def test_hush_stops_the_rest_of_the_chunk_being_played():
    speaker = Speaker()
    s = session_with(speaker)
    worker = writing(s, SECOND)
    s.hush()
    worker.join(2)
    # Cut off within a slice or two, not after the whole second.
    assert speaker.written < len(SECOND) // 4


def test_closing_waits_for_the_write_and_nothing_is_written_after():
    speaker = Speaker()
    s = session_with(speaker)
    worker = writing(s, SECOND)
    s._close_streams()
    worker.join(2)
    assert speaker.closed
    assert speaker.overlaps == []
    assert speaker.written < len(SECOND) // 4


def test_a_write_with_no_speaker_is_nothing():
    s = session_with(None)
    s._write(SECOND)               # no stream, no error


def test_the_whole_chunk_is_written_when_nothing_interrupts():
    speaker = Speaker()
    s = session_with(speaker)
    s._write(b"\0\0" * 2400)       # a tenth of a second
    assert speaker.written == 4800
