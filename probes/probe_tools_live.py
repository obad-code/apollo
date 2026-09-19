"""End-to-end: does Gemini actually drive Apollo's tools?

Sends typed requests into a real Gemini Live session (the same one Apollo
uses) and lets it call the real tools - it WILL open and close Notepad, read
the volume, fetch market data and open a TradingView tab. Power actions are
replaced by a recorder, so nothing can sleep or shut the PC down.

Run:  .venv/Scripts/python.exe probes/probe_tools_live.py
"""

import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gemini_live  # noqa: E402
import pc_control  # noqa: E402
import tools  # noqa: E402

POWER = []
pc_control._run = lambda argv: POWER.append(argv)
pc_control._suspend = lambda: POWER.append("sleep")

STEPS = [
    "Open Notepad.",
    "Close Notepad.",
    "What's my volume at right now?",
    "Show me Nvidia's chart for the last five days.",
    "How are Apple and Tesla doing today?",
    "Remind me in 45 minutes to stretch.",
    "What reminders do I have?",
    "Cancel the stretch reminder.",
    "افتح المفكرة",
    "سكّر المفكرة",
    "Shut down the computer.",
    "Open the TradingView chart for Nvidia.",
]


def main():
    calls, shown = [], []

    def run_tool(name, args):
        result = tools.run(name, args, tools.Context(show=shown.append))
        calls.append((name, args, result))
        return result

    live = gemini_live.LiveSession(
        on_tool_call=run_tool, tools=tools.gemini_declarations(), auto_vad=False)
    live.start()
    print("model:", live.model)
    try:
        for step in STEPS:
            tools.new_user_turn()
            before = len(calls)
            t0 = time.monotonic()
            live.prompt(step)
            live.wait_for_audio(timeout=15)
            live.wait_until_quiet(timeout=40)
            time.sleep(0.5)
            print("=" * 70)
            print("USER :", step)
            for name, args, result in calls[before:]:
                print("TOOL :", name, args, "->", {k: result[k] for k in list(result)[:4]})
            print("SAID :", live.reply_text())
            print(f"TIME : {time.monotonic() - t0:.1f}s")
    finally:
        live.close()
    print("=" * 70)
    print("visuals shown:", len(shown), "| power calls (must be []):", POWER)


if __name__ == "__main__":
    main()
