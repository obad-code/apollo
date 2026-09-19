"""What Apollo's APIs have cost today, counted on this machine.

Neither provider will tell an ordinary API key what it has spent, so Apollo
keeps its own ledger: tokens as they are reported on each response, totalled
per day in %LOCALAPPDATA%\\Apollo\\usage.json, and a cost worked out from the
table below. The prices are the published list ones and they change, so every
figure this module produces is marked `estimated` - the display says "approx"
and the voice says "about".
"""

import json
import logging
import os
import threading
from datetime import date

log = logging.getLogger("apollo.usage")

PATH = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                    "Apollo", "usage.json")

# Dollars per million tokens. Edit to match what you are actually billed.
PRICES = {
    "gemini": {"prompt": 3.00, "response": 12.00},    # native-audio in/out
    "claude": {"prompt": 5.00, "response": 25.00},    # Opus 5
}

_lock = threading.Lock()


def _today_key():
    return date.today().isoformat()


def _load():
    try:
        with open(PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(data):
    try:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError as e:
        log.info("could not write the usage ledger: %s", e)


def reset():
    """Forget today's totals (used by tests, and by a deliberate wipe)."""
    with _lock:
        data = _load()
        data.pop(_today_key(), None)
        _save(data)


def record(provider, model="", prompt=0, response=0, seconds=0.0):
    """Add one exchange to today's ledger. Never raises."""
    try:
        with _lock:
            data = _load()
            day = data.setdefault(_today_key(), {"turns": 0})
            entry = day.setdefault(provider, {"prompt": 0, "response": 0, "seconds": 0.0})
            entry["prompt"] += int(prompt or 0)
            entry["response"] += int(response or 0)
            entry["seconds"] = round(entry.get("seconds", 0.0) + float(seconds or 0.0), 1)
            day["turns"] = day.get("turns", 0) + 1
            day["model_" + provider] = model or day.get("model_" + provider, "")
            _save(data)
    except Exception:  # noqa: BLE001 - a ledger must never break a turn
        log.debug("usage not recorded", exc_info=True)


def today():
    """Today's totals and an estimated cost."""
    with _lock:
        day = _load().get(_today_key(), {})
    out = {"turns": day.get("turns", 0), "estimated": True}
    cost = 0.0
    for provider, price in PRICES.items():
        entry = day.get(provider) or {"prompt": 0, "response": 0, "seconds": 0.0}
        out[provider] = {"prompt": entry.get("prompt", 0),
                         "response": entry.get("response", 0),
                         "seconds": entry.get("seconds", 0.0)}
        cost += (entry.get("prompt", 0) * price["prompt"]
                 + entry.get("response", 0) * price["response"]) / 1_000_000
    out["cost"] = round(cost, 2)
    out["tokens"] = sum(out[p]["prompt"] + out[p]["response"] for p in PRICES)
    return out
