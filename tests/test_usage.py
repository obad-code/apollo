import json
import os

import usage


def test_records_tokens_per_provider(tmp_path, monkeypatch):
    monkeypatch.setattr(usage, "PATH", str(tmp_path / "usage.json"))
    usage.reset()
    usage.record("gemini", "native-audio", prompt=1000, response=500)
    usage.record("gemini", "native-audio", prompt=200, response=100)
    usage.record("claude", "opus", prompt=3000, response=700)
    today = usage.today()
    assert today["gemini"]["prompt"] == 1200 and today["gemini"]["response"] == 600
    assert today["claude"]["prompt"] == 3000
    assert today["turns"] == 3


def test_cost_is_marked_estimated(tmp_path, monkeypatch):
    monkeypatch.setattr(usage, "PATH", str(tmp_path / "usage.json"))
    usage.reset()
    usage.record("claude", "opus", prompt=1_000_000, response=1_000_000)
    today = usage.today()
    assert today["estimated"] is True
    assert today["cost"] == round(usage.PRICES["claude"]["prompt"] + usage.PRICES["claude"]["response"], 2)


def test_survives_a_corrupt_file(tmp_path, monkeypatch):
    path = tmp_path / "usage.json"
    path.write_text("{ this is not json")
    monkeypatch.setattr(usage, "PATH", str(path))
    usage.reset()
    usage.record("gemini", "m", prompt=10)
    assert usage.today()["gemini"]["prompt"] == 10


def test_a_new_day_starts_at_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(usage, "PATH", str(tmp_path / "usage.json"))
    usage.reset()
    monkeypatch.setattr(usage, "_today_key", lambda: "2026-09-19")
    usage.record("gemini", "m", prompt=100)
    monkeypatch.setattr(usage, "_today_key", lambda: "2026-09-20")
    assert usage.today()["gemini"]["prompt"] == 0
