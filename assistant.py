"""A minimal Windows voice assistant.

Hold CTRL+ALT, speak, release - or press CTRL+1 once and just talk. Either
way your voice goes to Gemini Live and Apollo answers in Puck's voice, and
that is true of everything you say to it: chat, a quick command, a question
about your own code. One assistant, one voice.

Claude is still here and still has the tools, but it belongs to the seven
agents now and is reached by calling one of them by name - see `agents`, which
is the only module that touches `ask_claude`. Conversation cannot get there,
deliberately: routing by keyword meant the voice you were answered in changed
depending on whether your sentence sounded technical.

Run this file for the console version, or `apollo.py` for the always-on desktop
overlay. Both share everything below; only the reporting differs.

The console version quits on ESC. The overlay does not - see `run_loop`.
"""

import ctypes
import io
import json
import logging
import os
import pathlib
import sys
import threading
import time
import urllib.error
import urllib.request
import wave

import anthropic
import keyboard
import numpy as np
import pyttsx3
import sounddevice as sd
from faster_whisper import WhisperModel

import agents
import briefing
import gemini_live
import journal
import overlay_content
import router
import tools
import usage


def load_env(path=None):
    """Read .env into the environment, without adding a dependency.

    Called at import, before anything looks at os.environ. Existing variables
    win, so a real Windows environment variable still overrides the file and
    `set FISH_API_KEY=` for one session behaves the way you would expect.
    """
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # Set, don't overwrite: the real environment is the stronger source.
            if key and key not in os.environ:
                os.environ[key] = value


load_env()

# huggingface_hub warns on every download that Windows without Developer Mode
# can't symlink its cache. It works regardless; the warning is only noise.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

# Four voices, tried in order: Fish Audio in the cloud, then VoiceBox over its
# local REST API, then Piper, then Windows SAPI (pyttsx3). Each fallback is a
# step down in quality, not a failure - a missing engine, a dead server or an
# empty credit balance degrades the voice instead of refusing to start.
try:
    import piper
    from piper.download_voices import download_voice
except ImportError:
    piper = None

# --- Settings you might want to change -------------------------------------

HOTKEY = "ctrl+alt"         # hold this to talk
LISTEN_TOGGLE = "ctrl+1"    # ...or press this once to stop having to hold it
SAMPLE_RATE = 16000         # what Whisper expects
WHISPER_SIZE = "small"      # multilingual (Arabic + English); a backup now - see WhisperBackup
CLAUDE_MODEL = "claude-opus-5"
VOICE_RATE = 185            # words per minute for the spoken reply
MIN_SECONDS = 0.4           # ignore accidental taps shorter than this
# Turning mic RMS into the 0-1 number the orb blooms on. Measured on this
# machine: a silent room sits at about 0.00001 RMS and never crossed 0.0004,
# so the gate below is comfortably above the floor without clipping a quiet
# voice. The exponent is perceptual - linear RMS barely moves for ordinary
# speech and the orb would only react to shouting.
VOICE_FLOOR = 0.002         # below this is silence, not you
VOICE_FULL = 0.12           # RMS that counts as full voice
VOICE_CURVE = 0.6
GREETING = "Systems online."  # spoken once at startup

# Fish Audio, the primary voice. Unlike everything else in Apollo this one is
# a cloud service: the text of each reply is sent to Fish's servers to be
# synthesised, and it is billed per use. Your microphone audio still never
# leaves the machine - Whisper is local - but the reply text does.
#
# FISH_VOICE is a voice model id from https://fish.audio. The default is a
# British female voice tagged energetic, cheerful, enthusiastic, bright,
# friendly - optimistic without being chirpy, which is the character the
# system prompt asks for. Search for others with
#   GET https://api.fish.audio/model?title=<name>
FISH_URL = "https://api.fish.audio"
FISH_VOICE = "a4c68282850b4568bc92749fa2c16815"   # "British" - bright, energetic
FISH_BACKEND = "s1"        # s1 is the current best; speech-1.6 is cheaper
FISH_CONNECT_TIMEOUT = 6   # the startup key and credit check only
FISH_TIMEOUT = 30          # synthesising one reply

# VoiceBox, the first fallback. A local server, so this is a loopback call and
# nothing leaves the machine. Used whenever Fish is unavailable, which also
# makes it the offline voice. VOICEBOX_PROFILE is matched against the `name`
# field of GET /profiles at startup; create or rename profiles in the VoiceBox
# UI rather than hardcoding an id here, since ids change if a profile is
# rebuilt. VOICE_RATE does not apply to it - POST /generate has no speed knob,
# so that setting now only shapes the Piper and SAPI fallbacks.
VOICEBOX_URL = "http://127.0.0.1:17493"
VOICEBOX_PROFILE = "Apollo Emma"     # British female, Kokoro bf_emma
VOICEBOX_ENGINE = "kokoro"           # CPU-friendly; this box has no GPU
VOICEBOX_CONNECT_TIMEOUT = 3         # the startup health check only
VOICEBOX_TIMEOUT = 45                # generating and fetching one reply

# Piper, the second fallback. Any name from
# https://huggingface.co/rhasspy/piper-voices works - en_GB-alba-medium is a
# Scottish female voice, en_US-lessac-medium an American one. Downloaded
# once into voices/ on first run, the same way Whisper caches.
PIPER_VOICE = "en_GB-jenny_dioco-medium"
PIPER_NATURAL_WPM = 175     # about what the model speaks at unscaled

HERE = os.path.dirname(os.path.abspath(__file__))
VOICES_DIR = os.path.join(HERE, "voices")

SYSTEM_PROMPT = (
    "You are Apollo, a voice assistant running on the user's own Windows PC. "
    "You hear them through a Whisper model on that PC when they hold "
    "Control+Alt to talk, and you appear as a small overlay at the top of "
    "their screen. Treat questions about your microphone, your hotkey or your "
    "own setup as questions about this PC - never ask which app or service "
    "you are. Reply in the language the user spoke - Arabic or English.\n\n"
    "Be accurate about what is local and what is not, because they may be "
    "deciding what is safe to say near you. Their microphone audio never "
    "leaves the machine: recording and transcription both happen on this PC. "
    "What does leave is text - their transcribed words go to the Claude API "
    "for you to answer, and the text of your reply goes to Fish Audio, a "
    "cloud service, to be spoken. If Fish is unreachable or "
    "out of credit you fall back to a local voice instead, so the voice they "
    "hear may be either; say so rather than claiming your voice is definitely "
    "local. Never overstate the privacy in either direction.\n\n"
    "Your replies are read aloud by a "
    "text-to-speech engine, so keep them short and conversational: two or "
    "three sentences unless the user explicitly asks for detail. Never use "
    "markdown, bullet points, code blocks, or emoji, because they are "
    "unpleasant when spoken. Spell out symbols and abbreviations the way a "
    "person would say them.\n\n"
    "Your character is optimistic, game for a challenge, and firm. Treat every "
    "problem as solvable and say what the way forward is: lead with the move, "
    "not with the difficulty. When a task is big or unfamiliar, take it on "
    "readily and name the first step rather than listing everything that could "
    "go wrong. Be firm - answer straight, commit to your best judgement, and "
    "skip the hedging and the piled-up caveats. If the user is wrong about "
    "something that matters, say so plainly in one sentence and give them the "
    "right answer; do not soften it into agreement. If you genuinely do not "
    "know, say that outright and say how you would find out - that is firmness "
    "too, not a failure.\n\n"
    "Three ways that character gets faked, all of which you avoid. It is not "
    "cheerfulness: no exclamations, no pep talks, no praising the user or their "
    "questions, no 'great idea' or 'happy to help'. It is not bluster: never "
    "claim something works when you have not checked, and never promise an "
    "outcome you cannot deliver - real optimism survives contact with bad news, "
    "so when something has genuinely failed, say so first and directly, then "
    "say what you would try next. It is not curtness: firm means clear and "
    "unhedged, never clipped or cold. Above all it is not longer - character "
    "shows in which words you choose, not in how many, so the two or three "
    "sentences above are still the whole budget.\n\n"
    "Hold that budget, because it is the rule most easily lost. Three sentences "
    "is the ceiling for an ordinary answer and one is often enough - 'Four.' is "
    "a complete reply to what two plus two is. Never write a blank line or a "
    "second paragraph: it is one spoken breath, not a document. Cut the "
    "throat-clearing and the summary at the end; say the thing once. End with a "
    "question back to the user only when you genuinely cannot proceed without "
    "their answer, not as a way to be helpful - an offer they did not ask for "
    "costs them a whole turn to decline. In particular, stop closing with "
    "'Want me to open...?' or 'Shall I...?'. If the request was really a "
    "command, just call the tool and say what you did; if it was a question, "
    "answer it and stop talking. Aim for about forty words, and never pad a "
    "sentence to carry more - if a full answer truly needs more room, give "
    "the short answer first and let them ask for the rest.\n\n"
    "You can act on this PC through your tools - open and close apps, "
    "websites, files and folders, control media, volume and windows, type "
    "text, press keys, set reminders, and look up live market data. Whenever "
    "the request is really a command, call the tool instead of talking about "
    "it, then confirm in one short sentence what happened, or say briefly "
    "that it failed.\n\n"
    "You can also search the web. Use web_search whenever the answer "
    "depends on current information - news, prices, scores, releases, "
    "anything that changes - rather than guessing from memory. For a "
    "thorough request, where the user says 'research', 'dig deeper', "
    "'look into', or otherwise asks for something careful, call "
    "deep_research instead and report what it finds.\n\n"
    "Because you are being read aloud: never speak a URL, a domain, or a "
    "markdown link. Name sources the way a person would - 'according to "
    "Reuters' - and keep the answer to the few sentences that matter. If "
    "sources disagreed or something could not be confirmed, say so.\n\n"
    "The overlay can draw as well as speak. When your answer rests on real "
    "numbers you may add one last line, after your sentences, in exactly this "
    "form:\n"
    "[[apollo:vis]]{\"chart\": {\"label\": \"AAPL, 5 days\", \"unit\": \"$\", "
    "\"points\": [205.1, 206.4, 204.9, 208.2, 213.4]}, \"cards\": "
    "[{\"label\": \"Last\", \"value\": \"213.40\"}, {\"label\": \"Week\", "
    "\"value\": \"+4.1%\"}]}\n"
    "That line is never spoken and never shown as text - it is stripped off "
    "and drawn under the overlay - so it costs you nothing against your "
    "sentence budget, and your spoken sentences must still make complete "
    "sense on their own without it. Both keys are optional. Include `chart` "
    "only when you have at least four real readings of one quantity in order, "
    "such as a price over several days; include `cards` only for two to six "
    "discrete figures worth reading side by side. Keep labels under about "
    "twenty characters and values short enough to read at a glance.\n"
    "Every number in it must be one you actually have, from a search result "
    "or from the user. Never invent a series to make a chart appear, never "
    "smooth or round one into a nicer shape, and leave the whole line out for "
    "ordinary conversational answers - which is most of them. A wrong chart "
    "is far worse than no chart."
)

# Server-side tools: Anthropic runs these, so there is nothing to execute
# locally and they never come back as a client tool_use block. The _20260209
# variants add dynamic filtering (results are narrowed server-side before they
# reach the context window); they need Opus 4.6+ / Sonnet 4.6+, and this app is
# on Opus 5. Do NOT also declare code_execution - these run it under the hood,
# and a second execution environment confuses the model.
WEB_SEARCH = {"type": "web_search_20260209", "name": "web_search", "max_uses": 5}
WEB_FETCH = {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 6}

# Deep research runs as its own separate conversation (see deep_research).
RESEARCH_EFFORT = "high"      # the main chat stays on "low" for snappiness
RESEARCH_SEARCHES = 12
RESEARCH_MAX_TOKENS = 16000

RESEARCH_SYSTEM = (
    "You are a research assistant. Search the web repeatedly to build a "
    "well-sourced answer: start broad, then follow up on the specifics that "
    "matter, and fetch the most important sources in full so you are reading "
    "them rather than their search snippets. Cross-reference at least two "
    "independent sources for any contested or numeric claim. State plainly "
    "when sources disagree, and when something could not be confirmed say so "
    "instead of smoothing over it. Name sources by publication. Finish with "
    "a clear summary of what you found and how confident it is."
)

# Apollo's own tools come from the shared registry (`tools.py`), so Claude
# and Gemini can do exactly the same things. Deep research and web search
# are Claude's alone.
TOOLS = tools.claude_tools() + [
    {
        "name": "deep_research",
        "description": (
            "Research a question thoroughly: several web searches, full "
            "source pages read, and claims cross-referenced before "
            "answering. Slow - it takes a minute or two. Call this only "
            "when the user asks for depth ('research this', 'dig deeper', "
            "'look properly into'), or when a question genuinely needs "
            "several sources reconciled. For a simple current-information "
            "question, use web_search instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": (
                        "The research question, written out in full as a "
                        "self-contained question - the researcher cannot "
                        "see this conversation."
                    ),
                },
            },
            "required": ["question"],
        },
    },
    WEB_SEARCH,
]

# ---------------------------------------------------------------------------

# Constructing the client logs a warning that ANTHROPIC_API_KEY shadows the
# SDK's profile / federation auto-discovery. Using the key directly is the
# whole point here, so that note is pure noise - and with no logging
# configured it goes straight to stderr, where the window has no console to
# show it and the console version doesn't want it.
logging.getLogger("anthropic.lib.credentials._auth").setLevel(logging.ERROR)

log = logging.getLogger("apollo.assistant")

# ...but Apollo's own loggers do want a console. There are two backends now and
# the single most useful thing to see while debugging is which one each turn
# went to, so `apollo.router` and `apollo.gemini` get a handler of their own
# rather than sharing the root logger with every library in the process.
# Nothing is configured on the root logger deliberately: under pythonw.exe
# there is no console at all, and this must stay silent rather than fail.
def _utf8_console():
    """Make the console take Arabic.

    Windows hands Python a cp1252 console here, and the first Arabic line -
    your words, Apollo's answer, a router log - raised UnicodeEncodeError.
    Under pythonw there is no console at all (the streams are None), which is
    why every step is guarded.
    """
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


_utf8_console()


def _log_to_console(level=logging.INFO):
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("  [%(name)s] %(message)s"))
    for name in ("apollo.router", "apollo.gemini"):
        logger = logging.getLogger(name)
        if not logger.handlers:
            logger.addHandler(handler)
            logger.setLevel(level)
            # Still propagating, so these reach Apollo's log file as well as
            # the console. They were cut off from it, and they are the two
            # most useful things Apollo writes - which backend a turn went to,
            # and whether Gemini connected - under pythonw, where the console
            # they were kept to does not exist.


_log_to_console()

# Identity-linked API keys must state which workspace each request acts in.
# The SDK has no parameter for this, so it goes in as a default header.
WORKSPACE_ID = os.environ.get("ANTHROPIC_WORKSPACE_ID", "").strip()

client = anthropic.Anthropic(
    default_headers={"anthropic-workspace-id": WORKSPACE_ID} if WORKSPACE_ID else None
)
history = []

# Set to False automatically if this account can't use the fallback beta.
use_fallbacks = True


def api_error_detail(e):
    """Pull the actual error text out of an API exception, not just the code."""
    lines = [f"HTTP {e.status_code}"]

    body = getattr(e, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            lines.append(f"{err.get('type', 'error')}: {err.get('message', '')}")
        else:
            lines.append(str(body))
    else:
        lines.append(str(e.message))

    if getattr(e, "request_id", None):
        lines.append(f"request_id: {e.request_id}")

    # The one error with a fix specific enough to spell out.
    if "anthropic-workspace-id" in str(body):
        lines.append(
            "\n  Your key is identity-linked, so every request must name a "
            "workspace.\n"
            "  Find the ID at https://console.anthropic.com/settings/workspaces "
            "- open\n"
            "  your workspace and copy the wrkspc_... id from the URL, then:\n"
            '      setx ANTHROPIC_WORKSPACE_ID "wrkspc_..."\n'
            "  ...and open a new terminal."
        )

    return "\n  ".join(lines)


def is_fallback_beta_error(e):
    """True if a 400 is about the fallback beta rather than the request itself."""
    text = str(getattr(e, "body", "")) .lower()
    return "fallback" in text or "beta" in text


# Windows virtual-key codes for the two halves of the talk chord, both the
# generic and the side-specific ones - GetAsyncKeyState reports them
# separately and a held LCTRL does not light up the generic VK_CONTROL on
# every machine.
_VK_CHORD = (0x11, 0xA2, 0xA3,     # CONTROL, LCONTROL, RCONTROL
             0x12, 0xA4, 0xA5)     # MENU (alt), LMENU, RMENU
_VK_MOUSE = (0x01, 0x02, 0x04, 0x05, 0x06)
_GetAsyncKeyState = ctypes.windll.user32.GetAsyncKeyState


def _vk_down(vk):
    return bool(_GetAsyncKeyState(vk) & 0x8000)


# CTRL+1, the always-listening toggle. 0x31 is the "1" along the top of the
# keyboard, not the numpad's, which is 0x61 - the numpad one is deliberately
# left alone so that typing figures never trips it.
_VK_LISTEN = (0x11, 0x31)


class ListenToggle(threading.Thread):
    """Watches CTRL+1 and flips always-listening on and off.

    A thread of its own for the same reason `apollo.Watcher` is one: the run
    loop is busy for the whole of a turn, and a toggle that only answered
    between turns would feel broken at exactly the moment you reach for it.

    Polled rather than registered through `keyboard.add_hotkey`, because the
    callback form does not fire at all on this machine - the same finding that
    put `talk_held` on GetAsyncKeyState. Acts on the press rather than the
    hold, so leaning on the keys toggles once and not forty times a second.
    """

    def __init__(self, on_toggle, stop=None):
        super().__init__(daemon=True, name="listen-toggle")
        self.on_toggle = on_toggle
        self.stop = stop or (lambda: False)
        self.enabled = threading.Event()

    def run(self):
        held = False
        while not self.stop():
            down = all(_vk_down(vk) for vk in _VK_LISTEN)
            if down and not held:
                held = True
                if self.enabled.is_set():
                    self.enabled.clear()
                else:
                    self.enabled.set()
                try:
                    self.on_toggle(self.enabled.is_set())
                except Exception:
                    pass      # a reporting hiccup must not wedge the hotkey
            elif not down:
                held = False
            time.sleep(0.04)


def talk_held():
    """True while the talk chord - and nothing else - is held.

    `keyboard.is_pressed("ctrl+alt")` cannot be used for this. It tests only
    that the named keys are down, never that others are up, so every chord
    that *contains* CTRL+ALT would satisfy it: CTRL+ALT+SHIFT+Q (quit) would
    start a recording on its way to quitting, and so would every CTRL+ALT
    shortcut belonging to whatever app you are actually using.

    So the test is exclusive: both halves of the chord down, and no other key
    down at all. Pressing CTRL+ALT+O still opens a recording for the few
    milliseconds before the O lands, but that clip is far under MIN_SECONDS
    and is discarded, which is why that is a non-event rather than a bug.

    Mouse buttons are ignored deliberately - clicking something while holding
    the chord should not cut you off mid-sentence.
    """
    if not (_vk_down(0x11) and _vk_down(0x12)):
        return False
    for vk in range(0x01, 0xFF):
        if vk in _VK_CHORD or vk in _VK_MOUSE:
            continue
        if _vk_down(vk):
            return False
    return True


def voice_level(block):
    """Mic block -> 0-1, gated and curved. See VOICE_FLOOR / VOICE_FULL."""
    rms = float(np.sqrt(np.mean(np.square(block))))
    span = (rms - VOICE_FLOOR) / (VOICE_FULL - VOICE_FLOOR)
    if span <= 0.0:
        return 0.0
    return min(1.0, span) ** VOICE_CURVE


# How the running transcription behaves while you are still holding the key.
# It re-transcribes everything said so far rather than the newest slice alone,
# because Whisper is a sequence model: fed a two-second fragment it guesses at
# words that the rest of the sentence would have settled. Re-running the whole
# utterance costs more and is the reason PARTIAL_EVERY is not smaller, but it
# is what makes the line on screen converge on the truth instead of drifting.
PARTIAL_EVERY = 0.75        # seconds between passes
PARTIAL_MIN = 0.9           # ...and how much audio there must be to start

# Whisper's model object is not safe to drive from two threads at once, and
# the running transcription deliberately overlaps the final one at the moment
# you let go of the key. One lock, held for the length of a pass.
_whisper_lock = threading.Lock()


def _follow_along(frames, done, whisper, on_partial):
    """The running transcription, as a thread that reads a growing frame list.

    Shared by both capture paths - the live session and the local fallback -
    because the two differ only in where the audio comes from. Returns an
    unstarted thread, or None if there is nothing to report to; the caller
    starts it, and sets `done` when the audio stops.
    """
    if on_partial is None or whisper is None:
        return None

    def run():
        last = 0
        while not done.wait(PARTIAL_EVERY):
            count = len(frames)
            if count == last:
                continue                  # nothing new to hear
            last = count
            heard = np.concatenate(frames[:count], axis=0).flatten()
            if len(heard) < PARTIAL_MIN * SAMPLE_RATE:
                continue
            try:
                text = transcribe(whisper, heard, final=False)
            except Exception:
                continue                  # a partial is never worth a failure
            if text and not done.is_set():
                on_partial(text)

    return threading.Thread(target=run, daemon=True)


def record_while_held(hotkey, on_level=None, on_partial=None, whisper=None):
    """Capture mono audio for as long as the hotkey is held down.

    The local fallback, used only when the live session is not up: it opens a
    microphone stream of its own, which is exactly what must not happen while
    Gemini Live already owns the device. The normal path is `capture_turn`.

    `on_level`, if given, is called with a 0-1 loudness for every block as it
    arrives, so the overlay can react to your voice while you are still
    speaking. It runs on PortAudio's callback thread: it must be cheap and it
    must not touch the UI - the orb only stores the number.

    `on_partial`, with `whisper`, turns on the running transcription: your
    words appear under the overlay as you say them instead of only once you
    stop. It runs on a thread of its own so a pass that takes half a second
    never delays the recording, and a pass is skipped rather than queued if
    the previous one is still going.
    """
    frames = []

    def callback(indata, _frames, _time, status):
        if status:
            print(f"  (audio warning: {status})", file=sys.stderr)
        frames.append(indata.copy())
        if on_level is not None:
            try:
                on_level(voice_level(indata))
            except Exception:
                pass          # never let a UI hiccup break the recording

    done = threading.Event()
    listener = _follow_along(frames, done, whisper, on_partial)

    with sd.InputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=callback
    ):
        if listener is not None:
            listener.start()
        try:
            while talk_held():
                time.sleep(0.03)
        finally:
            done.set()

    if listener is not None:
        # Brief: the pass in flight is finishing on audio that is already a
        # prefix of what the final transcription will see, so waiting for it
        # only avoids two Whisper passes overlapping on one CPU.
        listener.join(timeout=2.0)

    if not frames:
        return None
    return np.concatenate(frames, axis=0).flatten()


class LiveCapture:
    """Reads along with the live session's microphone, without opening one.

    Gemini Live holds the only microphone stream Apollo opens (see
    `gemini_live.LiveSession`), so everything that used to watch the local
    recording now watches this instead: the orb's bloom, and Whisper's running
    transcription. Same audio, one device, two readers.

    Whisper still gets the whole utterance even though Gemini is hearing it
    live, because the transcript is what the router reads to decide whose turn
    this is - and what the overlay draws as your line.

    `feed` runs on PortAudio's callback thread. It converts and appends, and
    that is all it is allowed to cost.
    """

    def __init__(self, on_level=None):
        self.on_level = on_level
        self.frames = []
        self.recording = False
        # Always-listening has no turns to keep audio for - the model does the
        # transcribing - but the orb should still bloom when you speak. So the
        # level meter and the frame buffer are separate switches, and that
        # mode turns on only the first. Keeping frames there would be a leak
        # with no reader: nothing ever empties them.
        self.metering = False
        # Anyone else who wants the level of every block, turn or no turn -
        # Apollo asleep, listening for a voice to wake to. Only the level
        # leaves this method; the audio itself goes nowhere new.
        self.listener = None

    def feed(self, data):
        """One block of int16 PCM, straight from the live session's mic."""
        listener = self.listener
        if not (self.recording or self.metering or listener is not None):
            return            # the stream is always on; the turn is not

        # The stream is int16 because that is what the Live API wants; Whisper
        # and the level meter both want float32 in -1..1.
        block = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
        level = voice_level(block)

        if self.recording:
            self.frames.append(block)
        if self.on_level is not None and (self.recording or self.metering):
            try:
                self.on_level(level)
            except Exception:
                pass          # never let a UI hiccup break the recording
        if listener is not None:
            try:
                listener(level)
            except Exception:
                pass

    def start(self):
        self.frames = []
        self.recording = True

    def stop(self):
        self.recording = False
        if not self.frames:
            return None
        return np.concatenate(self.frames, axis=0).flatten()


def capture_turn(live, capture):
    """Hold-to-talk over the live session. Returns the audio, kept as a backup.

    The audio is already on its way to Gemini by the time this returns - that
    is the point of the fast path, and why there is no send step here. Your
    words appear on screen as you say them through the session's own
    transcript (`on_heard`), which streams while the chord is held; the local
    copy of the audio is only for `WhisperBackup`, should that transcript
    never arrive.
    """
    capture.start()
    live.begin_turn()
    try:
        while talk_held():
            time.sleep(0.03)
    finally:
        # Stop forwarding before anything else: every block sent after the
        # key is up delays the reply by exactly that much.
        live.end_turn()
        audio = capture.stop()
    return audio


def transcribe(whisper, audio, final=True):
    """Turn recorded audio into text, locally.

    `final` picks the settings: the real transcription gets Whisper's voice
    filter and its default search, while a partial trades some accuracy for
    latency - a greedy pass, and no VAD, because the filter can decide that a
    sentence still in progress is silence and hand back nothing at all.
    """
    with _whisper_lock:
        segments, _info = whisper.transcribe(
            audio, language=None, vad_filter=final,
            beam_size=5 if final else 1,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()


MAX_TOOL_ROUNDS = 5    # safety net against a runaway tool-call loop
MAX_PAUSE_RESUMES = 5  # ...and against a server-side tool that never settles


def _call(request, beta, stream):
    """One request, four ways: beta or not, streamed or not."""
    if beta:
        # If a safety classifier declines the request, the API silently
        # retries it on another model instead of just giving up.
        request = dict(
            request,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if stream:
            with client.beta.messages.stream(**request) as s:
                return s.get_final_message()
        return client.beta.messages.create(**request)

    if stream:
        with client.messages.stream(**request) as s:
            return s.get_final_message()
    return client.messages.create(**request)


def _send(request, stream=False):
    """POST one request, transparently dropping the fallback beta if unsupported.

    `stream` doesn't change what comes back - the final message either way -
    only how it travels. Streaming is what keeps a long research run from
    hitting the SDK's HTTP timeout.
    """
    global use_fallbacks

    try:
        response = _call(request, use_fallbacks, stream)
        _note_usage(response)
        return response
    except anthropic.BadRequestError as e:
        # Only retry if the beta itself was rejected. Retrying on any 400 masks
        # real request errors behind a second, identical-looking failure.
        if not use_fallbacks or not is_fallback_beta_error(e):
            raise
        use_fallbacks = False  # beta not enabled on this account; carry on without it
        response = _call(request, False, stream)
        _note_usage(response)
        return response


def _note_usage(response):
    """Add one Claude response to the day's ledger. Never raises."""
    try:
        counts = getattr(response, "usage", None)
        if counts is not None:
            usage.record("claude", CLAUDE_MODEL,
                         prompt=getattr(counts, "input_tokens", 0),
                         response=getattr(counts, "output_tokens", 0))
    except Exception:
        pass


def ask_once(system, prompt, max_tokens=2000):
    """One plain question to Claude - no tools, no chat history - and the
    text of its answer. For Apollo's own background work (see `interests`),
    not for anything you say to it."""
    response = _send(dict(model=CLAUDE_MODEL, max_tokens=max_tokens, system=system,
                          messages=[{"role": "user", "content": prompt}]))
    return _text_of(response)


def _text_of(response):
    """Every text block in a response, joined - tool turns can interleave them."""
    return " ".join(b.text for b in response.content if b.type == "text").strip()


def deep_research(question, ui=None):
    """Research one question in a conversation of its own, and report back.

    Deliberately separate from the main chat history: a research pass burns a
    dozen searches and a lot of fetched page text, and folding all of that into
    the running conversation would bloat every later turn of a session that is
    meant to stay quick. Only the finished write-up comes back.
    """
    if ui:
        # Warn the user before going quiet for a minute or two.
        ui.status(SPEAKING)
        speak("Give me a minute while I look into that.")
        ui.status(THINKING)
        ui.note(f"Researching: {question}")

    request = dict(
        model=CLAUDE_MODEL,
        max_tokens=RESEARCH_MAX_TOKENS,
        system=RESEARCH_SYSTEM,
        output_config={"effort": RESEARCH_EFFORT},
        tools=[dict(WEB_SEARCH, max_uses=RESEARCH_SEARCHES), WEB_FETCH],
        messages=[{"role": "user", "content": question}],
    )

    response = _send(request, stream=True)

    resumes = 0
    while response.stop_reason == "pause_turn" and resumes < MAX_PAUSE_RESUMES:
        resumes += 1
        if ui:
            ui.note(f"Still researching (pass {resumes + 1})...")
        # The server paused mid-turn at its own iteration limit. Re-sending with
        # the paused turn on the end tells it to resume; it recognises the
        # trailing server_tool_use block, so no "continue" message is needed.
        request["messages"].append({"role": "assistant", "content": response.content})
        response = _send(request, stream=True)

    if response.stop_reason == "refusal":
        return "The research request was declined."

    return _text_of(response) or "The research came back empty."


def _run_tool(block, ui):
    """Execute one client-side tool call. web_search never lands here - it runs
    server-side and comes back as content, not as a request to do something.

    Anything that goes wrong comes back as text rather than an exception: a
    tool_result Claude can read lets it apologise or try again, where a raised
    error would take down the whole turn.
    """
    args = block.input if isinstance(block.input, dict) else {}
    try:
        if block.name == "deep_research":
            return deep_research(args.get("question", ""), ui)
        if block.name in tools.REGISTRY:
            return json.dumps(tools.run(block.name, args, tools.Context(
                show=getattr(ui, "visual", None),
                activity=getattr(ui, "activity", None),
                refresh=getattr(ui, "refresh", None),
                panels_hook=getattr(ui, "panels", None),
                story_hook=getattr(ui, "story", None),
                stock_hook=getattr(ui, "stock", None),
                idle_hook=getattr(ui, "idle", None),
                tab_hook=getattr(ui, "tab", None),
                away_hook=getattr(ui, "going_out", None),
                osiris_hook=getattr(ui, "ask_osiris", None),
                display_hook=getattr(ui, "ask_display", None))))
        return f"Failed: unknown tool '{block.name}'."
    except Exception as e:
        return f"Failed: {type(e).__name__}: {e}"


def _note_searches(response, ui):
    """Surface server-side searches in the UI, so a pause isn't unexplained.

    Cosmetic only, so it swallows its own errors - a surprise in the shape of a
    content block must not cost the user an answer that already arrived.
    """
    if not ui:
        return
    try:
        for block in response.content:
            if block.type == "server_tool_use" and block.name == "web_search":
                query = (block.input or {}).get("query")
                if query:
                    ui.note(f"Searched: {query}")
    except Exception:
        pass


def ask_claude(user_text, ui=None):
    """Send the transcript to Claude, keeping the conversation going.

    Claude may call tools before giving its final spoken reply: control_pc and
    deep_research run here and their results are fed back, while web_search
    runs server-side and simply arrives as part of the response.
    """
    history_mark = len(history)
    history.append({"role": "user", "content": user_text})

    request = dict(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        # Thinking is on by default on Opus 5. Low effort keeps the assistant
        # snappy, which matters far more than depth for spoken chit-chat.
        # Deep research overrides this in its own request.
        output_config={"effort": "low"},
        tools=TOOLS,
        messages=history,
    )

    response = _send(request)
    _note_searches(response, ui)

    paused_turns = []
    rounds = 0
    while rounds < MAX_TOOL_ROUNDS:
        rounds += 1

        if response.stop_reason == "pause_turn":
            # A server-side tool (web search) hit the server's own iteration
            # limit part way through. Re-sending with the paused turn appended
            # resumes it. Without this the loop would fall straight through and
            # speak whatever half-finished text had accumulated.
            paused = {"role": "assistant", "content": response.content}
            paused_turns.append(paused)
            history.append(paused)
            request["messages"] = history
            response = _send(request)
            _note_searches(response, ui)
            continue

        if response.stop_reason != "tool_use":
            break

        history.append({"role": "assistant", "content": response.content})

        tool_results = [
            {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": _run_tool(block, ui),
            }
            for block in response.content
            if block.type == "tool_use"
        ]
        history.append({"role": "user", "content": tool_results})

        request["messages"] = history
        response = _send(request)
        _note_searches(response, ui)

    # A paused turn was only ever needed to tell the server where to resume.
    # Once the answer is in hand it is protocol noise - a pile of search-result
    # blocks ending in an unmatched server_tool_use - so keeping it would bloat
    # every later turn for nothing. Removed by identity, not equality.
    if paused_turns:
        history[:] = [m for m in history if not any(m is p for p in paused_turns)]

    if response.stop_reason == "refusal":
        del history[history_mark:]
        detail = response.stop_details
        return f"I can't help with that{f' ({detail.category})' if detail else ''}."

    reply = _text_of(response)

    # An assistant turn with empty content is rejected by the API on the *next*
    # request, so a silent reply here would poison every turn after it. Two ways
    # to land here: the tool-round cap above was hit while Claude still wanted to
    # call something, or the reply was cut off before any text block. Drop the
    # whole exchange rather than leave an unsendable message in the history.
    if not reply:
        del history[history_mark:]
        return "Sorry, I lost track of that one. Ask me again."

    history.append({"role": "assistant", "content": reply})
    return reply


# --- Fish Audio ------------------------------------------------------------
#
# True once the startup check has found a usable key with credit behind it.
# False means "speak through VoiceBox instead".
_fish_ready = False


def check_fish(ui=None):
    """Validate the Fish Audio key and its credit balance. True if usable.

    Fish bills API credit separately from the platform credit you spend on
    fish.audio itself, so a working login and a paid-up website account can
    still leave the API at zero. That shows up as a 402 on the first reply,
    which is too late to be useful, so the balance is checked here instead.
    """
    global _fish_ready
    _fish_ready = False

    key = os.environ.get("FISH_API_KEY")
    if not key:
        if ui:
            ui.note("No FISH_API_KEY in .env; using VoiceBox.")
        return False

    request = urllib.request.Request(
        f"{FISH_URL}/wallet/self/api-credit",
        headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(request, timeout=FISH_CONNECT_TIMEOUT) as r:
            credit = float(json.load(r).get("credit") or 0)
    except urllib.error.HTTPError as e:
        if ui:
            reason = "key rejected" if e.code in (401, 403) else f"HTTP {e.code}"
            ui.note(f"Fish Audio {reason}; using VoiceBox.")
        return False
    except Exception as e:
        # No internet, DNS failure, a timeout: all fine, we have local voices.
        if ui:
            ui.note(f"Fish Audio unreachable ({e}); using VoiceBox.")
        return False

    if credit <= 0:
        if ui:
            ui.note("Fish Audio has no API credit (add funds at "
                    "fish.audio/app/developers); using VoiceBox.")
        return False

    _fish_ready = True
    return True


def _speak_fish(text):
    """Speak through Fish Audio. Raises if anything at all goes wrong.

    One call: the response body *is* the WAV, so there is nothing to poll.
    """
    body = json.dumps({
        "text": text,
        "reference_id": FISH_VOICE,
        "format": "wav",
        "normalize": True,
        "latency": "normal",
    }).encode("utf-8")

    request = urllib.request.Request(
        f"{FISH_URL}/v1/tts", data=body, method="POST",
        headers={
            "Authorization": f"Bearer {os.environ['FISH_API_KEY']}",
            "Content-Type": "application/json",
            "model": FISH_BACKEND,
        })

    with urllib.request.urlopen(request, timeout=FISH_TIMEOUT) as r:
        audio = r.read()

    _play_wav(audio)


# --- VoiceBox --------------------------------------------------------------
#
# VoiceBox is a local TTS server. We hold its profile id once the startup
# health check has found it; None means "speak through Piper instead" - either
# the server was down when we looked, or the profile is missing.
_voicebox_profile = None
_voicebox_checked = False


def _vb_get(path, timeout):
    """GET a JSON body from VoiceBox."""
    with urllib.request.urlopen(VOICEBOX_URL + path, timeout=timeout) as r:
        return json.load(r)


def _vb_post(path, body, timeout):
    """POST a JSON body to VoiceBox and return the JSON reply."""
    request = urllib.request.Request(
        VOICEBOX_URL + path,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as r:
        return json.load(r)


def check_voicebox(ui=None):
    """Health-check VoiceBox and resolve VOICEBOX_PROFILE to an id.

    Returns the id, or None if we should fall back to Piper. Deliberately
    total: a refused connection, a half-started server, a renamed profile and
    a malformed reply all come back as None with a note, because losing the
    good voice is not a reason to stop the assistant from starting.
    """
    global _voicebox_profile, _voicebox_checked
    _voicebox_checked = True

    try:
        health = _vb_get("/health", VOICEBOX_CONNECT_TIMEOUT)
    except Exception as e:
        # Almost always ConnectionRefusedError - the server is not running.
        if ui:
            ui.note(f"VoiceBox is not answering ({e}); using Piper.")
        return None

    if health.get("status") != "healthy":
        if ui:
            ui.note(f"VoiceBox is {health.get('status')}; using Piper.")
        return None

    try:
        profiles = _vb_get("/profiles", VOICEBOX_CONNECT_TIMEOUT)
    except Exception as e:
        if ui:
            ui.note(f"VoiceBox profiles unreadable ({e}); using Piper.")
        return None

    # Match on name, not id. Case-insensitive, so renaming the profile in the
    # VoiceBox UI with different capitalisation doesn't silently drop us to
    # Piper.
    wanted = VOICEBOX_PROFILE.strip().lower()
    for profile in profiles:
        if str(profile.get("name", "")).strip().lower() == wanted:
            _voicebox_profile = profile.get("id")
            return _voicebox_profile

    if ui:
        names = ", ".join(str(p.get("name")) for p in profiles) or "none"
        ui.note(f"No VoiceBox profile named {VOICEBOX_PROFILE!r} "
                f"(have: {names}); using Piper.")
    return None


def _vb_wait(generation_id, deadline):
    """Block until a generation finishes. True if it produced audio.

    GET /generate/{id}/status is a server-sent event stream rather than a plain
    body: it stays open and pushes one 'data: {...}' line per state change, so
    reading it *is* the wait - no polling loop, and the reply plays as soon as
    it is ready.
    """
    remaining = max(1, int(deadline - time.monotonic()))
    url = f"{VOICEBOX_URL}/generate/{generation_id}/status"
    with urllib.request.urlopen(url, timeout=remaining) as stream:
        for raw in stream:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue  # SSE comments and the blank separator lines
            status = json.loads(line[len("data:"):]).get("status")
            if status == "completed":
                return True
            if status in ("failed", "error", "cancelled"):
                return False
            if time.monotonic() > deadline:
                return False
    return False  # stream closed without ever saying it finished


def _play_wav(data):
    """Play a WAV held in memory, blocking until it has finished.

    The same sounddevice path the Piper branch uses, so the run loop's "the
    reply is over once speak() returns" assumption holds for both engines.
    """
    with wave.open(io.BytesIO(data), "rb") as w:
        channels = w.getnchannels()
        width = w.getsampwidth()
        rate = w.getframerate()
        frames = w.readframes(w.getnframes())

    # VoiceBox sends 16-bit; Fish is not contractually bound to, so handle the
    # other widths rather than fall back to the robot voice over a format.
    if width == 2:
        audio = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    elif width == 4:
        audio = np.frombuffer(frames, dtype="<i4").astype(np.float32) / 2147483648.0
    elif width == 1:
        # 8-bit WAV is unsigned, centred on 128.
        audio = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128) / 128.0
    else:
        raise ValueError(f"unsupported sample width: {width * 8}-bit")
    if channels > 1:
        audio = audio.reshape(-1, channels)

    sd.play(audio, samplerate=rate)
    sd.wait()


def _speak_voicebox(text):
    """Speak through VoiceBox. Raises if anything at all goes wrong.

    Three calls: POST /generate queues the line, the status stream waits for
    it, GET /audio/{id} hands back the WAV.
    """
    deadline = time.monotonic() + VOICEBOX_TIMEOUT

    generation = _vb_post("/generate", {
        "profile_id": _voicebox_profile,
        "text": text,
        "engine": VOICEBOX_ENGINE,
        "language": "en",
    }, VOICEBOX_TIMEOUT)

    generation_id = generation.get("id")
    if not generation_id:
        raise ValueError("VoiceBox returned no generation id")

    # It can come back already finished, for a line short enough to synthesise
    # inside the POST itself.
    if generation.get("status") != "completed":
        if not _vb_wait(generation_id, deadline):
            raise RuntimeError(f"generation failed: {generation.get('error')}")

    remaining = max(1, int(deadline - time.monotonic()))
    with urllib.request.urlopen(
            f"{VOICEBOX_URL}/audio/{generation_id}", timeout=remaining) as r:
        audio = r.read()

    _play_wav(audio)


# --- Piper and SAPI, the fallbacks -----------------------------------------

# The loaded Piper voice, or None once we know we're going without it. Loading
# an ONNX model takes about a second, so it happens once and is kept.
_voice = None
_voice_unavailable = False


def load_voice(ui=None):
    """Prepare the voice: Fish, else VoiceBox, else Piper.

    Called once at startup by both front ends, so a first-run download or an
    unreachable server is reported with something on screen to explain it,
    rather than silently stalling the greeting. Returns the loaded Piper voice
    or None - callers use that for their note, not for the decision.

    Safe to call repeatedly: every outcome is cached.
    """
    # The checks run in quality order. If either network voice answers, Piper
    # is never loaded at all, which also saves its ~60MB download on a fresh
    # machine.
    if check_fish(ui):
        if ui:
            ui.note("Voice: Fish Audio (British female).")
        return None

    if _voicebox_profile is None and check_voicebox(ui) is not None:
        if ui:
            ui.note(f"Voice: VoiceBox ({VOICEBOX_PROFILE}).")
        return None

    return _load_piper(ui)


def _load_piper(ui=None):
    """Load the Piper model, or None if it isn't usable.

    Split out from load_voice so that speak() can reach Piper without
    re-running the Fish and VoiceBox checks - those answer "a better voice is
    available", which is the wrong answer for a line that has just failed on
    that better voice.

    Safe to call repeatedly: the model and the giving-up are both cached.
    """
    global _voice, _voice_unavailable

    if _voice is not None or _voice_unavailable:
        return _voice

    if piper is None:
        _voice_unavailable = True
        return None

    try:
        model = os.path.join(VOICES_DIR, f"{PIPER_VOICE}.onnx")
        if not os.path.exists(model):
            if ui:
                ui.note(f"Downloading voice ({PIPER_VOICE})... one time, ~60MB.")
            os.makedirs(VOICES_DIR, exist_ok=True)
            # Takes a Path, not a str - it builds paths with the / operator.
            download_voice(PIPER_VOICE, pathlib.Path(VOICES_DIR))

        _voice = piper.PiperVoice.load(model)
    except Exception as e:
        # No voice is not fatal - SAPI still works, it just sounds worse.
        if ui:
            ui.note(f"Voice unavailable ({e}); using the Windows voice.")
        _voice_unavailable = True
        return None

    return _voice


def _speak_sapi(text):
    """The original Windows voice. A fresh engine per call avoids pyttsx3's
    'run loop already started' error when speaking repeatedly."""
    engine = pyttsx3.init()
    engine.setProperty("rate", VOICE_RATE)
    # Windows defaults to David, who is male. Apollo is female on every other
    # rung of the chain, so match it here too when a female voice is installed
    # - Zira on a stock Windows 11. If none is, David is still better than
    # silence, so this is a preference and not a requirement.
    for candidate in engine.getProperty("voices"):
        if (getattr(candidate, "gender", "") or "").lower() == "female":
            engine.setProperty("voice", candidate.id)
            break
    engine.say(text)
    engine.runAndWait()
    engine.stop()


def speak(text):
    """Read the reply aloud: Fish, else VoiceBox, else Piper, else Windows.

    Blocks until the audio has finished playing, which the run loop relies on
    to know when to drop back to idle.
    """
    if _fish_ready:
        try:
            _speak_fish(text)
            return
        except Exception:
            # A 402 once the credit runs dry mid-session, a 429, a timeout, a
            # dropped connection. Fall through to the local voices for this
            # line rather than answer with silence. Not sticky: Fish is
            # retried next turn, since a rate limit or a blip is transient.
            pass

    # If Fish answered at startup, VoiceBox was never looked at - so look now,
    # once. Without this a Fish line that fails drops straight past the good
    # local voice to the robot one. A refused connection is cached by
    # _voicebox_checked, so a machine without VoiceBox pays the 3s probe once
    # per run, not once per reply.
    if _voicebox_profile is None and not _voicebox_checked:
        check_voicebox()

    if _voicebox_profile is not None:
        try:
            _speak_voicebox(text)
            return
        except Exception:
            # A stopped server, a deleted profile, a synthesis error, a
            # timeout: fall through to Piper for this line rather than answer
            # with silence. Not sticky - VoiceBox is retried next turn, since
            # the usual cause is transient.
            pass

    voice = _load_piper()
    if voice is None:
        _speak_sapi(text)
        return

    try:
        # length_scale stretches time, so it's the reciprocal of speed. Deriving
        # it from VOICE_RATE keeps that one knob meaningful for both engines.
        config = piper.SynthesisConfig(
            length_scale=PIPER_NATURAL_WPM / VOICE_RATE
        )
        chunks = list(voice.synthesize(text, syn_config=config))
        if not chunks:
            return

        audio = np.concatenate([c.audio_float_array for c in chunks])
        sd.play(audio, samplerate=chunks[0].sample_rate)
        sd.wait()
    except Exception:
        # Anything at all - a bad model file, no output device, a text the
        # phonemiser chokes on - is better answered by the robot voice than by
        # silence, since this is the only channel the user has.
        _speak_sapi(text)


# --- Reporting -------------------------------------------------------------
#
# The loop below never prints. It reports through a small "reporter" object so
# the console and the desktop window can each render events their own way.

IDLE = "Idle"
LISTENING = "Listening"
THINKING = "Thinking"
SPEAKING = "Speaking"


class ConsolePrinter:
    """The original console output, behind the reporter interface."""

    def status(self, state):
        print(f"[{state}]")

    def turn(self, speaker, text, visual=None):
        print(f"  {speaker + ':':7} {text}")

    def partial(self, text):
        """Words heard so far, while you are still talking.

        Rewritten in place rather than printed as new lines: this fires every
        time the running transcription gets further through the sentence, and
        a console that scrolled a line per revision would bury the turn it
        belongs to.
        """
        print(f"\r  {'...':7} {text[-90:]}", end="", flush=True)

    def note(self, text):
        print(f"  {text}")

    def level(self, value):
        """Live mic loudness, 0-1. The console has nothing to do with it."""

    def visual(self, visual):
        """A chart or cards from a tool - the console can only say so."""
        print(f"  [visual] {', '.join(sorted((visual or {}).keys()))}")

    def activity(self, text):
        print(f"  ... {text}")


class Offline(RuntimeError):
    """The network is not there yet - worth waiting for, unlike a bad key."""


# Seconds between tries while the network comes up. Short at first, because
# at sign-in it is usually a few seconds away; capped, because a machine that
# has been offline for an hour should still notice within half a minute.
WAIT_DELAYS = (2, 3, 5, 8, 13, 20, 30)


def wait_for_api(ui=None, stop=lambda: False, sleep=time.sleep, check=None):
    """`check_api`, but patient about the network.

    Apollo starts at sign-in, exactly when Wi-Fi is least likely to have
    connected yet, and the startup check used to treat "could not reach the
    API" like "your key is wrong": it put up a note and the worker returned
    for good. Apollo went on running with no voice, no data, no reminders and
    no recap, and never tried again.

    Offline now means wait and try again, with the note said once. Anything
    else - no key, a rejected key, a missing model - still raises at once,
    because waiting will not fix it. False if Apollo is quitting meanwhile.
    """
    check = check or check_api
    attempt = 0
    while True:
        try:
            check()
            if attempt:
                log.info("the API is reachable after %d tries", attempt + 1)
            return True
        except Offline as exc:
            if stop():
                return False
            if attempt == 0:
                log.info("waiting for the network: %s", exc)
                note = getattr(ui, "note", None)
                if note is not None:
                    try:
                        note("Waiting for the network…")
                    except Exception:  # noqa: BLE001 - a note is not the point
                        pass
            sleep(WAIT_DELAYS[min(attempt, len(WAIT_DELAYS) - 1)])
            attempt += 1


def check_api():
    """Validate the key, workspace header and model name before we start.

    This is a free GET, so misconfiguration surfaces now rather than after you
    have already spoken into the mic. Raises RuntimeError with text worth
    showing the user.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set.\n"
            "Get a key at https://console.anthropic.com/settings/keys then run:\n"
            '  setx ANTHROPIC_API_KEY "sk-ant-..."\n'
            "...and open a NEW terminal (setx only affects new terminals)."
        )

    try:
        client.models.retrieve(CLAUDE_MODEL)
    except anthropic.APIConnectionError as e:
        raise Offline(f"Couldn't reach the API. Check your internet.\n  {e}")
    except anthropic.APIStatusError as e:
        raise RuntimeError(api_error_detail(e))


class WhisperBackup:
    """Whisper, loaded in the background, for the rare turn Gemini missed.

    Gemini's own transcript is Apollo's transcript now (it streams while you
    hold the chord, and it understands Arabic). Whisper stays as the backup
    for a turn where that transcript never arrives, so it must not delay
    startup: the model loads on a thread of its own, the first run
    downloading it, and a transcription asked for before it is ready waits
    up to 20 s and then returns nothing.
    """

    def __init__(self, size=None):
        self._model = None
        self._ready = threading.Event()
        threading.Thread(target=self._load, args=(size or WHISPER_SIZE,),
                         daemon=True, name="whisper-load").start()

    def _load(self, size):
        try:
            self._model = WhisperModel(size, device="cpu", compute_type="int8")
        except Exception:
            self._model = None
        finally:
            self._ready.set()

    def transcribe(self, audio, **kw):
        if not self._ready.wait(timeout=20) or self._model is None:
            return iter(()), None
        return self._model.transcribe(audio, **kw)


def load_whisper():
    """The backup transcriber. Returns at once; the model loads behind it."""
    return WhisperBackup()


def greet(ui):
    """Speak one line at startup, then settle into idle.

    Reported as a normal SPEAKING turn so a host UI lights up for it exactly
    as it does for a real answer.
    """
    try:
        ui.status(SPEAKING)
        speak(GREETING)
    finally:
        ui.status(IDLE)


class Voice:
    """Apollo's live session, as one thing that can be replaced and closed.

    A holder rather than a bare pair of variables, because the session is not
    a constant: switching between push-to-talk and always-listening replaces
    it (see `open`), and quitting can arrive from another thread entirely -
    the tray icon, the window closing - at any moment in between. With the
    session held in two places, the closer and the switcher end up looking at
    different objects, and the one that gets left behind is a live websocket
    and an open microphone that nothing will ever shut.

    So there is exactly one of these per Apollo, everyone talks to it, and the
    lock means a toggle landing at the same moment as a quit resolves one way
    or the other rather than half of each.
    """

    def __init__(self, ui, on_level=None, on_user_text=None, on_heard=None,
                 on_reply=None, on_activity=None, run_tool=None):
        self.ui = ui
        self.on_level = on_level
        self.on_user_text = on_user_text
        self.on_heard = on_heard          # your words, live, as Gemini hears them
        self.on_reply = on_reply          # Apollo's words, live, as it speaks them
        self.on_activity = on_activity    # "opening Chrome", "searching the web"
        self.run_tool = run_tool          # (name, args) -> result dict
        self.live = None
        self.capture = None
        self.listener = None              # see `listen`
        self._lock = threading.Lock()

    def listen(self, fn):
        """Hand every block's level to `fn` (or stop, with None).

        Kept here as well as on the capture because a reconnect builds a new
        capture, and the listener has to survive it.
        """
        self.listener = fn
        capture = self.capture
        if capture is not None:
            capture.listener = fn

    @property
    def ready(self):
        return self.live is not None and self.live.alive

    @property
    def auto_vad(self):
        """True if the session that is up is the always-listening one."""
        return self.live is not None and self.live.auto_vad

    @property
    def busy(self):
        """True while a reconnect is in progress, and the microphone is nobody's.

        `open` closes the old session before the new one exists, so there is a
        second or so in which `live` is None. Without this, a chord held
        across that gap would send `push_to_talk_turn` down its local-recorder
        fallback and open a *second* microphone stream, moments before the new
        session opens its own. One device, one owner - so the loop waits.
        """
        return self._lock.locked()

    def open(self, auto_vad=False):
        """(Re)connect in the given mode. True if it came up.

        The mode is part of the session's setup message - whether the model
        runs its own voice activity detection - and that is sent once, at
        connect. So switching modes is a reconnect rather than a flag flip.
        It costs about a second, which is the right price for something you
        press on purpose, and it is the honest implementation rather than
        pretending a live session can be reconfigured underneath itself.
        """
        with self._lock:
            if self.live is not None:
                self.live.close()
                self.live, self.capture = None, None

            if not gemini_live.available():
                self.ui.note("No GEMINI_API_KEY; Apollo has no voice. "
                             "See the README.")
                return False

            capture = LiveCapture(on_level=self.on_level)
            # Always-listening keeps no audio of its own - the model does the
            # transcribing - but the orb should still bloom when you speak.
            capture.metering = auto_vad
            capture.listener = self.listener

            live = gemini_live.LiveSession(
                on_audio=capture.feed, auto_vad=auto_vad,
                on_user_text=self.on_user_text, on_text=self.on_reply,
                on_heard=self.on_heard, on_user_turn=tools.new_user_turn,
                on_activity=self._activity, on_tool_call=self.run_tool,
                on_usage=lambda prompt, reply: usage.record(
                    "gemini", gemini_live.MODEL, prompt=prompt, response=reply),
                tools=tools.gemini_declarations() if self.run_tool else None)
            try:
                live.start()
            except RuntimeError as e:
                self.ui.note(f"Gemini Live unavailable.\n  {e}")
                live.close()
                return False

            self.live, self.capture = live, capture
            return True

    def _activity(self, kind, detail):
        if self.on_activity is None:
            return
        words = tools.TOOL_LABELS.get(detail) if kind == "tool" else ACTIVITY_WORDS.get(kind)
        try:
            self.on_activity(words or detail)
        except Exception:
            pass

    def close(self):
        """Shut the session down. Safe to call twice, and from any thread."""
        with self._lock:
            if self.live is not None:
                self.live.close()
            self.live, self.capture = None, None


# One lock for "a turn is in progress". The run loop holds it for every turn,
# and the reminder watcher takes it before speaking, so a reminder waits for
# your sentence to finish instead of talking over it.
TURN_GATE = threading.Lock()

# What the overlay says while a model-side search runs.
ACTIVITY_WORDS = {"search": "searching the web"}


def tool_runner(ui):
    """Build the callable Gemini's tool calls go through."""
    def run(name, args):
        ctx = tools.Context(show=getattr(ui, "visual", None),
                            activity=getattr(ui, "activity", None),
                            refresh=getattr(ui, "refresh", None),
                            panels_hook=getattr(ui, "panels", None),
                            story_hook=getattr(ui, "story", None),
                            stock_hook=getattr(ui, "stock", None),
                            idle_hook=getattr(ui, "idle", None),
                            tab_hook=getattr(ui, "tab", None),
                            away_hook=getattr(ui, "going_out", None),
                            osiris_hook=getattr(ui, "ask_osiris", None),
                            display_hook=getattr(ui, "ask_display", None))
        return tools.run(name, args, ctx)
    return run


def announce(ui, voice, instruction, fallback):
    """Say something nobody asked for, in Apollo's own voice if it can.

    Gemini is prompted with an instruction and speaks the result, so a
    reminder sounds like every other answer and is in the language you last
    used. With no live session the fallback line goes to the local voices.
    """
    live = voice.live if voice is not None else None
    held = LISTENING if (voice is not None and voice.auto_vad) else IDLE
    ui.status(SPEAKING)
    try:
        if live is not None and live.prompt(instruction):
            live.wait_for_audio(timeout=10)
            live.wait_until_quiet()
        else:
            ui.turn("Apollo", fallback)
            speak(fallback)
    finally:
        ui.status(held)


def brief_now(ui, voice):
    """Say the day's recap, in Apollo's voice and your language.

    The facts are gathered here; the words are Gemini's (see
    `briefing.spoken`), because a briefing written in Python always sounds
    like a form letter and never matches the language you last used.
    """
    payload = briefing.compose()
    visual = overlay_content.clean_visual({"cards": tools._briefing_cards(payload)})
    if visual is not None and hasattr(ui, "visual"):
        ui.visual(visual)
    announce(ui, voice, briefing.spoken(payload),
             "Here is your briefing. The data services are not answering right now.")


def fire_reminder(ui, voice, reminder, late):
    """The reminder watcher's callback: say the reminder, now."""
    text = reminder.get("text", "")
    instruction = (f"A reminder the user set is due now: \"{text}\". Tell them in "
                   f"one short sentence, in the language they last spoke"
                   + (", and say it's a little late." if late else "."))
    announce(ui, voice, instruction, f"Reminder: {text}")


def fire_prayer(ui, voice, name, when, lead_minutes):
    """A prayer is close. Say so, once, in the language they last used."""
    instruction = (
        f"{name} prayer in Riyadh is at {when.strftime('%H:%M')}, about "
        f"{lead_minutes} minutes from now. Tell the user in one short "
        f"sentence, in the language they last spoke to you in - their dialect "
        f"if it was Arabic. Say only that; do not add anything else.")
    announce(ui, voice, instruction,
             f"{name} at {when.strftime('%H:%M')}")


def answer_with_agent(name, said, ui):
    """Hand one turn to a summoned agent, and speak what comes back.

    The only route to Claude and to the Fish / VoiceBox voice that exists in
    this file. Conversation cannot reach it: `router.route_request` returns
    AGENT only when one of the seven was called by name, and `agents.handle`
    is the single door through to `ask_claude`.
    """
    try:
        reply = agents.handle(name, said, ui, ask=ask_claude)
    except anthropic.APIConnectionError as e:
        ui.note(f"Error: couldn't reach the API. Check your internet.\n  {e}")
        return
    except anthropic.APIStatusError as e:
        # Covers auth, rate limit, 400s and 5xx - all of them report the real
        # message from the API rather than just the status code.
        ui.note(f"Error: {api_error_detail(e)}")
        return

    # Anything the reply carries for the overlay to draw is split off here,
    # before either the screen or the voice sees it: `spoken` is the sentences
    # and nothing else, so the tag can never be read out.
    spoken, visual = overlay_content.split_reply(reply)
    ui.turn(name, spoken, visual)
    journal.answered(spoken, who=name)

    ui.status(SPEAKING)
    speak(spoken)


def agent_interrupt(ui):
    """Build the callback that lets a summoned agent take a turn off Gemini.

    Always-listening only. Gemini starts answering the moment you stop
    speaking, so by the time a turn is finished it is far too late to decide
    it belonged to somebody else. This runs instead while your words are still
    arriving: returning True tells the session to abandon the reply it is
    composing, and the finished turn then comes back through `next_turn` with
    an empty answer for the loop to hand to the agent.
    """
    def heard(said):
        name = agents.detect(said)
        if name is None:
            return False
        ui.note(f"{name} summoned - standing Gemini down.")
        return True

    return heard


def retry_after_drop(ui, voice, said):
    """The session died mid-turn. Reconnect and ask again, in your words.

    Measured: the Live API sometimes closes a session with "1011 Internal
    error occurred" exactly when the model goes to call a tool. The audio of
    your turn is gone with the socket - but Apollo has its own transcript of
    you, so the question can be put again as text rather than leaving you
    talking to something that has quietly died.
    """
    if not said:
        return ""
    ui.note("Voice dropped mid-answer; reconnecting and asking again.")
    reply = ""
    if voice.open(auto_vad=False):
        live = voice.live
        if live is not None and live.prompt(said):
            live.wait_for_audio(timeout=10)
            live.wait_until_quiet()
            reply = live.reply_text()
    if reply:
        return reply

    # Twice in a row means the service is refusing this turn, not that the
    # socket blinked. Say so in the local voice: silence would leave you
    # waiting on an assistant that is never going to answer.
    apology = "The voice service dropped that one. Say it again."
    ui.turn("Apollo", apology)
    speak(apology)
    return ""


def push_to_talk_turn(ui, whisper, voice):
    """One CTRL+ALT turn, from key down to the answer being spoken."""
    live = voice.live
    ui.status(LISTENING)
    if live is not None:
        audio = capture_turn(live, voice.capture)
    else:
        audio = record_while_held(HOTKEY, on_level=ui.level,
                                  on_partial=getattr(ui, "partial", None),
                                  whisper=whisper)
    ui.level(0.0)              # let the bloom fall back the moment you stop

    if audio is None or len(audio) < MIN_SECONDS * SAMPLE_RATE:
        if live is not None:
            live.discard_reply()
        ui.note("(too short, ignored)")
        return

    ui.status(THINKING)
    # Gemini's transcript first: it streamed while you spoke and settles about
    # a third of a second after you let go. Whisper only if it never came.
    said = live.heard_text() if live is not None else ""
    if not said and whisper is not None:
        said = transcribe(whisper, audio)

    if not said:
        if live is not None:
            live.discard_reply()
        ui.note("(nothing heard)")
        return

    ui.turn("You", said)
    journal.said(said)

    # The one decision a turn makes, and there is one question in it: was an
    # agent called by name? Everything else is conversation, and conversation
    # has one voice.
    route = router.route_request(said)
    router.log_route(route, said)

    if route.name == router.GEMINI:
        if live is None:
            # No voice at all. Say so rather than answer in a different one:
            # the Claude path still exists, but it belongs to an agent and is
            # not a stand-in for chat - that substitution is the thing this
            # design removes.
            ui.note("No Gemini Live session, so there is nothing to answer with.")
            return
        # Nothing to send: Gemini heard the audio live and is already
        # answering. All that happens here is that the answer is allowed out
        # of the speakers.
        live.allow_reply()
        ui.status(SPEAKING)
        if not live.wait_for_reply():
            ui.note("Gemini Live didn't finish that reply in time.")
        spoken = live.reply_text()
        if not spoken and not live.alive:
            spoken = retry_after_drop(ui, voice, said)
        if spoken:
            ui.turn("Apollo", spoken)
            journal.answered(spoken)
        return

    # An agent was summoned. Whatever Gemini was about to say is thrown away
    # first, so the two never talk over each other.
    if live is not None:
        live.discard_reply()
    answer_with_agent(route.agent, said, ui)


def always_listening_turn(ui, voice):
    """One turn that nobody pressed a key for. Returns once, or not at all.

    Inside out compared to push-to-talk: the model decided where your sentence
    ended and has already answered it, so there is nothing to wait for and
    nothing to release. All that is left is to report it - unless an agent was
    summoned, in which case `agent_interrupt` has already stood Gemini down
    and the answer is still owed.
    """
    turn = voice.live.next_turn(timeout=0.25)
    if turn is None:
        return
    said, reply = turn
    if not said and not reply:
        return

    if said:
        ui.turn("You", said)
        journal.said(said)

    route = router.route_request(said)
    router.log_route(route, said)

    if route.name == router.AGENT:
        ui.status(THINKING)
        try:
            answer_with_agent(route.agent, said, ui)
        finally:
            ui.status(LISTENING)
        return

    if reply:
        ui.turn("Apollo", reply)
        journal.answered(reply)
        # Gemini has already answered - the audio is playing now - so this
        # is the one moment the overlay should say so. Back to LISTENING once
        # it has finished, which is what starts the answer's linger.
        ui.status(SPEAKING)
        voice.live.wait_until_quiet()
        ui.status(LISTENING)


def run_loop(ui, whisper, stop=None, esc_quits=False, voice=None, toggle=None):
    """Talk to Apollo forever, in whichever of the two modes is switched on.

    `ui` is a reporter (see ConsolePrinter). `stop`, if given, is a callable
    checked between turns so a host can shut the loop down.

    `voice` is the `Voice` holding the Gemini Live session. Every spoken turn
    goes to it and comes back in Puck's voice; the only thing that diverts one
    is summoning an agent by name, which `router.route_request` decides and
    `answer_with_agent` carries out. There is no path from ordinary
    conversation to Claude, which is the point.

    `toggle` is the `ListenToggle` watching CTRL+1. Its flag is read here
    rather than acted on from the hotkey thread, so a mode change lands
    between turns and never in the middle of one - and the two microphone
    paths can never both be live, because there is only ever one session and
    it is in one mode.

    `esc_quits` is for the console version, where ESC belongs to this program
    because it is the foreground app. The overlay must leave it alone: it runs
    for days behind whatever you are actually using, and a global ESC would
    make dismissing any unrelated dialog silently kill the assistant.
    """
    def wanted():
        return toggle is not None and toggle.enabled.is_set()

    # The mode the session that is up was opened for. Tracked rather than read
    # back off the session, so that a failed connection does not leave the
    # loop retrying every fiftieth of a second forever.
    applied = voice.auto_vad if voice is not None else False

    while stop is None or not stop():
        if esc_quits and keyboard.is_pressed("esc"):
            return

        if voice is None:
            time.sleep(0.05)
            continue

        # Two reasons to rebuild the session, and one piece of code for both,
        # because rebuilding is exactly what a mode change *is* - the mode is
        # part of the setup message (see `Voice.open`). Either the toggle has
        # moved, or the session died under us: a dropped websocket, a closed
        # laptop. Neither should take the assistant with it.
        want = wanted()
        dropped = voice.live is not None and not voice.ready
        if applied != want or dropped:
            if dropped:
                ui.note("Gemini Live dropped; reconnecting.")
            else:
                ui.note("Always-listening ON - just speak; CTRL+1 to stop."
                        if want else
                        "Always-listening OFF - hold CTRL+ALT to talk.")
            voice.open(want)
            applied = want
            # The overlay's own "listening" state, held for as long as the
            # mode is: the orb stays lit rather than blooming for one turn,
            # which is the cue that the microphone is no longer waiting on a
            # key. IDLE puts it back exactly where it was before.
            ui.status(LISTENING if want else IDLE)
            continue

        if voice.busy:
            time.sleep(0.05)   # a reconnect is under way; the mic is nobody's
            continue

        if voice.ready and voice.auto_vad:
            # Reports its own transitions. It used to be followed by an
            # unconditional LISTENING after every 250ms poll, which chimed
            # the page four times a second and wiped every answer.
            with TURN_GATE:
                always_listening_turn(ui, voice)
            continue

        # Push-to-talk. Nothing happens until the chord goes down.
        if not talk_held():
            time.sleep(0.05)
            continue

        try:
            with TURN_GATE:
                push_to_talk_turn(ui, whisper, voice)
        finally:
            ui.status(IDLE)

def main():
    ui = ConsolePrinter()

    print("Checking API access...", end="", flush=True)
    try:
        check_api()
    except RuntimeError as e:
        sys.exit(f"\n  {e}")
    print(" ok.")

    whisper = load_whisper()     # a background load; nothing waits for it

    load_voice(ui)

    print("Connecting to Gemini Live...")
    voice = Voice(ui, on_level=ui.level, on_user_text=agent_interrupt(ui),
                  on_heard=ui.partial, on_reply=lambda text: None,
                  on_activity=ui.activity, run_tool=tool_runner(ui))
    # Push-to-talk is the state Apollo starts in, always. Always-listening is
    # something you turn on, not something you arrive to.
    voice.open(auto_vad=False)

    toggle = ListenToggle(
        on_toggle=lambda on: ui.note(f"[{LISTEN_TOGGLE.upper()}] always-listening "
                                     f"{'ON' if on else 'OFF'}"))
    toggle.start()

    import reminders
    reminders.start_watcher(lambda r, late: fire_reminder(ui, voice, r, late),
                            TURN_GATE, lambda: False)

    import clips
    buffer = clips.ReplayBuffer().start()
    tools.set_clip_buffer(buffer)
    print(f"Replay buffer: last {clips.SECONDS}s of the screen, in memory. "
          f"Clips go to {clips.folder()}")

    print(f"\nReady. Hold [{HOTKEY.upper()}] and speak. Release to send.")
    print(f"[{LISTEN_TOGGLE.upper()}] toggles always-listening. ESC quits.\n")
    try:
        run_loop(ui, whisper, esc_quits=True, voice=voice, toggle=toggle)
    finally:
        # Before the interpreter tears anything down, and inside the `finally`
        # so that Ctrl+C goes through it too. This is the call that stops the
        # microphone callback while its event loop is still alive - skip it
        # and the exit prints "Event loop is closed" instead of "Bye".
        voice.close()
    print("Bye.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBye.")
