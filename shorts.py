"""YouTube Shorts, made by LYLA: a stick-man video, vertical, with a voice.

One a day at the peak hour (SHORTS_HOUR, 13:00 by default), a fact one day and
a story the next, or any time you ask ("ليلى سوي شورت عن ..."). Each one:

    1. the script - Gemini writes it as scenes: a hook first, then the beats,
       each with what is said, a pose for the stick man, a prop over him and
       a few words of caption;
    2. the voice - Edge TTS (free), one clip per scene;
    3. the pictures - drawn here: a stick man on white, moving (he breathes,
       his arms swing, he jumps when shocked), the prop beside him, and the
       caption in big type, its words lighting up as they are said;
    4. the video - FFmpeg, 1080x1920, every scene with its voice, joined.

It lands in Documents\\Apollo\\Shorts with a .txt beside it: the title, the
description and the hashtags, ready to paste when you upload.

Needs: pip install pillow edge-tts imageio-ffmpeg (FFmpeg comes with it).
SHORTS_LANG=ar for Arabic (default English); SHORTS_VOICE to pick a voice.
"""

import datetime as dt
import functools
import json
import logging
import math
import random
import os
import re
import subprocess
import tempfile
import threading

log = logging.getLogger("apollo.shorts")

# FFmpeg is run many times per Short; without this each run flashes a black console window on Windows
VERSION = "2026.10.04-r6 (vector, worlds, transitions, refined scripts)"      # shown in Telegram so you know which build made a Short
NOWIN = {"creationflags": 0x08000000} if os.name == "nt" else {}

W, H, FPS = 1080, 1920, 15
LEAD, PAUSE = 0.12, 0.3      # a short breath around each scene's words: brisk, but never a rant
LANG = (os.environ.get("SHORTS_LANG") or "en").lower()
VOICE = os.environ.get("SHORTS_VOICE") or ("ar-SA-HamedNeural" if LANG == "ar" else "en-US-AndrewNeural")
GLASSES = os.environ.get("SHORTS_GLASSES", "0").strip().lower() in ("1", "true", "yes", "on")
HOUR = int(os.environ.get("SHORTS_HOUR") or 13)

POSES = ("stand", "wave", "point", "think", "shock", "run", "cheer", "sad", "shrug")
CAMS = ("close", "push", "fisheye", "pull", "shake", "pan", "wide")
import shorts_art
import shorts_hero
import shorts_scenes
BGS = ("none",) + shorts_scenes.NAMES
IMAGES = os.environ.get("SHORTS_IMAGES", "").strip().lower() == "gemini"       # a Gemini picture per scene (paid)
STYLE = (os.environ.get("SHORTS_STYLE") or "vector").strip().lower()      # vector (flat, cel-shaded) or ink (pencil)
WRITER = os.environ.get("SHORTS_WRITER", "").strip().lower()                  # "claude" writes the scripts with Claude (paid)
CLAUDE_WRITER = os.environ.get("SHORTS_CLAUDE_MODEL") or "claude-sonnet-5-5"
ENGINE = os.environ.get("SHORTS_VOICE_ENGINE", "").strip().lower()            # "gemini" or "elevenlabs": paid, more human voices
ELEVEN_VOICE = os.environ.get("SHORTS_ELEVEN_VOICE") or "JBFqnCBsd6RMkjVDRZzb"
ELEVEN_MODEL = os.environ.get("SHORTS_ELEVEN_MODEL") or "eleven_multilingual_v2"
GEMINI_VOICE = os.environ.get("SHORTS_GEMINI_VOICE") or "Charon"
TTS_MODEL = os.environ.get("SHORTS_TTS_MODEL") or "gemini-2.5-flash-preview-tts"
GRADES = shorts_hero.GRADES
SIDES = ("none",) + shorts_hero.SIDES
WORLDS = {
    "sea": (("sea", "beach", "island", "underwater", "night"), ("sailor", "stranger")),
    "forest": (("forest", "mountains", "cave", "rain", "night"), ("farmer", "stranger")),
    "library": (("library", "room", "school", "night", "rain"), ("librarian", "teacher")),
    "prison": (("prison", "room", "rain", "night"), ("guard", "prisoner")),
    "money": (("city", "office", "bank", "chart", "cafe", "room"), ("boss", "banker", "landlord")),
    "desert": (("desert", "night", "cave", "mountains"), ("stranger",)),
    "space": (("space", "night", "room"), ("friend", "stranger")),
    "hospital": (("hospital", "room", "night"), ("doctor", "friend")),
    "school": (("school", "library", "room"), ("teacher", "friend")),
    "travel": (("airport", "city", "cafe", "sea"), ("pilot", "waiter", "stranger")),
    "castle": (("castle", "forest", "night", "mountains"), ("king", "guard")),
}
SHOWS = ("man", "env")
SFX = ("whoosh", "pop", "ding", "boom", "riser", "click")
PROPS = ("none", "note", "book", "key", "coffee", "map", "phone", "suitcase", "trophy", "question", "exclaim", "bulb", "money", "clock", "skull", "heart", "earth", "fire")

SYSTEM = (
    "You write YouTube Shorts scripts for a faceless channel in a flat 2D vector, bold-outline "
    "animation style: a blank-faced narrator-hero and the story shown on screen. 40-50 seconds "
    "spoken (115 to 140 words in all - short Shorts are watched to the end). Something must change "
    "on screen at least every 3 seconds. Build a real arc: a hook that lands in two seconds, the "
    "setup, the rising problem, the twist or the key insight, the payoff, then one line the viewer "
    "can repeat. EXPLAIN FULLY: say what happened, WHY it happened and what it means - a stranger "
    "must understand the whole idea, with concrete names, places, numbers and cause and effect, "
    "never vague claims. The very last line must lead straight back into the first line, so the "
    "Short loops without a seam (a replay counts as another view). 8 to 9 scenes, each 1 or 2 "
    "flowing sentences of 12 to 22 words, and every "
    "scene SHOWS something - never just a man talking. WRITING RULES: vary sentence length constantly (short fragments beside "
    "longer ones, never three sentences in a row with the same shape); never state an emotion, "
    "show it through an action or a detail; every money figure is oddly specific ($34, $1,847 - "
    "never $1,000); banned words: delve, moreover, furthermore, game-changer, unlock, elevate, "
    "navigate, landscape, embark, tapestry, testament to, 'in today's world', 'let's dive in', 'in "
    "conclusion', 'it's important to note', 'at the end of the day'. Use fragments on purpose ('Just "
    "tired.'), let some beats stay unresolved, add an occasional plainly-delivered quoted line from "
    "a side character and never explain it, and give each closing 'rule' line a different lead-in "
    "(or none). For money stories the narration is second person, present tense, flat and deadpan, "
    "zero exclamation marks, figures illustrative, and the video opens and closes on the same "
    "hyper-mundane moment (an exact time, one tiny detail); the closing scene may hand off to a new "
    "anonymous person starting at level one (newcomer: true). No music, nothing indecent, "
    "nothing against Islam. Answer ONLY with JSON: "
    '{"title": "...", "description": "...", "hashtags": ["#..."], "scenes": [{"say": '
    '"what the narrator says", "caption": "at most ONE short text: a number or 2-4 words", "bg": one of '
    + json.dumps(BGS) + ', "show": "man" or "env" (env = just the place, no narrator), "pose": one of '
    + json.dumps(POSES) + ', "prop": one of ' + json.dumps(PROPS) + ', "cam": one of ' + json.dumps(CAMS)
    + ', "sfx": one of ' + json.dumps(SFX) + ', "grade": one of ' + json.dumps(GRADES)
    + ', "tier": 1 broke / 2 stable / 3 established / 4 elite (his clothes), "friend": one of '
    + json.dumps(SIDES) + ' (a side character with a real face, when one is in the beat), "stat": '
    '{"text": "$1,847", "tone": "gain" or "loss"} (optional floating figure box), "arrow": "up" or "down" '
    '(optional), "split": [1-4, 1-4] (optional split-screen of two tiers), "newcomer": true (optional)}], '
    '"tags": ["..."] (15-25 searchable tags: broad, format, specific, long-tail; under 450 characters in all). '
    'The title follows a click formula with a specific dollar anchor when it fits (e.g. "Your Life at Every '
    'Level of Wealth - $0 to $10M", "Which Path? Same $60,000 a Year, Two Different Lives"); the description is '
    'a one-line hook, then 2-3 plain sentences, then a soft call to action. '
    'Side-character archetypes: a reckless-but-likable spender (friend), a wise elder (elder), a partner '
    '(partner), institutional figures (banker, boss, landlord) who get warmer as the tier rises. '
    "Pick the bg that matches what is told in that very scene; stay inside one world and change place "
    "only when the story truly moves. Keep the same side character throughout. "
    "grade is the mood (ladder stories only): warm = comfort or progress, cool = stress or hardship, neutral = facts, "
    "night = high stakes or late at night. sfx: boom for a shock, ding for a win or an idea, pop "
    "when an object appears, riser before a reveal, whoosh otherwise. Keep the camera moving, "
    "never the same cam twice in a row, fisheye and shake at most once.")


def style_file():
    import files
    return os.path.join(files.root(), "shorts_style.txt")


def style_notes():
    """The owner's standing instructions for every Short (what to tell, how slow, what to avoid)."""
    try:
        with open(style_file(), encoding="utf-8") as f:
            return f.read().strip()[:2000]
    except OSError:
        return ""


def set_style(text, add=True):
    """Save (or add to) the standing instructions; "" clears them."""
    text = (text or "").strip()
    keep = style_notes() if add and text else ""
    with open(style_file(), "w", encoding="utf-8") as f:
        f.write((keep + "\n" + text).strip() if text else "")
    return style_notes()


def kind_for(day):
    """A fact one day, a story the next."""
    return ("fact", "story", "ladder", "paths", "treatment")[day.toordinal() % 5]


KINDS = {
    "fact": "one amazing true fact, explained",
    "story": "a gripping short story with a twist (fiction is fine)",
    "paths": ("PATH A vs PATH B: one person, one identical paycheck, two lives run in parallel across the same age "
              "checkpoints - a builder who saves and invests disciplined amounts against a spender who upgrades "
              "his lifestyle - ending on the stark net-worth gap. At least 6 checkpoints, each a split-screen scene "
              "(split: [tier of the builder, tier of the spender]). Second person, present tense, flat and deadpan, "
              "oddly specific figures. Illustrative figures."),
    "treatment": ("a TREATMENT LADDER: how banks, family, coworkers and landlords treat the very same person at each "
                  "wealth tier. At least 6 tiers, each opening with an oddly specific dollar figure; the institutional "
                  "figure (teller, banker, landlord) gets visibly warmer as the money rises. Second person, present "
                  "tense, flat and deadpan, a closing one-line rule per tier. Illustrative figures."),
    "ladder": ("a POV wealth ladder: second person, present tense, flat and deadpan. Six levels from broke to "
               "elite, each opening with an oddly specific dollar figure (never round: $34, $1,847, $9,412), "
               "one hyper-granular money detail, a side character beat, and a closing one-line rule worded "
               "differently each time. Open and close on the same hyper-mundane moment (an exact time, a tiny "
               "detail). End with a one-sentence takeaway and a question for the comments. Illustrative figures."),
}


def _system():
    notes = style_notes()
    return ((SYSTEM.replace("8 to 10 scenes", "6 to 8 scenes") if IMAGES else SYSTEM)
            + (f" The channel owner's standing instructions, always follow them: {notes}" if notes else ""))


def _write(prompt, system):
    """The writer: Claude when SHORTS_WRITER=claude and there is a key (the strongest scripts),
    else - or if Claude fails - LYLA's usual brains."""
    if WRITER == "claude" and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            import assistant
            return assistant.ask_once(system, prompt, max_tokens=4500, model=CLAUDE_WRITER)
        except Exception as e:  # noqa: BLE001
            log.info("Claude did not write the script (%s); using LYLA's brains", e)
    import lyla
    return lyla.think(prompt, system)[0]


def ask_script(kind, topic="", think=None, world=""):
    language = "Arabic (clear Gulf-friendly Fusha)" if LANG == "ar" else "English"
    prompt = (f"Language: {language}. Kind: {KINDS.get(kind, KINDS['fact'])}. "
              f"Topic: {topic or 'your choice - something people would share'}."
              + (f" Set the whole story in this world: {world}. Backgrounds to use, mostly: {', '.join(WORLDS[world][0])}. "
                 f"Side characters that fit: {', '.join(WORLDS[world][1])}." if world in WORLDS else ""))
    if think is None:
        notes = style_notes()
        text = _write(prompt, _system())
    else:
        text = think(prompt)
    found = re.search(r"\{.*\}", text or "", re.S)
    if not found:
        raise RuntimeError("The script did not come back as JSON.")
    data = json.loads(found.group(0))
    if os.environ.get("SHORTS_REFINE", "1").strip().lower() not in ("0", "false", "no", "off"):
        data = _refine(data, think, prompt) or data
    scenes = [s for s in data.get("scenes", []) if str(s.get("say", "")).strip()]
    if not scenes:
        raise RuntimeError("The script had no scenes.")
    for s in scenes:
        s["pose"] = s.get("pose") if s.get("pose") in POSES else "stand"
        s["prop"] = s.get("prop") if s.get("prop") in PROPS else "none"
        s["caption"] = str(s.get("caption") or s["say"])[:60]
    for s in scenes:
        s["bg"] = s.get("bg") if s.get("bg") in shorts_scenes.NAMES else ""
        s["show"] = s.get("show") if s.get("show") in SHOWS and s["bg"] else "man"
        s["sfx"] = s.get("sfx") if s.get("sfx") in SFX else ""
        s["grade"] = s.get("grade") if s.get("grade") in GRADES else ""
        s["friend"] = s.get("friend") if s.get("friend") in shorts_hero.SIDES else ""
        s["tier"] = s.get("tier") if s.get("tier") in (1, 2, 3, 4) else 2
        s["caption"] = " ".join(s["caption"].split()[:6])
        stat = s.get("stat")
        s["stat"] = ({"text": str(stat.get("text", ""))[:12], "tone": stat.get("tone") if stat.get("tone") in ("gain", "loss") else "gain"}
                     if isinstance(stat, dict) and stat.get("text") else None)
        s["arrow"] = s.get("arrow") if s.get("arrow") in ("up", "down") else ""
        sp = s.get("split")
        s["split"] = [int(sp[0]), int(sp[1])] if isinstance(sp, list) and len(sp) == 2 and all(str(x).isdigit() and 1 <= int(x) <= 4 for x in sp) else None
        s["newcomer"] = bool(s.get("newcomer"))
    for i, s in enumerate(scenes):
        if s.get("cam") not in CAMS or (i and s["cam"] == scenes[i - 1]["cam"]):
            s["cam"] = CAMS[i % len(CAMS)]
    _lock_consistency(scenes, kind, world)
    data["scenes"] = scenes
    data["tags"] = trim_tags(data.get("tags") or [])
    if kind in WEALTH_KINDS and "disclaimer" not in str(data.get("description", "")).lower():
        data["description"] = (str(data.get("description", "")).strip() + "\n\nDisclaimer: this video is for entertainment and "
                               "educational illustration only. Figures are simplified, hypothetical estimates, not financial advice.").strip()
    return data


REFINE = ("You are the editor. Below is a draft Shorts script as JSON. Improve it and return the SAME JSON schema, "
          "nothing else. Check and fix: (1) does it FULLY explain the idea - what, why, and what it means - so a "
          "stranger understands it; add the missing cause-and-effect and concrete detail; (2) a hook that lands in two "
          "seconds, a clear arc, a closing line worth repeating; (3) specific figures, no banned words (delve, moreover, "
          "furthermore, game-changer, unlock, elevate, navigate, landscape, embark, tapestry); (4) every scene sentence "
          "has something visual to show; (5) 115-140 words in total, ending on a line that loops back to the opening; (6) captions at most 4 words. Keep every field "
          "(bg, show, pose, prop, cam, sfx, tier, friend) valid. Draft:\n")


def _refine(data, think, prompt):
    """A second pass by the model as editor; the first draft stands if it does not come back clean."""
    try:
        if think is None:
            text = _write(REFINE + json.dumps(data, ensure_ascii=False), _system())
        else:
            text = think(REFINE + json.dumps(data, ensure_ascii=False))
        found = re.search(r"\{.*\}", text or "", re.S)
        better = json.loads(found.group(0)) if found else None
        return better if better and len(better.get("scenes", [])) >= 4 else None
    except Exception:  # noqa: BLE001 - the draft is still good
        log.info("script refine failed", exc_info=True)
        return None


WEALTH_KINDS = ("ladder", "paths", "treatment")


def trim_tags(tags, limit=480):
    """Comma-joined tags kept under YouTube's ~500 character limit."""
    out, size = [], 0
    for t in tags:
        t = str(t).strip().lstrip("#")
        if t and size + len(t) + 2 <= limit:
            out.append(t)
            size += len(t) + 2
    return out


def _lock_consistency(scenes, kind, world):
    """One look for the whole video: the places stay in one world, the same side character,
    the same clothes and colour - unless it is a wealth ladder, where those change on purpose."""
    places = WORLDS[world][0] if world in WORLDS else ()
    last = places[0] if places else ""
    friend = next((s["friend"] for s in scenes if s.get("friend")), "")
    tier = scenes[0].get("tier", 2)
    for s in scenes:
        if places and s["bg"] not in places:
            s["bg"] = last
        if s["bg"]:
            last = s["bg"]
        if friend and s.get("friend"):
            s["friend"] = friend
        if kind not in WEALTH_KINDS:
            s["tier"], s["grade"] = tier, ""
    if len(scenes) > 2:                                # the story ends where it began: a seamless loop
        scenes[-1]["bg"] = scenes[0]["bg"]
        if kind in WEALTH_KINDS:
            scenes[-1]["tier"] = scenes[0]["tier"] if not scenes[-1].get("newcomer") else 1


# -- drawing -------------------------------------------------------------------------

SS = 1.25         # the world is drawn this much bigger, so a close-up stays sharp
PAPER = (248, 247, 242)
INK = (30, 29, 33)
_cache = {}


@functools.lru_cache(maxsize=16)
def _font(size):
    from PIL import ImageFont
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(here, "fonts", "thmanyahsans-Black.otf"),
                 "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/seguibl.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


class Pen:
    """A pen that draws like a hand: every line wobbles a little, and the wobble
    changes a few times a second (the 'boil' of hand-drawn animation). Everything
    is in plain 1080x1920 numbers; the picture itself is drawn k times bigger.
    `place()` shrinks what is drawn next about a point, to put the man small in a scene."""

    def __init__(self, d, k, seed=0):
        self.d, self.k, self.seed, self.n = d, k, seed, 0
        self.s, self.ax, self.ay, self.tx, self.ty = 1.0, 0.0, 0.0, 0.0, 0.0

    def place(self, scale=1.0, anchor=(0, 0), to=None):
        self.s, (self.ax, self.ay) = scale, anchor
        self.tx, self.ty = to if to is not None else anchor
        return self

    def _rand(self):
        self.n += 1
        return random.Random(self.seed * 7919 + self.n)

    def _pts(self, pts):
        if pts and isinstance(pts[0], (int, float)):
            pts = list(zip(pts[::2], pts[1::2]))
        return list(pts)

    def _m(self, x, y):
        return ((self.tx + (x - self.ax) * self.s) * self.k, (self.ty + (y - self.ay) * self.s) * self.k)

    def _w(self, width):
        return max(1, round(width * self.k * (self.s if self.s < 1 else 1)))

    def _wobble(self, pts, amount):
        if STYLE == "vector":
            amount = 0
        rnd, out = self._rand(), []
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            steps = max(1, int(math.hypot(x1 - x0, y1 - y0) / 45))
            for i in range(steps):
                f = i / steps
                out.append((x0 + (x1 - x0) * f + rnd.uniform(-amount, amount), y0 + (y1 - y0) * f + rnd.uniform(-amount, amount)))
        out.append((pts[-1][0] + rnd.uniform(-amount, amount), pts[-1][1] + rnd.uniform(-amount, amount)))
        return out

    def line(self, pts, fill=INK, width=7, wobble=2.2):
        pts = self._wobble(self._pts(pts), wobble)
        sc = [self._m(x, y) for x, y in pts]
        w = self._w(width)
        self.d.line(sc, fill=fill, width=w, joint="curve")
        r = w / 2 - 0.5
        for x, y in (sc[0], sc[-1]):
            self.d.ellipse([x - r, y - r, x + r, y + r], fill=fill)

    def polygon(self, pts, fill=None, outline=INK, width=7, wobble=2.2):
        pts = self._pts(pts)
        if fill is not None:
            self.d.polygon([self._m(x, y) for x, y in pts], fill=fill)
        if outline:
            self.line(pts + [pts[0]], fill=outline, width=width, wobble=wobble)

    def ellipse(self, box, fill=None, outline=INK, width=7, wobble=2.2):
        x0, y0, x1, y1 = box
        cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
        if fill is not None:
            (a, b), (c, e) = self._m(x0, y0), self._m(x1, y1)
            self.d.ellipse([a, b, c, e], fill=fill)
        if outline:
            rnd = self._rand()
            start = rnd.uniform(0, 6.28)
            n = max(14, int((rx + ry) / 6))
            pts = [(cx + rx * math.cos(start + 6.5 * i / n), cy + ry * math.sin(start + 6.5 * i / n)) for i in range(n + 1)]
            self.line(pts, fill=outline, width=width, wobble=wobble * 0.6)

    def dot(self, c, r, fill=INK):
        x, y = self._m(*c)
        rr = r * self.k * (self.s if self.s < 1 else 1)
        self.d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=fill)

    def arc(self, box, start, end, width=7):
        x0, y0, x1, y1 = box
        cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
        n = 14
        pts = [(cx + rx * math.cos(math.radians(start + (end - start) * i / n)),
                cy + ry * math.sin(math.radians(start + (end - start) * i / n))) for i in range(n + 1)]
        self.line(pts, width=width, wobble=1.0)

    def hatch(self, x0, y0, x1, y1, gap=15, slant=0.55, width=4):
        """Diagonal shading strokes inside a box - the shadow of a pencil drawing."""
        if STYLE == "vector":
            return
        h = y1 - y0
        x = x0 - slant * h
        while x < x1:
            a, b = x, x + slant * h          # from the bottom-left up to the top-right
            lo, hi = max(a, x0), min(b, x1)
            if hi > lo:
                f0, f1 = (lo - a) / (b - a), (hi - a) / (b - a)
                self.line([(lo, y1 - h * f0), (hi, y1 - h * f1)], width=width, wobble=1.2)
            x += gap

    def text(self, xy, text, font=None, fill=INK, anchor=None):
        x, y = self._m(*xy)
        if hasattr(font, "font_variant"):
            font = font.font_variant(size=max(1, int(font.size * self.k * (self.s if self.s < 1 else 1))))
        self.d.text((x, y), text, font=font, fill=fill, anchor=anchor)


def limbs(pose, t):
    """Angles (degrees from straight down) of the +x arm, the -x arm, the +x leg,
    the -x leg, and a small hop in px, for `pose` at time `t` seconds. Calm: it is a story."""
    s = math.sin(t * 2.4)
    table = {
        "stand": (16 + 2 * s, -16 - 2 * s, 5, -5, 0),
        "wave": (16, -140 + 16 * math.sin(t * 5), 5, -5, 0),
        "point": (16, -100 + 3 * s, 5, -5, 0),
        "think": (16, -150, 5, -5, 0),
        "shock": (118 + 4 * s, -118 - 4 * s, 10, -10, abs(math.sin(t * 5)) * 8),
        "run": (38 * s, -38 * s, 24 * s, -24 * s, abs(s) * 6),
        "cheer": (145 + 5 * s, -145 - 5 * s, 9, -9, abs(math.sin(t * 4)) * 8),
        "sad": (7, -7, 3, -3, 0),
        "pleased": (16, -16, 5, -5, 0),
        "shrug": (65 + 3 * s, -65 - 3 * s, 5, -5, 0),
    }
    return table.get(pose, table["stand"])


def _tip(a, length, angle):
    rad = math.radians(angle)
    return (a[0] + length * math.sin(rad), a[1] + length * math.cos(rad))


def _hand(d, c):
    d.ellipse([c[0] - 20, c[1] - 20, c[0] + 20, c[1] + 20], fill=PAPER, width=6)


def draw_man(d, cx, ground, pose, t, talking=False, prop="none", glasses=None, hero=None, tier=2):
    glasses = GLASSES if glasses is None else glasses
    if STYLE == "vector":
        return shorts_hero.draw_hero(d, cx, ground, pose, t, prop, hero or shorts_hero.hero_for("apollo"), tier,
                                     limbs(pose, t), _hold, glasses)
    if prop == "note":
        return _desk_scene(d, cx, pose, t, glasses)
    la, ra, ll, rl, jump = limbs(pose, t)
    hip_y = ground - 300 - jump
    sh_y = hip_y - 330 + math.sin(t * 1.8) * 3
    head_c = (cx + math.sin(t * 1.3) * 4, sh_y - 128 + (10 if pose == "sad" else 0))
    # the shadow on the floor, hatched
    d.line([(cx - 190, ground + 8), (cx + 190, ground + 8)], width=5)
    d.hatch(cx - 160, ground + 12, cx + 160, ground + 44, gap=16, width=3)
    # legs and feet
    for side, ang in ((1, ll), (-1, rl)):
        hip = (cx + side * 52, hip_y)
        knee = _tip(hip, 160, ang)
        foot = _tip(knee, 150, ang * 0.6)
        d.line([hip, knee, foot], width=8)
        d.line([foot, (foot[0] + side * 56, foot[1] + 6)], width=8)
    # the body: a shirt, with a hatched tie
    d.polygon([(cx - 118, sh_y), (cx + 118, sh_y), (cx + 86, hip_y), (cx - 86, hip_y)], fill=PAPER, width=8)
    d.polygon([(cx - 16, sh_y + 4), (cx + 16, sh_y + 4), (cx + 24, sh_y + 190), (cx, sh_y + 230), (cx - 24, sh_y + 190)], fill=PAPER, width=6, wobble=1.2)
    d.hatch(cx - 20, sh_y + 20, cx + 20, sh_y + 190, gap=9, width=3)
    d.hatch(cx + 40, sh_y + 30, cx + 82, hip_y - 20, gap=17, width=3)
    # the head
    d.line([(head_c[0], head_c[1] + 100), (cx, sh_y)], width=8)
    r = 110
    d.ellipse([head_c[0] - r, head_c[1] - r, head_c[0] + r, head_c[1] + r], fill=PAPER, width=8)
    for hx in (-14, 8, 30):                                   # a few hairs
        d.line([(head_c[0] + hx, head_c[1] - r + 4), (head_c[0] + hx + 8, head_c[1] - r - 26)], width=6, wobble=1.0)
    _face(d, head_c, pose, t, glasses)
    # arms, and what he holds
    hands = {}
    for side, ang in ((1, la), (-1, ra)):
        sh = (cx + side * 112, sh_y + 20)
        elbow = _tip(sh, 120, ang)
        hand = _tip(elbow, 110, ang * 0.85 + (-side * 22 if pose in ("stand", "think", "point") else 0))
        hands[side] = hand
        d.line([sh, elbow, hand], width=8)
    _hold(d, prop, hands, t)
    for hand in hands.values():
        _hand(d, hand)
    return head_c


def _face(d, head_c, pose, t, glasses):
    x, y = head_c
    shut = (t % 3.6) < 0.12
    big = pose == "shock"
    look = math.sin(t * 0.7) * 4
    for side in (-1, 1):
        ex, ey = x + side * 40, y - 4
        if shut:
            d.line([(ex - 10, ey), (ex + 10, ey)], width=5, wobble=0.5)
        else:
            d.dot((ex + look, ey), 11 if big else 8)
        if pose in ("shock", "think", "sad"):
            lift = {"shock": -24, "think": -16 if side > 0 else -4, "sad": -14}[pose]
            slant = 12 * side if pose == "sad" else 0
            d.line([(ex - 20, ey - 30 + lift + slant), (ex + 20, ey - 30 + lift - slant)], width=5, wobble=0.8)
    if glasses:
        for side in (-1, 1):
            gx = x + side * 40
            d.ellipse([gx - 36, y - 40, gx + 36, y + 32], fill=None, width=6, wobble=1.4)
        d.line([(x - 5, y - 6), (x + 5, y - 6)], width=5, wobble=0.4)
        d.line([(x - 76, y - 12), (x - 108, y - 22)], width=5, wobble=0.6)
        d.line([(x + 76, y - 12), (x + 108, y - 22)], width=5, wobble=0.6)
    mx, my = x, y + 50
    if big:
        d.ellipse([mx - 15, my - 6, mx + 15, my + 28], fill=INK, width=4)
    elif pose == "sad":
        d.arc([mx - 28, my + 4, mx + 28, my + 40], 200, 340, width=6)
    else:
        d.arc([mx - 34, my - 22, mx + 34, my + 14], 25, 155, width=6)        # the small smile


def _desk_scene(d, cx, pose, t, glasses):
    """Behind a desk, writing: the picture the channel is built on."""
    desk = 1250
    sh_y = desk - 250
    head_c = (cx + math.sin(t * 1.1) * 4, sh_y - 128)
    d.polygon([(cx - 118, sh_y), (cx + 118, sh_y), (cx + 140, desk), (cx - 140, desk)], fill=PAPER, width=8)
    d.polygon([(cx - 16, sh_y + 4), (cx + 16, sh_y + 4), (cx + 24, sh_y + 170), (cx, sh_y + 205), (cx - 24, sh_y + 170)], fill=PAPER, width=6, wobble=1.2)
    d.hatch(cx - 20, sh_y + 20, cx + 20, sh_y + 170, gap=9, width=3)
    d.hatch(cx + 50, sh_y + 30, cx + 120, desk - 6, gap=17, width=3)
    d.line([(head_c[0], head_c[1] + 100), (cx, sh_y)], width=8)
    r = 110
    d.ellipse([head_c[0] - r, head_c[1] - r, head_c[0] + r, head_c[1] + r], fill=PAPER, width=8)
    for hx in (-14, 8, 30):
        d.line([(head_c[0] + hx, head_c[1] - r + 4), (head_c[0] + hx + 8, head_c[1] - r - 26)], width=6, wobble=1.0)
    _face(d, head_c, "pleased", t, glasses)
    # the desk, with its grain
    d.line([(40, desk), (1040, desk + 6)], width=7, wobble=3)
    for i, (a, b) in enumerate(((60, 330), (150, 480), (700, 1000), (800, 1030))):
        d.line([(a, desk + 22 + i * 15), (b, desk + 22 + i * 15 + 3)], width=3, wobble=2)
    # the pad, and a hand that writes
    pad = [(cx - 250, desk + 110), (cx - 60, desk + 40), (cx + 170, desk + 55), (cx + 130, desk + 190)]
    d.polygon([pad[0], pad[1], pad[2], pad[3]], fill=PAPER, width=7)
    for i in range(4):
        d.line([(cx - 170 + i * 16, desk + 105 + i * 20), (cx + 60 + i * 12, desk + 72 + i * 20)], width=3, wobble=1.5)
    wx, wy = cx - 60 + math.sin(t * 2.5) * 20, desk + 92 + math.sin(t * 4) * 4
    d.line([(cx - 115, sh_y + 30), (cx - 175, desk - 60), (wx, wy)], width=8)
    d.line([(cx + 115, sh_y + 30), (cx + 200, desk - 50), (cx + 120, desk + 80)], width=8)
    d.line([(wx, wy), (wx - 22, wy - 85)], width=9, wobble=0.8)               # the pencil
    _hand(d, (wx - 6, wy - 12))
    _hand(d, (cx + 120, desk + 80))
    return head_c


def _hold(d, prop, hands, t):
    """What he holds or shows, drawn at his hand."""
    if prop == "none" or (prop == "note" and STYLE != "vector"):
        return
    hx, hy = hands[1]
    if prop == "note":                                       # a pad in one hand, a pencil in the other
        pad = [(hx - 40, hy - 150), (hx + 100, hy - 138), (hx + 78, hy + 40), (hx - 56, hy + 28)]
        d.polygon(pad, fill=(255, 239, 196), outline=INK, width=8)
        ox, oy = hands[-1]
        a, b2 = (ox - 66, oy - 150), (ox + 50, oy + 24)
        d.line([a, b2], fill=INK, width=40)
        d.line([a, b2], fill=(246, 190, 40), width=26)
        d.polygon([(b2[0] - 14, b2[1] - 2), (b2[0] + 16, b2[1] - 6), (b2[0] + 14, b2[1] + 40)], fill=(244, 214, 160), outline=INK, width=5)
        return
    cx, cy = hx + 10, hy - 100 + math.sin(t * 2) * 5
    if prop == "book":
        d.polygon([(cx - 70, cy - 60), (cx + 70, cy - 60), (cx + 70, cy + 60), (cx - 70, cy + 60)], fill=(196, 90, 80), outline=INK, width=8)
        d.polygon([(cx - 56, cy - 46), (cx + 56, cy - 46), (cx + 56, cy + 46), (cx - 56, cy + 46)], fill=(246, 240, 226), outline=INK, width=5)
        d.line([(cx, cy - 46), (cx, cy + 46)], width=5)
        return
    if prop == "key":
        d.ellipse([cx - 56, cy - 56, cx + 8, cy + 8], fill=(240, 200, 70), outline=INK, width=8)
        d.line([(cx - 8, cy), (cx + 80, cy + 70)], fill=INK, width=30)
        d.line([(cx - 8, cy), (cx + 80, cy + 70)], fill=(240, 200, 70), width=16)
        d.line([(cx + 50, cy + 48), (cx + 50, cy + 80)], fill=(240, 200, 70), width=12)
        return
    if prop == "coffee":
        d.polygon([(cx - 50, cy - 40), (cx + 50, cy - 40), (cx + 38, cy + 56), (cx - 38, cy + 56)], fill=(250, 250, 248), outline=INK, width=8)
        d.polygon([(cx - 46, cy - 14), (cx + 46, cy - 14), (cx + 42, cy + 16), (cx - 42, cy + 16)], fill=(140, 90, 60), outline=None)
        d.line([(cx - 20, cy - 70), (cx - 10, cy - 100), (cx - 20, cy - 130)], fill=(200, 200, 206), width=6)
        return
    if prop == "map":
        d.polygon([(cx - 90, cy - 60), (cx - 30, cy - 70), (cx + 30, cy - 56), (cx + 90, cy - 66), (cx + 90, cy + 60), (cx + 30, cy + 70), (cx - 30, cy + 56), (cx - 90, cy + 66)],
                  fill=(244, 226, 176), outline=INK, width=8)
        d.line([(cx - 60, cy + 30), (cx - 10, cy - 10), (cx + 30, cy + 20), (cx + 60, cy - 30)], fill=(200, 60, 60), width=7)
        return
    if prop == "phone":
        d.polygon([(cx - 36, cy - 66), (cx + 36, cy - 66), (cx + 36, cy + 66), (cx - 36, cy + 66)], fill=(40, 44, 56), outline=INK, width=8)
        d.polygon([(cx - 26, cy - 50), (cx + 26, cy - 50), (cx + 26, cy + 44), (cx - 26, cy + 44)], fill=(150, 214, 255), outline=None)
        return
    if prop == "suitcase":
        d.polygon([(cx - 80, cy - 40), (cx + 80, cy - 40), (cx + 80, cy + 60), (cx - 80, cy + 60)], fill=(150, 100, 64), outline=INK, width=8)
        d.line([(cx - 30, cy - 40), (cx - 30, cy - 66), (cx + 30, cy - 66), (cx + 30, cy - 40)], fill=INK, width=8)
        d.line([(cx - 80, cy + 8), (cx + 80, cy + 8)], fill=INK, width=5)
        return
    if prop == "trophy":
        d.polygon([(cx - 56, cy - 70), (cx + 56, cy - 70), (cx + 40, cy + 10), (cx - 40, cy + 10)], fill=(244, 200, 70), outline=INK, width=8)
        d.line([(cx, cy + 10), (cx, cy + 56)], fill=INK, width=14)
        d.polygon([(cx - 46, cy + 56), (cx + 46, cy + 56), (cx + 46, cy + 80), (cx - 46, cy + 80)], fill=(244, 200, 70), outline=INK, width=7)
        return
    f = _font(110)
    if prop in ("question", "exclaim"):
        d.ellipse([cx - 70, cy - 70, cx + 70, cy + 70], fill=PAPER, width=7)
        d.text((cx, cy + 4), "?" if prop == "question" else "!", font=f, anchor="mm")
    elif prop == "bulb":
        d.ellipse([cx - 56, cy - 70, cx + 56, cy + 44], fill=PAPER, width=7)
        d.polygon([(cx - 26, cy + 40), (cx + 26, cy + 40), (cx + 22, cy + 80), (cx - 22, cy + 80)], fill=PAPER, width=6)
        d.line([(cx - 20, cy + 58), (cx + 20, cy + 58)], width=4, wobble=1)
        for ang in (-50, -10, 30, 70, 110, 150, 190):
            a = math.radians(ang - 90)
            d.line([(cx + math.cos(a) * 80, cy - 12 + math.sin(a) * 80), (cx + math.cos(a) * 110, cy - 12 + math.sin(a) * 110)], width=5, wobble=1)
    elif prop == "money":
        d.polygon([(cx - 95, cy - 55), (cx + 95, cy - 60), (cx + 92, cy + 55), (cx - 98, cy + 58)], fill=PAPER, width=7)
        d.ellipse([cx - 34, cy - 34, cx + 34, cy + 34], fill=None, width=5)
        d.text((cx, cy + 2), "$", font=_font(70), anchor="mm")
    elif prop == "heart":
        pts = [(cx, cy + 70), (cx - 78, cy - 5), (cx - 66, cy - 55), (cx - 28, cy - 62), (cx, cy - 32),
               (cx + 28, cy - 62), (cx + 66, cy - 55), (cx + 78, cy - 5)]
        d.polygon(pts, fill=PAPER, width=7, wobble=1.5)
        d.hatch(cx + 10, cy - 20, cx + 60, cy + 30, gap=11, width=3)
    elif prop == "clock":
        d.ellipse([cx - 72, cy - 72, cx + 72, cy + 72], fill=PAPER, width=7)
        a = t * 1.2
        d.line([(cx, cy), (cx + math.sin(a) * 48, cy - math.cos(a) * 48)], width=6, wobble=0.5)
        d.line([(cx, cy), (cx + math.sin(a / 12) * 32, cy - math.cos(a / 12) * 32)], width=8, wobble=0.5)
    elif prop == "earth":
        d.ellipse([cx - 74, cy - 74, cx + 74, cy + 74], fill=PAPER, width=7)
        d.arc([cx - 40, cy - 74, cx + 40, cy + 74], 90, 270, width=4)
        d.line([(cx - 74, cy), (cx + 74, cy)], width=4, wobble=1)
        d.hatch(cx - 60, cy + 10, cx - 10, cy + 55, gap=12, width=3)
    elif prop == "fire":
        sway = math.sin(t * 6) * 6
        d.polygon([(cx - 60, cy + 56), (cx - 44 + sway, cy - 14), (cx - 6, cy - 48), (cx + sway, cy - 98),
                   (cx + 30, cy - 36), (cx + 62, cy - 8), (cx + 58, cy + 56)], fill=PAPER, width=7, wobble=1.5)
        d.hatch(cx - 24, cy + 10, cx + 28, cy + 52, gap=10, width=3)
    elif prop == "skull":
        d.ellipse([cx - 62, cy - 68, cx + 62, cy + 36], fill=PAPER, width=7)
        d.polygon([(cx - 34, cy + 28), (cx + 34, cy + 28), (cx + 30, cy + 70), (cx - 30, cy + 70)], fill=PAPER, width=6)
        for s in (-1, 1):
            d.ellipse([cx + s * 26 - 15, cy - 22, cx + s * 26 + 15, cy + 10], fill=INK, width=3)


def draw_prop(*_):
    """Kept for old callers: props are held by the man now (see draw_man)."""


def _background(pose, size):
    key = ("paper", size)
    if key not in _cache:
        from PIL import Image
        _cache[key] = Image.new("RGB", size, PAPER)
    return _cache[key].copy()


def avatar(path, size=1024, pose="pleased", prop="none", glasses=False):
    """A portrait of the character on paper, in the channel's style - a profile picture."""
    from PIL import Image, ImageDraw
    k = 2.0
    big = Image.new("RGB", (int(W * k), int(H * k)), PAPER)
    d = Pen(ImageDraw.Draw(big), k, seed=3)
    draw_man(d, W / 2, 1500, pose, 0.4, prop=prop, glasses=glasses, hero=shorts_hero.hero_for("avatar"), tier=3)
    box = tuple(int(v * k) for v in (W / 2 - 330, 560, W / 2 + 330, 1560))
    art = big.crop(box)
    side = max(art.size)
    canvas = Image.new("RGB", (side, side), PAPER)
    canvas.paste(art, ((side - art.width) // 2, (side - art.height) // 2))
    canvas.resize((size, size), Image.LANCZOS).save(path)
    return path


def _ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def camera(cam, t, p, head, body):
    """Where the camera looks: (zoom, focus x, focus y, bulge), in 1080x1920 numbers."""
    punch = 1
    bulge = 0.0
    if cam == "close":
        z, f = 1.5 + 0.25 * _ease(p), (head[0], head[1] + 60)
    elif cam == "push":
        z, f = 1.25 + 0.4 * _ease(p), (body[0], body[1] + (head[1] - body[1]) * _ease(p))
    elif cam == "pull":
        z, f = 1.8 - 0.55 * _ease(p), (head[0], head[1] + 140 * _ease(p))
    elif cam == "fisheye":
        z, f, bulge = 1.5 + 0.1 * math.sin(t * 2), (body[0], body[1] - 40), 0.2
    elif cam == "shake":
        z, f = 1.55, (body[0] + math.sin(t * 23) * 6, body[1] + math.cos(t * 19) * 6)
    elif cam == "pan":
        z, f = 1.6, (W * (0.3 + 0.4 * _ease(p)), body[1])
    else:
        z, f = 1.4, (body[0], body[1])
    return z * punch, f[0], f[1], bulge


def _bulge(img, s):
    """A fisheye: the middle swells, the edges hold."""
    import numpy as np
    from PIL import Image
    s = round(s, 1)
    key = ("bulge", s)
    if key not in _cache:
        ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
        dx, dy = (xs - W / 2) / (W / 2), (ys - H / 2) / (H / 2)
        r2 = np.clip((dx * dx + dy * dy) / 2, 0, 1)
        k = 1 - s * (1 - r2)
        _cache[key] = (np.clip(W / 2 + dx * k * W / 2, 0, W - 1).astype(np.int32),
                       np.clip(H / 2 + dy * k * H / 2, 0, H - 1).astype(np.int32))
    sx, sy = _cache[key]
    return Image.fromarray(np.asarray(img)[sy, sx])


def frame(scene, t, progress, title):
    """One picture of `scene`, `t` seconds in, `progress` 0..1 through its words."""
    from PIL import Image, ImageDraw
    pose = scene["pose"]
    art = scene.get("_art")
    if art:                                   # a Gemini picture: just move the camera over it
        key = ("art", art)
        if key not in _cache:
            _cache[key] = shorts_art.fits(art, (int(W * SS), int(H * SS)))
        world = _cache[key].copy()
        z, fx, fy, bulge = camera(scene.get("cam", "wide"), t, progress, (W / 2, 820), (W / 2, 1000))
        z = 1.0 + (z - 1.0) * 0.5
        cw, ch = W / z, H / z
        left = min(max(fx - cw / 2, 0), W - cw)
        top = min(max(fy - ch / 2, 0), H - ch)
        return _caption(world.resize((W, H), Image.BILINEAR, box=(left * SS, top * SS, (left + cw) * SS, (top + ch) * SS)), scene, progress, title, t)
    world = _background(pose, (int(W * SS), int(H * SS)))
    raw = ImageDraw.Draw(world)
    d = Pen(raw, SS, seed=int(t * 6))
    ground, cx = 1500, W / 2
    bg, show = scene.get("bg", ""), scene.get("show", "man")
    if bg:
        shorts_scenes.draw(d, bg, t)
    k, mx = (0.7, W * 0.62) if bg else (1.0, cx)         # in a place he is smaller, off to one side
    tier = scene.get("tier", 2)
    if show == "env":
        head, body = (W / 2, 700), (W / 2, 900)
    elif scene.get("split") and STYLE == "vector":        # path A | path B: the same man, two lives, side by side
        for x, tr, p in ((W * 0.27, scene["split"][0], "pleased"), (W * 0.73, scene["split"][1], pose if pose != "stand" else "sad")):
            d.place(0.56, (cx, ground), (x, ground))
            draw_man(d, cx, ground, p, t, prop="none", hero=scene.get("_hero"), tier=tr)
            d.place()
        d.line([(W / 2, 260), (W / 2, 1560)], width=10, wobble=0)
        head, body = (W / 2, 900), (W / 2, 1000)
    else:
        d.place(k, (cx, ground), (mx, ground))
        head = draw_man(d, cx, ground, pose, t, talking=progress < 1, prop=scene["prop"],
                        hero=scene.get("_hero"), tier=tier)
        d.place()
        if scene.get("friend") and STYLE == "vector":
            side = scene["friend"]
            institutional = side in ("banker", "boss", "landlord", "guard", "teacher", "doctor", "librarian")
            mood = "warm" if (institutional and tier >= 3) else ("angry" if pose == "shock" else ("sad" if pose == "sad" else "calm"))
            d.place(0.6, (W * 0.27, ground), (W * 0.27, ground))
            shorts_hero.draw_side(d, side, W * 0.27, ground, t, mood)
            d.place()
        head = (mx + (head[0] - cx) * k, ground + (head[1] - ground) * k)
        body = (mx, ground + (1000 - ground) * k)
    if scene.get("stat") and STYLE == "vector":            # a floating figure box, and an arrow
        _stat(d, scene["stat"], scene.get("arrow", ""), head if show != "env" else (W / 2, 700), t)
    # the camera: crop the big world to a window and scale it to the screen
    z, fx, fy, bulge = camera(scene.get("cam", "wide"), t, progress, head, body)
    if bg:
        z = 1.0 + (z - 1.0) * 0.55                       # keep the place in view
    cw, ch = W / z, H / z
    left = min(max(fx - cw / 2, 0), W - cw)
    top = min(max(fy - ch / 2, 0), H - ch)
    img = world.resize((W, H), Image.BILINEAR, box=(left * SS, top * SS, (left + cw) * SS, (top + ch) * SS))
    if bulge:
        try:
            img = _bulge(img, bulge)
        except ImportError:
            pass
    if scene.get("grade") and STYLE == "vector":
        img = shorts_hero.grade(img, scene["grade"])
    return _caption(img, scene, progress, title, t)


def _stat(d, stat, arrow, near, t):
    """A rounded callout with a glowing border and a bold number, plus an up or down arrow."""
    x, y = near[0] + 20, near[1] - 330 + math.sin(t * 2.2) * 6
    col = (46, 190, 110) if stat["tone"] == "gain" else (214, 70, 70)
    glow = tuple(int(c + (255 - c) * 0.65) for c in col)
    w = 56 + 40 * len(stat["text"])
    for grow, c in ((16, glow), (8, glow), (0, col)):
        box = [x - w / 2 - grow, y - 56 - grow, x + w / 2 + grow, y + 56 + grow]
        d.polygon([(box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])], fill=None if grow else (255, 255, 255),
                  outline=c, width=8, wobble=0)
    d.text((x, y), stat["text"], font=_font(78), fill=(30, 29, 33), anchor="mm")
    if arrow:
        sign = -1 if arrow == "up" else 1
        ax, ay = x + w / 2 + 70, y
        d.polygon([(ax, ay + sign * 56), (ax - 44, ay - sign * 22), (ax - 14, ay - sign * 22), (ax - 14, ay - sign * 60),
                   (ax + 14, ay - sign * 60), (ax + 14, ay - sign * 22), (ax + 44, ay - sign * 22)], fill=col, outline=INK, width=6, wobble=0)


def _caption(img, scene, progress, title, age=9.0):
    from PIL import Image, ImageDraw
    # the caption sits on the screen, never zoomed: calm ink type, the spoken words dark
    d = ImageDraw.Draw(img)
    pop = 1 + 0.16 * max(0.0, 1 - age / 0.22)          # each new caption pops in, a beat the eye catches
    big = _font(int(78 * pop))
    words = scene["caption"].split()
    lit = max(1, math.ceil(len(words) * min(1.0, progress * 1.1)))
    lines, cur = [], []
    for w in words:
        if len(" ".join(cur + [w])) > 18 and cur:
            lines.append(cur)
            cur = []
        cur.append(w)
    lines.append(cur)
    y, n = 400, 0                                         # below the app's top bar, far above the bottom 20%
    rtl = LANG == "ar"
    widest = max(d.textlength(" ".join(line), font=big) for line in lines)
    card = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle([W / 2 - widest / 2 - 40, y - 24, W / 2 + widest / 2 + 40, y + 100 * len(lines) + 4],
                                           radius=36, fill=PAPER + (238,))
    img = Image.alpha_composite(img.convert("RGBA"), card).convert("RGB")
    d = ImageDraw.Draw(img)
    for line in lines:
        text_w = d.textlength(" ".join(line), font=big)
        x = W / 2 - text_w / 2
        for w in (reversed(line) if rtl else line):
            n += 1
            d.text((x, y), w, font=big, fill=INK if n <= lit else (176, 174, 170))
            x += d.textlength(w + " ", font=big)
        y += 100
    return img


# -- voice and video -----------------------------------------------------------------

def _ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _gemini_pcm(text, voice):
    """Gemini's text-to-speech: raw 16-bit mono PCM at 24 kHz. Tests replace this."""
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    style = os.environ.get("SHORTS_VOICE_STYLE") or "Read this as a calm, gripping storyteller, natural and unhurried, with real feeling:"
    response = client.models.generate_content(
        model=TTS_MODEL, contents=f"{style} {text}",
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)))))
    for part in response.candidates[0].content.parts:
        if getattr(part, "inline_data", None) is not None and part.inline_data.data:
            return part.inline_data.data
    raise RuntimeError("Gemini returned no audio")


def _eleven_mp3(text):
    """ElevenLabs text-to-speech: MP3 bytes. Tests replace this."""
    import json as _json
    import urllib.request
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE}?output_format=mp3_44100_128",
        _json.dumps({"text": text, "model_id": ELEVEN_MODEL}).encode(),
        {"xi-api-key": os.environ.get("ELEVENLABS_API_KEY", ""), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310 - fixed https host
        return r.read()


def speak(text, path, voice=VOICE):
    if ENGINE == "elevenlabs" and os.environ.get("ELEVENLABS_API_KEY"):
        try:
            data = _eleven_mp3(text)
            with open(path, "wb") as f:
                f.write(data)
            return
        except Exception as e:  # noqa: BLE001 - the free voice is still there
            log.info("ElevenLabs voice failed (%s); using the free voice", str(e)[:160])
    if ENGINE == "gemini" and os.environ.get("GEMINI_API_KEY"):
        try:
            import wave
            pcm = _gemini_pcm(text, GEMINI_VOICE)
            with wave.open(path, "wb") as w:             # a WAV in the scene's file: FFmpeg reads it by content
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(24000)
                w.writeframes(pcm)
            return
        except Exception as e:  # noqa: BLE001 - the free voice is still there
            log.info("Gemini voice failed (%s); using the free voice", str(e)[:160])
    import asyncio
    import edge_tts
    asyncio.run(edge_tts.Communicate(text, voice, rate="+8%").save(path))


def duration(path):
    out = subprocess.run([_ffmpeg(), "-i", path], capture_output=True, text=True, **NOWIN).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 3.0


def _pad(audio, out):
    """The voice with a breath of silence before it and after it."""
    subprocess.run([_ffmpeg(), "-y", "-loglevel", "error",
                    "-f", "lavfi", "-t", str(LEAD), "-i", "anullsrc=r=24000:cl=mono", "-i", audio,
                    "-f", "lavfi", "-t", str(PAUSE), "-i", "anullsrc=r=24000:cl=mono",
                    "-filter_complex", "[1:a]aresample=24000,aformat=channel_layouts=mono[v];[0:a][v][2:a]concat=n=3:v=0:a=1[out]",
                    "-map", "[out]", out], check=True, capture_output=True, **NOWIN)
    return out


IMAGE_MAX = int(os.environ.get("SHORTS_IMAGE_MAX") or 12)


def _pictures(scenes, hero, folder, step):
    """A Gemini picture per scene. Stops for good on a quota or billing error; one scene that
    fails is simply drawn the usual way."""
    made = 0
    for i, scene in enumerate(scenes):
        if made >= IMAGE_MAX:
            break
        step(f"Picture {i + 1} of {len(scenes)} (Gemini)")
        try:
            scene["_art"] = shorts_art.generate(scene, hero, folder)
            made += 1
        except Exception as e:  # noqa: BLE001
            text = str(e)
            log.info("Gemini picture %d failed: %s", i + 1, text[:200])
            if any(k in text for k in ("429", "RESOURCE_EXHAUSTED", "billing", "PERMISSION_DENIED", "limit: 0", "quota")):
                step("Gemini pictures are not available on this key (billing or quota) - drawing the rest myself")
                break


def _with_sound(padded, scene, first, work):
    """The voice with the sound of the place and the accents on the cut; the bare voice if numpy is missing."""
    try:
        import shorts_sfx
    except ImportError:
        return padded
    accent = scene.get("sfx") or ({"shock": "boom", "cheer": "ding"}.get(scene.get("pose"))
                                  or ("pop" if scene.get("prop") not in (None, "none", "note") else ""))
    cues = [(0.0, "riser" if first else "whoosh")] + ([(LEAD + 0.1, accent)] if accent else [])
    try:
        return shorts_sfx.mix(padded, work, scene.get("bg", ""), cues)
    except Exception:  # noqa: BLE001 - a sound that fails never costs the video
        log.info("sound mix failed", exc_info=True)
        return padded


def _render_cuts(script, out_path, speak_fn=speak, work=None, step=lambda t: None):
    """The whole video as separate scene clips joined with hard cuts (used when numpy is missing)."""
    work = work or tempfile.mkdtemp(prefix="short-")
    parts = []
    hero = shorts_hero.hero_for(script.get("title", "") or work)          # picked once, locked for the whole video
    for scene in script["scenes"]:
        scene["_hero"] = hero
    if IMAGES:
        _pictures(script["scenes"], hero, os.path.join(work, "art"), step)
    for i, scene in enumerate(script["scenes"]):
        step(f"Scene {i + 1} of {len(script['scenes'])}: voice and drawing")
        audio = os.path.join(work, f"s{i}.mp3")
        speak_fn(scene["say"], audio)
        spoken = duration(audio)
        secs = LEAD + spoken + PAUSE
        clip = os.path.join(work, f"s{i}.mp4")
        padded = _pad(audio, os.path.join(work, f"s{i}.wav"))
        padded = _with_sound(padded, scene, first=(i == 0), work=os.path.join(work, f"s{i}m.wav"))
        cmd = [_ffmpeg(), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS),
               "-i", "-", "-i", padded, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
               "-c:a", "aac", "-t", f"{secs:.2f}", clip]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, **NOWIN)
        try:
            for f in range(int(secs * FPS)):
                t = f / FPS
                frame(scene, t, max(0.0, t - LEAD) / max(0.1, spoken), script.get("title", "")).save(
                    proc.stdin, "PNG", compress_level=1)
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass            # FFmpeg stopped early: its own message says why, below
        err = proc.stderr.read().decode("utf-8", "replace").strip()
        if proc.wait() != 0:
            raise RuntimeError("FFmpeg could not make a scene: " + (err[-400:] or "no message"))
        parts.append(clip)
    listing = os.path.join(work, "list.txt")
    with open(listing, "w", encoding="utf-8") as f:
        f.writelines(f"file '{p}'\n" for p in parts)
    subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listing,
                    "-c", "copy", out_path], check=True, **NOWIN)
    return out_path


TRANS = 0.3       # seconds two scenes overlap in a transition
TRANSITIONS = ("slide", "fade", "zoom", "whip")


def _transition(a, b, p, kind):
    """The picture `p` (0..1) of the way from scene picture `a` to `b`."""
    from PIL import Image, ImageFilter
    p = _ease(p)
    if kind == "fade":
        return Image.blend(a, b, p)
    if kind == "zoom":                                   # a pushes in and dissolves into b
        z = 1 + 0.45 * p
        cw, ch = W / z, H / z
        zoomed = a.resize((W, H), Image.BILINEAR, box=((W - cw) / 2, (H - ch) / 2, (W + cw) / 2, (H + ch) / 2))
        return Image.blend(zoomed, b, p)
    shift = int(W * p)                                   # slide / whip: b pushes a out to the left
    out = Image.new("RGB", (W, H))
    out.paste(a, (-shift, 0))
    out.paste(b, (W - shift, 0))
    if kind == "whip":
        out = out.filter(ImageFilter.GaussianBlur(26 * math.sin(math.pi * p)))
    return out


def _pick_transitions(scenes):
    """Same place: a soft fade. A new place: slide, zoom or whip, never the same twice running."""
    kinds, last = [], ""
    for i, sc in enumerate(scenes):
        if i == 0:
            kinds.append("")
            continue
        same = sc.get("bg") == scenes[i - 1].get("bg")
        pool = ("fade",) if same else tuple(k for k in TRANSITIONS if k != "fade" and k != last) or TRANSITIONS
        last = pool[(i * 7) % len(pool)]
        kinds.append(last)
    return kinds


def render(script, out_path, speak_fn=speak, work=None, step=lambda t: None):
    """The whole video in one pass, with real transitions between scenes. Returns out_path."""
    try:
        import numpy as np
        import shorts_sfx
    except ImportError:
        return _render_cuts(script, out_path, speak_fn, work, step)
    work = work or tempfile.mkdtemp(prefix="short-")
    scenes = script["scenes"]
    hero = shorts_hero.hero_for(script.get("title", "") or work)          # picked once, locked for the whole video
    for scene in scenes:
        scene["_hero"] = hero
        if scene.get("newcomer"):                       # the hand-off: someone new, at level one
            scene["_hero"], scene["tier"] = shorts_hero.hero_for((script.get("title", "") or work) + "#new"), 1
    if IMAGES:
        _pictures(scenes, hero, os.path.join(work, "art"), step)
    # 1. every scene's voice, with its sound under it
    infos = []
    for i, scene in enumerate(scenes):
        step(f"Scene {i + 1} of {len(scenes)}: voice and sound")
        audio = os.path.join(work, f"s{i}.mp3")
        speak_fn(scene["say"], audio)
        spoken = duration(audio)
        padded = _pad(audio, os.path.join(work, f"s{i}.wav"))
        mixed = _with_sound(padded, scene, first=(i == 0), work=os.path.join(work, f"s{i}m.wav"))
        infos.append({"wav": mixed, "spoken": spoken, "length": LEAD + spoken + PAUSE})
    # 2. the timeline: each scene starts TRANS before the last one ends
    starts, at = [], 0.0
    for info in infos:
        starts.append(at)
        at += info["length"] - TRANS
    total = starts[-1] + infos[-1]["length"]
    master = np.zeros(int(total * shorts_sfx.SR) + 1, dtype=np.float32)
    for st, info in zip(starts, infos):
        voice, _rate = shorts_sfx.read_wav(info["wav"])
        s0 = int(st * shorts_sfx.SR)
        edge = int(0.05 * shorts_sfx.SR)
        voice[:edge] *= np.linspace(0, 1, edge)
        voice[-edge:] *= np.linspace(1, 0, edge)
        master[s0:s0 + len(voice)] += voice
    master_wav = os.path.join(work, "master.wav")
    shorts_sfx.write_wav(master_wav, master / max(1.0, float(np.max(np.abs(master)))))
    # 3. the picture, scene by scene, blended where two overlap
    kinds = _pick_transitions(scenes)
    cmd = [_ffmpeg(), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
           "-i", master_wav, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-preset", "veryfast", "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.2f}", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, **NOWIN)
    title = script.get("title", "")

    def pic(i, T):
        local = T - starts[i]
        return frame(scenes[i], local, max(0.0, local - LEAD) / max(0.1, infos[i]["spoken"]), title)

    try:
        frames = int(total * FPS)
        for f in range(frames):
            if f % (FPS * 4) == 0:
                step(f"Drawing the video: {int(100 * f / frames)}%")
            T = f / FPS
            i = max(k for k in range(len(starts)) if starts[k] <= T)
            if i and T < starts[i] + TRANS:
                img = _transition(pic(i - 1, T), pic(i, T), (T - starts[i]) / TRANS, kinds[i])
            else:
                img = pic(i, T)
            img.save(proc.stdin, "PNG", compress_level=1)
        proc.stdin.close()
    except (BrokenPipeError, OSError):
        pass            # FFmpeg stopped early: its own message says why, below
    err = proc.stderr.read().decode("utf-8", "replace").strip()
    if proc.wait() != 0:
        raise RuntimeError("FFmpeg could not make the video: " + (err[-400:] or "no message"))
    return out_path


def folder():
    import files
    path = os.path.join(files.root(), "Shorts")
    os.makedirs(path, exist_ok=True)
    return path


def _preview(video, out):
    """One picture of the whole Short - a frame every few seconds - so it can be looked at (or sent) without playing it."""
    try:
        rate = 16 / max(2.0, duration(video))                 # sixteen frames, spread over the whole Short
        subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-i", video, "-vf",
                        f"fps={rate:.4f},scale=240:-1,tile=8x2:padding=6:color=white", "-frames:v", "1", out],
                       check=True, capture_output=True, **NOWIN)
    except Exception:  # noqa: BLE001 - a preview is a convenience
        log.info("no preview sheet", exc_info=True)


def make(kind=None, topic="", think=None, speak_fn=speak, now=None, step=lambda t: None, world=""):
    """Write, voice, draw and join one Short. Returns {path, title, notes}."""
    now = now or dt.datetime.now()
    kind = kind or kind_for(now.date())
    for need in ("PIL", "edge_tts", "imageio_ffmpeg"):
        try:
            __import__(need)
        except ImportError as e:
            raise RuntimeError("Missing a library: run  python -m pip install pillow edge-tts imageio-ffmpeg") from e
    step(f"Writing the script ({kind})")
    script = ask_script(kind, topic, think, world)
    slug = re.sub(r"[^\w\- ]+", "", script.get("title", "short"))[:50].strip() or "short"
    base = os.path.join(folder(), f"{now:%Y-%m-%d %H%M} {slug}")
    render(script, base + ".mp4", speak_fn, step=step)
    step("Making the preview sheet")
    _preview(base + ".mp4", base + " preview.png")
    step("Joining the scenes")
    notes = (f"{script.get('title', '')}\n\n{script.get('description', '')}\n\n"
             + " ".join(script.get("hashtags", []) + ["#shorts"])
             + (f"\n\nTags: {', '.join(script['tags'])}" if script.get("tags") else "")
             + f"\n\n[made by Apollo build {VERSION}]")
    with open(base + ".txt", "w", encoding="utf-8") as f:
        f.write(notes)
    log.info("short made: %s", base)
    return {"path": base + ".mp4", "title": script.get("title", ""), "notes": base + ".txt", "kind": kind}


def make_in_background(kind=None, topic="", done=None):
    """Hand it to LYLA's desk: her card shows it, Apollo tells you when done."""
    try:
        import crew
        what = f"Make a YouTube Short{(' about ' + topic) if topic else ''}"
        return crew.desk("LYLA").take(what, short=True, kind=kind, topic=topic)
    except Exception:  # noqa: BLE001 - no desk: make it on a thread of its own
        log.debug("no LYLA desk for the short", exc_info=True)
    return _make_on_thread(kind, topic, done)


def _make_on_thread(kind=None, topic="", done=None):
    def run():
        try:
            result = make(kind, topic)
        except Exception as e:  # noqa: BLE001
            log.warning("short failed: %s", e)
            result = {"error": str(e) or type(e).__name__}
        if done:
            done(result)
    threading.Thread(target=run, daemon=True, name="short").start()
