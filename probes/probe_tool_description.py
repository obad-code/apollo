"""Why save_clip's description is worded the way it is.

Measured 2026-09-20 against gemini-2.5-flash-native-audio-latest: a tool
description can make the Live API close the session with "1011 Internal error
occurred" the instant the model goes to call it. The argument types and the
user's phrasing were red herrings - integers are fine, Arabic is fine, "clip
that" is fine. The description is what decides it.

Run:  .venv/Scripts/python.exe probes/probe_tool_description.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import gemini_live  # noqa: E402
import tools  # noqa: E402
from google.genai import types  # noqa: E402

BROKE = ("Save what just happened on screen to a video file - the last 60 seconds by "
         "default. Use for 'clip that', 'save the last minute', 'record that'.")
WORKS = ("Save the last N seconds of the screen to a video file. N is the seconds "
         "argument, 60 if the user does not say.")


def trial(label, description, prompt="Clip the last ten seconds."):
    declaration = types.FunctionDeclaration(
        name="save_clip", description=description,
        parameters_json_schema={"type": "object", "properties": {
            "seconds": {"type": "integer", "description": "How far back to save, 5-60"}},
            "required": []})
    calls = []
    live = gemini_live.LiveSession(
        on_tool_call=lambda name, args: (calls.append((name, args)),
                                         {"ok": True, "seconds": 10, "path": "x.mp4"})[1],
        tools=[declaration])
    live.start()
    tools.new_user_turn()
    live.prompt(prompt)
    for _ in range(20):
        time.sleep(1)
        if not live.alive or (live.reply_text() and not live.playing):
            break
    print(f"{label:22} alive={live.alive} calls={calls} said={live.reply_text()[:44]!r}")
    live.close()


if __name__ == "__main__":
    trial("description that broke", BROKE)
    trial("description we ship", WORKS)
