"""Which stocks Apollo watches, and how you change them by voice.

A list in a file rather than a constant in the source: asking him to follow
Palantir should outlive the session it was asked in. `market.WATCHLIST` stays
as the list it starts from.

Nothing here raises. A name that cannot be resolved to a symbol is refused
with a sentence worth saying out loud, because that is what happens to it.
"""

import json
import logging
import os
import threading

import market

log = logging.getLogger("apollo.watchlist")

PATH = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                    "Apollo", "watchlist.json")
DEFAULT = market.WATCHLIST

# The display draws these as cards in two columns; past this they stop fitting
# the column, which is a worse answer than "that is enough stocks".
MAX = 12

_memo = None
_lock = threading.Lock()
# Held across a whole change - read, edit, save. "Take off Apple, Tesla and
# Meta" can arrive as three tool calls on three threads, and without this each
# read the same list, dropped its own, and saved: the last save won.
_edit = threading.Lock()


def current():
    """The symbols being watched, in order."""
    global _memo
    with _lock:
        if _memo is not None:
            return list(_memo)
    symbols = None
    try:
        with open(PATH, encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, list) and all(isinstance(s, str) for s in loaded):
            symbols = [s.upper() for s in loaded][:MAX]
    except (OSError, ValueError) as e:
        log.info("watchlist unreadable, using the built-in list: %s", e)
    if not symbols:
        symbols = list(DEFAULT)
    with _lock:
        _memo = list(symbols)
    return list(symbols)


def _save(symbols):
    global _memo
    with _lock:
        _memo = list(symbols)
    try:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        with open(PATH, "w", encoding="utf-8") as handle:
            json.dump(symbols, handle)
    except OSError as e:
        log.info("could not save the watchlist: %s", e)


def _symbol_for(text):
    """A name or ticker as spoken -> a symbol, or None."""
    try:
        symbol = market.resolve(text)
    except Exception:  # noqa: BLE001 - "I couldn't find that" is the answer
        return None
    return (symbol or "").upper() or None


def _unknown(text):
    # The market search knows companies by their English names. You say them
    # in Arabic and the model passes them on as said, so the refusal says
    # what to try instead: the model reads it and calls again.
    return {"ok": False, "error": f"I couldn't find a stock called {text}. "
                                  "Try its English name or its ticker."}


def add(text):
    """Start watching whatever `text` names."""
    symbol = _symbol_for(text)
    if symbol is None:
        return _unknown(text)
    with _edit:
        symbols = current()
        if symbol in symbols:
            return {"ok": True, "already": True, "symbol": symbol,
                    "watchlist": symbols}
        if len(symbols) >= MAX:
            return {"ok": False, "symbol": symbol,
                    "error": f"The watchlist is full at {MAX}. Take one off first."}
        symbols.append(symbol)
        _save(symbols)
    return {"ok": True, "symbol": symbol, "watchlist": symbols}


def remove(text):
    """Stop watching it."""
    symbol = _symbol_for(text)
    if symbol is None:
        return _unknown(text)
    with _edit:
        symbols = current()
        if symbol not in symbols:
            return {"ok": False, "symbol": symbol,
                    "error": f"{symbol} isn't on the watchlist."}
        symbols.remove(symbol)
        _save(symbols)
    return {"ok": True, "symbol": symbol, "watchlist": symbols}
