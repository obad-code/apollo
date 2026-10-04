---
name: win-check
description: Check Apollo off Windows - run the test suite with the Windows modules stood in for, and take screenshots of the display with Playwright. Use after changing Apollo's Python or its display (ui/), before committing.
---

# Checking Apollo off Windows

Apollo is a Windows app; this container is Linux. Two checks stand in for running it.

## 1. Tests

```bash
PYTHONPATH=.claude/skills/win-check/shim python3 .claude/skills/win-check/runwin.py -q tests
```

`shim/sitecustomize.py` and `runwin.py` swap in mocks for `ctypes.windll`, pywin32, pycaw,
webview, sounddevice and the rest. Pass a single file to run fewer.

Known Windows-only failures here (not bugs): overlay_paint, fonts, overlay_gil (.NET),
clips (nvenc), scanner, scan_drop, desk_tabs (Windows paths), start_log. Anything else that
fails is real - fix it.

## 2. Screenshots of the display

```bash
python3 -m http.server 8765 --directory ui &      # serve the display
node .claude/skills/win-check/shot.mjs http://localhost:8765/full/index.html "$SCRATCH/shot.png" 1920 1080 "optional JS to run first"
```

Then read the PNG. It prints the page's console errors. Save screenshots to the scratchpad,
never the repo. Stop the server when done.

## Say honestly
What these cannot cover: the real overlay (GDI+), keyboard focus (WS_EX_NOACTIVATE), the
microphone, speakers and Gemini Live. Tell the user those are untested until run on their PC.
