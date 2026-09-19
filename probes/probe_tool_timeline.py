"""Event timeline of one tool turn: when does Gemini speak relative to the call?

Run:  .venv/Scripts/python.exe probes/probe_tool_timeline.py "Open Notepad."
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import gemini_live  # noqa: E402
import tools  # noqa: E402
from google import genai  # noqa: E402
from google.genai import types  # noqa: E402


async def main(text):
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    cfg = gemini_live._config(False, tools.gemini_declarations())
    async with client.aio.live.connect(model=gemini_live.MODELS[0], config=cfg) as s:
        t0 = time.monotonic()
        stamp = lambda: f"{time.monotonic() - t0:5.2f}s"
        await s.send_client_content(turns=types.Content(role="user", parts=[types.Part(text=text)]),
                                    turn_complete=True)
        completes = 0

        async def listen():
            nonlocal completes
            while True:
                async for msg in s.receive():
                    await handle(msg)

        async def handle(msg):
            nonlocal completes
            if msg.tool_call:
                for fc in msg.tool_call.function_calls:
                    print(stamp(), "TOOL_CALL", fc.name, dict(fc.args or {}))
                    await asyncio.sleep(0.4)
                    await s.send_tool_response(function_responses=[types.FunctionResponse(
                        id=fc.id, name=fc.name, response={"ok": True, "result": "Launched Notepad."})])
                    print(stamp(), "TOOL_RESPONSE sent")
            sc = msg.server_content
            if sc and sc.output_transcription and sc.output_transcription.text:
                print(stamp(), "SAID", repr(sc.output_transcription.text))
            if sc and sc.turn_complete:
                completes += 1
                print(stamp(), "TURN_COMPLETE", completes)
            if sc and sc.generation_complete:
                print(stamp(), "GENERATION_COMPLETE")

        try:
            await asyncio.wait_for(listen(), timeout=10)
        except asyncio.TimeoutError:
            pass
        print(stamp(), "end")


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "Open Notepad."))
