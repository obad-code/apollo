"""Windows actions Claude can trigger via tool use: launch apps, open files
and folders.

Everything here returns a plain string describing what happened (or what
went wrong), meant to be fed back to Claude as a tool_result - it decides how
to phrase the spoken confirmation from there.
"""

import os
import shutil

# Common names -> what to hand to os.startfile (ShellExecute). Most resolve
# through the "App Paths" registry key the installer sets up, which is why a
# bare name like "chrome" works even though chrome.exe isn't on PATH.
# Protocol launches (the "...:" entries) are for apps that don't register an
# App Paths entry at all.
KNOWN_APPS = {
    "chrome": "chrome", "google chrome": "chrome",
    "firefox": "firefox", "mozilla firefox": "firefox",
    "edge": "msedge", "microsoft edge": "msedge",
    "notepad": "notepad",
    "spotify": "spotify:",
    "calculator": "calc", "calc": "calc",
    "explorer": "explorer", "file explorer": "explorer",
    "word": "winword", "microsoft word": "winword",
    "excel": "excel", "microsoft excel": "excel",
    "powerpoint": "powerpnt", "microsoft powerpoint": "powerpnt",
    "outlook": "outlook",
    "paint": "mspaint",
    "cmd": "cmd", "command prompt": "cmd",
    "powershell": "powershell",
    "terminal": "wt", "windows terminal": "wt",
    "settings": "ms-settings:",
    "task manager": "taskmgr",
    "control panel": "control",
    "vscode": "code", "vs code": "code", "visual studio code": "code",
}

USER_FOLDERS = ["Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos"]
MAX_SEARCH_DEPTH = 3


def _try_start(path_or_command):
    try:
        os.startfile(path_or_command)
        return True
    except OSError:
        return False


def _find_start_menu_shortcut(target):
    """Search Start Menu .lnk files for a name matching `target`."""
    roots = [
        os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"),
                      "Microsoft", "Windows", "Start Menu", "Programs"),
        os.path.join(os.environ.get("APPDATA", ""),
                      "Microsoft", "Windows", "Start Menu", "Programs"),
    ]
    target_l = target.strip().lower()
    best_partial = None

    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            for name in files:
                if not name.lower().endswith(".lnk"):
                    continue
                stem = name[:-4].lower()
                full = os.path.join(dirpath, name)
                if stem == target_l:
                    return full
                if best_partial is None and target_l in stem:
                    best_partial = full

    return best_partial


def open_app(target):
    """Launch an application by common name, PATH lookup, or Start Menu search."""
    key = target.strip().lower()
    tried = []

    if key in KNOWN_APPS:
        tried.append(KNOWN_APPS[key])
    tried.append(target)

    for candidate in tried:
        if _try_start(candidate):
            return f"Launched {target}."

    exe = shutil.which(target) or shutil.which(target + ".exe")
    if exe and _try_start(exe):
        return f"Launched {target}."

    shortcut = _find_start_menu_shortcut(target)
    if shortcut and _try_start(shortcut):
        return f"Launched {target}."

    return f"Failed: could not find an app called '{target}'."


def _known_folder(target):
    """Resolve 'Desktop', 'my Documents', 'Downloads folder' to the real path.

    Checked before any searching: these names are unambiguous, and a fuzzy
    search would happily match something like 'Telegram Desktop' instead.
    """
    key = target.strip().lower()
    for prefix in ("my ", "the "):
        key = key.removeprefix(prefix)
    key = key.removesuffix(" folder").removesuffix(" directory").strip()

    home = os.path.expanduser("~")
    if key in ("home", "user", "user folder"):
        return home

    for name in USER_FOLDERS:
        if key == name.lower():
            path = os.path.join(home, name)
            if os.path.isdir(path):
                return path
    return None


def _search_for(target_l, roots, want_folder):
    """Find a name under `roots`. An exact match anywhere beats a partial one."""
    best_partial = None

    for root in roots:
        if not os.path.isdir(root):
            continue
        base_depth = root.rstrip(os.sep).count(os.sep)
        for dirpath, dirnames, filenames in os.walk(root):
            if dirpath.rstrip(os.sep).count(os.sep) - base_depth >= MAX_SEARCH_DEPTH:
                dirnames[:] = []
                continue
            names = dirnames if want_folder else filenames
            for name in names:
                low = name.lower()
                if low == target_l or os.path.splitext(low)[0] == target_l:
                    return os.path.join(dirpath, name)
                if best_partial is None and target_l in low:
                    best_partial = os.path.join(dirpath, name)

    return best_partial


def open_path(target, want_folder=False):
    """Open a file or folder by exact path, or by searching common user folders."""
    if want_folder:
        known = _known_folder(target)
        if known and _try_start(known):
            return f"Opened {target}."

    expanded = os.path.expanduser(os.path.expandvars(target))
    if os.path.exists(expanded):
        kind_ok = os.path.isdir(expanded) if want_folder else True
        if kind_ok and _try_start(expanded):
            return f"Opened {target}."

    home = os.path.expanduser("~")
    roots = [os.path.join(home, name) for name in USER_FOLDERS] + [home]

    match = _search_for(target.strip().lower(), roots, want_folder)
    if match and _try_start(match):
        return f"Opened {target}."

    kind = "folder" if want_folder else "file"
    return f"Failed: could not find a {kind} called '{target}'."


def execute(action, target):
    """Dispatch a tool call from Claude. Always returns a short status string."""
    if not target or not target.strip():
        return "Failed: no target was given."

    if action == "open_app":
        return open_app(target)
    if action == "open_folder":
        return open_path(target, want_folder=True)
    return open_path(target, want_folder=False)
