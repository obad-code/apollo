"""Screenshots of the full display in the real window: the feed, a story
opened out of it, and the idle screen - with the real feeds in it.

The browser pane throttles a hidden page to no frames at all, which is every
transition on this page; the only honest look is WebView2 on the actual
screen. The window covers the work area for a minute and closes itself.

Run:  .venv/Scripts/python.exe probes/probe_feed_shots.py [out_dir]
"""

import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import webview  # noqa: E402

import apollo  # noqa: E402
import dataservice  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "shots")


def grab(box, path):
    """The screen inside `box` (x, y, w, h), saved as a PNG, via .NET."""
    import clr
    clr.AddReference("System.Drawing")
    import System.Drawing as D
    x, y, w, h = box
    bitmap = D.Bitmap(w, h)
    g = D.Graphics.FromImage(bitmap)
    try:
        g.CopyFromScreen(x, y, 0, 0, D.Size(w, h))
    finally:
        g.Dispose()
    bitmap.Save(path, D.Imaging.ImageFormat.Png)
    bitmap.Dispose()
    print("saved", path)


def pointer_at(row):
    """Put the pointer over one row of the feed, as far as the page can tell."""
    return f"""
    (() => {{
      const row = document.querySelectorAll('#stories .story')[{row}];
      const box = row.getBoundingClientRect();
      const at = {{ clientX: box.left + box.width * 0.4, clientY: box.top + box.height / 2,
                    bubbles: true }};
      row.dispatchEvent(new PointerEvent('pointerover', at));
      document.getElementById('feed').dispatchEvent(new PointerEvent('pointermove', at));
      return row.textContent.trim().slice(0, 40);
    }})()"""


def main():
    os.makedirs(OUT, exist_ok=True)
    left, top, right, bottom = apollo.Overlay.work_area()
    box = (left, top, right - left, bottom - top)

    snapshot = {}

    def read_world():
        service = dataservice.DataService()
        service.refresh(force=True)
        snapshot.update(service.snapshot)

    reader = threading.Thread(target=read_world, daemon=True)
    reader.start()

    window = webview.create_window("Apollo probe", apollo.INDEX, x=left, y=top,
                                   width=box[2], height=box[3], frameless=True,
                                   on_top=True, background_color="#000000")

    def drive():
        try:
            reader.join(timeout=60)
            time.sleep(4)
            if snapshot:
                window.evaluate_js(f"window.apollo.data({json.dumps(snapshot)})")
            window.evaluate_js("window.apollo.mode('full'); window.apollo.status('Idle')")
            time.sleep(3)
            print("errors:", window.evaluate_js(
                "JSON.stringify({stories: document.querySelectorAll('#stories .story').length,"
                " pictures: [...document.querySelectorAll('#peek img')].length})"))
            grab(box, os.path.join(OUT, "1-dashboard.png"))

            print("hover:", window.evaluate_js(pointer_at(1)))
            time.sleep(1.2)
            grab(box, os.path.join(OUT, "2-hover.png"))
            print("hover next:", window.evaluate_js(pointer_at(3)))
            time.sleep(1.2)
            grab(box, os.path.join(OUT, "3-hover-next.png"))

            # The first story that has a picture, so the opened view shows one.
            pictured = window.evaluate_js(
                "[...document.querySelectorAll('#stories .story')].findIndex(r => r.querySelector('.pic'))")
            pictured = pictured if isinstance(pictured, int) and pictured >= 0 else 0
            print("hover pictured:", window.evaluate_js(pointer_at(pictured)))
            time.sleep(1.2)
            grab(box, os.path.join(OUT, "3b-hover-picture.png"))
            print("open:", window.evaluate_js(f"JSON.stringify(window.apollo.story({pictured + 1}))"))
            time.sleep(0.25)
            grab(box, os.path.join(OUT, "4-opening.png"))
            time.sleep(1.6)
            grab(box, os.path.join(OUT, "5-story.png"))
            window.evaluate_js("window.apollo.story(0)")
            time.sleep(1.0)

            window.evaluate_js("window.apollo.sleep(true)")
            time.sleep(1.2)
            grab(box, os.path.join(OUT, "6-falling-asleep.png"))
            time.sleep(5)
            grab(box, os.path.join(OUT, "7-asleep.png"))
            time.sleep(17)
            grab(box, os.path.join(OUT, "8-asleep-next-fact.png"))
            window.evaluate_js("window.apollo.sleep(false)")
            time.sleep(4)
            grab(box, os.path.join(OUT, "9-awake.png"))
        except Exception as exc:  # noqa: BLE001 - the probe reports, never raises
            print("probe failed:", exc)
        finally:
            window.destroy()

    threading.Thread(target=drive, daemon=True).start()
    webview.start(private_mode=True)


if __name__ == "__main__":
    main()
