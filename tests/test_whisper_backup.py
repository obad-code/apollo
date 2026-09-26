"""Whisper is loaded when it is first needed, not at startup.

It is the backup transcriber - for a turn whose transcript Gemini never
sent, or for when the voice service is down - and it was loaded at every
start regardless: faster-whisper's import alone reserved 400 MB, and the
model another 2.2 GB, making it most of Apollo's memory for something most
days never use.
"""
import sys
import threading
import time

import assistant


class Model:
    def transcribe(self, audio, **kw):
        return iter(["heard"]), "info"


def counting(monkeypatch, slow=0.0, fail=False):
    made = []

    def model(size):
        made.append(size)
        time.sleep(slow)
        if fail:
            raise RuntimeError("no model")
        return Model()

    monkeypatch.setattr(assistant, "_whisper_model", model)
    return made


def test_nothing_is_loaded_until_it_is_needed(monkeypatch):
    made = counting(monkeypatch)
    assistant.load_whisper()
    time.sleep(0.2)
    assert made == []


def test_the_first_transcription_loads_it_and_later_ones_reuse_it(monkeypatch):
    made = counting(monkeypatch)
    backup = assistant.load_whisper()
    segments, _info = backup.transcribe(b"")
    assert list(segments) == ["heard"]
    backup.transcribe(b"")
    assert made == [assistant.WHISPER_SIZE]


def test_two_at_once_load_it_once(monkeypatch):
    made = counting(monkeypatch, slow=0.3)
    backup = assistant.load_whisper()
    threads = [threading.Thread(target=backup.transcribe, args=(b"",)) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(made) == 1


def test_a_model_that_will_not_load_gives_nothing(monkeypatch):
    counting(monkeypatch, fail=True)
    segments, info = assistant.load_whisper().transcribe(b"")
    assert list(segments) == [] and info is None


def test_faster_whisper_is_not_imported_with_apollo():
    assert "faster_whisper" not in sys.modules or not hasattr(assistant, "WhisperModel")
