"""Apollo's voice: a live audio session with Gemini.

This is how Apollo talks now - all of it. Your microphone audio goes straight
to Gemini's native-audio model over a websocket and its spoken reply comes
back as audio, with nothing transcribed, re-prompted or re-synthesised in
between. Every spoken turn comes through here and comes back in Puck's voice,
whatever it was about. Claude is still in the building, but it is reached by
summoning an agent by name (see `agents`), never by saying something that
sounds technical.

There are two ways to hold a conversation with it, and `auto_vad` picks which:
push-to-talk, where the CTRL+ALT chord says when you are speaking, and
always-listening, where the model works that out for itself. They differ in
more than a flag - see `_config` for why, and for the failure mode that made
the distinction necessary rather than a preference.

Everything here is the pattern that was validated standalone on this machine
and is deliberately not improvised on: `sounddevice` rather than pyaudio,
because pyaudio has no wheel for Python 3.14 and no portaudio.h to build
against; int16 PCM at 16 kHz in and 24 kHz out, which is what the Live API
speaks; and the Puck voice, chosen after listening to all thirty.

The awkward part is that the Live API is asyncio and the rest of Apollo is
threads. So `LiveSession` owns a private event loop on a thread of its own and
presents an ordinary blocking object to its caller: start, begin_turn,
end_turn, wait_for_reply, next_turn, close. Nothing outside this file touches
asyncio.

--- Why the shutdown code looks the way it does ---------------------------

The obvious version of this module dies on Ctrl+C with "Event loop is closed".
PortAudio does not call the microphone callback on our thread - it calls it on
its own, from C, on a schedule of its own - so the callback is still running
after the interrupt has unwound the loop, and its `call_soon_threadsafe` lands
on a loop that no longer exists. Closing the stream is not instant either:
`close()` waits for the callback in flight, so the race is real rather than
theoretical.

Three things together fix it, and all three are needed:

  1. `_closing` is set before anything else is torn down, and the callback
     checks it first. From that moment the callback does nothing at all.
  2. The audio streams are stopped and closed *inside* the loop's own
     `finally`, while the loop is still running, so by the time it closes
     there is no callback left that could touch it.
  3. The callback re-checks `loop.is_closed()` and swallows the RuntimeError
     anyway, because 1 and 2 narrow the window rather than close it.
"""

import asyncio
import json
import logging
import os
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import numpy as np
import sounddevice as sd
from google import genai
from google.genai import types

import agents
import interests
import memory

log = logging.getLogger("apollo.gemini")

# Asking for `output_audio_transcription` means every reply carries text parts
# alongside the audio, and the SDK warns once per turn that it is handing back
# only the data parts. That is exactly what we want it to do - the transcript
# is read separately, off `server_content` - so the warning is noise on every
# single turn rather than information.
logging.getLogger("google_genai.types").setLevel(logging.ERROR)

# Queued in among the audio blocks to mark where a turn starts and stops. They
# go through the same queue as the audio rather than being sent directly, so
# they cannot overtake the speech they are describing.
_SPEECH_START = object()
_SPEECH_END = object()
_DISCARD = object()

# --- Settings --------------------------------------------------------------
#
# All four of these are load-bearing and were confirmed end to end before this
# module existed. The rates in particular are not preferences: the Live API
# sends 24 kHz and expects 16 kHz, and getting either wrong sounds like a
# chipmunk rather than like an error.

# Measured 2026-09-19 (probes/probe_live_models.py): the "latest" alias passes
# every check Apollo needs and is the quickest to first audio; the September
# preview is the proven fallback. gemini-3.8-live exists but this key has no
# quota for it. APOLLO_GEMINI_MODEL puts another model at the front.
MODELS = tuple(filter(None, (os.environ.get("APOLLO_GEMINI_MODEL"),
                             "gemini-2.5-flash-native-audio-latest",
                             "gemini-2.5-flash-native-audio-preview-09-2025")))
MODEL = MODELS[0]
VOICE = os.environ.get("APOLLO_VOICE") or "Puck"
# Affective dialog: the native-audio model hears how you say things and
# answers in a tone to match - warmer, livelier, quieter when you are. It is
# asked for first, and where the key or model does not offer it the session
# falls back to the plain voice it has always had. APOLLO_EXPRESSIVE=0 skips it.
EXPRESSIVE = (os.environ.get("APOLLO_EXPRESSIVE") or "1").strip() not in ("0", "false", "no")
INPUT_RATE = 16000       # what we send
OUTPUT_RATE = 24000      # what Gemini sends back
BLOCK = 1600             # 100 ms of input per callback
SLICE = 960              # 40 ms of reply per write - see `_write`

CONNECT_TIMEOUT = 20     # seconds to wait for the websocket at startup
REPLY_TIMEOUT = 60       # ...and for one spoken answer to finish

# Always-listening hears the room, and while Apollo talks the room is Apollo:
# his own voice out of the speakers, back into the microphone. Sent on, the
# model hears itself - it cuts itself off, takes its own words for yours, or
# answers itself, which is a repeated answer. So while he is talking, a block
# is only sent if it is louder than his echo is likely to be (you talking
# over him, close to the mic); everything quieter is left out. 0 turns the
# gate off - headphones need none. APOLLO_BARGE_IN sets it (0..1 RMS).
BARGE_IN = float(os.environ.get("APOLLO_BARGE_IN", "0.06") or 0)

# Gemini is answering as Apollo, so it needs Apollo's character and Apollo's
# length budget. Short, because this text is spoken: the whole point of this
# path is that the reply starts almost immediately, and a model that opens
# with a paragraph throws that away. Deliberately not `assistant.SYSTEM_PROMPT`
# - that one describes the Whisper-and-Claude pipeline, which is not the
# pipeline this reply is travelling down.
SYSTEM_INSTRUCTION = (
    "You are Apollo, a voice assistant running on the user's own Windows PC, "
    "answering out loud.\n\n"
    "Language: the user speaks only Arabic or English. Reply in the one they just "
    "spoke: Arabic in their dialect (they are Saudi), or English. Never reply in "
    "any other language, whatever you think you heard. Keep numbers as digits.\n\n"
    "Length: one or two sentences unless they ask for detail. No markdown, lists "
    "or emoji. Never read out a URL.\n\n"
    "Character: optimistic, game for a challenge, firm - lead with the move, "
    "answer straight, skip the hedging. Not cheerful filler, not bluster, not "
    "curt, and never longer.\n\n"
    "Voice: sound like a person, not a reader - natural pace, real warmth, "
    "energy when the news is good, calm when it is serious, a smile in it when "
    "they joke. Never flat, never sing-song.\n\n"
    "Finishing things: a request with several steps - open a site and search, "
    "open an app and send a message, find a video and play it - is done to the "
    "end, never left at the first step. Use the one tool that does it all "
    "(search_site, play_youtube, send_chat_message); otherwise call the tools one "
    "after another until it is done.\n\n"
    "Doing things: you control this PC through your tools. When the user asks "
    "you to do something - open or close an app or website, play or skip music, "
    "change the volume, move or switch windows, type text, press keys, set a "
    "reminder - call the tool first, before saying anything, then confirm "
    "once in a few words. If a tool reports a failure, say so plainly.\n\n"
    "Live information: for anything current - prices, news, scores, weather, "
    "what someone posted - use Google Search or your market tools; never answer "
    "from memory. For a stock, index, crypto or commodity call show_stock_chart "
    "or stock_quote (they draw it on screen) and speak only the numbers they "
    "return. Open TradingView only when asked.\n\n"
    "Your crew - four agents who work for you in the background, each with its "
    "own tool: LYLA does research and downloads videos (ask_lyla, "
    "download_video); THEIA is the professor who analyses any idea - analysis, "
    "critique and the best way to do it (ask_theia); MONEYPENNY is the markets "
    "desk - a stock or the whole watchlist with a verdict and red flags "
    "(ask_moneypenny); Q files a request for Claude to build a feature or fix "
    "something in you (request_feature). When the user names one of them, that "
    "is who gets the job. They never speak; when one finishes you are told, and "
    "you pass it on in your own voice. You decide who does what. "
    "For anything that takes more than a quick answer, think for a second about "
    "which is better: doing it yourself now, or handing it to the right agent "
    "and carrying on. The user's word always wins over that choice: if they say "
    "\"you do it\", \"انت حلل\", \"لا تعطيها احد\", do it yourself, fully, and never "
    "say it is someone else's job; if they name an agent, hand it to that agent. "
    "Never refuse a task because of whose job it is.\n\n"
    "Seeing: when the user refers to something on their screen - \"this\", "
    "\"here\", \"وش هذا\", a chart or an error they are looking at - call "
    "look_at_screen with their question before you answer.\n\n"
    "Showing: you can show as well as tell. When a picture would teach better "
    "than words - how something works, the steps of a process, the parts of an "
    "idea - lay it out with explain_visually while you speak; draw a picture "
    "with show_image when they ask to see something. A stock always gets its "
    "chart.\n\n"
    "Yourself: you know everything you can do - when asked what you can do or "
    "whether you can do something, call apollo_features and answer from it; "
    "never say you cannot do something it lists.\n\n"
    "Memory: when the user asks you to remember something, call remember. When "
    "they report a problem with you, call log_problem. When they ask you to make "
    "or save a file, call write_file - never type a file into Notepad.\n\n"
    "Safety: sleep, restart, shut down and sign out need the user's explicit yes. "
    "Ask first; call system_power with confirmed=true only after they say yes."
)


# What you speak, as the transcription is told it (BCP-47).
LANGUAGES = ("ar-SA", "en-US")
# Names it would otherwise spell as it pleased - and the agents are routed on
# the transcript by name, so a misspelt one is a summons missed.
VOCABULARY = ("Apollo", "LYLA", "OSIRIS", "Private Eye", "TradingView", *agents.NAMES)

_ARABIC = ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF))


def foreign(text):
    """True if a transcript is written in neither Arabic nor Latin letters -
    the transcription wandering into another language, not you speaking.
    Text with no letters at all (digits, punctuation) is not judged."""
    letters = [c for c in str(text or "") if c.isalpha()]
    if not letters:
        return False
    ours = sum(1 for c in letters
               if ord(c) < 0x250 or any(low <= ord(c) <= high for low, high in _ARABIC))
    return ours * 2 < len(letters)


def loud(data, threshold):
    """True if a block of int16 PCM is louder (RMS, 0..1) than `threshold`."""
    block = np.frombuffer(data, dtype=np.int16)
    if not block.size:
        return False
    rms = float(np.sqrt(np.mean((block.astype(np.float32) / 32768.0) ** 2)))
    return rms >= threshold


def system_instruction(now=None):
    """The instruction, what Apollo knows about you, and the date and time -
    fixed when a session opens. What it knows comes from `interests`, which
    learns it a day at a time from the record of what you say and open; it
    starts from the list this instruction used to carry by hand."""
    now = now or datetime.now()
    return (SYSTEM_INSTRUCTION
            + "\n\n" + interests.summary(interests.load())
            + _remembered(now)
            + f"\n\nRight now it is {now:%A %d %B %Y, %H:%M} in Riyadh.")


def _remembered(now):
    """What he was told to remember, and the talk so far - see `memory`."""
    try:
        kept = memory.summary(now)
    except Exception:  # noqa: BLE001 - a memory that cannot be read is no memory
        log.debug("memory unavailable", exc_info=True)
        return ""
    return "\n\n" + kept if kept else ""


def _config(auto_vad=False, tools=None, instruction=None, expressive=False):
    """The session settings. `auto_vad` picks which of the two modes this is.

    Push-to-talk (`auto_vad=False`, the default) tells the model when you are
    speaking. Automatic voice activity detection is the wrong tool there and
    fails in a specific, silent way: it decides you have stopped by *hearing*
    you stop, and Apollo stops sending the instant you release the chord. Cut
    off mid-word with no trailing silence to score, the detector never fires,
    and the turn hangs with no reply and no error - measured, not theorised.
    The chord is unambiguous, so `activity_start` / `activity_end` say so
    directly, and there is no silence threshold to wait out.

    Always-listening (`auto_vad=True`) is the case that failure mode does not
    apply to: nothing ever cuts the stream, so there is always trailing
    silence for the detector to hear, and there is no key press to take the
    cue from anyway. Detection is the model's job here.

    Both modes ask for `input_audio_transcription`: the model's transcript of
    you is Apollo's transcript now. It streams while you are still talking, so
    it is the live line on screen, and it is what agent names are routed on -
    in Arabic as well as English, which the local Whisper could not do.
    """
    detection = types.AutomaticActivityDetection(disabled=not auto_vad)
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE)
            )
        ),
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=detection,
        ),
        # Your words, transcribed by the model, in both modes: this is Apollo's
        # transcript of you now - the live line on screen and the agent-name
        # routing - and unlike the local Whisper it had, it understands Arabic.
        # Arabic and English only: left to detect the language itself, it
        # heard Telugu and Thai in Arabic speech and in the room's noise. The
        # names you call things by are its vocabulary, so they come out right.
        input_audio_transcription=types.AudioTranscriptionConfig(
            language_codes=list(LANGUAGES), custom_vocabulary=list(VOCABULARY)),
        # Apollo's tools, and Google Search for anything current.
        tools=([types.Tool(function_declarations=list(tools))] if tools else [])
              + [types.Tool(google_search=types.GoogleSearch())],
        # No thinking pass. This is the voice of the assistant now - every
        # spoken turn comes through here - and what it has to be is quick.
        # Measured over three turns each: 5.50s to first word with it, 4.36s
        # without. Anything that wants deliberation is an agent's job, and an
        # agent is summoned by name rather than guessed at (see `agents`).
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        system_instruction=instruction or system_instruction(),
        # Gemini's own words, in text, alongside the audio. Nothing is
        # synthesised from this - the audio is the reply - but the overlay has
        # a transcript line to draw, and without this the fast path would
        # answer out loud while the screen stayed blank.
        output_audio_transcription=types.AudioTranscriptionConfig(),
        # An audio session is cut off once its context fills - about fifteen
        # minutes of talk - and the reconnect that follows starts with no
        # memory of what was said. A sliding window lets the oldest turns go
        # instead, so a long conversation keeps going and keeps its thread.
        context_window_compression=types.ContextWindowCompressionConfig(
            sliding_window=types.SlidingWindow()),
        **({"enable_affective_dialog": True} if expressive else {}),
    )


def available():
    """True if there is a key to connect with. Checked before starting."""
    return bool(os.environ.get("GEMINI_API_KEY"))


class LiveSession:
    """One live audio conversation with Gemini, driven from ordinary threads.

    The microphone stream belongs to this object and runs for the whole life
    of the session, not per turn - opening a PortAudio stream costs a
    noticeable fraction of a second and doing it on every key press is exactly
    the latency this path exists to avoid. `begin_turn` and `end_turn` only
    open and close a gate on what gets forwarded.

    `on_audio`, if given, is handed every raw int16 block as it arrives, so
    the rest of Apollo can keep doing what it did with its own microphone
    stream - drive the orb's bloom, and run the local running transcription -
    without a second stream fighting for the device. It is called on
    PortAudio's thread: it must be cheap and must not touch the UI.

    `on_text` receives Gemini's reply as text, in fragments, as it is spoken.

    `auto_vad` picks the mode, and the two are different enough to be worth
    stating plainly. Push-to-talk (the default) is driven from outside: the
    caller says when a turn starts and stops, and reads the answer back with
    `wait_for_reply`. Always-listening is driven by the model: the microphone
    never closes, the model decides where your sentences end, and finished
    turns arrive through `next_turn`. The mode is fixed for the life of a
    session because it is part of the setup message - switching means closing
    this session and opening another, which is what `assistant` does when you
    press the toggle.

    `on_user_text` is always-listening only: it is handed your own words as
    the model transcribes them, and returning True from it abandons the reply
    Gemini is composing. That is how a summoned agent takes a turn away from a
    conversation that has already started answering it.
    """

    def __init__(self, on_audio=None, on_text=None, api_key=None,
                 auto_vad=False, on_user_text=None, tools=None,
                 on_tool_call=None, on_heard=None, on_activity=None,
                 on_user_turn=None, on_usage=None, models=None):
        self._on_audio = on_audio
        self._on_text = on_text
        self._on_user_text = on_user_text
        self.auto_vad = auto_vad
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY")

        self._thread = None
        self._loop = None
        self._session = None
        self._mic = None
        self._speaker = None
        # The speaker is written from a worker thread, hushed from the one you
        # interrupted on and closed from the loop, and PortAudio allows none
        # of those at once: a write that meets an abort ends the session
        # ("Stream is stopped"), and one that meets a close reads freed memory
        # and takes the whole app down. Everything that touches it holds this.
        self._speaker_lock = threading.Lock()
        self._hushes = 0    # bumped by hush: a write under way stops at its next slice

        # Cross-thread flags. `_closing` is checked by the PortAudio callback
        # and so is a threading.Event, not an asyncio one - see the module
        # docstring.
        self._closing = threading.Event()
        self._ready = threading.Event()      # connected, or failed trying
        self._reply_done = threading.Event()
        self._reply_done.set()
        self._error = None

        self._mic_open = threading.Event()   # forwarding to Gemini right now
        self._play_open = threading.Event()  # ...and allowed to be heard
        self._play_open.set()
        self._armed = False                  # a turn is running - see begin_turn
        # Both of these are the loop thread's alone. `_in_flight` says the
        # model has been asked for a reply and has not finished it; it is set
        # by the end-of-speech marker when the chord drives the turn, and by
        # the first words it hears when its own detector does. `_discarded`
        # says the ending still to come belongs to a turn nobody is listening
        # to any more.
        self._in_flight = False
        self._discarded = False
        self._false_start = False   # the model was cut off mid-reply
        self._last_write = 0.0      # monotonic time of the last block played

        self._reply = []        # Gemini's own words, as it speaks them
        self._heard = []        # ...and yours, when the model is transcribing
        self._turns = None      # finished turns, for always-listening
        self._out_q = None      # mic blocks waiting to be sent
        self._play_q = None     # reply audio waiting to be played
        self._stop = None       # asyncio.Event, set by close()
        self._turn_over = None  # asyncio.Event, set on turn_complete

        # Tools, and the live transcript of you. See `_dispatch_tool`.
        self._tools = list(tools or [])
        self._on_tool_call = on_tool_call
        self._on_heard = on_heard
        self._on_activity = on_activity
        self._on_user_turn = on_user_turn
        self._on_usage = on_usage
        self._models = tuple(models or MODELS)
        self.model = None               # whichever of `_models` connected
        self._epoch = 0                 # bumped by discard_reply; see _tool_allowed
        self._cancelled = set()         # tool call ids the server withdrew
        self._last_heard = 0.0          # when the last transcript fragment landed
        self._prompted = False          # the turn in flight was Apollo's own idea
        self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="apollo-tool")

    # -- lifecycle ----------------------------------------------------------

    def start(self, timeout=CONNECT_TIMEOUT):
        """Connect, and open the microphone. Raises RuntimeError if it can't.

        Blocks until the websocket is up so the caller knows, before the user
        has spoken a word, whether this path is available at all.
        """
        if not self._api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set.\n"
                "Get a key at https://aistudio.google.com/apikey then run:\n"
                '  setx GEMINI_API_KEY "..."\n'
                "...and open a NEW terminal (setx only affects new terminals)."
            )

        self._thread = threading.Thread(target=self._run, name="gemini-live",
                                        daemon=True)
        self._thread.start()

        if not self._ready.wait(timeout):
            self.close()
            raise RuntimeError(f"Gemini Live did not connect within {timeout}s.")
        if self._error is not None:
            raise RuntimeError(f"Gemini Live failed to connect: {self._error}")

        if self.auto_vad:
            # Nothing opens or closes the microphone in this mode: it is open
            # from here until the session is closed, and the model decides
            # where your sentences begin and end.
            self._mic_open.set()

        log.info("connected: model=%s voice=%s mode=%s", self.model, VOICE,
                 "always-listening" if self.auto_vad else "push-to-talk")
        return self

    def close(self):
        """Shut the session down and wait for the thread to finish.

        Safe to call twice, and safe to call from a signal handler - which is
        the whole reason it sets a flag and lets the loop do the work rather
        than tearing anything down from here.
        """
        self._closing.set()
        self._mic_open.clear()
        loop, stop = self._loop, self._stop
        if loop is not None and stop is not None and not loop.is_closed():
            try:
                loop.call_soon_threadsafe(stop.set)
            except RuntimeError:
                pass          # already on its way down; nothing to signal
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._reply_done.set()
        self._pool.shutdown(wait=False, cancel_futures=True)

    @property
    def alive(self):
        return (self._thread is not None and self._thread.is_alive()
                and not self._closing.is_set())

    # -- one turn -----------------------------------------------------------

    def begin_turn(self):
        """Start forwarding the microphone to Gemini.

        Playback is left shut. Which of the two models answers this turn is
        not known yet - that is decided from the transcript once you stop
        talking - so the audio streams out now for the latency, and the
        decision to let the answer be heard is made separately by
        `allow_reply` or `discard_reply`.
        """
        # `_armed` is what stops the new turn inheriting the old one's ending.
        # `_turn_over` is still set from last time and can only be cleared on
        # the loop's thread, so for the moment between those two the play loop
        # would otherwise see "Gemini has finished and the queue is empty",
        # call the turn over before a syllable of it exists, and hand
        # `wait_for_reply` an instant, silent answer. Disarmed here, rearmed by
        # `_arm` once the flag it depends on has actually been cleared - and
        # both of those happen on the loop thread, so the play loop can never
        # observe one without the other.
        self._armed = False
        self._play_open.clear()
        self._reply_done.clear()
        self._reply = []
        self._heard = []
        self._last_heard = 0.0
        self._prompted = False
        if self._on_user_turn is not None:
            try:
                self._on_user_turn()
            except Exception:
                pass
        self.hush()          # if he is mid-sentence, the press cuts him off
        loop = self._loop
        if loop is not None and not loop.is_closed():
            try:
                loop.call_soon_threadsafe(self._arm)
            except RuntimeError:
                pass
        self._mic_open.set()
        self._mark(_SPEECH_START)

    def _arm(self):
        """Loop thread: this turn may now be allowed to end. See `begin_turn`."""
        self._turn_over.clear()
        self._armed = True

    def end_turn(self):
        """Stop forwarding, and tell the model the turn is yours no longer.

        This is the message that makes it answer. With activity detection
        turned off (see `_config`) nothing else would: the model waits to be
        told, rather than waiting to hear a pause.
        """
        self._mic_open.clear()
        self._mark(_SPEECH_END)

    def _mark(self, marker):
        """Queue a turn boundary behind whatever audio is still in flight."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(self._offer, marker)
        except RuntimeError:
            pass

    def allow_reply(self):
        """This turn is Gemini's. Let the audio - and its words - through."""
        self._play_open.set()
        self._emit_reply()

    def discard_reply(self):
        """This turn belongs to an agent. Throw away whatever Gemini says back.

        Gemini heard the audio and is answering it regardless - there is no
        way to un-ask it - so the reply has to be dropped on this side. That
        means dropping all of it, including the parts that arrive *after* the
        next turn has already started: its audio, its transcript, and above
        all its `turn_complete`.

        That last one is the one that bites. Left alone it is read as the end
        of the *following* turn, which then finishes instantly with no audio
        and no words - a turn that silently does nothing, every time the one
        before it went to Claude. The marker goes through the send queue so it
        is ordered against `end_turn`, and the `_DISCARD` marker decides from
        `_in_flight` whether there is anything left to swallow.
        """
        self._epoch += 1            # cancels any tool call still waiting on the gate
        self._armed = False
        self._play_open.clear()
        self._drain(self._play_q)
        self._reply_done.set()
        self._mark(_DISCARD)

    def next_turn(self, timeout=0.25):
        """Always-listening only: the next finished turn, or None.

        Returns `(you_said, gemini_said)`. `gemini_said` is empty for a turn
        that was discarded, which is how the caller learns that a summoned
        agent now owes an answer. Polled rather than pushed because the caller
        is `assistant.run_loop`, an ordinary thread that also has a toggle key
        to watch - a callback would land on the session's event loop, which is
        the one place a slow reply must never run.
        """
        if self._turns is None:
            return None
        try:
            return self._turns.get(timeout=timeout)
        except queue.Empty:
            return None

    def reply_text(self):
        """What Gemini said this turn, in text, for the overlay to draw.

        Transcribed by the API from its own output rather than by us - the
        reply itself is audio, and this is a read-out of it, so it can lag the
        voice by a fragment and is only worth reading once the turn is over.
        """
        return "".join(self._reply).strip()

    # How long after the last block was written the speakers are still
    # sounding it: PortAudio buffers roughly this much ahead of the DAC.
    PLAY_TAIL = 0.35

    @property
    def playing(self):
        """True while reply audio is queued or still coming out of the speakers."""
        q = self._play_q
        queued = q is not None and not q.empty()
        return queued or (time.monotonic() - self._last_write) < self.PLAY_TAIL

    def spoke_since(self, moment):
        """True if any reply audio reached the speakers after `moment`
        (a time.monotonic() reading)."""
        return self._last_write >= moment

    def wait_until_quiet(self, timeout=REPLY_TIMEOUT):
        """Block until the reply has finished playing. True if it did.

        Always-listening's counterpart to `wait_for_reply`: there the turn is
        already over by the time the caller hears of it, and the only thing
        left to wait for is the sound.
        """
        deadline = time.monotonic() + timeout
        while self.playing and not self._closing.is_set():
            if time.monotonic() > deadline:
                return False
            time.sleep(0.05)
        return True

    def wait_for_reply(self, timeout=REPLY_TIMEOUT):
        """Block until Gemini has finished speaking. True if it finished."""
        return self._reply_done.wait(timeout)

    @staticmethod
    def _drain(q):
        if q is None:
            return
        while True:
            try:
                q.get_nowait()
            except (asyncio.QueueEmpty, AttributeError):
                return

    TOOL_GATE_TIMEOUT = 20.0

    def _dispatch_tool(self, call):
        """Run one tool call off the event loop, and answer it.

        In push-to-talk the model may call a tool before Apollo has read your
        transcript and decided the turn is Gemini's at all - "hey LYLA, open
        Chrome" must not open Chrome twice. So a call waits for the playback
        gate (`allow_reply`) and is cancelled if `discard_reply` comes first.
        """
        epoch = self._epoch
        name, args = call.name, dict(call.args or {})

        def work():
            if not self._tool_allowed(epoch):
                result = {"ok": False, "error": "Cancelled: this turn was handed to someone else."}
            elif self._on_tool_call is None:
                result = {"ok": False, "error": "No tools are available."}
            else:
                self._activity("tool", name)
                try:
                    result = self._on_tool_call(name, args)
                except Exception as e:  # noqa: BLE001
                    result = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            if call.id in self._cancelled:
                return
            self._reply_tool(call, result)

        self._pool.submit(work)

    def _tool_allowed(self, epoch):
        deadline = time.monotonic() + self.TOOL_GATE_TIMEOUT
        while not self._closing.is_set():
            if self._epoch != epoch:
                return False
            if self._play_open.is_set():
                return True
            if time.monotonic() > deadline:
                return False
            time.sleep(0.02)
        return False

    def _reply_tool(self, call, result):
        loop, session = self._loop, self._session
        if loop is None or loop.is_closed() or session is None:
            return
        payload = json.loads(json.dumps(result, default=str))
        response = types.FunctionResponse(id=call.id, name=call.name, response=payload)
        try:
            asyncio.run_coroutine_threadsafe(
                session.send_tool_response(function_responses=[response]), loop)
        except RuntimeError:
            pass

    def _activity(self, kind, detail=""):
        if self._on_activity is not None:
            try:
                self._on_activity(kind, detail)
            except Exception:
                pass

    # -- the private event loop ---------------------------------------------

    def _run(self):
        """The session thread: own loop, one coroutine, then a clean close.

        The loop is closed here and nowhere else, and only after `_main` has
        returned - which it does not do until the audio streams are shut. That
        ordering is the fix for "Event loop is closed"; see the module
        docstring.
        """
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._main())
        except Exception as e:          # noqa: BLE001 - reported, not raised
            self._error = e
            log.error("session ended: %s", e)
        finally:
            self._closing.set()
            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True))
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()
            self._loop = None
            self._ready.set()           # a failed start must not hang start()
            self._reply_done.set()

    async def _main(self):
        self._out_q = asyncio.Queue(maxsize=50)
        self._play_q = asyncio.Queue()
        self._turns = queue.Queue()
        self._stop = asyncio.Event()
        self._turn_over = asyncio.Event()

        last_error = None
        # The expressive voice first (it lives on the v1alpha API), then the
        # plain one, for each model in turn.
        tries = ([(True, genai.Client(api_key=self._api_key,
                                      http_options={"api_version": "v1alpha"}))] if EXPRESSIVE else [])
        tries.append((False, genai.Client(api_key=self._api_key)))
        for model in self._models:
            for expressive, client in tries:
                connected = False
                try:
                    async with client.aio.live.connect(
                            model=model, config=_config(self.auto_vad, self._tools,
                                                        expressive=expressive)) as session:
                        connected = True
                        self.model = model
                        self.expressive = expressive
                        await self._serve(session)
                    return
                except Exception as e:  # noqa: BLE001
                    if connected:
                        raise
                    last_error = e
                    log.warning("model %s%s unavailable: %s", model,
                                " (expressive)" if expressive else "", e)
        raise last_error or RuntimeError("no Gemini Live model is available")

    async def _serve(self, session):
        tasks = []
        try:
            self._session = session
            self._open_streams()
            self._ready.set()
            tasks = [
                asyncio.create_task(self._send_loop(), name="gemini-send"),
                asyncio.create_task(self._receive_loop(), name="gemini-recv"),
                asyncio.create_task(self._play_loop(), name="gemini-play"),
            ]
            done, _pending = await asyncio.wait(
                [asyncio.create_task(self._stop.wait()), *tasks],
                return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                if task in tasks and task.exception() is not None:
                    raise task.exception()
        finally:
            self._closing.set()
            self._mic_open.clear()
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            self._close_streams()
            self._session = None

    # -- audio devices ------------------------------------------------------

    def _open_streams(self):
        self._mic = sd.RawInputStream(
            samplerate=INPUT_RATE, blocksize=BLOCK, channels=1,
            dtype="int16", callback=self._mic_callback,
        )
        # APOLLO_OUTPUT_DEVICE picks the speakers by (part of) their name or
        # number, for when Windows' default is not where you are listening.
        wanted = (os.environ.get("APOLLO_OUTPUT_DEVICE") or "").strip()
        device = None
        if wanted:
            device = int(wanted) if wanted.isdigit() else wanted
        speaker = sd.RawOutputStream(
            samplerate=OUTPUT_RATE, channels=1, dtype="int16", device=device,
        )
        try:
            info = sd.query_devices(speaker.device, "output")
            log.info("speaker: %s", info.get("name"))
        except Exception:  # noqa: BLE001
            pass
        self._mic.start()
        speaker.start()
        with self._speaker_lock:      # handed over started, never half-way
            self._speaker = speaker

    def _close_streams(self):
        # The speaker under its lock: a write still running on its worker
        # thread - cancelling the task does not stop the thread - finishes its
        # slice first, and finds no speaker when it comes back for the next.
        with self._speaker_lock:
            speaker, self._speaker = self._speaker, None
            self._shut(speaker)
        self._shut(self._mic)
        self._mic = None

    @staticmethod
    def _shut(stream):
        if stream is None:
            return
        try:
            stream.abort(ignore_errors=True)
        except Exception:
            pass
        try:
            stream.close(ignore_errors=True)
        except Exception:
            pass

    def _write(self, chunk):
        """The reply's audio to the sound card, on a worker thread.

        A slice at a time, each under the speaker's lock, so a hush or a close
        waits no longer than one slice and never lands in the middle of a
        write - and the rest of a chunk that was hushed is not played after it.
        """
        hushes = self._hushes
        step = SLICE * 2          # int16: two bytes a sample
        for at in range(0, len(chunk), step):
            with self._speaker_lock:
                speaker = self._speaker
                if speaker is None or self._hushes != hushes:
                    return
                speaker.write(chunk[at:at + step])

    def _mic_callback(self, indata, _frames, _time, status):
        """PortAudio's thread, not ours. Cheap, and defensive about the loop."""
        if self._closing.is_set():
            return
        if status:
            log.debug("input status: %s", status)

        data = bytes(indata)

        if self._on_audio is not None:
            try:
                self._on_audio(data)
            except Exception:
                pass          # a UI hiccup must never break the recording

        if not self._mic_open.is_set():
            return
        if self.auto_vad and BARGE_IN > 0 and self.playing and not loud(data, BARGE_IN):
            return            # his own voice coming back; see BARGE_IN

        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(self._offer, data)
        except RuntimeError:
            pass              # the loop closed between the check and the call

    def _offer(self, data):
        """Queue a block for sending, dropping it if we are behind."""
        try:
            self._out_q.put_nowait(data)
        except asyncio.QueueFull:
            pass              # a late block is worse than a missing one

    # -- the three coroutines -----------------------------------------------

    async def _send_loop(self):
        while True:
            data = await self._out_q.get()
            if self._closing.is_set():
                return
            if data is _SPEECH_START:
                await self._session.send_realtime_input(
                    activity_start=types.ActivityStart())
                continue
            if data is _SPEECH_END:
                await self._session.send_realtime_input(
                    activity_end=types.ActivityEnd())
                # A reply has been asked for and is now owed an ending.
                self._in_flight = True
                continue
            if data is _DISCARD:
                # Nothing is owed if the reply already finished while the
                # route was being decided - then there is no stray ending to
                # swallow, and swallowing one would strand the next turn.
                self._discarded = self._in_flight
                continue
            await self._session.send_realtime_input(
                audio={"data": data, "mime_type": f"audio/pcm;rate={INPUT_RATE}"}
            )

    async def _receive_loop(self):
        while not self._closing.is_set():
            async for response in self._session.receive():
                if data := response.data:
                    # Audio means a generation is under way, so whatever was
                    # interrupted before it is behind us - see `_false_start`.
                    self._false_start = False
                    # `_discarded` outranks the playback gate: the next turn
                    # may already have opened it, and the tail of an abandoned
                    # reply must not come out of the speakers under its name.
                    if self._play_open.is_set() and not self._discarded:
                        self._play_q.put_nowait(data)
                    continue

                if response.tool_call is not None:
                    for call in response.tool_call.function_calls or []:
                        self._dispatch_tool(call)
                    continue
                withdrawn = getattr(response, "tool_call_cancellation", None)
                if withdrawn is not None:
                    self._cancelled.update(withdrawn.ids or [])
                    continue

                meta = getattr(response, "usage_metadata", None)
                if meta is not None:
                    self._note_usage(meta)

                content = response.server_content
                if content is None:
                    continue

                heard = getattr(content, "input_transcription", None)
                if heard is not None and heard.text:
                    self._note_heard(heard.text)

                # Google Search runs as code on the model's side; seeing it is
                # the only sign a search is under way, so the overlay can say so.
                turn = getattr(content, "model_turn", None)
                if turn is not None and any(getattr(p, "executable_code", None)
                                            for p in (turn.parts or [])):
                    self._activity("search", "")

                transcript = getattr(content, "output_transcription", None)
                if transcript is not None and transcript.text:
                    self._false_start = False   # a new generation is running
                if transcript is not None and transcript.text and not self._discarded:
                    self._reply.append(transcript.text)
                    self._emit_reply()

                if content.interrupted:
                    # The model answers eagerly - in always-listening it will
                    # often start replying before you have finished your
                    # sentence - and carrying on talking cuts it off. What
                    # follows is an `interrupted` and then a `turn_complete`,
                    # and that ending is a false start rather than an answer:
                    # your utterance is still going, and the real reply comes
                    # after it. Reporting it as a finished turn is what made a
                    # reply arrive one chunk long and the rest of it land
                    # under the next turn's name.
                    #
                    # The flag clears itself the moment any new output
                    # appears, so it can only ever swallow the ending that
                    # belongs to the generation it just watched die - never an
                    # unrelated turn later on.
                    self.hush()      # you spoke over him; stop the speakers
                    self._false_start = True
                    self._reply = []        # cut off mid-sentence; not worth keeping
                    log.debug("interrupted: generation abandoned")
                if content.turn_complete:
                    self._finish_turn()
                    if self.auto_vad:
                        self._finish_turn_transcript()

    def _note_usage(self, meta):
        """Tokens as the server reports them, for the day's ledger."""
        if self._on_usage is None:
            return
        try:
            self._on_usage(int(getattr(meta, "prompt_token_count", 0) or 0),
                           int(getattr(meta, "response_token_count", 0) or 0))
        except Exception:
            pass          # a ledger must never cost a turn

    def hush(self):
        """Stop talking now, not at the end of the sentence.

        Draining the queue is not enough. The queue holds what has not been
        written yet; the sound card holds what has, and a RawOutputStream's
        `stop` plays that out before it returns. `abort` throws it away, which
        is the difference between Apollo going quiet when you speak and Apollo
        finishing his sentence over you.
        """
        self._play_open.clear()
        self._drain(self._play_q)
        with self._speaker_lock:
            self._hushes += 1
            speaker = self._speaker
            if speaker is None:
                return
            try:
                speaker.abort()
                speaker.start()
            except Exception:  # noqa: BLE001 - a device that will not flush is
                pass           # still a device that should keep working

    def _finish_turn_transcript(self):
        """Forget what was heard, so the next sentence stands on its own.

        `begin_turn` does this for push-to-talk. Always-listening has no press
        to begin anything, so nothing emptied the buffer and every sentence
        was shown stuck onto every sentence before it - which is why what
        appeared on screen was not what had just been said.
        """
        self._heard = []
        self._last_heard = 0.0

    def _note_heard(self, text):
        """Your own words, as the model transcribes them - both modes now."""
        if foreign(text):
            log.debug("transcript in another script, not taken: %r", text)
            return
        first = not self._heard
        self._heard.append(text)
        self._last_heard = time.monotonic()
        self._in_flight = True
        if first and self.auto_vad and self._on_user_turn is not None:
            try:
                self._on_user_turn()
            except Exception:
                pass
        if self._on_heard is not None:
            try:
                self._on_heard("".join(self._heard).strip())
            except Exception:
                pass
        if not self.auto_vad or self._on_user_text is None or self._discarded:
            return
        try:
            if self._on_user_text("".join(self._heard).strip()):
                self.discard_reply()
        except Exception:
            pass          # a routing hiccup must not derail the conversation

    def heard_text(self, settle=0.35, timeout=1.5):
        """Push-to-talk: your words, once the transcript has stopped arriving.

        Measured: fragments stream while the chord is held, and the last one
        lands about 0.2 s after release - so this waits for `settle` seconds
        of quiet (or `timeout`) and returns the whole sentence, or "" if the
        model heard nothing.
        """
        start = time.monotonic()
        while True:
            now = time.monotonic()
            if self._heard and now - max(self._last_heard, start) >= settle:
                break
            if now - start >= timeout:
                break
            time.sleep(0.03)
        return "".join(self._heard).strip()

    def _emit_reply(self):
        if (self._on_text is not None and self._play_open.is_set()
                and not self._discarded and self._reply):
            try:
                self._on_text(self.reply_text())
            except Exception:
                pass

    def prompt(self, text):
        """Have Apollo say something nobody asked for - a reminder, the briefing."""
        loop, session = self._loop, self._session
        if loop is None or loop.is_closed() or session is None or self._closing.is_set():
            return False
        self._play_open.set()
        self._reply = []
        self._prompted = True
        content = types.Content(role="user", parts=[types.Part(text=text)])
        try:
            asyncio.run_coroutine_threadsafe(
                session.send_client_content(turns=content, turn_complete=True),
                loop).result(timeout=5)
            return True
        except Exception as e:  # noqa: BLE001
            log.warning("prompt failed: %s", e)
            self._prompted = False
            return False

    def wait_for_audio(self, timeout=10):
        """Block until reply audio has started playing. True if it did."""
        deadline = time.monotonic() + timeout
        while not self.playing and not self._closing.is_set():
            if time.monotonic() > deadline:
                return False
            time.sleep(0.03)
        return self.playing

    def _finish_turn(self):
        """A turn is over: hand it to the caller and reset for the next one."""
        if self._false_start:
            # Not an answer's ending - an interruption's. You are still
            # mid-sentence, so `_heard` stays exactly where it is and
            # `_in_flight` stays true: the real reply is still to come.
            self._false_start = False
            log.debug("turn_complete swallowed (false start)")
            return

        said, reply = "".join(self._heard).strip(), self.reply_text()
        discarded = self._discarded

        self._in_flight = False
        self._discarded = False
        if not discarded:
            self._turn_over.set()
        # ...and when it *was* discarded, `_turn_over` is deliberately left
        # alone: that ending belongs to a turn nobody is listening to, and
        # raising it would end the next one before it had said a word. See
        # `discard_reply`.

        if self.auto_vad:
            # Nothing else opens the gate in this mode, and `discard_reply`
            # shut it. Every new turn starts audible; it is the agent check
            # that closes it again, per turn.
            self._play_open.set()
            self._heard, self._reply = [], []
            log.debug("turn done: discarded=%s said=%r reply=%r",
                      discarded, said[:40], reply[:40])
            # A turn Apollo started itself (`prompt`) with nobody speaking is
            # already on screen and in the air; the caller that prompted it
            # waits for it, so it is not queued as if you had said something.
            prompted, self._prompted = self._prompted, False
            if self._turns is not None and (said or reply) and not (prompted and not said):
                self._turns.put((said, "" if discarded else reply))

    async def _play_loop(self):
        """Write reply audio to the speakers, and decide when a turn is over.

        The timeout is what makes the second half work: a turn has ended only
        once Gemini says it has *and* there is nothing left queued, and with a
        plain blocking `get()` there would be no moment at which to notice
        that both are true.
        """
        while not self._closing.is_set():
            try:
                chunk = await asyncio.wait_for(self._play_q.get(), timeout=0.1)
            except asyncio.TimeoutError:
                if self._armed and self._turn_over.is_set():
                    self._armed = False
                    self._reply_done.set()
                continue

            if self._closing.is_set() or self._speaker is None:
                return
            # Blocking in C: off the loop, or the receive loop stalls behind
            # the sound card and the reply arrives in stutters.
            await asyncio.to_thread(self._write, chunk)
            self._last_write = time.monotonic()
