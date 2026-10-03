"""Windows actions Apollo can take for you: launch and close apps, open files,
folders and websites, and control the keyboard, media, volume, windows and
power.

Everything here returns a plain string (or, for volume, a dict) describing
what happened or what went wrong. `tools.run` hands it back to whichever model
asked - Gemini or Claude - and the model phrases the spoken confirmation.
"""

import ctypes
import os
import re
import shutil
import subprocess
import time
import urllib.parse
from ctypes import wintypes

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
    """Switch to an app that is already open, or launch it.

    An app with a window already on screen is brought forward instead of
    started again - "open Spotify" means "show me Spotify", not "start a
    second one". Otherwise: known name, PATH lookup, then Start Menu search.
    """
    running = find_windows(target)
    if running:
        _focus(running[0][0])
        return f"Switched to {target}."

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


# --- websites ---------------------------------------------------------------

KNOWN_SITES = {
    "youtube": "https://www.youtube.com", "gmail": "https://mail.google.com",
    "google": "https://www.google.com", "github": "https://github.com",
    "tradingview": "https://www.tradingview.com", "netflix": "https://www.netflix.com",
    "x": "https://x.com", "twitter": "https://x.com", "reddit": "https://www.reddit.com",
    "chatgpt": "https://chatgpt.com", "claude": "https://claude.ai",
    "instagram": "https://www.instagram.com", "whatsapp": "https://web.whatsapp.com",
    "spotify web": "https://open.spotify.com", "amazon": "https://www.amazon.com",
    "twitch": "https://www.twitch.tv", "discord web": "https://discord.com/app",
    "truth social": "https://truthsocial.com", "yahoo finance": "https://finance.yahoo.com",
    "playstation store": "https://store.playstation.com", "rockstar": "https://www.rockstargames.com",
}


def resolve_url(site):
    """A site name, domain or URL -> an https URL. Never anything but http(s)."""
    raw = (site or "").strip()
    key = raw.lower()
    for prefix in ("the ", "open "):
        key = key.removeprefix(prefix)
    for suffix in (" website", " site", " dot com", " homepage"):
        key = key.removesuffix(suffix)
    key = key.strip()
    if key in KNOWN_SITES:
        return KNOWN_SITES[key]
    if re.match(r"^https?://\S+$", raw, re.I):
        return raw
    if re.fullmatch(r"[\w-]+(\.[\w-]+)+(/\S*)?", key):
        return "https://" + key
    return "https://www.google.com/search?q=" + urllib.parse.quote_plus(raw)


def open_url(site):
    url = resolve_url(site)
    if not _try_start(url):
        return f"Failed: could not open {url}."
    return f"Opened {url}."


# --- the keyboard -----------------------------------------------------------
#
# Everything goes through SendInput, which injects into whatever window has
# focus - and that is always yours, because Apollo never takes focus.

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
MAX_TYPE = 2000

MODIFIERS = {"ctrl": 0x11, "control": 0x11, "shift": 0x10, "alt": 0x12,
             "win": 0x5B, "windows": 0x5B, "super": 0x5B}
NAMED_KEYS = {
    "enter": 0x0D, "return": 0x0D, "esc": 0x1B, "escape": 0x1B, "tab": 0x09,
    "space": 0x20, "backspace": 0x08, "delete": 0x2E, "del": 0x2E, "insert": 0x2D,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "page up": 0x21, "pagedown": 0x22,
    "page down": 0x22, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "printscreen": 0x2C, "print screen": 0x2C, "capslock": 0x14, "caps lock": 0x14,
    "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD, ";": 0xBA, "'": 0xDE,
    ",": 0xBC, ".": 0xBE, "/": 0xBF, "\\": 0xDC,
}
EXTENDED = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x5B}


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


def _key(vk=0, scan=0, flags=0):
    event = INPUT()
    event.type = INPUT_KEYBOARD
    if vk in EXTENDED:
        flags |= KEYEVENTF_EXTENDEDKEY
    event.u.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
    return event


def _send(events):
    """The one place that touches the real keyboard."""
    array = (INPUT * len(events))(*events)
    return ctypes.windll.user32.SendInput(len(events), array, ctypes.sizeof(INPUT))


def parse_chord(keys):
    """"ctrl+shift+t" -> [VK_CONTROL, VK_SHIFT, 'T']. ValueError on a key it doesn't know."""
    parts = [p.strip().lower() for p in re.split(r"\s*\+\s*", (keys or "").strip()) if p.strip()]
    if not parts:
        raise ValueError("No keys were given.")
    vks = []
    for part in parts:
        if part in MODIFIERS:
            vks.append(MODIFIERS[part])
        elif part in NAMED_KEYS:
            vks.append(NAMED_KEYS[part])
        elif re.fullmatch(r"f([1-9]|1\d|2[0-4])", part):
            vks.append(0x6F + int(part[1:]))
        elif len(part) == 1 and part.isascii() and part.isalnum():
            vks.append(ord(part.upper()))
        else:
            raise ValueError(f"I don't know the key '{part}'.")
    return vks


def _chord_events(vks):
    return [_key(vk) for vk in vks] + [_key(vk, flags=KEYEVENTF_KEYUP) for vk in reversed(vks)]


def press_keys(keys):
    try:
        vks = parse_chord(keys)
    except ValueError as e:
        return f"Failed: {e}"
    if {0x11, 0x12, 0x2E} <= set(vks):
        return "Failed: Windows doesn't let any program press Ctrl+Alt+Delete."
    _send(_chord_events(vks))
    return f"Pressed {keys}."


def _utf16_units(ch):
    raw = ch.encode("utf-16-le")
    return [int.from_bytes(raw[i:i + 2], "little") for i in range(0, len(raw), 2)]


HELD_KEYS = (0x10, 0x11, 0x12, 0x5B, 0x5C)    # shift, ctrl, alt, both windows keys
RELEASE_WAIT = 3.0


def wait_for_release(timeout=RELEASE_WAIT, down=None, sleep=time.sleep):
    """Wait until no modifier is held. True if they were all let go in time.

    The talk chord is Ctrl+Alt, and Apollo can be asked to type while you are
    still holding it. Text injected under a held Ctrl or Alt is not text to
    the window, it is a stream of shortcuts - one letter repeated, a page
    bookmarked, a line deleted - which is what "dddddddd" was.
    """
    if down is None:
        def down(vk):
            return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)
    deadline = time.monotonic() + timeout
    while any(down(vk) for vk in HELD_KEYS):
        if time.monotonic() > deadline:
            return False
        sleep(0.05)
    return True


def type_text(text):
    """Type into the focused window. Unicode, so Arabic types as Arabic."""
    if not wait_for_release():
        return "Failed: let go of Ctrl, Alt and Shift first, then ask me to type again."
    text = (text or "")[:MAX_TYPE]
    events = []
    for ch in text:
        if ch == "\n":
            events += [_key(0x0D), _key(0x0D, flags=KEYEVENTF_KEYUP)]
            continue
        for unit in _utf16_units(ch):
            events += [_key(0, unit, KEYEVENTF_UNICODE),
                       _key(0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)]
    if events:
        _send(events)
    return f"Typed {len(text)} characters."


MEDIA = {"play_pause": (0xB3, "Toggled play and pause."),
         "next": (0xB0, "Skipped to the next track."),
         "previous": (0xB1, "Went back a track."),
         "stop": (0xB2, "Stopped playback.")}


def media(action):
    vk, said = MEDIA[action]
    _send(_chord_events([vk]))
    return said


# --- volume -----------------------------------------------------------------

def _endpoint():
    try:
        import comtypes
        comtypes.CoInitialize()
    except Exception:
        pass
    from pycaw.pycaw import AudioUtilities
    return AudioUtilities.GetSpeakers().EndpointVolume


def volume(action, level=None):
    ep = _endpoint()
    now = int(round(ep.GetMasterVolumeLevelScalar() * 100))
    if action == "get":
        return {"ok": True, "level": now, "muted": bool(ep.GetMute())}
    if action in ("mute", "unmute"):
        ep.SetMute(1 if action == "mute" else 0, None)
        return {"ok": True, "level": now, "muted": action == "mute"}
    if action == "set":
        if level is None:
            return {"ok": False, "error": "Say what level to set the volume to."}
        target = level
    else:
        step = level if level else 10
        target = now + step if action == "up" else now - step
    target = max(0, min(100, int(target)))
    ep.SetMasterVolumeLevelScalar(target / 100.0, None)
    if target > 0:
        ep.SetMute(0, None)
    return {"ok": True, "level": target, "muted": False}


# --- windows ----------------------------------------------------------------

SHELL_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}
PROCESS_NAMES = {
    "chrome": "chrome.exe", "google chrome": "chrome.exe", "edge": "msedge.exe",
    "microsoft edge": "msedge.exe", "firefox": "firefox.exe", "spotify": "spotify.exe",
    "notepad": "notepad.exe", "discord": "discord.exe", "steam": "steam.exe",
    "word": "winword.exe", "excel": "excel.exe", "powerpoint": "powerpnt.exe",
    "vs code": "code.exe", "vscode": "code.exe", "visual studio code": "code.exe",
    "file explorer": "explorer.exe", "explorer": "explorer.exe", "task manager": "taskmgr.exe",
    "paint": "mspaint.exe", "obs": "obs64.exe", "telegram": "telegram.exe",
    "whatsapp": "whatsapp.exe", "epic games": "epicgameslauncher.exe",
}
_user32 = ctypes.windll.user32
_EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _user_windows():
    """Every visible, titled, top-level window: (hwnd, pid, title, class)."""
    found = []

    def visit(hwnd, _):
        if not _user32.IsWindowVisible(hwnd):
            return True
        length = _user32.GetWindowTextLengthW(hwnd)
        title = ctypes.create_unicode_buffer(length + 1)
        _user32.GetWindowTextW(hwnd, title, length + 1)
        cls = ctypes.create_unicode_buffer(256)
        _user32.GetClassNameW(hwnd, cls, 256)
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if _user32.GetWindowLongW(hwnd, -20) & 0x80:      # WS_EX_TOOLWINDOW
            return True
        found.append((int(hwnd), pid.value, title.value, cls.value))
        return True

    _user32.EnumWindows(_EnumProc(visit), 0)
    return found


def top_windows():
    """Windows an app action may touch: the shell's own are never among them.

    WM_CLOSE to the desktop (Progman) opens the Shut Down Windows dialog, so
    it and the taskbar are filtered out here, before anything can target them.
    """
    return [w for w in _user_windows() if w[3] not in SHELL_CLASSES and w[2]]


def _process_names():
    import psutil
    names = {}
    for proc in psutil.process_iter(["name"]):
        names[proc.pid] = (proc.info.get("name") or "").lower()
    return names


def find_windows(app):
    """Windows belonging to `app`: by process name first, then by title."""
    key = (app or "").strip().lower()
    if not key:
        return []
    exe = PROCESS_NAMES.get(key, key if key.endswith(".exe") else key.replace(" ", "") + ".exe")
    names = _process_names()
    windows = top_windows()
    by_process = [w for w in windows if names.get(w[1], "") == exe]
    return by_process or [w for w in windows if key in w[2].lower()]


def _post_close(hwnd):
    _user32.PostMessageW(hwnd, 0x0010, 0, 0)      # WM_CLOSE: the app asks about unsaved work


def _show(hwnd, cmd):
    _user32.ShowWindow(hwnd, cmd)


def _foreground():
    return int(_user32.GetForegroundWindow() or 0)


def _focus(hwnd):
    """Bring a window forward from a background process.

    Windows refuses SetForegroundWindow to a process that isn't in the
    foreground unless the input queues are joined for the call - so they are,
    briefly, with the thread that owns the current foreground window.
    """
    if _user32.IsIconic(hwnd):
        _user32.ShowWindow(hwnd, 9)
    fg = _user32.GetForegroundWindow()
    fg_thread = _user32.GetWindowThreadProcessId(fg, None) if fg else 0
    me = ctypes.windll.kernel32.GetCurrentThreadId()
    joined = bool(fg_thread and fg_thread != me and _user32.AttachThreadInput(me, fg_thread, True))
    try:
        _user32.BringWindowToTop(hwnd)
        _user32.SetForegroundWindow(hwnd)
    finally:
        if joined:
            _user32.AttachThreadInput(me, fg_thread, False)


def close_app(name):
    windows = [w for w in find_windows(name) if w[3] not in SHELL_CLASSES]
    if not windows:
        return f"Failed: {name} isn't open."
    for hwnd, *_ in windows:
        _post_close(hwnd)
    return f"Closing {name}."


WINDOW_SAID = {"minimize": "Minimized the window.", "maximize": "Maximized the window.",
               "restore": "Restored the window.", "close": "Closing the window.",
               "focus": "Switched to it.", "snap_left": "Snapped it to the left.",
               "snap_right": "Snapped it to the right."}


def window(action, app=None):
    if action == "show_desktop":
        _send(_chord_events([0x5B, ord("D")]))
        return "Showing the desktop."
    if app:
        found = find_windows(app)
        if not found:
            return f"Failed: {app} isn't open."
        hwnd = found[0][0]
    else:
        hwnd = _foreground()
        if not hwnd:
            return "Failed: there's no window in front."
    if action == "minimize":
        _show(hwnd, 6)
    elif action == "maximize":
        _show(hwnd, 3)
    elif action == "restore":
        _show(hwnd, 9)
    elif action == "close":
        _post_close(hwnd)
    elif action == "focus":
        _focus(hwnd)
    elif action in ("snap_left", "snap_right"):
        _focus(hwnd)
        _send(_chord_events([0x5B, 0x25 if action == "snap_left" else 0x27]))
    return WINDOW_SAID[action]


# --- power ------------------------------------------------------------------

def _run(argv):
    subprocess.run(argv, check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _suspend():
    ctypes.windll.powrprof.SetSuspendState(False, True, False)


def _lock():
    _user32.LockWorkStation()


def lock_pc():
    _lock()
    return "Locked."


def system_power(action):
    if action == "sleep":
        _suspend()
        return "Going to sleep."
    if action == "sign_out":
        _run(["shutdown", "/l"])
        return "Signing out."
    if action == "restart":
        _run(["shutdown", "/r", "/t", "10"])
        return "Restarting in 10 seconds. Say cancel shutdown to stop it."
    if action == "shutdown":
        _run(["shutdown", "/s", "/t", "10"])
        return "Shutting down in 10 seconds. Say cancel shutdown to stop it."
    if action == "cancel":
        _run(["shutdown", "/a"])
        return "Cancelled."
    return f"Failed: unknown power action {action}."
