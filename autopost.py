"""LYLA's daily Shorts, on autopilot.

Every day (or every SHORTS_EVERY days) at SHORTS_HOUR she:

    1. looks at what is trending (Google Trends, free) and picks SHORTS_COUNT
       topics that would stop the scroll - safe ones only;
    2. makes a Short for each (shorts.make);
    3. asks you which one to post (Apollo says it, and an email if set up);
    4. posts the one you pick to YouTube - or, if you have not answered in
       SHORTS_WAIT_HOURS (3 by default), her own first pick.

Say "نزل رقم ٢" / "post number 2" to pick, "لا تنزل شي" to skip today.
Upload needs a one-time YouTube setup - see youtube_upload.py.
"""

import datetime as dt
import json
import logging
import os
import re
import urllib.request
import xml.etree.ElementTree as ET

log = logging.getLogger("apollo.autopost")

from shorts import WORLDS  # noqa: E402

COUNT = max(1, min(5, int(os.environ.get("SHORTS_COUNT") or 2)))
AUTO = os.environ.get("SHORTS_AUTO", "").strip().lower() in ("1", "true", "yes", "on")          # make Shorts by itself every day (off unless asked)
AUTOPOST = os.environ.get("SHORTS_AUTOPOST", "").strip().lower() in ("1", "true", "yes", "on")  # post by itself after the wait (off unless asked)
POST_ALL = os.environ.get("SHORTS_POST_ALL", "1").strip().lower() not in ("0", "false", "no", "off")
EVERY = max(1, int(os.environ.get("SHORTS_EVERY") or 1))
WAIT_HOURS = float(os.environ.get("SHORTS_WAIT_HOURS") or 3)
GEO = os.environ.get("SHORTS_GEO") or "US"
STATE = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                     "Apollo", "shorts_pending.json")

PICK_SYSTEM = (
    "You pick topics for a faceless animated YouTube Shorts channel that wants views. "
    "Given today's trending searches, choose topics that are curious, shareable and "
    "evergreen-friendly: a surprising fact, a gripping story, or a POV wealth ladder, tied to a "
    "trend. Never politics, tragedy, real private people, anything indecent or against Islam. "
    "Every pick must happen in a DIFFERENT world - each Short gets its own setting and look. "
    'Answer ONLY with JSON: [{"kind": "fact" or "story" or "ladder", "world": one of '
    + json.dumps(sorted(WORLDS)) + ', "topic": "...", "why": "..."}], best first.')


def trends(geo=GEO, fetch=None):
    """Today's trending searches, as plain titles. [] if unreachable."""
    url = f"https://trends.google.com/trending/rss?geo={geo}"
    try:
        if fetch is None:
            with urllib.request.urlopen(url, timeout=15) as r:  # noqa: S310 - fixed https url
                body = r.read()
        else:
            body = fetch(url)
        return [i.findtext("title", "").strip() for i in ET.fromstring(body).iter("item")][:25]
    except Exception:  # noqa: BLE001
        log.info("trends unreachable", exc_info=True)
        return []


def pick_topics(count=COUNT, found=None, think=None):
    found = trends() if found is None else found
    prompt = (f"Pick {count} topics. Trending now: {', '.join(found) or 'unknown - use your judgement'}.")
    if think is None:
        import shorts
        text = shorts._write(prompt, PICK_SYSTEM)
    else:
        text = think(prompt)
    m = re.search(r"\[.*\]", text or "", re.S)
    picks = []
    try:
        picks = [p for p in json.loads(m.group(0)) if str(p.get("topic", "")).strip()] if m else []
    except ValueError:
        pass
    while len(picks) < count:
        picks.append({"kind": ("fact", "story", "ladder")[len(picks) % 3], "topic": ""})
    out, used = [], set()
    for p in picks[:count]:
        world = p.get("world") if p.get("world") in WORLDS and p.get("world") not in used else ""
        if not world:                                  # a different world for every Short
            world = next((w for w in sorted(WORLDS) if w not in used), "")
        used.add(world)
        out.append({"kind": p.get("kind") if p.get("kind") in ("fact", "story", "ladder") else "fact",
                    "world": world, "topic": str(p.get("topic", ""))[:120]})
    return out


# -- the pending choice ----------------------------------------------------------------
def load(path=STATE):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data, path=STATE):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def offer(made, now=None, path=STATE):
    """Remember today's Shorts and when to post on our own."""
    now = now or dt.datetime.now()
    data = {"made": made, "asked": now.isoformat(),
            "deadline": (now + dt.timedelta(hours=WAIT_HOURS)).isoformat(), "status": "waiting"}
    save(data, path)
    return data


def question(made):
    if len(made) == 1:                      # a Short you asked for: you decide what happens to it
        return (f"Your Short is ready: {made[0]['title']}. Do you want it posted, saved on YouTube as a private draft, "
                "or just kept as a file?")
    lines = [f"{i + 1}. {m['title']}" for i, m in enumerate(made)]
    if POST_ALL:
        return ("Today's Shorts are ready: " + " | ".join(lines)
                + f". I'll post them all in {WAIT_HOURS:g} hours unless you say which one only (post 2) or skip.")
    return ("Shorts ready - which one should I post? " + " | ".join(lines)
            + f". If you don't answer in {WAIT_HOURS:g} hours I'll post number 1.")


def choose(number, path=STATE, upload=None, privacy=None):
    """Post the Short you picked (1-based) - `privacy` "private" saves it on YouTube as a private draft.
    0 = keep it as a file only."""
    data = load(path)
    if data.get("status") != "waiting":
        return {"ok": False, "error": "No Shorts are waiting for a pick."}
    if number == 0:
        data["status"] = "skipped"
        save(data, path)
        return {"ok": True, "result": "Kept as a file only - nothing was posted."}
    made = data.get("made", [])
    if not 1 <= number <= len(made):
        return {"ok": False, "error": f"Pick 1 to {len(made)}."}
    return _post(data, made[number - 1], path, upload, privacy)


def choose_all(path=STATE, upload=None):
    """Post every Short that is waiting."""
    data = load(path)
    if data.get("status") != "waiting":
        return {"ok": False, "error": "No Shorts are waiting for a pick."}
    links, errors = [], []
    for item in data.get("made", []):
        r = _post(dict(data), item, path, upload)
        (links if r.get("ok") else errors).append(r.get("link") or r.get("error"))
    data.update(status="posted" if links else "failed", posted=f"{len(links)} Shorts", link=", ".join(links), error="; ".join(errors))
    save(data, path)
    return {"ok": bool(links), "result": f"Posted {len(links)} Short(s)" + (f"; {len(errors)} failed" if errors else ""),
            "link": ", ".join(links), **({"error": "; ".join(errors)} if errors and not links else {})}


def _post(data, item, path, upload, privacy=None):
    if upload is None:
        import youtube_upload
        upload = youtube_upload.upload
    try:
        link = upload(item["path"], item.get("notes", "")) if not privacy else upload(item["path"], item.get("notes", ""), privacy)
    except Exception as e:  # noqa: BLE001
        data["status"] = "failed"
        data["error"] = str(e) or type(e).__name__
        save(data, path)
        log.warning("short upload failed: %s", e)
        return {"ok": False, "error": data["error"]}
    data.update(status="posted", posted=item["title"], link=link)
    save(data, path)
    try:
        import emailer
        emailer.notify(("Private draft saved on YouTube: " if privacy == "private" else "Posted on YouTube: ") + item["title"], link)
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "result": (f"Saved as a private draft on YouTube: {item['title']}" if privacy == "private"
                                    else f"Posted: {item['title']}"), "link": link}


def tick(now=None, path=STATE, upload=None):
    """Past the deadline with no answer: post LYLA's first pick."""
    now = now or dt.datetime.now()
    if not AUTOPOST:                       # nothing is ever posted unless you say so (post 1 / post all)
        return None
    data = load(path)
    if data.get("status") != "waiting" or not data.get("made"):
        return None
    if now < dt.datetime.fromisoformat(data["deadline"]):
        return None
    if POST_ALL:
        return choose_all(path, upload)
    return _post(data, data["made"][0], path, upload)


def due_today(today, last_iso):
    """Every EVERY days."""
    if not last_iso:
        return True
    return (today - dt.date.fromisoformat(last_iso)).days >= EVERY
