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
import logging
import os
import queue
import threading
import time

import sounddevice as sd
from google import genai
from google.genai import types

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

MODEL = "gemini-2.5-flash-native-audio-preview-09-2025"
VOICE = "Puck"
INPUT_RATE = 16000       # what we send
OUTPUT_RATE = 24000      # what Gemini sends back
BLOCK = 1600             # 100 ms of input per callback

CONNECT_TIMEOUT = 20     # seconds to wait for the websocket at startup
REPLY_TIMEOUT = 60       # ...and for one spoken answer to finish

# Gemini is answering as Apollo, so it needs Apollo's character and Apollo's
# length budget. Short, because this text is spoken: the whole point of this
# path is that the reply starts almost immediately, and a model that opens
# with a paragraph throws that away. Deliberately not `assistant.SYSTEM_PROMPT`
# - that one describes the Whisper-and-Claude pipeline, which is not the
# pipeline this reply is travelling down.
SYSTEM_INSTRUCTION = (
    "You are Apollo, a voice assistant running on the user's own Windows PC. "
    "You are speaking aloud, so keep it to one or two sentences unless they "
    "ask for detail. Never use markdown, bullet points or emoji. "
    "Your character is optimistic, game for a challenge, and firm: lead with "
    "the move rather than the difficulty, answer straight, and skip the "
    "hedging. Not cheerfulness, not bluster, not curtness - and above all not "
    "longer. If you do not know something, say so and say how you would find "
    "out."
)


def _config(auto_vad=False):
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
    cue from anyway. Detection is the model's job here, and it is told what it
    heard you say (`input_audio_transcription`) because with no key defining
    the turn, that transcript is the only way Apollo knows you spoke at all -
    and the only way it can tell an agent's name from ordinary conversation.
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
        input_audio_transcription=(
            types.AudioTranscriptionConfig() if auto_vad else None
        ),
        # No thinking pass. This is the voice of the assistant now - every
        # spoken turn comes through here - and what it has to be is quick.
        # Measured over three turns each: 5.50s to first word with it, 4.36s
        # without. Anything that wants deliberation is an agent's job, and an
        # agent is summoned by name rather than guessed at (see `agents`).
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        system_instruction=SYSTEM_INSTRUCTION,
        # Gemini's own words, in text, alongside the audio. Nothing is
        # synthesised from this - the audio is the reply - but the overlay has
        # a transcript line to draw, and without this the fast path would
        # answer out loud while the screen stayed blank.
        output_audio_transcription=types.AudioTranscriptionConfig(),
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
                 auto_vad=False, on_user_text=None):
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

        log.info("connected: model=%s voice=%s mode=%s", MODEL, VOICE,
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
        self._drain(self._play_q)
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
        """This turn is Gemini's. Let the audio through to the speakers."""
        self._play_open.set()

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
        # A thread queue, not an asyncio one: the reader is `next_turn`, called
        # from `run_loop` on an ordinary thread.
        self._turns = queue.Queue()
        self._stop = asyncio.Event()
        self._turn_over = asyncio.Event()

        client = genai.Client(api_key=self._api_key)
        tasks = []
        try:
            async with client.aio.live.connect(
                    model=MODEL, config=_config(self.auto_vad)) as session:
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
                    return_when=asyncio.FIRST_COMPLETED,
                )
                # Surface a task that died on its own rather than exiting as
                # if this were a normal shutdown.
                for task in done:
                    if task in tasks and task.exception() is not None:
                        raise task.exception()
        finally:
            # Order matters, and this is the order (module docstring, 1-3):
            # stop the callbacks, then stop the coroutines, then close the
            # devices - all of it while the loop is still running.
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
        self._speaker = sd.RawOutputStream(
            samplerate=OUTPUT_RATE, channels=1, dtype="int16",
        )
        self._mic.start()
        self._speaker.start()

    def _close_streams(self):
        for stream in (self._mic, self._speaker):
            if stream is None:
                continue
            try:
                stream.abort(ignore_errors=True)
            except Exception:
                pass
            try:
                stream.close(ignore_errors=True)
            except Exception:
                pass
        self._mic = self._speaker = None

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

                content = response.server_content
                if content is None:
                    continue

                heard = getattr(content, "input_transcription", None)
                if heard is not None and heard.text:
                    self._note_heard(heard.text)

                transcript = getattr(content, "output_transcription", None)
                if transcript is not None and transcript.text:
                    self._false_start = False   # a new generation is running
                if transcript is not None and transcript.text and not self._discarded:
                    self._reply.append(transcript.text)
                    if self._on_text:
                        try:
                            self._on_text(transcript.text)
                        except Exception:
                            pass

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
                    self._drain(self._play_q)
                    self._false_start = True
                    self._reply = []        # cut off mid-sentence; not worth keeping
                    log.debug("interrupted: generation abandoned")
                if content.turn_complete:
                    self._finish_turn()

    def _note_heard(self, text):
        """Your own words, as the model transcribes them. Always-listening only.

        Two jobs. It is the only signal that a turn has begun at all when no
        key defines one - and it is the last chance to take the turn away from
        Gemini, because `_on_user_text` is where an agent's name is spotted
        and answering it is somebody else's job. Both have to happen while the
        reply is still being composed; by `turn_complete` it has been spoken.
        """
        self._heard.append(text)
        self._in_flight = True
        if self._on_user_text is None or self._discarded:
            return
        try:
            if self._on_user_text("".join(self._heard).strip()):
                self.discard_reply()
        except Exception:
            pass          # a routing hiccup must not derail the conversation

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
            if self._turns is not None and (said or reply):
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
            await asyncio.to_thread(self._speaker.write, chunk)
            self._last_write = time.monotonic()
