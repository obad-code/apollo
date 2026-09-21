"""Put the real overlay on the real screen and photograph it.

Everything probe_overlay_shots.py proves, it proves offscreen: the card is
composed into a bitmap and saved. None of that exercises the part that has
actually broken before - UpdateLayeredWindow, per-pixel alpha, and the window
sitting over the desktop with its top quarter above the screen's edge. This
runs the genuine article for a few seconds and screenshots the desktop.

Run:  .venv/Scripts/python.exe probes/probe_overlay_live.py [outdir]
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import clr  # noqa: E402

clr.AddReference("System.Drawing")
clr.AddReference("System.Windows.Forms")
import System.Drawing as D  # noqa: E402
import System.Windows.Forms as WF  # noqa: E402
from System import Action  # noqa: E402

import apollo  # noqa: E402
import orb as orb_module  # noqa: E402
import overlay_content  # noqa: E402
import overlay_state  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "probes", "live")

STOCK = {"stock": {"symbol": "NVDA", "name": "NVIDIA", "price": 222.27,
                   "change_pct": 1.34, "unit": "$", "period": "1MO",
                   "points": [206.1, 210.4, 214.2, 211.8, 218.6, 224.3,
                              229.7, 232.4, 226.1, 220.4, 222.27],
                   "logo": os.path.join(ROOT, "ui", "full", "logos", "NVDA.png"),
                   "target": 327.7, "upside": 47.43, "pe": 28.1}}


def shoot(name):
    bounds = WF.Screen.PrimaryScreen.Bounds
    bitmap = D.Bitmap(bounds.Width, bounds.Height)
    graphics = D.Graphics.FromImage(bitmap)
    graphics.CopyFromScreen(0, 0, 0, 0, D.Size(bounds.Width, bounds.Height))
    graphics.Dispose()
    path = os.path.join(OUT, name + ".png")
    bitmap.Save(path, D.Imaging.ImageFormat.Png)
    bitmap.Dispose()
    print(f"{name:14} -> {path}", flush=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    # Read the box through apollo.Overlay, the way apollo.py does. Computing
    # it here instead put the window at the screen's top edge rather than
    # `overhang` above it, so the quarter of the card meant to hide off-screen
    # sat on screen as a band of empty cream - a bug in this probe that looked
    # exactly like a bug in the overlay.
    overlay_box = apollo.Overlay.__new__(apollo.Overlay)
    x, y, size, _ = overlay_box.box_for(apollo.Overlay.ORB)
    overhang = apollo.Overlay.orb_overhang()

    # Not minimized: a minimized form never raises Shown here, and the overlay
    # is built from that event. One pixel, off the edge, and invisible.
    host = WF.Form()
    host.ShowInTaskbar = False
    host.FormBorderStyle = getattr(WF.FormBorderStyle, "None")
    host.StartPosition = WF.FormStartPosition.Manual
    host.Location = D.Point(-4000, -4000)
    host.Size = D.Size(1, 1)
    host.Opacity = 0.0

    overlay = orb_module.Orb(size=size, position=(x, y), overhang=overhang)

    def when_shown(sender, args):
        print("host shown; building the overlay", flush=True)
        overlay.start_on(host)
        print("overlay ready:", overlay.ready.wait(5.0), flush=True)

        def later(seconds, work):
            timer = WF.Timer()
            timer.Interval = int(seconds * 1000)

            def tick(s, a):
                timer.Stop()
                work()
            timer.Tick += tick
            timer.Start()

        def step(delay, name, work):
            """Change the state, then photograph it once it has settled.

            The card grows on a spring and the words arrive a word at a time,
            so a shot taken in the same tick as the change catches the frame
            before it - which is how the first run of this probe produced a
            'stock' picture that was still showing the listening card.
            """
            later(delay, work)
            later(delay + 1.3, lambda: shoot(name))

        step(1.4, "live-1-rest", lambda: None)
        step(3.2, "live-2-listening", lambda: (
            overlay.set_state(overlay_state.LISTENING),
            overlay.set_content(overlay_content.USER, "how is nvidia doing")))
        step(5.8, "live-3-stock", lambda: (
            overlay.set_state(overlay_state.REPLY),
            overlay.set_content(overlay_content.APOLLO,
                                "Nvidia closed at 222.27, up 1.3% on the day.",
                                STOCK)))
        step(8.4, "live-4-arabic", lambda: (
            overlay.set_content(overlay_content.USER, "كم سعر سهم إنفيديا اليوم"),
            overlay.set_content(overlay_content.APOLLO,
                                "سهم إنفيديا أغلق عند 222.27 دولار، مرتفعاً 1.3% اليوم.",
                                STOCK)))
        later(11.4, lambda: (overlay.stop(), host.Close(), WF.Application.Exit()))

    host.Shown += when_shown
    WF.Application.Run(host)
    print(f"frames drawn: {overlay.frames}, errors: {overlay.errors}", flush=True)


if __name__ == "__main__":
    main()
