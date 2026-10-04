"""Your projects - the ones you add yourself (Apollo, Nolock…), each with a board.

A project is a name, a line about it, and a board: a free canvas like Apple's
Freeform - pen strokes, lines and arrows, sticky notes, text, pictures and
files - opened full screen from the project. THEIA looks after them: when a
board changes she looks at it (a picture of the board, its text, the project)
and leaves her notes - what she sees, what to do next, what is missing - and
the project wears her mark until you have read them.

Everything is kept on this PC under %LOCALAPPDATA%\\Apollo\\projects:
index.json (the list), boards\\<id>.json (each board), files\\<id>\\ (files
dropped on a board).
"""

import base64
import json
import logging
import os
import re
import threading
import time
import uuid

log = logging.getLogger("apollo.myprojects")

ROOT = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Apollo", "projects")
MAX_BOARD = 40 * 1024 * 1024
_lock = threading.Lock()


def _p(*parts, root=None):
    return os.path.join(root or ROOT, *parts)


def _read(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def all(root=None):  # noqa: A001 - read as myprojects.all()
    """Every project, most recently touched first."""
    items = _read(_p("index.json", root=root), [])
    return sorted([i for i in items if isinstance(i, dict)], key=lambda i: -i.get("touched", 0))


def get(pid, root=None):
    return next((p for p in all(root) if p["id"] == pid), None)


def add(name, about="", root=None):
    name = " ".join(str(name or "").split())[:80]
    if not name:
        raise ValueError("A project needs a name.")
    with _lock:
        items = _read(_p("index.json", root=root), [])
        same = next((p for p in items if p["name"].lower() == name.lower()), None)
        if same:
            return same
        now = time.time()
        project = {"id": uuid.uuid4().hex[:10], "name": name, "about": str(about or "").strip()[:400],
                   "created": now, "touched": now, "board_at": 0, "theia": None}
        items.append(project)
        _write(_p("index.json", root=root), items)
    return project


def update(pid, root=None, **fields):
    with _lock:
        items = _read(_p("index.json", root=root), [])
        for p in items:
            if p["id"] == pid:
                p.update({k: v for k, v in fields.items() if k in ("name", "about", "theia", "board_at", "preview", "reviewed_at")})
                p["touched"] = time.time()
                _write(_p("index.json", root=root), items)
                return p
    return None


def remove(pid, root=None):
    with _lock:
        items = _read(_p("index.json", root=root), [])
        kept = [p for p in items if p["id"] != pid]
        _write(_p("index.json", root=root), kept)
    try:
        os.remove(_p("boards", f"{pid}.json", root=root))
    except OSError:
        pass
    return len(kept) != len(items)


def board(pid, root=None):
    return _read(_p("boards", f"{pid}.json", root=root), {"items": [], "view": {"x": 0, "y": 0, "k": 1}})


def save_board(pid, data, preview="", root=None):
    """The board as the page has it, and a small picture of it for the project card."""
    text = json.dumps(data, ensure_ascii=False)
    if len(text) > MAX_BOARD:
        raise ValueError("The board is too big to keep - take a few pictures off it.")
    _write(_p("boards", f"{pid}.json", root=root), data)
    fields = {"board_at": time.time()}
    if preview.startswith("data:image/"):
        fields["preview"] = preview[:400_000]
    update(pid, root=root, **fields)
    return True


def keep_file(pid, name, data_url, root=None):
    """A file dropped on a board, kept beside it. Returns its path."""
    name = re.sub(r"[^\w.\- ()؀-ۿ]+", "_", os.path.basename(str(name or "file")))[:80] or "file"
    raw = base64.b64decode(str(data_url).split(",", 1)[-1])
    folder = _p("files", pid, root=root)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{int(time.time())}-{name}")
    with open(path, "wb") as f:
        f.write(raw)
    return path


def board_text(data):
    """What is written on a board, for THEIA."""
    out = []
    for item in data.get("items", []):
        if item.get("type") in ("note", "text") and str(item.get("text", "")).strip():
            out.append(f"- {item['type']}: {item['text'].strip()[:400]}")
        elif item.get("type") == "file":
            out.append(f"- file: {item.get('name', '')}")
        elif item.get("type") == "image":
            out.append("- a picture")
    return "\n".join(out[:120])


# -- THEIA -----------------------------------------------------------------------------------

REVIEW = (
    "You are THEIA, the analyst in charge of the user's projects. You are shown a picture of one "
    "project's planning board and what is written on it. Help them move it forward. Answer in the "
    "language they write in (Gulf Arabic if Arabic). Exactly this shape:\n"
    "SUMMARY: one sentence - where the project stands, as you read the board.\n"
    "WHAT I SEE: two or three short bullets.\n"
    "NEXT: the three most useful next steps, concrete.\n"
    "MISSING: what the plan does not answer yet.\n"
    "QUESTION: one question for them that would unblock the most.")


def _vision(picture_png, prompt):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=(os.environ.get("GEMINI_CREW_KEY") or os.environ.get("GEMINI_API_KEY")))
    parts = ([types.Part.from_bytes(data=picture_png, mime_type="image/png")] if picture_png else []) + [prompt]
    last = None
    for model in ("gemini-flash-latest", "gemini-2.5-flash"):
        try:
            out = client.models.generate_content(model=model, contents=parts,
                                                 config=types.GenerateContentConfig(system_instruction=REVIEW, temperature=0.4))
            if out.text:
                return out.text
        except Exception as e:  # noqa: BLE001 - the next model may answer
            last = e
    raise RuntimeError(f"THEIA could not look at the board: {last}")


def review(pid, picture="", ask=None, root=None):
    """THEIA's notes on one project's board. `picture` is a PNG data URL of the board."""
    project = get(pid, root)
    if project is None:
        raise ValueError("No such project.")
    png = base64.b64decode(picture.split(",", 1)[-1]) if str(picture).startswith("data:image/png") else b""
    prompt = (f"Project: {project['name']}\nAbout it: {project.get('about') or '(not said)'}\n"
              f"Written on the board:\n{board_text(board(pid, root)) or '(nothing written yet)'}")
    text = (ask or _vision)(png, prompt).strip()
    found = re.search(r"SUMMARY:\s*(.+)", text)
    notes = {"summary": (found.group(1).strip() if found else text.splitlines()[0])[:300],
             "notes": text[:6000], "at": time.time(), "seen": False}
    update(pid, root=root, theia=notes, reviewed_at=time.time())
    return notes


def seen(pid, root=None):
    p = get(pid, root)
    if p and p.get("theia"):
        p["theia"]["seen"] = True
        update(pid, root=root, theia=p["theia"])
    return True


def snapshot(root=None):
    """The list, for the display (boards and big previews are fetched when opened)."""
    return {"mine": [{k: p.get(k) for k in ("id", "name", "about", "created", "touched", "board_at", "theia", "preview")}
                     for p in all(root)]}
