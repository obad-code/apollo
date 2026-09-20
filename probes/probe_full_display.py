"""Open the full display in the real window and check it came up whole.

The browser pane is Chromium; Apollo's window is WebView2, served by
pywebview's own HTTP server. Three things could work in one and not the
other - ES modules over that server, WebGL for the shader, and the bridge
registering on `window` - so this loads the actual page in the actual window
and asks it.

Run:  .venv/Scripts/python.exe probes/probe_full_display.py
"""

import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import webview  # noqa: E402

import apollo  # noqa: E402

CHECKS = """
(() => {
  const bridge = Object.keys(window.apollo || {});
  const gl = document.getElementById('shader').getContext('webgl');
  const lyla = document.getElementById('lyla');
  // Her room is the window. A stylesheet that gives this canvas a height -
  // a leftover from when she sat in a grid cell - squashes the whole room
  // into a strip, and it only shows at the width the rule applies to.
  const box = lyla.getBoundingClientRect();
  const roomIsTheWindow = Math.round(box.width) === innerWidth
                       && Math.round(box.height) === innerHeight;
  // The bundled face has to actually load: a @font-face that 404s falls back
  // silently, and the display looks almost right in the wrong typeface.
  const thmanyah = document.fonts.check('16px Thmanyah');
  const rows = document.querySelectorAll('.stock').length;
  const sparks = document.querySelectorAll('.stock svg path').length;
  const panels = [...document.querySelectorAll('.rise')]
    .map(p => Number(getComputedStyle(p).opacity));
  return JSON.stringify({
    bridge, webgl: !!gl, lylaCanvas: [lyla.width, lyla.height], roomIsTheWindow,
    lylaBox: [Math.round(box.width), Math.round(box.height)],
    viewport: [innerWidth, innerHeight], thmanyah,
    rows, sparks, panelsVisible: panels.filter(o => o > 0.9).length,
    panelCount: panels.length,
    label: document.getElementById('lyla-label').textContent,
    clock: document.getElementById('hhmm').textContent,
    nasdaq: (document.querySelectorAll('#indices .figure')[1] || {}).textContent,
  });
})()
"""


# A cheap fingerprint of each animated canvas: if a loop is still running these
# change between two reads a second and a half apart.
SAMPLE_CANVASES = """
JSON.stringify(['ring', 'lyla', 'shader'].map((id) => {
  const c = document.getElementById(id);
  try { return c.toDataURL().length; } catch (e) { return 'blocked'; }
}))
"""


def main():
    window = webview.create_window("Apollo probe", apollo.INDEX,
                                   width=1600, height=900, frameless=True,
                                   background_color="#000000")

    def drive():
        time.sleep(6)               # let the module load and a few frames run
        try:
            report = window.evaluate_js(CHECKS)
            print(report)
            window.evaluate_js("window.apollo.status('Speaking');"
                               "window.apollo.turn('You', 'how is nvidia doing');"
                               "window.apollo.turn('Apollo', 'NVIDIA is at 222.27, up 1.34%.')")
            time.sleep(2)
            # A headline that tries to run: it must land as text, not markup.
            window.evaluate_js("""
              window.apollo.data({market:{indices:[],watchlist:[],status:''},
                news:{gaming:[{title:"<img src=x onerror=\\"window.__pwned=1\\">boom",
                               source:"<b>src</b>", age:"1h ago"}]},
                posts:[], weather:{}, system:{}, usage:{}, updated:0, stamps:{}});
            """)
            time.sleep(0.5)
            print("escaping:", window.evaluate_js(
                "JSON.stringify({pwned: !!window.__pwned,"
                " imgs: document.querySelectorAll('#stories img').length,"
                " shown: document.querySelector('#stories .story').textContent.slice(0,22)})"))
            # Closing the display must stop the ring, the shader and LYLA:
            # Apollo's window is hidden by Win32, so nothing throttles them.
            window.evaluate_js("window.apollo.mode('orb')")
            before = window.evaluate_js(SAMPLE_CANVASES)
            time.sleep(1.5)
            after = window.evaluate_js(SAMPLE_CANVASES)
            print("stopped while hidden:", before == after, before, after)

            # ...and start again when it opens, or the stop is just a break.
            window.evaluate_js("window.apollo.mode('full')")
            woke = window.evaluate_js(SAMPLE_CANVASES)
            time.sleep(1.5)
            print("running again:", woke != window.evaluate_js(SAMPLE_CANVASES))
            print("answering:", window.evaluate_js(
                "JSON.stringify({body: document.body.className,"
                " answer: getComputedStyle(document.getElementById('answer')).opacity})"))
        except Exception as exc:  # noqa: BLE001 - the probe reports, never raises
            print("probe failed:", exc)
        finally:
            window.destroy()

    threading.Thread(target=drive, daemon=True).start()
    # A private profile means no cache: the probe always sees the files
    # as they are on disk, not as they were the last time it ran.
    webview.start(private_mode=True)


if __name__ == "__main__":
    main()
