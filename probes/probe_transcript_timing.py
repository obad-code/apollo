"""Does Gemini's input transcription stream while the chord is still held?

Sends a recorded sentence in real time between activity_start/activity_end,
with the receive loop running concurrently, and prints when each piece of
input transcription arrives relative to the end of speech. Negative times
mean it arrived while "you" were still talking.

Run:  .venv/Scripts/python.exe probes/probe_transcript_timing.py [model]
"""

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_live_models import config, sample_pcm16k  # noqa: E402
from google import genai  # noqa: E402
from google.genai import types  # noqa: E402


async def main(model):
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    async with client.aio.live.connect(model=model, config=config(True)) as s:
        pcm = sample_pcm16k()
        end = {"t": None}
        t0 = time.monotonic()

        async def recv():
            async for msg in s.receive():
                sc = msg.server_content
                now = time.monotonic()
                rel = (now - end["t"]) if end["t"] else (now - t0) - 99
                if sc and sc.input_transcription and sc.input_transcription.text:
                    print(f"input  {rel:+6.2f}s  {sc.input_transcription.text!r}")
                if sc and getattr(sc, "interim_input_transcription", None):
                    print(f"interim {rel:+6.2f}s {sc.interim_input_transcription}")
                if msg.data and not getattr(recv, "audio", False):
                    recv.audio = True
                    print(f"audio  {rel:+6.2f}s  first reply audio")
                if sc and sc.turn_complete:
                    print(f"done   {rel:+6.2f}s")
                    return

        task = asyncio.create_task(recv())
        await s.send_realtime_input(activity_start=types.ActivityStart())
        for i in range(0, len(pcm), 3200):
            await s.send_realtime_input(audio=types.Blob(data=pcm[i:i + 3200],
                                                         mime_type="audio/pcm;rate=16000"))
            await asyncio.sleep(0.1)
        end["t"] = time.monotonic()
        print(f"speech ended after {end['t'] - t0:.2f}s of audio")
        await s.send_realtime_input(activity_end=types.ActivityEnd())
        await asyncio.wait_for(task, 30)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "gemini-2.5-flash-native-audio-latest"))
