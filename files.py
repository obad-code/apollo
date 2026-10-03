"""Apollo's own folder: files he writes for you, and the problem log.

Asked to "make a file and write X in it", Apollo used to have no way to do
it except open Notepad and type - through `type_text`, into whatever window
had focus, while you were still holding Ctrl+Alt. That is where the
`dddddddd` came from: a keyboard injected into the wrong place. Writing a
file is not a keyboard job. This module writes it directly.

Every file lives under one folder, Documents\\Apollo, and nowhere else: a
name from the model is a name inside that folder, never a path. Text only,
UTF-8, so Arabic is kept as Arabic.

The problem log (PROBLEMS) is the file you asked for: "if I tell you about
any problem, write it down". `log_problem` appends a dated line to it, and
the same problem also goes to the System panel's issues.
"""

import datetime
import logging
import os
import re
import threading

log = logging.getLogger("apollo.files")

TEXT_TYPES = (".txt", ".md", ".csv", ".json", ".log", ".html", ".py", ".js", ".css")
LARGEST = 200_000          # characters one write may carry
READ_MOST = 20_000         # characters read back to the model
PROBLEMS = "Apollo problems.md"

_lock = threading.Lock()


def root():
    """Documents\\Apollo - where OneDrive keeps Documents, if it does."""
    home = os.path.expanduser("~")
    for documents in (os.path.join(os.environ.get("OneDrive", ""), "Documents"),
                      os.path.join(home, "Documents")):
        if documents and os.path.isdir(documents):
            return os.path.join(documents, "Apollo")
    return os.path.join(home, "Apollo")


def safe_name(name):
    """A file name inside Apollo's folder, or ValueError.

    Folders below it are allowed ("notes/today.md"), climbing out is not, and
    a name with no type of its own becomes a .txt.
    """
    raw = str(name or "").strip().replace("\\", "/")
    parts = [p for p in raw.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        raise ValueError("That is not a file name I can use.")
    cleaned = []
    for part in parts:
        part = re.sub(r'[<>:"|?*\x00-\x1f]', "", part).strip(" .")
        if not part:
            raise ValueError("That is not a file name I can use.")
        cleaned.append(part[:120])
    stem, ext = os.path.splitext(cleaned[-1])
    if not ext:
        cleaned[-1] = stem + ".txt"
    elif ext.lower() not in TEXT_TYPES:
        raise ValueError(f"I only write text files ({', '.join(TEXT_TYPES)}).")
    return os.path.join(*cleaned)


def path_of(name, base=None):
    base = base or root()
    full = os.path.normpath(os.path.join(base, safe_name(name)))
    if os.path.commonpath([full, os.path.normpath(base)]) != os.path.normpath(base):
        raise ValueError("That is outside Apollo's folder.")
    return full


def write(name, text, append=False, base=None):
    """Write (or add to) a file. Returns {path, chars, appended}."""
    text = str(text or "")
    if len(text) > LARGEST:
        raise ValueError(f"That is too long to write in one go ({len(text)} characters).")
    full = path_of(name, base)
    with _lock:
        os.makedirs(os.path.dirname(full), exist_ok=True)
        if append and os.path.exists(full) and text and not text.startswith("\n"):
            with open(full, "rb") as handle:
                handle.seek(0, os.SEEK_END)
                if handle.tell():
                    handle.seek(-1, os.SEEK_END)
                    if handle.read(1) != b"\n":
                        text = "\n" + text
        with open(full, "a" if append else "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
    return {"path": full, "chars": len(text), "appended": bool(append)}


def read(name, base=None):
    full = path_of(name, base)
    with open(full, encoding="utf-8", errors="replace") as handle:
        text = handle.read(READ_MOST + 1)
    return {"path": full, "text": text[:READ_MOST], "cut": len(text) > READ_MOST}


def listing(base=None):
    """The files in Apollo's folder, newest first: (name, size, modified)."""
    base = base or root()
    found = []
    for dirpath, _dirs, names in os.walk(base):
        for name in names:
            full = os.path.join(dirpath, name)
            try:
                stat = os.stat(full)
            except OSError:
                continue
            found.append((os.path.relpath(full, base), stat.st_size, stat.st_mtime))
    return sorted(found, key=lambda f: -f[2])


def log_problem(problem, base=None, now=None):
    """Append one problem to the problem log, dated. Returns the write result."""
    problem = " ".join(str(problem or "").split())
    if not problem:
        raise ValueError("There was no problem to write down.")
    now = now or datetime.datetime.now()
    full = path_of(PROBLEMS, base)
    header = "" if os.path.exists(full) else "# Apollo problems\n\nWhat went wrong, as you told Apollo.\n\n"
    return write(PROBLEMS, f"{header}- [ ] {now:%Y-%m-%d %H:%M} — {problem}\n",
                 append=True, base=base)
