"""Can a WebView2 window be genuinely see-through here?

`apollo.py`'s docstring lists everything that has already been tried and
failed - colour keys, TransparencyKey, DwmExtendFrameIntoClientArea,
SetWindowCompositionAttribute - which is why the overlay is drawn by hand in
`orb.py`. One thing was never tried: `DwmEnableBlurBehindWindow` with an
*empty* blur region, which is how winit and tao make transparent windows on
Windows. It tells DWM to honour the window's alpha channel, and GDI painting
leaves alpha at zero, so the parts the page does not draw should vanish.

The test is a measurement, not an impression:

  1. screenshot the strip of desktop the window will cover;
  2. show a page that paints one opaque circle on nothing;
  3. screenshot the same strip again.

If it worked, the pixels around the circle are unchanged (the desktop shows
through) and the pixels inside it are not. Anything else - a black box, a
white box, a grey box - shows up as "background changed too".

Run:  .venv/Scripts/python.exe probes/probe_transparent_webview.py
"""

import ctypes
import os
import sys
import threading
import time
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
                      "--autoplay-policy=no-user-gesture-required")

import webview  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, "_transparent_test.html")

BOX = (700, 300, 400, 300)          # x, y, w, h - where the window goes

HTML = """<!doctype html>
<html><head><meta charset="utf-8"><style>
  html, body { margin:0; height:100%; background:transparent; overflow:hidden; }
  .dot { position:absolute; left:150px; top:100px; width:100px; height:100px;
         border-radius:50%; background:#ff2d55; }
</style></head><body><div class="dot"></div></body></html>
"""


class Margins(ctypes.Structure):
    _fields_ = [("cxLeftWidth", ctypes.c_int), ("cxRightWidth", ctypes.c_int),
                ("cyTopHeight", ctypes.c_int), ("cyBottomHeight", ctypes.c_int)]


class BlurBehind(ctypes.Structure):
    _fields_ = [("dwFlags", wintypes.DWORD), ("fEnable", wintypes.BOOL),
                ("hRgnBlur", wintypes.HRGN), ("fTransitionOnMaximized", wintypes.BOOL)]


DWM_BB_ENABLE = 0x01
DWM_BB_BLURREGION = 0x02
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000


def grab(box):
    """A screenshot of `box` as a list of (r, g, b), via .NET."""
    import clr
    clr.AddReference("System.Drawing")
    import System.Drawing as D

    x, y, w, h = box
    bitmap = D.Bitmap(w, h)
    graphics = D.Graphics.FromImage(bitmap)
    graphics.CopyFromScreen(x, y, 0, 0, D.Size(w, h))
    graphics.Dispose()
    pixels = []
    for yy in range(0, h, 4):
        for xx in range(0, w, 4):
            colour = bitmap.GetPixel(xx, yy)
            pixels.append((colour.R, colour.G, colour.B, xx, yy))
    bitmap.Dispose()
    return pixels


def make_transparent(hwnd):
    """The untried trick: an empty blur region makes DWM honour alpha."""
    region = ctypes.windll.gdi32.CreateRectRgn(0, 0, -1, -1)
    blur = BlurBehind(DWM_BB_ENABLE | DWM_BB_BLURREGION, True, region, False)
    result = ctypes.windll.dwmapi.DwmEnableBlurBehindWindow(hwnd, ctypes.byref(blur))
    ctypes.windll.gdi32.DeleteObject(region)
    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    ctypes.windll.user32.SetWindowLongW(
        hwnd, GWL_EXSTYLE,
        style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
    ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, 255, 0x02)   # LWA_ALPHA
    return result


def report(before, after):
    x, y, w, h = BOX
    dot_centre = (150 + 50, 100 + 50)
    inside = outside = changed_inside = changed_outside = 0
    for (r1, g1, b1, xx, yy), (r2, g2, b2, _, _) in zip(before, after):
        far = ((xx - dot_centre[0]) ** 2 + (yy - dot_centre[1]) ** 2) ** 0.5 > 70
        changed = abs(r1 - r2) + abs(g1 - g2) + abs(b1 - b2) > 24
        if far:
            outside += 1
            changed_outside += changed
        else:
            inside += 1
            changed_inside += changed
    print(f"background: {changed_outside}/{outside} pixels changed "
          f"({100 * changed_outside / max(1, outside):.0f}%)")
    print(f"the circle: {changed_inside}/{inside} pixels changed "
          f"({100 * changed_inside / max(1, inside):.0f}%)")
    see_through = changed_outside / max(1, outside) < 0.08
    drawn = changed_inside / max(1, inside) > 0.6
    print("VERDICT:", "per-pixel transparency WORKS" if (see_through and drawn)
          else "not transparent" if drawn else "the page did not draw")


def main():
    with open(PAGE, "w", encoding="utf-8") as f:
        f.write(HTML)

    before = grab(BOX)
    window = webview.create_window("ApolloTransparencyProbe", PAGE,
                                   x=BOX[0], y=BOX[1], width=BOX[2], height=BOX[3],
                                   frameless=True, easy_drag=False, shadow=False,
                                   focus=False, on_top=True, transparent=True,
                                   background_color="#000000")

    def after_load():
        time.sleep(1.0)
        hwnd = ctypes.windll.user32.FindWindowW(None, "ApolloTransparencyProbe")
        print("hwnd:", hwnd)
        print("DwmEnableBlurBehindWindow ->", make_transparent(hwnd))
        time.sleep(1.5)
        after = grab(BOX)
        report(before, after)
        window.destroy()

    window.events.loaded += lambda: threading.Thread(target=after_load, daemon=True).start()
    webview.start()


if __name__ == "__main__":
    main()
