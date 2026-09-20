"""Four ways to ask WebView2 for a see-through window, measured one by one.

Same measurement as probe_transparent_webview.py - screenshot the strip,
show the page, screenshot again - but the window stays up while each
technique is applied in turn, so one run says which combination (if any)
lets the desktop through.

Run:  .venv/Scripts/python.exe probes/probe_transparent_matrix.py
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

from probe_transparent_webview import (BOX, HTML, PAGE, BlurBehind, DWM_BB_BLURREGION,  # noqa: E402
                                       DWM_BB_ENABLE, GWL_EXSTYLE, WS_EX_LAYERED,
                                       WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW,
                                       WS_EX_TRANSPARENT, grab)

user32 = ctypes.windll.user32


def blur_behind(hwnd):
    region = ctypes.windll.gdi32.CreateRectRgn(0, 0, -1, -1)
    blur = BlurBehind(DWM_BB_ENABLE | DWM_BB_BLURREGION, True, region, False)
    result = ctypes.windll.dwmapi.DwmEnableBlurBehindWindow(hwnd, ctypes.byref(blur))
    ctypes.windll.gdi32.DeleteObject(region)
    return result


def passive_styles(hwnd, layered):
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    style |= WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    if layered:
        style |= WS_EX_LAYERED
    else:
        style &= ~WS_EX_LAYERED
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    if layered:
        user32.SetLayeredWindowAttributes(hwnd, 0, 255, 0x02)


def controller_transparent(window):
    """Reach the real WebView2 control and clear its background."""
    try:
        import clr
        clr.AddReference("System.Drawing")
        import System.Drawing as D
        from System import Action

        form = window.native
        found = []

        def walk(control):
            for child in control.Controls:
                found.append(child)
                walk(child)

        walk(form)
        names = [type(c).__name__ for c in found]
        target = next((c for c in found if "WebView2" in type(c).__name__), None)
        if target is None:
            return f"no WebView2 control among {names}"

        def apply():
            target.DefaultBackgroundColor = D.Color.Transparent
            form.BackColor = D.Color.Black
            form.TransparencyKey = D.Color.Black

        form.Invoke(Action(apply))
        return f"set on {type(target).__name__} (children: {names})"
    except Exception as e:  # noqa: BLE001
        return f"failed: {type(e).__name__}: {e}"


def measure(label, before):
    after = grab(BOX)
    centre = (200, 150)
    inside = outside = changed_in = changed_out = 0
    for (r1, g1, b1, xx, yy), (r2, g2, b2, _, _) in zip(before, after):
        far = ((xx - centre[0]) ** 2 + (yy - centre[1]) ** 2) ** 0.5 > 70
        changed = abs(r1 - r2) + abs(g1 - g2) + abs(b1 - b2) > 24
        if far:
            outside += 1
            changed_out += changed
        else:
            inside += 1
            changed_in += changed
    back = 100 * changed_out / max(1, outside)
    dot = 100 * changed_in / max(1, inside)
    verdict = ("TRANSPARENT" if back < 8 and dot > 60
               else "opaque" if dot > 60 else "page not drawn")
    print(f"{label:38} background {back:5.1f}% changed | circle {dot:5.1f}% | {verdict}")


def main():
    with open(PAGE, "w", encoding="utf-8") as f:
        f.write(HTML)
    before = grab(BOX)
    window = webview.create_window("ApolloTransparencyProbe", PAGE,
                                   x=BOX[0], y=BOX[1], width=BOX[2], height=BOX[3],
                                   frameless=True, easy_drag=False, shadow=False,
                                   focus=False, on_top=True, transparent=True,
                                   background_color="#000000")

    def run():
        time.sleep(1.2)
        hwnd = user32.FindWindowW(None, "ApolloTransparencyProbe")
        measure("as pywebview leaves it", before)

        print("control:", controller_transparent(window))
        time.sleep(1.0)
        measure("WebView2 DefaultBackgroundColor", before)

        blur_behind(hwnd)
        time.sleep(1.0)
        measure("+ DwmEnableBlurBehindWindow", before)

        passive_styles(hwnd, layered=False)
        time.sleep(1.0)
        measure("+ click-through, not layered", before)

        passive_styles(hwnd, layered=True)
        time.sleep(1.0)
        measure("+ layered, alpha 255", before)

        window.destroy()

    window.events.loaded += lambda: threading.Thread(target=run, daemon=True).start()
    webview.start()


if __name__ == "__main__":
    main()
