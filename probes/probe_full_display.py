"""Open the full display in the real window and check it came up whole.

The browser pane is Chromium; Apollo's window is WebView2, served by
pywebview's own HTTP server. Three things could work in one and not the
other - ES modules over that server, WebGL for the shader, and the bridge
registering on `window` - so this loads the actual page in the actual window
and asks it.

Run:  .venv/Scripts/python.exe probes/probe_full_display.py [shot.png]
"""

import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import webview  # noqa: E402

import apollo  # noqa: E402

SHOT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "full_display.png")

CHECKS = """
(() => {
  const bridge = Object.keys(window.apollo || {});
  const gl = document.getElementById('shader').getContext('webgl');
  const lyla = document.getElementById('lyla');
  const rows = document.querySelectorAll('.stock').length;
  const sparks = document.querySelectorAll('.stock svg path').length;
  const panels = [...document.querySelectorAll('.rise')]
    .map(p => Number(getComputedStyle(p).opacity));
  return JSON.stringify({
    bridge, webgl: !!gl, lylaCanvas: [lyla.width, lyla.height],
    rows, sparks, panelsVisible: panels.filter(o => o > 0.9).length,
    panelCount: panels.length,
    label: document.getElementById('lyla-label').textContent,
    clock: document.getElementById('hhmm').textContent,
    nasdaq: (document.querySelectorAll('#indices .figure')[1] || {}).textContent,
  });
})()
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
            print("answering:", window.evaluate_js(
                "JSON.stringify({body: document.body.className,"
                " answer: getComputedStyle(document.getElementById('answer')).opacity})"))
        except Exception as exc:  # noqa: BLE001 - the probe reports, never raises
            print("probe failed:", exc)
        finally:
            window.destroy()

    threading.Thread(target=drive, daemon=True).start()
    webview.start(private_mode=False)


if __name__ == "__main__":
    main()
