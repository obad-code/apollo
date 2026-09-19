"""Temporary: drive ui/index.html through every state with no mic or API."""
import os
import subprocess
import threading
import time

import apollo

# Don't start the real backend (mic, Whisper, API) for this run.
apollo.Apollo.on_loaded = lambda self: None

app = apollo.Apollo()

FRAMES = os.path.join(apollo.HERE, "_frames")
os.makedirs(FRAMES, exist_ok=True)

SNAP = r"""
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
$bmp.Save('%s')
$g.Dispose(); $bmp.Dispose()
"""


def snap(name):
    path = os.path.join(FRAMES, name + ".png")
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", SNAP % path],
        capture_output=True,
    )
    print("   snap ->", name, os.path.exists(path), flush=True)


SCRIPT = [
    (0.5, "status", ("Waking",)),
    (0.3, "note", ("Loading Whisper (base.en)... first run downloads the model.",)),
    (1.5, "snap", ("1-waking",)),
    (2.0, "status", ("Speaking",)),
    (2.5, "snap", ("2-greeting-speaking",)),
    (0.2, "status", ("Idle",)),
    (3.5, "snap", ("3-idle",)),
    (0.2, "status", ("Listening",)),
    (3.5, "snap", ("4-listening",)),
    (0.2, "status", ("Thinking",)),
    (0.1, "turn", ("You", "What is the weather in Lisbon?")),
    (2.0, "snap", ("5-thinking",)),
    (0.2, "status", ("Speaking",)),
    (0.1, "turn", ("Apollo", "It is twenty-two degrees and partly cloudy in Lisbon right now.")),
    (2.0, "snap", ("6-answer",)),
    (5.5, "snap", ("7-after-hold",)),
    (0.2, "status", ("Idle",)),
    (2.5, "snap", ("8-back-to-idle",)),
]


def run():
    app.window.evaluate_js(
        "window.__errs=[];"
        "window.onerror=(m,s,l,c)=>{window.__errs.push(m+' @'+l+':'+c);};"
        "'ready'"
    )
    for delay, kind, args in SCRIPT:
        time.sleep(delay)
        print(f"[{time.strftime('%H:%M:%S')}] {kind}{args}", flush=True)
        if kind == "snap":
            snap(*args)
            continue
        try:
            getattr(app.ui, kind)(*args)
        except Exception as e:
            print("  ERROR:", e, flush=True)

    print("JS errors:", app.window.evaluate_js("JSON.stringify(window.__errs)"), flush=True)
    print("final:", app.window.evaluate_js(
        "JSON.stringify({phase:core.phase, env:+core.env.toFixed(3),"
        " label:document.getElementById('statusLabel').textContent,"
        " qShown:document.getElementById('question').style.display!=='none',"
        " aShown:document.getElementById('answer').style.display!=='none',"
        " fit:core.fit, stars:(core.stars||[]).length})"), flush=True)
    app.quit()


app.window.events.loaded += lambda: threading.Thread(target=run, daemon=True).start()
# http_server, like apollo.main does: the page fetches its own sound
# effects and font by relative path, which file:// will not serve.
apollo.webview.start(http_server=True)
