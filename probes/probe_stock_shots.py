"""Screenshots of the stock panel in the real window: the frame on a card, a
stock opened out of its card over each span, the line run along its chart,
one taken off, the add picker and one put on - and the background, twice,
a few seconds apart, to show it moving.

Uses a watchlist of its own in %TEMP%, so it changes nothing of yours.

Run:  .venv/Scripts/python.exe probes/probe_stock_shots.py [out_dir]
"""

import json
import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import webview  # noqa: E402

import apollo  # noqa: E402
import dataservice  # noqa: E402
import stockdesk  # noqa: E402
import watchlist  # noqa: E402
from probe_feed_shots import grab  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "shots")


def card(symbol):
    return f"[...document.querySelectorAll('#watchlist .card')].find(c => c.dataset.symbol === {json.dumps(symbol)})"


def main():
    os.makedirs(OUT, exist_ok=True)
    watchlist.PATH = os.path.join(tempfile.mkdtemp(), "watchlist.json")
    watchlist._memo = None
    left, top, right, bottom = apollo.Overlay.work_area()
    box = (left, top, right - left, bottom - top)

    service = dataservice.DataService()
    window = None

    def push():
        window.evaluate_js(f"window.apollo.data({json.dumps(service.snapshot)})")

    def reread(*keys):
        def run():
            service._read_market()
            push()
        threading.Thread(target=run, daemon=True).start()

    reader = threading.Thread(target=lambda: service.refresh(force=True), daemon=True)
    reader.start()
    window = webview.create_window(
        "Apollo probe", apollo.INDEX, x=left, y=top, width=box[2], height=box[3],
        frameless=True, on_top=True, background_color="#000000",
        js_api=apollo.Api(lambda: None, desk=stockdesk.StockDesk(poke=reread)))

    def js(script):
        return window.evaluate_js(script)

    def panels(step):
        print(step, js("JSON.stringify({hidden: document.hidden, panels: [...document.querySelectorAll('.panel')]"
                       ".map(p => p.id + ':' + getComputedStyle(p).opacity + ':' + getComputedStyle(p).display"
                       " + ':' + p.getAnimations().length + ':' + (p.style.opacity || '-'))})"))

    def hover(target):
        return js(f"""(() => {{ const c = {target}; if (!c) return 'none';
            c.dispatchEvent(new PointerEvent('pointerover', {{bubbles: true}}));
            return c.dataset.symbol || 'add'; }})()""")

    def drive():
        try:
            reader.join(timeout=60)
            time.sleep(4)
            js("window.__errors = []; window.addEventListener('error',"
               " (e) => window.__errors.push(String(e.message)))")
            push()
            js("window.apollo.mode('full'); window.apollo.status('Idle')")
            time.sleep(3)
            panels("s1-dashboard.png")
            grab(box, os.path.join(OUT, "s1-dashboard.png"))
            time.sleep(6)
            panels("s1b-dashboard-6s-later.png")
            grab(box, os.path.join(OUT, "s1b-dashboard-6s-later.png"))

            print("hover:", hover(card("NVDA")))
            time.sleep(0.8)
            panels("s2-hover.png")
            grab(box, os.path.join(OUT, "s2-hover.png"))
            print("hover add:", hover("document.querySelector('#watchlist .add')"))
            time.sleep(0.8)
            grab(box, os.path.join(OUT, "s3-hover-add.png"))

            js(f"{card('NVDA')}.click()")
            print("open:", js("document.getElementById('stock').className"))
            time.sleep(0.25)
            grab(box, os.path.join(OUT, "s4-opening.png"))
            time.sleep(2.5)
            panels("s5-open-1d.png")
            grab(box, os.path.join(OUT, "s5-open-1d.png"))

            js("document.querySelector('#stock [data-span=\"1mo\"]').click()")
            time.sleep(3.5)
            panels("s6-open-1mo.png")
            grab(box, os.path.join(OUT, "s6-open-1mo.png"))
            js("document.querySelector('#stock [data-span=\"1y\"]').click()")
            time.sleep(3.5)
            js("""(() => { const big = document.querySelector('#stock .big');
                const b = big.getBoundingClientRect();
                big.dispatchEvent(new PointerEvent('pointermove', {bubbles: true,
                  clientX: b.left + b.width * 0.62, clientY: b.top + b.height / 2})); })()""")
            time.sleep(0.5)
            grab(box, os.path.join(OUT, "s7-open-1y-scrub.png"))

            js("document.querySelector('#stock [data-act=\"drop\"]').click()")
            time.sleep(0.4)
            grab(box, os.path.join(OUT, "s8-remove-ask.png"))
            js("document.querySelector('#stock [data-act=\"drop\"]').click()")
            time.sleep(1.8)
            print("after remove:", js("[...document.querySelectorAll('#watchlist .card')]"
                                     ".map(c => c.dataset.symbol || 'add').join(',')"))
            panels("s9-removed.png")
            grab(box, os.path.join(OUT, "s9-removed.png"))

            js("document.querySelector('#watchlist .add').click()")
            time.sleep(2.0)
            grab(box, os.path.join(OUT, "s10-picker.png"))
            js("document.querySelector('#stock [data-pick=\"PLTR\"]').click()")
            time.sleep(0.8)
            grab(box, os.path.join(OUT, "s11-pending.png"))
            time.sleep(8)
            print("after add:", js("[...document.querySelectorAll('#watchlist .card')]"
                                  ".map(c => c.dataset.symbol || 'add').join(',')"))
            panels("s12-added.png")
            grab(box, os.path.join(OUT, "s12-added.png"))

            print("voice:", js("JSON.stringify(window.apollo.stock('MSFT'))"))
            time.sleep(2.5)
            grab(box, os.path.join(OUT, "s13-voice-open.png"))
            js("window.apollo.stock('')")
            time.sleep(1)
            print("console errors:", js("window.__errors || 'none recorded'"))
        except Exception as exc:  # noqa: BLE001 - the probe reports, never raises
            print("probe failed:", exc)
        finally:
            window.destroy()

    threading.Thread(target=drive, daemon=True).start()
    webview.start(private_mode=True)


if __name__ == "__main__":
    main()
