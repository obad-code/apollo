"""Q's fixes: Apollo's interface, looked at and improved a little every day.

Once a day, while the full display is up, Q takes one screenshot of it and
suggests three concrete improvements - in the look you like, which he learns
from what you send on and what you turn down. On the display's FIXES button:

    Send to Claude   files it as a GitHub issue for Claude to build (github_requests)
    Not my style     dropped, and remembered so he stops suggesting things like it
    Point at it      you click anything on the display and say what is wrong with it

Q never edits Apollo himself; Claude builds what you send, and update.bat brings it.
"""

import datetime as dt
import json
import logging
import os
import re
import threading
import time
import uuid

log = logging.getLogger("apollo.qfixes")

PATH = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Apollo", "q_fixes.json")
KEEP_TASTE = 30
_lock = threading.Lock()

LOOK = (
    "You are Q, the quartermaster of Apollo - a voice assistant whose full-screen display is in "
    "this screenshot. Suggest exactly three small, concrete improvements to this interface: layout, "
    "spacing, legibility, motion, colour, a missing affordance, something that looks broken. Each "
    "must be buildable in one sitting and point at a specific part of the screen. Follow the user's "
    "taste below - never suggest anything like what they turned down. Answer ONLY with JSON: "
    '[{"title": "under 70 chars", "area": "which part of the screen", "detail": "what to change '
    'and why, under 60 words"}]')


def load(path=PATH):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data, path=PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def taste(data):
    t = data.get("taste") or {}
    liked = "; ".join(t.get("liked", [])[-KEEP_TASTE:]) or "nothing yet"
    disliked = "; ".join(t.get("disliked", [])[-KEEP_TASTE:]) or "nothing yet"
    return f"They sent on: {liked}.\nThey turned down: {disliked}."


def _ask_vision(picture, prompt):
    import screen
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    last = None
    for model in screen.MODELS:
        try:
            out = client.models.generate_content(
                model=model, contents=[types.Part.from_bytes(data=picture, mime_type="image/jpeg"), prompt],
                config=types.GenerateContentConfig(system_instruction=LOOK, temperature=0.5))
            if out.text:
                return out.text
        except Exception as e:  # noqa: BLE001 - the next model may answer
            last = e
    raise RuntimeError(f"Q could not look: {last}")


def look(grab=None, ask=None, path=PATH, today=None):
    """Three new suggestions from a fresh look at the display. Returns them."""
    if grab is None:
        import screen
        grab = screen.capture
    ask = ask or _ask_vision
    with _lock:
        data = load(path)
    text = ask(grab(), "What the user likes and dislikes:\n" + taste(data))
    found = re.search(r"\[.*\]", text or "", re.S)
    rows = json.loads(found.group(0)) if found else []
    new = [{"id": uuid.uuid4().hex[:8], "title": str(r.get("title", ""))[:90], "area": str(r.get("area", ""))[:60],
            "detail": str(r.get("detail", ""))[:500], "status": "new", "at": time.time()}
           for r in rows if isinstance(r, dict) and r.get("title")][:3]
    with _lock:
        data = load(path)
        data["suggestions"] = (new + [s for s in data.get("suggestions", []) if s.get("status") != "new"])[:40]
        data["looked"] = (today or dt.date.today()).isoformat()
        save(data, path)
    return new


def due(today=None, path=PATH):
    return load(path).get("looked") != (today or dt.date.today()).isoformat()


def _remember(data, side, text):
    t = data.setdefault("taste", {"liked": [], "disliked": []})
    t.setdefault(side, []).append(text[:140])
    t[side] = t[side][-KEEP_TASTE:]


def send(sid, file_issue=None, path=PATH):
    """Send one suggestion to Claude as a GitHub issue."""
    if file_issue is None:
        import github_requests
        file_issue = github_requests.file_issue
    with _lock:
        data = load(path)
        s = next((s for s in data.get("suggestions", []) if s["id"] == sid), None)
        if s is None:
            return {"ok": False, "error": "That suggestion is gone."}
        body = (f"**Where:** {s['area']}\n\n{s['detail']}\n\n"
                f"_Suggested by Apollo's Q from a look at the display; the user sent it on._\n\n"
                f"The user's taste so far:\n{taste(data)}")
    made = file_issue(f"UI: {s['title']}", body)
    with _lock:
        data = load(path)
        for one in data.get("suggestions", []):
            if one["id"] == sid:
                one.update(status="sent", issue=made.get("url", ""))
                _remember(data, "liked", one["title"])
        save(data, path)
    return {"ok": True, "url": made.get("url", ""), "number": made.get("number")}


def no(sid, path=PATH):
    """Not my style: dropped, and remembered."""
    with _lock:
        data = load(path)
        for one in data.get("suggestions", []):
            if one["id"] == sid:
                one["status"] = "no"
                _remember(data, "disliked", f"{one['title']} ({one['detail'][:80]})")
        save(data, path)
    return {"ok": True}


def report(note, element, file_issue=None, path=PATH):
    """Something you pointed at on the display, and what is wrong with it - straight to Claude."""
    if file_issue is None:
        import github_requests
        file_issue = github_requests.file_issue
    note = " ".join(str(note or "").split())
    if not note:
        return {"ok": False, "error": "Say what is wrong with it."}
    el = element or {}
    body = (f"**What the user said:** {note}\n\n**What they pointed at on the display:**\n"
            f"- selector: `{el.get('selector', '')}`\n- text: {str(el.get('text', ''))[:200]}\n"
            f"- size: {el.get('size', '')}\n\n_Filed from the display's FIXES button._")
    made = file_issue(f"UI fix: {note[:60]}", body)
    with _lock:
        data = load(path)
        _remember(data, "liked", note)
        data.setdefault("reported", []).append({"note": note, "url": made.get("url", ""), "at": time.time()})
        data["reported"] = data["reported"][-40:]
        save(data, path)
    return {"ok": True, "url": made.get("url", ""), "number": made.get("number")}


def board(path=PATH):
    data = load(path)
    return {"suggestions": data.get("suggestions", [])[:12], "looked": data.get("looked", ""),
            "new": sum(1 for s in data.get("suggestions", []) if s.get("status") == "new")}
