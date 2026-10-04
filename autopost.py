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

COUNT = max(1, min(5, int(os.environ.get("SHORTS_COUNT") or 3)))
EVERY = max(1, int(os.environ.get("SHORTS_EVERY") or 1))
WAIT_HOURS = float(os.environ.get("SHORTS_WAIT_HOURS") or 3)
GEO = os.environ.get("SHORTS_GEO") or "US"
STATE = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                     "Apollo", "shorts_pending.json")

PICK_SYSTEM = (
    "You pick topics for a faceless stick-man YouTube Shorts channel that wants views. "
    "Given today's trending searches, choose topics that are curious, shareable and "
    "evergreen-friendly: a surprising fact or a gripping story tied to a trend. Never "
    "politics, tragedy, real private people, anything indecent or against Islam. "
    'Answer ONLY with JSON: [{"kind": "fact" or "story", "topic": "...", "why": "..."}], '
    "best first.")


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
        import lyla
        text, _ = lyla.think(prompt, PICK_SYSTEM)
    else:
        text = think(prompt)
    m = re.search(r"\[.*\]", text or "", re.S)
    picks = []
    try:
        picks = [p for p in json.loads(m.group(0)) if str(p.get("topic", "")).strip()] if m else []
    except ValueError:
        pass
    while len(picks) < count:
        picks.append({"kind": "fact" if len(picks) % 2 == 0 else "story", "topic": ""})
    return [{"kind": p.get("kind") if p.get("kind") in ("fact", "story") else "fact",
             "topic": str(p.get("topic", ""))[:120]} for p in picks[:count]]


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
    lines = [f"{i + 1}. {m['title']}" for i, m in enumerate(made)]
    return ("Shorts ready - which one should I post? " + " | ".join(lines)
            + f". If you don't answer in {WAIT_HOURS:g} hours I'll post number 1.")


def choose(number, path=STATE, upload=None):
    """Post the Short you picked (1-based). 0 = post nothing today."""
    data = load(path)
    if data.get("status") != "waiting":
        return {"ok": False, "error": "No Shorts are waiting for a pick."}
    if number == 0:
        data["status"] = "skipped"
        save(data, path)
        return {"ok": True, "result": "Nothing posted today."}
    made = data.get("made", [])
    if not 1 <= number <= len(made):
        return {"ok": False, "error": f"Pick 1 to {len(made)}."}
    return _post(data, made[number - 1], path, upload)


def _post(data, item, path, upload):
    if upload is None:
        import youtube_upload
        upload = youtube_upload.upload
    try:
        link = upload(item["path"], item.get("notes", ""))
    except Exception as e:  # noqa: BLE001
        data["status"] = "failed"
        data["error"] = str(e) or type(e).__name__
        save(data, path)
        log.warning("short upload failed: %s", e)
        return {"ok": False, "error": data["error"]}
    data.update(status="posted", posted=item["title"], link=link)
    save(data, path)
    return {"ok": True, "result": f"Posted: {item['title']}", "link": link}


def tick(now=None, path=STATE, upload=None):
    """Past the deadline with no answer: post LYLA's first pick."""
    now = now or dt.datetime.now()
    data = load(path)
    if data.get("status") != "waiting" or not data.get("made"):
        return None
    if now < dt.datetime.fromisoformat(data["deadline"]):
        return None
    return _post(data, data["made"][0], path, upload)


def due_today(today, last_iso):
    """Every EVERY days."""
    if not last_iso:
        return True
    return (today - dt.date.fromisoformat(last_iso)).days >= EVERY
