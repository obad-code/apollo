"""The live session's microphone, read along with for more than the turn."""
import numpy as np

import assistant


def _block(amplitude):
    samples = (np.ones(1600) * amplitude * 32767).astype(np.int16)
    return samples.tobytes()


def test_a_listener_hears_every_block_even_between_turns():
    """Asleep, Apollo listens for a voice to wake to. The stream is always on
    and there is no turn to record, so the listener must not depend on one."""
    heard = []
    capture = assistant.LiveCapture()
    capture.listener = heard.append
    capture.feed(_block(0.2))
    capture.feed(_block(0.0))
    assert len(heard) == 2
    assert heard[0] > 0.5 and heard[1] == 0.0
    assert capture.frames == []            # listening is not recording


def test_no_listener_is_the_old_behaviour():
    capture = assistant.LiveCapture()
    capture.feed(_block(0.2))              # nothing to do, nothing kept
    assert capture.frames == []


def test_a_listener_that_fails_does_not_break_the_recording():
    capture = assistant.LiveCapture()

    def broken(level):
        raise RuntimeError("the page went away")

    capture.listener = broken
    capture.start()
    capture.feed(_block(0.2))
    assert capture.stop() is not None


def test_the_voice_keeps_its_listener_across_a_reconnect():
    """A reconnect makes a new capture; the listener has to move to it."""
    voice = assistant.Voice(ui=None)
    fn = lambda level: None                # noqa: E731
    voice.listen(fn)
    assert voice.listener is fn
    voice.capture = assistant.LiveCapture()
    voice.listen(fn)
    assert voice.capture.listener is fn
    voice.listen(None)
    assert voice.capture.listener is None
