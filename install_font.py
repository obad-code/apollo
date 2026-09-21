"""Install Thmanyah for this Windows user, or remove it again.

Apollo does not need this: it loads the font files straight out of
`ui/fonts/thmanyah` into a private GDI+ collection, and the display loads them
with @font-face. This is for everything *else* - so the family shows up in
Word, in a browser, in anything you open - and so you can see for yourself
that the face Apollo is drawing with is the one you gave it.

Per-user, so it needs no administrator: the files go in the user's own font
folder and the names go under HKEY_CURRENT_USER. Nothing outside this account
is touched.

    .\\.venv\\Scripts\\python.exe install_font.py            install
    .\\.venv\\Scripts\\python.exe install_font.py --remove   undo it
"""

import ctypes
import os
import shutil
import sys
import winreg

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "ui", "fonts", "thmanyah")
TARGET = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts")
KEY = r"Software\Microsoft\Windows NT\CurrentVersion\Fonts"

# What each file is called in the font list. GDI+ reports the weights as
# separate families, and Windows wants the same names here.
NAMES = {
    "thmanyahsans-Light.otf": "thmanyah sans Light (OpenType)",
    "thmanyahsans-Regular.otf": "thmanyah sans (OpenType)",
    "thmanyahsans-Medium.otf": "thmanyah sans Med (OpenType)",
    "thmanyahsans-Bold.otf": "thmanyah sans Bold (OpenType)",
    "thmanyahsans-Black.otf": "thmanyah sans Black (OpenType)",
}

HWND_BROADCAST = 0xFFFF
WM_FONTCHANGE = 0x001D

_gdi32 = ctypes.windll.gdi32
_gdi32.AddFontResourceW.argtypes = [ctypes.c_wchar_p]
_gdi32.RemoveFontResourceW.argtypes = [ctypes.c_wchar_p]


def _tell_windows():
    """Let running programs know the font list changed."""
    try:
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_FONTCHANGE, 0, 0, 0, 1000, None)
    except Exception:  # noqa: BLE001 - cosmetic; a new program sees it anyway
        pass


def install():
    if not os.path.isdir(SOURCE):
        raise SystemExit(f"no font files at {SOURCE}")
    os.makedirs(TARGET, exist_ok=True)
    done = []
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, KEY) as key:
        for filename, name in NAMES.items():
            source = os.path.join(SOURCE, filename)
            if not os.path.exists(source):
                print(f"  skipped (missing): {filename}")
                continue
            destination = os.path.join(TARGET, filename)
            try:
                shutil.copy2(source, destination)
            except PermissionError:
                # Already installed and in use by a running program. The file
                # on disk is the same font, so the registry entry is enough.
                pass
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, destination)
            # The registry entry is what survives a sign-out; this is what
            # makes the font usable in this session without one.
            _gdi32.AddFontResourceW(destination)
            done.append(name)
    _tell_windows()
    print(f"installed {len(done)} weights for {os.environ.get('USERNAME', 'this user')}:")
    for name in done:
        print(f"  {name}")
    print("\nPrograms already open keep the old font list; new ones see it.")


def remove():
    gone = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0,
                            winreg.KEY_ALL_ACCESS) as key:
            for filename, name in NAMES.items():
                try:
                    winreg.DeleteValue(key, name)
                    gone.append(name)
                except FileNotFoundError:
                    pass
    except FileNotFoundError:
        pass
    for filename in NAMES:
        path = os.path.join(TARGET, filename)
        if os.path.exists(path):
            _gdi32.RemoveFontResourceW(path)
            try:
                os.remove(path)
            except OSError:
                print(f"  in use, left in place: {filename}")
    _tell_windows()
    print(f"removed {len(gone)} weights. Apollo still has its own copy and is "
          f"unaffected.")


if __name__ == "__main__":
    remove() if "--remove" in sys.argv else install()
