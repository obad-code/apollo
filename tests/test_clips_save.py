import os

import av
import numpy as np
import pytest

import clips


def test_audio_slice_matches_video_window():
    # 10 chunks, one per 0.1 s, each 4800 stereo samples of a known value
    chunks = []
    for i in range(10):
        block = np.full((4800, 2), i, dtype=np.int16)
        chunks.append((block.tobytes(), i * 0.1))
    taken = clips.audio_track(chunks, start=0.45, end=0.75, rate=48000, channels=2)
    values = np.frombuffer(taken, dtype=np.int16)
    values = values[values != 0]                        # ignore the silent padding
    # Chunks stamped inside the window only: sound may start a chunk late,
    # never a chunk early, so it can't run ahead of the picture.
    assert set(values.tolist()) == {5, 6, 7}
    assert 0.25 <= len(values) / 2 / 48000 <= 0.35


def test_audio_slice_empty_without_audio():
    assert clips.audio_slice([], start=0.0, end=1.0, rate=48000, channels=2) == []


def test_save_writes_a_playable_mp4(tmp_path, monkeypatch):
    """A real encode/mux round trip, with synthetic frames instead of a screen."""
    buffer = clips.ReplayBuffer(seconds=5)
    encoder = clips._open_encoder(320, 240)
    now = 1000.0
    for i in range(90):                       # three seconds at 30 fps
        frame = av.VideoFrame(320, 240, "nv12")
        for plane in frame.planes:
            memoryview(plane)[:] = bytes(len(memoryview(plane)))
        frame.pts = i
        frame.time_base = clips.fractions.Fraction(1, clips.FPS)
        when = now + i / 30.0
        for packet in encoder.encode(frame):
            buffer.video.add((bytes(packet), packet.pts, bool(packet.is_keyframe), when), when)
    for packet in encoder.encode(None):
        buffer.video.add((bytes(packet), packet.pts, True, now + 3.0), now + 3.0)

    monkeypatch.setattr(clips.time, "monotonic", lambda: now + 3.0)
    result = buffer.save(seconds=2, folder_path=str(tmp_path))
    assert result["ok"] is True, result
    assert os.path.exists(result["path"])
    back = av.open(result["path"])
    frames = sum(1 for _ in back.decode(video=0))
    back.close()
    assert frames > 30                        # about two seconds' worth
    assert 1.0 <= result["seconds"] <= 3.0


def test_save_without_a_buffer_explains_itself(tmp_path):
    buffer = clips.ReplayBuffer()
    buffer.error = "gdigrab failed"
    result = buffer.save(folder_path=str(tmp_path))
    assert result["ok"] is False and "gdigrab failed" in result["error"]


def test_save_with_nothing_recorded_is_polite(tmp_path):
    result = clips.ReplayBuffer().save(folder_path=str(tmp_path))
    assert result["ok"] is False and "nothing" in result["error"].lower()


def test_audio_track_places_sound_at_its_offset_and_pads_silence():
    """Loopback delivers nothing while the speakers are silent, so a clip
    where sound starts halfway must not begin with that sound."""
    import numpy as np
    chunk = np.full((4800, 2), 7, dtype=np.int16).tobytes()      # 0.1s of tone
    chunks = [(chunk, 10.6), (chunk, 10.7)]                      # sound late in the window
    track = clips.audio_track(chunks, start=10.0, end=11.0, rate=48000, channels=2)
    samples = np.frombuffer(track, dtype=np.int16).reshape(-1, 2)
    assert abs(len(samples) - 48000) <= 48                       # one second
    assert samples[:24000].any() == False                        # silent first half
    assert (samples[:, 0] == 7).sum() == 9600                    # two chunks of tone
    first_tone = int(np.argmax(samples[:, 0] == 7)) / 48000
    assert 0.45 <= first_tone <= 0.65                            # where it actually happened


def test_audio_track_without_sound_is_empty():
    assert clips.audio_track([], start=0.0, end=1.0, rate=48000, channels=2) == b""


def test_saved_clip_has_honest_timing(tmp_path):
    """A clip whose timestamps are muxed in the wrong time base plays at the
    wrong speed and reports no duration."""
    import av
    buffer = clips.ReplayBuffer(seconds=5)
    encoder = clips._open_encoder(320, 240)
    now = 2000.0
    for i in range(60):
        frame = av.VideoFrame(320, 240, "nv12")
        for plane in frame.planes:
            memoryview(plane)[:] = bytes(len(memoryview(plane)))
        frame.pts = i
        frame.time_base = clips.fractions.Fraction(1, clips.FPS)
        when = now + i / clips.FPS
        for packet in encoder.encode(frame):
            buffer.video.add((bytes(packet), packet.pts, bool(packet.is_keyframe), when), when)
    for packet in encoder.encode(None):
        buffer.video.add((bytes(packet), packet.pts, True, now + 2.0), now + 2.0)
    with_fake_clock = clips.time.monotonic
    clips.time.monotonic = lambda: now + 2.0
    try:
        result = buffer.save(seconds=5, folder_path=str(tmp_path))
    finally:
        clips.time.monotonic = with_fake_clock
    assert result["ok"], result
    back = av.open(result["path"])
    stream = back.streams.video[0]
    seconds = float(back.duration or 0) / 1e6
    assert 1.5 <= seconds <= 2.5, seconds
    assert 25 <= float(stream.average_rate) <= 35
    back.close()


def test_a_clip_starting_at_a_later_keyframe_still_plays(tmp_path):
    """The normal case: the window begins mid-buffer. Every keyframe must
    carry its own SPS/PPS or the file has no start code and plays as nothing."""
    import av
    buffer = clips.ReplayBuffer(seconds=10)
    encoder = clips._open_encoder(320, 240)
    now = 3000.0
    for i in range(120):                      # four seconds, keyframes each second
        frame = av.VideoFrame(320, 240, "nv12")
        for plane in frame.planes:
            memoryview(plane)[:] = bytes(len(memoryview(plane)))
        frame.pts = i
        frame.time_base = clips.fractions.Fraction(1, clips.FPS)
        when = now + i / clips.FPS
        for packet in encoder.encode(frame):
            buffer.video.add((bytes(packet), packet.pts, bool(packet.is_keyframe), when), when)
    for packet in encoder.encode(None):
        buffer.video.add((bytes(packet), packet.pts, True, now + 4.0), now + 4.0)

    real = clips.time.monotonic
    clips.time.monotonic = lambda: now + 4.0
    try:
        result = buffer.save(seconds=2, folder_path=str(tmp_path))   # starts at ~2s in
    finally:
        clips.time.monotonic = real
    assert result["ok"], result
    back = av.open(result["path"])
    frames = sum(1 for _ in back.decode(video=0))
    back.close()
    assert frames > 30


def test_stale_buffer_is_refused(tmp_path):
    """If capture stopped quietly, the newest frame is minutes old - saving it
    would hand back footage of whatever was on screen back then."""
    buffer = clips.ReplayBuffer(seconds=60)
    now = 5000.0
    for i in range(30):
        buffer.video.add((b"x", i, i == 0, now + i / 30.0), now + i / 30.0)
    real = clips.time.monotonic
    clips.time.monotonic = lambda: now + 30.0        # half a minute later
    try:
        result = buffer.save(seconds=10, folder_path=str(tmp_path))
    finally:
        clips.time.monotonic = real
    assert result["ok"] is False
    assert "stopped" in result["error"].lower() or "stale" in result["error"].lower()
