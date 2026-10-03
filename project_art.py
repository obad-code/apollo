"""A small picture for each project, drawn once by Gemini and kept.

The projects page shows each project as a card; a card with a picture of
its own reads at a glance. Pictures are drawn in the background, one at a
time, the first time a project is seen, and saved under ui/full/art/ so the
page can show them by name. A project that has one is never drawn again.
"""

import hashlib
import logging
import os
import re
import threading

import images

log = logging.getLogger("apollo.project_art")

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "ui", "full", "art")
STYLE = ("A minimal, calm illustration for a software project card: one simple "
         "central object on a dark charcoal background, soft studio light, a single "
         "accent colour, no text, no letters, no logos. The project: ")

_queue = []
_lock = threading.Lock()
_busy = False


def slug(name):
    base = re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")[:40] or "project"
    return f"{base}-{hashlib.sha1(str(name).encode()).hexdigest()[:6]}"


def path_of(name):
    for ext in (".png", ".jpg", ".webp"):
        full = os.path.join(ART, slug(name) + ext)
        if os.path.exists(full):
            return full
    return None


def src(name):
    """The page's address for the project's picture, or "" if it has none yet."""
    found = path_of(name)
    return f"art/{os.path.basename(found)}" if found else ""


def want(name, about=""):
    """Ask for a picture of `name` if it has none; drawn in the background."""
    if not os.environ.get("GEMINI_API_KEY") or path_of(name):
        return
    global _busy
    with _lock:
        if any(n == name for n, _ in _queue):
            return
        _queue.append((name, about))
        if _busy:
            return
        _busy = True
    threading.Thread(target=_drain, daemon=True, name="project-art").start()


def _drain():
    global _busy
    while True:
        with _lock:
            if not _queue:
                _busy = False
                return
            name, about = _queue.pop(0)
        try:
            made = images.make(STYLE + f"{name}. {about}".strip(), save_to=ART)
            ext = os.path.splitext(made["path"])[1] or ".png"
            os.replace(made["path"], os.path.join(ART, slug(name) + ext))
        except Exception as e:  # noqa: BLE001 - a card without a picture is fine
            log.info("no picture for %s: %s", name, e)


def decorate(snapshot):
    """Add `art` to every project in a projects snapshot, asking for any missing."""
    for group, about_key in (("sessions", "prompt"), ("folders", "last"), ("repos", "about")):
        for item in snapshot.get(group, []) or []:
            name = item.get("title") or item.get("name") or item.get("project") or ""
            item["art"] = src(name)
            if not item["art"]:
                want(name, item.get(about_key) or "")
    return snapshot
