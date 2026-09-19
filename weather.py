"""Riyadh's weather, from Open-Meteo: no key, no account, about a second."""

import json
import math
import threading
import time
import urllib.parse
import urllib.request

RIYADH = (24.7136, 46.6753)
TIMEZONE = "Asia/Riyadh"
TTL = 900
TIMEOUT = 6

# WMO weather codes, in the handful of words a voice would use.
CODES = {0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
         45: "fog", 48: "freezing fog", 51: "light drizzle", 53: "drizzle",
         55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
         71: "light snow", 73: "snow", 75: "heavy snow", 80: "rain showers",
         81: "rain showers", 82: "heavy rain showers", 95: "thunderstorms",
         96: "thunderstorms with hail", 99: "thunderstorms with hail"}

_cache = {}
_lock = threading.Lock()


def _round(value):
    """Half up, the way a person reads a thermometer: 32.5 is 33, not 32."""
    if value is None:
        return None
    return int(math.floor(float(value) + 0.5))


def describe(code):
    return CODES.get(int(code), "") if code is not None else ""


def _get(url, ttl):
    now = time.monotonic()
    with _lock:
        hit = _cache.get(url)
        if hit and hit[0] > now:
            return hit[1]
    with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
        data = json.load(response)
    with _lock:
        _cache[url] = (now + ttl, data)
    return data


def now(place=RIYADH):
    """Temperature now, today's high and low, and a word for the sky."""
    url = ("https://api.open-meteo.com/v1/forecast"
           f"?latitude={place[0]}&longitude={place[1]}"
           "&current=temperature_2m,weather_code"
           "&daily=temperature_2m_max,temperature_2m_min"
           f"&timezone={urllib.parse.quote(TIMEZONE)}&forecast_days=1")
    try:
        data = _get(url, TTL)
    except Exception:  # noqa: BLE001 - weather is a nicety, never a failure
        return {}
    current = data.get("current") or {}
    daily = data.get("daily") or {}
    code = current.get("weather_code")
    highs, lows = daily.get("temperature_2m_max") or [], daily.get("temperature_2m_min") or []
    return {"temp": _round(current.get("temperature_2m", 0)),
            "high": _round(highs[0]) if highs else None,
            "low": _round(lows[0]) if lows else None,
            "code": code, "text": describe(code)}
