"""Render every overlay state to a PNG, without opening a window.

The overlay composes itself into an offscreen surface anyway - the window is
only where that surface is pushed - so the states can be drawn, settled and
saved on their own. That makes it possible to look at all six against the
approved design in one go, and to do it again after any change.

Run:  .venv/Scripts/python.exe probes/probe_overlay_shots.py [outdir]
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
from System import IntPtr  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import orb as orb_module  # noqa: E402
import overlay_content  # noqa: E402
import overlay_paint  # noqa: E402
import overlay_state  # noqa: E402

WIDTH, HEIGHT = 620, 470
OVERHANG = 114          # what apollo.Overlay.orb_overhang() works out to


def headless():
    """An Orb with GDI+ wired up and no window behind it."""
    overlay = orb_module.Orb(size=190, position=(0, -OVERHANG), overhang=OVERHANG)
    overlay._D, overlay._WF, overlay._IntPtr = D, WF, IntPtr
    overlay.paint = overlay_paint.Backdrop(D)
    overlay.mark = overlay_paint.GlobeMark(D)
    overlay.sparkles = overlay_paint.Sparkles(D)
    return overlay


def settle(overlay, seconds=1.4, step=1 / 60):
    if overlay._content is not None:
        overlay._content["at"] = time.monotonic() - seconds
    for _ in range(int(seconds / step)):
        overlay.view.step(step)
        overlay._height.to(overlay._targets()[1])
        overlay._height.step(step)
        overlay.sparkles.advance(step, overlay._level)
        overlay._clock += step


def shot(overlay, name, outdir, desktop=(38, 40, 46)):
    surface = D.Bitmap(WIDTH, HEIGHT, D.Imaging.PixelFormat.Format32bppPArgb)
    graphics = D.Graphics.FromImage(surface)
    graphics.SmoothingMode = D.Drawing2D.SmoothingMode.AntiAlias
    graphics.TextRenderingHint = D.Text.TextRenderingHint.AntiAlias
    # A flat "desktop" behind it, so transparency is obvious in the picture.
    graphics.FillRectangle(D.SolidBrush(D.Color.FromArgb(255, *desktop)), 0, 0, WIDTH, HEIGHT)

    fade = overlay.view.ring_fade
    if fade > 0.01:
        overlay._draw_ring(graphics, (WIDTH - overlay.art) // 2, 0,
                           overlay.art, overlay.art, overlay._clock, fade)
    if overlay.view.panel_open > 0.005:
        # `now` is wall time, the same clock the body's stagger was stamped
        # with; the animation clock is a separate thing that speeds up with
        # your voice.
        overlay._draw_panel(graphics, WIDTH, overlay._clock, time.monotonic())
    graphics.Dispose()

    path = os.path.join(outdir, f"overlay-{name}.png")
    surface.Save(path, D.Imaging.ImageFormat.Png)
    surface.Dispose()
    print(f"{name:14} panel {overlay.view.panel_open:4.2f} "
          f"height {overlay._height.value:6.1f} -> {os.path.basename(path)}")


def main(outdir):
    os.makedirs(outdir, exist_ok=True)

    overlay = headless()
    settle(overlay, 0.6)
    shot(overlay, "1-rest", outdir)

    overlay.set_state(overlay_state.LISTENING)
    overlay.set_content(overlay_content.USER, "open chrome and show me nvidia")
    overlay._level = 0.6
    overlay._sync_content()
    settle(overlay)
    shot(overlay, "2-listening", outdir)

    overlay.set_state(overlay_state.SEARCHING)
    overlay.set_activity("fetching NVDA")
    settle(overlay, 0.5)
    shot(overlay, "3-searching", outdir)

    overlay.set_state(overlay_state.RESULT)
    overlay.set_activity("")
    overlay.set_content(overlay_content.APOLLO, "",
                        {"chart": None, "cards": [{"label": "CHROME", "value": "opened"},
                                                  {"label": "NVDA", "value": "222.27 ▲1.3%"},
                                                  {"label": "TSLA", "value": "364.27 ▼0.5%"}]})
    overlay._sync_content()
    settle(overlay)
    shot(overlay, "4-result", outdir)

    overlay.set_state(overlay_state.REPLY)
    overlay.set_content(overlay_content.APOLLO,
                        "Nvidia closed at 222.27, up 1.3% on the day and its third green day.",
                        {"chart": {"points": [210.4, 212.1, 209.8, 214.6, 213.2, 218.9,
                                              217.4, 220.1, 219.0, 222.27],
                                   "label": "NVDA · 5D", "unit": "$"},
                         "cards": []})
    overlay._sync_content()
    settle(overlay)
    shot(overlay, "5-reply-chart", outdir)

    # The stock card: what the overlay becomes when the question was a stock.
    overlay.set_content(overlay_content.USER, "how is nvidia doing")
    overlay.set_content(overlay_content.APOLLO,
                        "Nvidia closed at 222.27, up 1.3% on the day.",
                        {"stock": {"symbol": "NVDA", "name": "NVIDIA", "price": 222.27,
                                   "change_pct": 1.34, "unit": "$", "period": "1MO",
                                   "points": [206.1, 210.4, 214.2, 211.8, 218.6, 224.3,
                                              229.7, 232.4, 226.1, 220.4, 222.27],
                                   "logo": os.path.join(ROOT, "ui", "full", "logos", "NVDA.png"),
                                   "target": 327.7, "upside": 47.43, "pe": 28.1}})
    overlay._sync_content()
    settle(overlay)
    shot(overlay, "7-stock", outdir)

    overlay.set_content(overlay_content.USER, "كم سعر سهم إنفيديا اليوم")
    overlay.set_content(overlay_content.APOLLO,
                        "سهم إنفيديا أغلق عند 222.27 دولار، مرتفعاً 1.3% اليوم وهذا ثالث يوم أخضر على التوالي.",
                        {"chart": {"points": [210.4, 212.1, 209.8, 214.6, 213.2, 218.9,
                                              217.4, 220.1, 219.0, 222.27],
                                   "label": "NVDA · 5D", "unit": "$"}, "cards": []})
    overlay._sync_content()
    settle(overlay)
    shot(overlay, "6-reply-arabic", outdir)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join("_frames", "overlay"))
