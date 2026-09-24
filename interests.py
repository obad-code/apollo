"""What Apollo knows about you, and how he comes to know it.

A small file - %LOCALAPPDATA%\\Apollo\\profile.json - of what you care about,
each with how much it matters (0 to 1) and the words to search for it by;
what you do not care for; and a few facts. Gemini reads a summary of it at
the start of every session (gemini_live.system_instruction), so Apollo knows
you without being told; Private Eye hunts by it.

Nobody trains a model here. Claude reads each finished day of the record
(journal.py) with the file as it stands and writes it back updated, once
per day, the first time Apollo is running after the day is over. Interests
that stop coming up fade; a find you mark useful or not moves its interest
up or down at once.
"""

import copy
import datetime
import json
import logging
import os
import re
import threading

import journal

log = logging.getLogger("apollo.interests")

PATH = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                    "Apollo", "profile.json")

MOST = 25            # interests kept
MOST_OTHER = 10      # dislikes, facts
DECAY = 0.93         # per day an interest is not refreshed
FLOOR = 0.08         # below this an interest is let go
NUDGE = 0.15         # how far a thumbs-up or -down moves one
CATCH_UP = 3         # finished days learned at most in one go
DAY_CHARS = 24000    # of a day's record, at most, sent to be learned from

# Where it starts: what Apollo was told about you before he could learn it.
SEED = {
    "about": "",
    "interests": [
        {"name": name, "kind": kind, "weight": weight, "query": query}
        for name, kind, weight, query in (
            ("Nvidia", "company", 0.7, "Nvidia"),
            ("Apple", "company", 0.6, "Apple"),
            ("Microsoft", "company", 0.5, "Microsoft"),
            ("Tesla", "company", 0.5, "Tesla"),
            ("Amazon", "company", 0.45, "Amazon"),
            ("Alphabet", "company", 0.45, "Alphabet Google"),
            ("Meta", "company", 0.45, "Meta Platforms"),
            ("Stock market", "topic", 0.55, "stock market S&P 500 Nasdaq"),
            ("Marvel", "topic", 0.6, "Marvel"),
            ("GTA 6", "game", 0.65, "GTA 6"),
            ("PlayStation", "topic", 0.55, "PlayStation"),
            ("Gaming", "topic", 0.5, "video games"),
            ("Movies", "topic", 0.45, "box office movies"),
        )
    ],
    "dislikes": [],
    "facts": ["Lives in Riyadh", "Speaks Arabic (Saudi) and English"],
    "learned_through": "",
}

_lock = threading.Lock()


def load():
    """The profile, or the seed if there is none yet (or it is damaged)."""
    try:
        with open(PATH, encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            return _clean(loaded, fallback=copy.deepcopy(SEED))
    except (OSError, ValueError):
        pass
    return copy.deepcopy(SEED)


def save(profile):
    try:
        with _lock:
            os.makedirs(os.path.dirname(PATH), exist_ok=True)
            temporary = PATH + ".tmp"
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(profile, handle, ensure_ascii=False, indent=1)
            os.replace(temporary, PATH)
    except OSError as e:
        log.info("could not save the profile: %s", e)


def _clean(raw, fallback):
    """Whatever came back, made into a profile - or `fallback` where it can't be."""
    out = copy.deepcopy(fallback)
    if isinstance(raw.get("about"), str):
        out["about"] = raw["about"].strip()[:600]
    if isinstance(raw.get("interests"), list):
        kept = []
        for item in raw["interests"]:
            if not isinstance(item, dict) or not str(item.get("name") or "").strip():
                continue
            try:
                weight = float(item.get("weight", 0.5))
            except (TypeError, ValueError):
                weight = 0.5
            name = str(item["name"]).strip()[:60]
            kept.append({"name": name, "kind": str(item.get("kind") or "topic")[:20],
                         "weight": round(max(0.0, min(1.0, weight)), 3),
                         "query": str(item.get("query") or name).strip()[:80]})
        kept.sort(key=lambda i: -i["weight"])
        out["interests"] = kept[:MOST]
    for key in ("dislikes", "facts"):
        if isinstance(raw.get(key), list):
            out[key] = [str(v).strip()[:120] for v in raw[key] if str(v).strip()][:MOST_OTHER]
    if isinstance(raw.get("learned_through"), str):
        out["learned_through"] = raw["learned_through"]
    return out


def summary(profile):
    """A few lines for Gemini's instructions: what it knows, strongest first."""
    lines = ["What you know about the user - learned from what they say and "
             "open. Use it quietly to be more useful; never recite it back."]
    if profile.get("about"):
        lines.append(profile["about"])
    strongest = sorted(profile.get("interests", []), key=lambda i: -i["weight"])[:15]
    if strongest:
        lines.append("They care about, most first: "
                     + ", ".join(i["name"] for i in strongest) + ".")
    if profile.get("dislikes"):
        lines.append("They do not care for: " + ", ".join(profile["dislikes"]) + ".")
    if profile.get("facts"):
        lines.append("Facts: " + "; ".join(profile["facts"]) + ".")
    return "\n".join(lines)


def decay(profile, days):
    """Interests that did not come up for `days` days, a little weaker."""
    out = copy.deepcopy(profile)
    factor = DECAY ** max(0, days)
    out["interests"] = [dict(i, weight=round(i["weight"] * factor, 3))
                        for i in out.get("interests", []) if i["weight"] * factor >= FLOOR]
    return out


def rate(profile, name, useful):
    """A find about `name` was useful to you, or it was not."""
    out = copy.deepcopy(profile)
    for item in out.get("interests", []):
        if item["name"].lower() == str(name).lower():
            step = NUDGE if useful else -NUDGE
            item["weight"] = round(max(0.0, min(1.0, item["weight"] + step)), 3)
    out["interests"].sort(key=lambda i: -i["weight"])
    return out


# -- learning ------------------------------------------------------------------

LEARN_SYSTEM = (
    "You maintain a small profile of one person for their voice assistant, "
    "Apollo. You are given the profile as it stands and one day of their "
    "record: what they said to Apollo, what it answered, the tools it used and "
    "what they opened on its display. Return the updated profile as one JSON "
    "object and nothing else, with exactly these keys: "
    '"about" (at most 60 words, plain, in English), '
    f'"interests" (at most {MOST}: objects with "name", "kind" - company, game, '
    'topic, person, team, show, place or other - "weight" from 0 to 1 for how '
    'much it matters to them now, and "query", a few words to search news for '
    'it by), "dislikes" (short phrases), "facts" (short, useful, lasting facts '
    "about them). Raise the weight of what came up today, add what is new, "
    "keep what did not come up as it was. Record only what the day shows; "
    "never guess. Leave out anything sensitive - health, money owed, "
    "passwords, other people's private details."
)


def _day_text(entries):
    lines = []
    for e in entries:
        kind = e.get("kind")
        if kind == "you":
            lines.append(f"You said: {e.get('text', '')}")
        elif kind == "apollo":
            lines.append(f"Apollo answered: {e.get('text', '')}")
        elif kind == "tool":
            lines.append(f"Apollo used {e.get('name')}: {json.dumps(e.get('args', {}), ensure_ascii=False)}")
        elif kind == "opened":
            lines.append(f"They opened a {e.get('what')}: {e.get('title')} ({e.get('source', '')})")
        elif kind in ("watch", "unwatch"):
            lines.append(f"They {'added' if kind == 'watch' else 'removed'} {e.get('symbol')} "
                         "on their stock watchlist")
        elif kind == "rated":
            lines.append(f"They marked a find about {e.get('interest')} as "
                         f"{'useful' if e.get('useful') else 'not useful'}")
    text = "\n".join(lines)
    return text[-DAY_CHARS:]


def _json_in(text):
    """The first JSON object in a reply, fenced or not."""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidate = match.group(1) if match else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(candidate)


def learn(entries, profile, ask):
    """One day learned from. `ask(system, prompt)` is one question to Claude.
    Anything that goes wrong leaves the profile as it was."""
    day = _day_text(entries)
    if not day.strip():
        return profile
    known = {k: profile.get(k) for k in ("about", "interests", "dislikes", "facts")}
    prompt = ("The profile as it stands:\n" + json.dumps(known, ensure_ascii=False, indent=1)
              + "\n\nThe day's record:\n" + day)
    try:
        raw = _json_in(ask(LEARN_SYSTEM, prompt) or "")
    except Exception as e:  # noqa: BLE001 - the old profile is still a profile
        log.info("could not learn from the day: %s", type(e).__name__)
        return profile
    if not isinstance(raw, dict) or not isinstance(raw.get("interests"), list):
        return profile
    return _clean(raw, fallback=profile)


def catch_up(ask, today=None):
    """Learn every finished day not learned yet - the most recent CATCH_UP
    of them - and remember where it got to. Returns the days learned."""
    today = today or datetime.date.today()
    profile = load()
    try:
        through = datetime.date.fromisoformat(profile.get("learned_through") or "")
    except ValueError:
        through = None
    waiting = [d for d in journal.days() if d < today and (through is None or d > through)]
    learned = []
    for day in waiting[-CATCH_UP:]:
        if through is not None:
            profile = decay(profile, (day - through).days - 1)
        profile = learn(journal.day(day), profile, ask)
        profile["learned_through"] = day.isoformat()
        through = day
        learned.append(day)
        save(profile)
    if learned:
        log.info("learned from %s", ", ".join(d.isoformat() for d in learned))
    return learned


class Learner:
    """Catches up on its own thread: a couple of minutes after Apollo starts,
    then every hour - so a day is learned from the first time Apollo is
    running after it ends. `ask` is one question to Claude."""

    def __init__(self, ask, first=120.0, every=3600.0):
        self._ask = ask
        self._first = first
        self._every = every
        self._stopping = threading.Event()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True, name="apollo-learner")
        self._thread.start()
        return self

    def stop(self):
        self._stopping.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def alive(self):
        return self._thread is not None and self._thread.is_alive()

    def _run(self):
        if self._stopping.wait(self._first):
            return
        while not self._stopping.is_set():
            try:
                catch_up(self._ask)
            except Exception:  # noqa: BLE001 - try again next hour
                log.info("learning failed; trying again later", exc_info=True)
            self._stopping.wait(self._every)
