"""What does one overlay frame cost?

The overlay redraws sixty times a second while you speak, into a 32-bit
surface that is then handed to the compositor. This renders the whole
composition - panel, drifting clouds, scanlines, the three-ring orb, the
horizon, the sparkle field and a cached content blit - as fast as it can and
reports the mean and the worst frame, so "it feels smooth" is a number.

Run:  .venv/Scripts/python.exe probes/probe_overlay_frames.py [frames]
"""

import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import clr  # noqa: E402

clr.AddReference("System.Drawing")
import System.Drawing as D  # noqa: E402

import overlay_paint as paint  # noqa: E402

WIDTH, HEIGHT = 560, 420
PANEL_X, PANEL_W, PANEL_H = 30, 500, 200
BUDGET_MS = 16.7


def main(count=180):
    surface = D.Bitmap(WIDTH, HEIGHT, D.Imaging.PixelFormat.Format32bppPArgb)
    graphics = D.Graphics.FromImage(surface)
    graphics.SmoothingMode = D.Drawing2D.SmoothingMode.AntiAlias

    content = D.Bitmap(PANEL_W, 120, D.Imaging.PixelFormat.Format32bppPArgb)
    scratch = D.Graphics.FromImage(content)
    scratch.Clear(D.Color.FromArgb(40, 255, 255, 255))
    scratch.Dispose()

    backdrop = paint.Backdrop(D)
    mark = paint.GlobeMark(D)
    sparkles = paint.Sparkles(D, count=260)

    times = []
    clock = 0.0
    for frame in range(count):
        start = time.perf_counter()
        graphics.Clear(D.Color.FromArgb(0, 0, 0, 0))
        backdrop.panel(graphics, PANEL_X, 0, PANEL_W, PANEL_H, t=clock)
        mark.draw_at(graphics, PANEL_X + 56, 58, 25, t=clock, level=0.8)
        graphics.DrawImage(content, PANEL_X, 70)
        paint.horizon(graphics, D, PANEL_X, PANEL_H, PANEL_W)
        sparkles.advance(1 / 60, level=0.8)
        sparkles.draw_at(graphics, PANEL_X, PANEL_H, PANEL_W, 150)
        times.append((time.perf_counter() - start) * 1000)
        clock += 1 / 60

    graphics.Dispose()
    surface.Dispose()
    content.Dispose()

    warm = times[10:]
    mean = statistics.mean(warm)
    worst = max(warm)
    print(f"{len(warm)} frames | mean {mean:5.2f} ms | median {statistics.median(warm):5.2f} ms "
          f"| worst {worst:5.2f} ms | first {times[0]:5.2f} ms (builds the caches)")
    print(f"budget {BUDGET_MS} ms per frame at 60 fps -> "
          f"{'fits, with room' if mean < BUDGET_MS * 0.6 else 'fits' if worst < BUDGET_MS else 'TOO SLOW'}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 180)
