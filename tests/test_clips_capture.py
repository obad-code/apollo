import time

import pytest

import clips


class FakeFrame:
    def __init__(self, i):
        self.pts = None
        self.time_base = None
        self.index = i


class FakePacket:
    def __init__(self, i, keyframe):
        self.pts = i
        self.is_keyframe = keyframe
        self.size = 100

    def __bytes__(self):
        return b"p" * self.size


class FakeSource:
    name = "fake"

    def __init__(self, count=90):
        self.count = count
        self.closed = False

    def frames(self):
        for i in range(self.count):
            yield FakeFrame(i)
            time.sleep(0.001)

    def close(self):
        self.closed = True


class FakeEncoder:
    def __init__(self):
        self.sent = 0

    def encode(self, frame=None):
        if frame is None:
            return []
        self.sent += 1
        return [FakePacket(self.sent - 1, keyframe=(self.sent - 1) % 30 == 0)]


def test_buffer_collects_packets_and_stops(monkeypatch):
    source = FakeSource()
    monkeypatch.setattr(clips, "_open_source", lambda: source)
    monkeypatch.setattr(clips, "_open_encoder", lambda w, h: FakeEncoder())
    buffer = clips.ReplayBuffer(seconds=2)
    buffer.start()
    deadline = time.monotonic() + 3
    while buffer.frames < 60 and time.monotonic() < deadline:
        time.sleep(0.01)
    buffer.stop()
    assert buffer.frames >= 60
    assert source.closed is True
    assert buffer.running is False
    assert buffer.status()["source"] == "fake"


def test_buffer_reports_a_failure_instead_of_raising(monkeypatch):
    def refuse():
        raise OSError("no screen recorder here")
    monkeypatch.setattr(clips, "_open_source", refuse)
    buffer = clips.ReplayBuffer()
    buffer.start()
    deadline = time.monotonic() + 2
    while buffer.error is None and time.monotonic() < deadline:
        time.sleep(0.01)
    buffer.stop()
    assert "no screen recorder here" in buffer.error
    assert buffer.status()["ok"] is False


def test_status_reports_what_it_holds(monkeypatch):
    monkeypatch.setattr(clips, "_open_source", lambda: FakeSource(count=120))
    monkeypatch.setattr(clips, "_open_encoder", lambda w, h: FakeEncoder())
    buffer = clips.ReplayBuffer(seconds=30)
    buffer.start()
    deadline = time.monotonic() + 3
    while buffer.frames < 90 and time.monotonic() < deadline:
        time.sleep(0.01)
    status = buffer.status()
    buffer.stop()
    assert status["ok"] is True and status["seconds"] >= 0 and status["fps"] > 0


def test_gdigrab_is_the_default_source(monkeypatch):
    """ddagrab is never opened in-process: a hang inside it holds the GIL and
    freezes all of Apollo (measured - the main thread stops printing)."""
    picked = []
    monkeypatch.setattr(clips.VideoSource, "gdi", classmethod(lambda cls: picked.append("gdi")))
    monkeypatch.setattr(clips.VideoSource, "dda", classmethod(lambda cls: picked.append("dda")))
    monkeypatch.delenv("APOLLO_CAPTURE", raising=False)
    clips._open_source()
    assert picked == ["gdi"]


def test_ddagrab_only_on_explicit_request(monkeypatch):
    picked = []
    monkeypatch.setattr(clips.VideoSource, "gdi", classmethod(lambda cls: picked.append("gdi")))
    monkeypatch.setattr(clips.VideoSource, "dda", classmethod(lambda cls: picked.append("dda")))
    monkeypatch.setenv("APOLLO_CAPTURE", "ddagrab")
    clips._open_source()
    assert picked == ["dda"]
