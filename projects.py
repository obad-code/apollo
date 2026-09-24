"""Your projects, for the display's Projects tab: the Claude Code sessions
you have been working in, the git folders on this PC, and your GitHub repos.

Everything is read, never changed. Claude Code keeps each session as a JSON
lines file under ~/.claude/projects - some of them tens of megabytes - so
only the ends of a file are read: its title (the one you gave it, or the one
it was given) and the last thing you asked it are written again and again
all the way through. GitHub is asked at most every half an hour, with a
token only if you have saved one as GITHUB_TOKEN; without it, it lists your
public repos.
"""

import datetime
import json
import logging
import os
import re
import subprocess
import time
import urllib.request

log = logging.getLogger("apollo.projects")

ROOT = os.path.join(os.path.expanduser("~"), ".claude", "projects")
SKIP = ("claude-mem-observer",)          # another tool's sessions, not yours
HOME = os.path.expanduser("~")
FOLDER_ROOTS = [os.path.join(HOME, "Desktop"), os.path.join(HOME, "Documents"),
                os.path.join(HOME, "source", "repos"), os.path.join(HOME, "Projects"),
                os.path.join(HOME, "dev"), os.path.join(HOME, "code")]
GITHUB_EVERY = 1800
MOST = 8
CHUNK = 256 * 1024


def _saved(name):
    """A variable from the environment, or the one `setx` saved."""
    value = os.environ.get(name)
    if value:
        return value.strip()
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as handle:
            return str(winreg.QueryValueEx(handle, name)[0]).strip() or None
    except OSError:
        return None


# -- Claude Code -------------------------------------------------------------------

def _ends(path):
    """The last and the first CHUNK bytes of a file, as text, last first."""
    size = os.path.getsize(path)
    with open(path, "rb") as handle:
        handle.seek(max(0, size - CHUNK))
        tail = handle.read().decode("utf-8", "replace")
        head = ""
        if size > CHUNK:
            handle.seek(0)
            head = handle.read(CHUNK).decode("utf-8", "replace")
    return tail, head


def _session(path):
    custom = ai = prompt = cwd = None
    for text in _ends(path):
        for line in reversed(text.splitlines()):
            if not line.startswith("{"):
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict):
                continue
            custom = custom or entry.get("customTitle")
            ai = ai or entry.get("aiTitle")
            prompt = prompt or entry.get("lastPrompt")
            cwd = cwd or entry.get("cwd")
        if custom and prompt and cwd:
            break
    title = custom or ai or prompt
    if not title:
        return None
    folder = os.path.basename(os.path.dirname(path))
    project = os.path.basename(str(cwd).rstrip("\\/")) if cwd else folder.split("-")[-1]
    return {"id": os.path.splitext(os.path.basename(path))[0], "title": str(title)[:120],
            "project": project, "prompt": str(prompt or "")[:160],
            "when": os.path.getmtime(path)}


def claude_sessions(root=None, limit=MOST):
    root = root or ROOT
    found = []
    try:
        for folder in os.listdir(root):
            if any(s in folder for s in SKIP):
                continue
            base = os.path.join(root, folder)
            if not os.path.isdir(base):
                continue
            for name in os.listdir(base):
                if name.endswith(".jsonl"):
                    path = os.path.join(base, name)
                    found.append((os.path.getmtime(path), path))
    except OSError:
        return []
    sessions = []
    for _, path in sorted(found, reverse=True):
        try:
            session = _session(path)
        except (OSError, ValueError):
            continue
        if session:
            sessions.append(session)
        if len(sessions) >= limit:
            break
    return sessions


# -- folders on this PC ---------------------------------------------------------------

def _git(path, *args):
    out = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=3,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return out.stdout.strip() if out.returncode == 0 else ""


def _branch(path):
    try:
        with open(os.path.join(path, ".git", "HEAD"), encoding="utf-8") as handle:
            head = handle.read().strip()
    except OSError:
        return ""
    return head.rsplit("/", 1)[-1] if head.startswith("ref:") else head[:7]


def _repos_under(root, depth=2):
    try:
        entries = [e for e in os.scandir(root) if e.is_dir() and not e.name.startswith(".")
                   and e.name not in ("node_modules", "venv")]
    except OSError:
        return
    for entry in entries[:200]:
        if os.path.isdir(os.path.join(entry.path, ".git")):
            yield entry.path
        elif depth > 1:
            yield from _repos_under(entry.path, depth - 1)


def folders(roots=None, limit=MOST):
    found = []
    for root in roots or FOLDER_ROOTS:
        for path in _repos_under(root):
            try:
                last = _git(path, "log", "-1", "--format=%ct%x09%s")
            except (OSError, subprocess.SubprocessError):
                last = ""
            when, _, subject = last.partition("\t")
            found.append({"name": os.path.basename(path), "path": path, "branch": _branch(path),
                          "last": subject[:120], "when": int(when) if when.isdigit() else 0})
    found.sort(key=lambda f: -f["when"])
    return found[:limit]


def github_user(found=None):
    """GITHUB_USER, or whoever owns the GitHub remotes of the folders here."""
    user = _saved("GITHUB_USER")
    if user:
        return user
    owners = []
    for folder in found or []:
        try:
            url = _git(folder["path"], "config", "--get", "remote.origin.url")
        except (OSError, subprocess.SubprocessError):
            continue
        match = re.search(r"github\.com[:/]([^/]+)/", url)
        if match:
            owners.append(match.group(1))
    return max(set(owners), key=owners.count) if owners else None


# -- GitHub ------------------------------------------------------------------------

def _fetch_json(url, token=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "Apollo"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=8) as r:
        return json.load(r)


def github_repos(user, token=None, fetch=_fetch_json, limit=MOST):
    url = ("https://api.github.com/user/repos?sort=pushed&per_page=20" if token else
           f"https://api.github.com/users/{user}/repos?sort=pushed&per_page=20")
    try:
        data = fetch(url, token)
    except Exception as e:  # noqa: BLE001 - an empty list, not an error on screen
        log.debug("GitHub did not answer: %s", type(e).__name__)
        return []
    repos = []
    for repo in data if isinstance(data, list) else []:
        link = str(repo.get("html_url") or "")
        try:
            when = datetime.datetime.fromisoformat(
                str(repo.get("pushed_at")).replace("Z", "+00:00")).timestamp()
        except ValueError:
            when = 0
        repos.append({"name": repo.get("name", ""), "private": bool(repo.get("private")),
                      "link": link if link.startswith("https://github.com/") else "",
                      "about": str(repo.get("description") or "")[:120], "when": when})
    repos.sort(key=lambda r: -r["when"])
    return repos[:limit]


_github = (0.0, [])
_last_folders = []       # what the display was last shown, and so may open


def open_folder_with(path):
    """In VS Code if it is here, else in Explorer."""
    import shutil
    code = shutil.which("code")
    if code:
        subprocess.Popen([code, path], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        os.startfile(path)  # noqa: S606 - a folder this module listed itself


def open_folder(path):
    """Open one of the folders the display was shown - and nothing else: the
    page is handed feed data too, and must not get to open any path at all."""
    if path not in _last_folders:
        return False
    open_folder_with(path)
    return True


def snapshot():
    """The three lists, for the display."""
    global _github, _last_folders
    found = folders()
    _last_folders = [f["path"] for f in found]
    now = time.time()
    if now - _github[0] > GITHUB_EVERY:
        user = github_user(found)
        _github = (now, github_repos(user, _saved("GITHUB_TOKEN")) if user else [])
    return {"sessions": claude_sessions(), "folders": found, "repos": _github[1]}
