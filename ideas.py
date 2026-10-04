"""Ideas for new projects, said to Apollo and kept for later.

"Idea: a Discord bot for the clan" - kept in %LOCALAPPDATA%\\Apollo\\ideas.json,
newest first, on the display's Ideas tab beside your reminders, and read
back when you ask. Nothing here raises.
"""

import json
import logging
import os
import threading
import time
import uuid

import feeds
import journal

log = logging.getLogger("apollo.ideas")

PATH = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                    "Apollo", "ideas.json")
MOST = 100

_lock = threading.Lock()


def _read():
    try:
        with open(PATH, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    return [i for i in data if isinstance(i, dict) and i.get("text")] if isinstance(data, list) else []


def _write(items):
    try:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        temporary = PATH + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(items, handle, ensure_ascii=False)
        os.replace(temporary, PATH)
    except OSError as e:
        log.info("could not save the ideas: %s", e)


def all():  # noqa: A001 - read as ideas.all()
    """Every idea, newest first, with how long ago it was had."""
    now = time.time()
    with _lock:
        items = _read()
    return [dict(i, age=feeds.age_words(now - i.get("at", now)))
            for i in sorted(items, key=lambda i: -i.get("at", 0))]


def add(text):
    idea = {"id": uuid.uuid4().hex[:10], "text": str(text).strip()[:400], "at": time.time()}
    with _lock:
        items = _read()
        items.append(idea)
        _write(items[-MOST:])
    journal.write("idea", text=idea["text"])
    return idea


def remove(idea_id):
    with _lock:
        items = _read()
        kept = [i for i in items if i.get("id") != idea_id]
        if len(kept) == len(items):
            return False
        _write(kept)
    return True


# -- THEIA's read of each idea ----------------------------------------------------------------

THEIA_TASK = ("Analyse this idea the user saved, properly: what it really is, how it could work, "
              "what it needs, the risks, and the best way to do it - concrete first steps. Their idea: {text}")


def send_to_theia(idea, take=None):
    """Hand a new idea to THEIA, quietly: no announcement when she is done - it waits on the idea."""
    try:
        if take is None:
            if not ((os.environ.get("GEMINI_CREW_KEY") or os.environ.get("GEMINI_API_KEY")) or os.environ.get("ANTHROPIC_API_KEY")):
                return False                     # nothing for her to think with
            import crew
            take = crew.desk("THEIA").take
        take(THEIA_TASK.format(text=idea["text"]), idea=idea["id"], routine=True)
        return True
    except Exception:  # noqa: BLE001 - the idea is kept either way
        log.info("idea not sent to THEIA", exc_info=True)
        return False


def attach(idea_id, summary, report):
    """THEIA's analysis, kept on the idea itself."""
    with _lock:
        items = _read()
        for i in items:
            if i.get("id") == idea_id:
                i["theia"] = {"summary": str(summary)[:600], "report": str(report)[:12000],
                              "at": time.time(), "seen": False}
                _write(items)
                return True
    return False


def unseen():
    """Ideas THEIA has analysed that you have not looked at yet."""
    with _lock:
        return [i for i in _read() if (i.get("theia") or {}).get("seen") is False]


def mark_seen():
    with _lock:
        items = _read()
        for i in items:
            if i.get("theia"):
                i["theia"]["seen"] = True
        _write(items)
    return True


def waiting():
    """Ideas THEIA has not analysed yet (for a catch-up at start)."""
    with _lock:
        return [i for i in _read() if not i.get("theia")]


# -- talking an idea through with THEIA -------------------------------------------------------

CHAT = (
    "You are THEIA, the user's analyst, talking an idea of theirs through with them. You have "
    "already analysed it (below). Answer what they ask - think with them, be concrete and honest, "
    "push back when something is weak, suggest the next step. Short: a few sentences or a few "
    "bullets. Reply in the language and dialect they write in (Gulf Arabic if Arabic).")


def get(idea_id):
    with _lock:
        return next((i for i in _read() if i.get("id") == idea_id), None)


def _save_idea(idea):
    with _lock:
        items = _read()
        for n, i in enumerate(items):
            if i.get("id") == idea["id"]:
                items[n] = idea
                _write(items)
                return True
    return False


def analyse_now(idea_id, think=None):
    """THEIA's read, now, while you wait - for an idea she has not got to yet."""
    idea = get(idea_id)
    if idea is None:
        raise ValueError("That idea is gone.")
    if think is None:
        import crew
        think = lambda prompt: crew.thinker(crew.THEIA_SYSTEM, True)(prompt)[0]  # noqa: E731
    import lyla
    summary, report = lyla.split(think(THEIA_TASK.format(text=idea["text"])))
    attach(idea_id, summary, report)
    return get(idea_id)


def chat(idea_id, message, think=None):
    """One turn of your conversation with THEIA about an idea. Returns her reply."""
    message = " ".join(str(message or "").split())[:2000]
    idea = get(idea_id)
    if idea is None or not message:
        raise ValueError("Nothing to answer.")
    talk = idea.get("chat", [])[-16:]
    read = idea.get("theia") or {}
    prompt = (f"Their idea: {idea['text']}\n\nYour analysis of it:\n{read.get('summary', '')}\n{read.get('report', '')[:6000]}\n\n"
              "The conversation so far:\n" + "\n".join(f"{'Them' if m['who'] == 'you' else 'You'}: {m['text']}" for m in talk)
              + f"\n\nThem now: {message}")
    if think is None:
        import lyla
        think = lambda p: lyla.ask_gemini(p, CHAT)  # noqa: E731
    reply = (think(prompt) or "").strip() or "I need a moment - ask me again."
    now = time.time()
    idea = get(idea_id) or idea
    idea["chat"] = (idea.get("chat", []) + [{"who": "you", "text": message, "at": now},
                                            {"who": "theia", "text": reply[:4000], "at": now}])[-60:]
    _save_idea(idea)
    return reply
