"""Which Gemini Live model should be Apollo's voice? Measure, don't guess.

For each candidate this opens a real session with the configuration Apollo
needs - Puck, manual activity detection (push-to-talk), both transcriptions,
function calling and Google Search - and runs three turns:

  1. text  -> must call `open_app` (a fake tool; nothing is launched)
  2. text  -> a current-events question, to exercise Google Search
  3. audio -> a recorded sentence sent between activity_start/activity_end,
              which must come back as an input transcription and an answer

Run:  .venv/Scripts/python.exe probes/probe_live_models.py [model ...]

Needs GEMINI_API_KEY. Uses the network and costs a few cents.
"""

import asyncio
import os
import sys
import time
import wave

import numpy as np
from google import genai
from google.genai import types

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANDIDATES = ["gemini-3.8-live", "gemini-2.5-flash-native-audio-latest",
              "gemini-2.5-flash-native-audio-preview-09-2025"]
SAMPLE = os.path.join(HERE, "voicebox_samples", "1-george.wav")

OPEN_APP = types.FunctionDeclaration(
    name="open_app",
    description="Launch an application on the user's Windows PC by name.",
    parameters_json_schema={
        "type": "object",
        "properties": {"name": {"type": "string", "description": "App name"}},
        "required": ["name"],
    },
)


def config(thinking):
    kw = dict(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck"))),
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(disabled=True)),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        tools=[types.Tool(function_declarations=[OPEN_APP]),
               types.Tool(google_search=types.GoogleSearch())],
        system_instruction=("You are Apollo, a voice assistant on the user's PC. "
                            "Use open_app to open applications. Use Google Search "
                            "for anything current. Answer in one short sentence."),
    )
    if thinking:
        kw["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
    return types.LiveConnectConfig(**kw)


def sample_pcm16k():
    with wave.open(SAMPLE, "rb") as w:
        rate = w.getframerate()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32)
    n = int(len(pcm) * 16000 / rate)
    out = np.interp(np.linspace(0, len(pcm) - 1, n), np.arange(len(pcm)), pcm)
    return out.astype("<i2").tobytes()


async def collect(session, on_tool=None, limit=45):
    """Read one turn. Returns dict of what arrived."""
    got = {"audio": 0, "first_audio": None, "said": "", "heard": "", "tools": [],
           "grounded": False}
    t0 = time.monotonic()
    async for msg in session.receive():
        if time.monotonic() - t0 > limit:
            break
        if msg.data:
            got["audio"] += len(msg.data)
            if got["first_audio"] is None:
                got["first_audio"] = round(time.monotonic() - t0, 2)
        if msg.tool_call:
            for fc in msg.tool_call.function_calls or []:
                got["tools"].append((fc.name, dict(fc.args or {})))
                if on_tool:
                    await on_tool(fc)
        sc = msg.server_content
        if sc:
            if sc.input_transcription and sc.input_transcription.text:
                got["heard"] += sc.input_transcription.text
            if sc.output_transcription and sc.output_transcription.text:
                got["said"] += sc.output_transcription.text
            if getattr(sc, "grounding_metadata", None):
                got["grounded"] = True
            if sc.turn_complete:
                break
    got["secs"] = round(time.monotonic() - t0, 2)
    return got


async def probe(model):
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    result = {"model": model}
    for thinking in (True, False):
        try:
            async with client.aio.live.connect(model=model, config=config(thinking)) as s:
                result["thinking_budget_0"] = thinking

                async def answer(fc):
                    await s.send_tool_response(function_responses=[types.FunctionResponse(
                        id=fc.id, name=fc.name, response={"ok": True, "result": "Launched Notepad."})])

                await s.send_client_content(turns=types.Content(role="user", parts=[
                    types.Part(text="Open Notepad for me.")]), turn_complete=True)
                result["tool_turn"] = await collect(s, on_tool=answer)

                await s.send_client_content(turns=types.Content(role="user", parts=[
                    types.Part(text="What was the closing price of Nvidia stock on the most recent trading day?")]),
                    turn_complete=True)
                result["search_turn"] = await collect(s)

                pcm = sample_pcm16k()
                await s.send_realtime_input(activity_start=types.ActivityStart())
                for i in range(0, len(pcm), 3200):
                    await s.send_realtime_input(audio=types.Blob(
                        data=pcm[i:i + 3200], mime_type="audio/pcm;rate=16000"))
                    await asyncio.sleep(0.1)
                await s.send_realtime_input(activity_end=types.ActivityEnd())
                result["audio_turn"] = await collect(s)
                result["ok"] = True
                return result
        except Exception as e:  # noqa: BLE001 - this is a probe; report and move on
            result[f"error_thinking_{thinking}"] = f"{type(e).__name__}: {str(e)[:200]}"
    result["ok"] = False
    return result


def main():
    models = sys.argv[1:] or CANDIDATES
    for m in models:
        r = asyncio.run(probe(m))
        print("=" * 72)
        for k, v in r.items():
            print(f"{k:18} {v}")


if __name__ == "__main__":
    main()
