import json

import weather


PAYLOAD = {
    "current": {"temperature_2m": 32.5, "weather_code": 0},
    "daily": {"temperature_2m_max": [42.0], "temperature_2m_min": [29.7]},
}


def test_now_reads_the_payload(monkeypatch):
    weather._cache.clear()
    monkeypatch.setattr(weather, "_get", lambda url, ttl: PAYLOAD)
    reading = weather.now()
    assert reading["temp"] == 33 and reading["high"] == 42 and reading["low"] == 30
    assert reading["text"] == "clear"


def test_codes_have_words():
    assert weather.describe(0) == "clear"
    assert "rain" in weather.describe(61)
    assert weather.describe(999) == ""


def test_a_dead_service_is_empty_not_an_error(monkeypatch):
    weather._cache.clear()

    def boom(url, ttl):
        raise OSError("offline")

    monkeypatch.setattr(weather, "_get", boom)
    assert weather.now() == {}
