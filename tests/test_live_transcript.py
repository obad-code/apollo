"""Your words, as they are shown back to you.

The transcript arrives in fragments and is joined. It is emptied when a turn
begins - which is a thing that only happens on the push-to-talk path. In
always-listening there is no press to begin anything, so the buffer was never
emptied and every sentence was shown stuck onto every sentence before it.
"""
import threading

import gemini_live


def session(auto_vad):
    """A LiveSession with nothing started: only the accumulator is under test."""
    live = gemini_live.LiveSession.__new__(gemini_live.LiveSession)
    live._heard = []
    live._last_heard = 0.0
    live._in_flight = False
    live._discarded = False
    live.auto_vad = auto_vad
    live._on_user_turn = None
    live._on_user_text = None
    live.shown = []
    live._on_heard = live.shown.append
    # What hush holds while it stops the speaker (see test_live_speaker_race).
    live._speaker_lock = threading.Lock()
    live._hushes = 0
    return live


def test_each_utterance_is_shown_on_its_own_when_always_listening():
    live = session(auto_vad=True)

    for fragment in ("open ", "chrome"):
        live._note_heard(fragment)
    live._finish_turn_transcript()
    for fragment in ("what ", "is nvidia doing"):
        live._note_heard(fragment)

    assert live.shown[-1] == "what is nvidia doing", (
        f"the second sentence carried the first with it: {live.shown[-1]!r}")


def test_push_to_talk_is_unaffected():
    """It clears on begin_turn, and must not also clear mid-sentence."""
    live = session(auto_vad=False)
    for fragment in ("how ", "is ", "nvidia doing"):
        live._note_heard(fragment)
    assert live.shown[-1] == "how is nvidia doing"


class FakeSpeaker:
    def __init__(self):
        self.aborted = 0
        self.started = 0

    def abort(self):
        self.aborted += 1

    def start(self):
        self.started += 1


def test_speaking_over_apollo_stops_him_mid_word():
    """Draining the queue is not enough to make him stop.

    The queue holds what has not been written yet; the sound card holds what
    has. Emptying only the queue leaves whatever the device has buffered to
    play out, so he carries on talking over you for as long as that buffer
    lasts. The device has to be flushed too.
    """
    import asyncio

    live = session(auto_vad=True)
    # The real one is asyncio's; _drain only knows how that one goes empty.
    live._play_q = asyncio.Queue()
    for _ in range(5):
        live._play_q.put_nowait(b"\x00\x00")
    assert live._play_q.qsize() == 5, "the test queued nothing for hush to drain"
    live._speaker = FakeSpeaker()
    live._play_open = threading.Event()
    live._play_open.set()

    live.hush()

    assert live._play_q.empty(), "audio still queued"
    assert live._speaker.aborted == 1, "the sound card was left to play out"
    assert live._speaker.started == 1, "the stream was not reopened"
    assert not live._play_open.is_set()


def test_hushing_without_a_speaker_is_harmless():
    """It is called from the turn path, which runs before audio is up."""
    import asyncio

    live = session(auto_vad=False)
    live._play_q = asyncio.Queue()
    live._speaker = None
    live._play_open = threading.Event()
    live.hush()
