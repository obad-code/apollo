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
import json
import logging
import math
import os
import re
import subprocess
import tempfile
import threading

log = logging.getLogger("apollo.shorts")

W, H, FPS = 1080, 1920, 15
LANG = (os.environ.get("SHORTS_LANG") or "en").lower()
VOICE = os.environ.get("SHORTS_VOICE") or ("ar-SA-HamedNeural" if LANG == "ar" else "en-US-AndrewNeural")
HOUR = int(os.environ.get("SHORTS_HOUR") or 13)

POSES = ("stand", "wave", "point", "think", "shock", "run", "cheer", "sad", "shrug")
PROPS = ("none", "question", "exclaim", "bulb", "money", "clock", "skull", "heart", "earth", "fire")

SYSTEM = (
    "You write YouTube Shorts scripts for a stick-man animation channel. 35-50 seconds "
    "spoken. The first line is a hook that stops the scroll. Short punchy sentences. No "
    "music, nothing indecent, nothing against Islam. Answer ONLY with JSON: "
    '{"title": "...", "description": "...", "hashtags": ["#..."], "scenes": [{"say": '
    '"what the narrator says", "caption": "3-6 key words", "pose": one of '
    + json.dumps(POSES) + ', "prop": one of ' + json.dumps(PROPS) + "}]} with 6 to 9 scenes.")


def kind_for(day):
    """A fact one day, a story the next."""
    return "fact" if day.toordinal() % 2 == 0 else "story"


def ask_script(kind, topic="", think=None):
    language = "Arabic (clear Gulf-friendly Fusha)" if LANG == "ar" else "English"
    prompt = (f"Language: {language}. Kind: {'one amazing true fact, explained' if kind == 'fact' else 'a gripping short story with a twist (fiction is fine)'}. "
              f"Topic: {topic or 'your choice - something people would share'}.")
    if think is None:
        import lyla
        text, _brain = lyla.think(prompt, SYSTEM)
    else:
        text = think(prompt)
    found = re.search(r"\{.*\}", text or "", re.S)
    if not found:
        raise RuntimeError("The script did not come back as JSON.")
    data = json.loads(found.group(0))
    scenes = [s for s in data.get("scenes", []) if str(s.get("say", "")).strip()]
    if not scenes:
        raise RuntimeError("The script had no scenes.")
    for s in scenes:
        s["pose"] = s.get("pose") if s.get("pose") in POSES else "stand"
        s["prop"] = s.get("prop") if s.get("prop") in PROPS else "none"
        s["caption"] = str(s.get("caption") or s["say"])[:60]
    data["scenes"] = scenes
    return data


# -- drawing -------------------------------------------------------------------------

def _font(size):
    from PIL import ImageFont
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(here, "fonts", "thmanyahsans-Black.otf"),
                 "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/seguibl.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def limbs(pose, t):
    """Angles (degrees from straight down) of left arm, right arm, left leg,
    right leg, and a jump in px, for `pose` at time `t` seconds."""
    s = math.sin(t * 6.0)
    table = {
        "stand": (15 + 3 * s, -15 - 3 * s, 8, -8, 0),
        "wave": (15, -150 + 25 * s, 8, -8, 0),
        "point": (15, -90, 8, -8, 0),
        "think": (20, -150, 8, -8, 0),
        "shock": (140 + 10 * s, -140 - 10 * s, 25, -25, abs(math.sin(t * 9)) * 40),
        "run": (50 * s, -50 * s, 35 * s, -35 * s, abs(s) * 18),
        "cheer": (160 + 8 * s, -160 - 8 * s, 15, -15, abs(math.sin(t * 7)) * 30),
        "sad": (5, -5, 4, -4, 0),
        "shrug": (70, -70, 8, -8, 0),
    }
    return table.get(pose, table["stand"])


def _line(d, a, length, angle, width=14):
    rad = math.radians(angle)
    b = (a[0] + length * math.sin(rad), a[1] + length * math.cos(rad))
    d.line([a, b], fill=(20, 20, 24), width=width)
    return b


def draw_man(d, cx, ground, pose, t):
    la, ra, ll, rl, jump = limbs(pose, t)
    breathe = math.sin(t * 2.2) * 4
    hip = (cx, ground - 300 - jump)
    neck = (cx, hip[1] - 260 + breathe)
    tilt = -8 if pose == "sad" else 0
    head_c = (neck[0], neck[1] - 75 + (12 if pose == "sad" else 0))
    d.line([hip, neck], fill=(20, 20, 24), width=16)
    d.ellipse([head_c[0] - 70, head_c[1] - 70, head_c[0] + 70, head_c[1] + 70], outline=(20, 20, 24), width=14, fill="white")
    # eyes: a blink now and then; wide when shocked
    shut = (t % 3.3) < 0.12
    ew = 14 if pose == "shock" else 9
    for side in (-1, 1):
        ex, ey = head_c[0] + side * 24, head_c[1] - 6 + tilt
        if shut:
            d.line([ex - ew, ey, ex + ew, ey], fill=(20, 20, 24), width=6)
        else:
            d.ellipse([ex - ew, ey - ew, ex + ew, ey + ew], fill=(20, 20, 24))
    mouth = {"shock": "o", "sad": "frown", "cheer": "smile", "wave": "smile"}.get(pose, "line")
    mx, my = head_c[0], head_c[1] + 30
    if mouth == "o":
        d.ellipse([mx - 14, my - 10, mx + 14, my + 22], outline=(20, 20, 24), width=6)
    elif mouth == "smile":
        d.arc([mx - 28, my - 24, mx + 28, my + 14], 20, 160, fill=(20, 20, 24), width=6)
    elif mouth == "frown":
        d.arc([mx - 26, my + 2, mx + 26, my + 34], 200, 340, fill=(20, 20, 24), width=6)
    else:
        d.line([mx - 18, my + 4, mx + 18, my + 4], fill=(20, 20, 24), width=6)
    shoulder = (neck[0], neck[1] + 30)
    for angle in (la, ra):
        elbow = _line(d, shoulder, 120, angle)
        _line(d, elbow, 110, angle * 0.8)
    for angle in (ll, rl):
        knee = _line(d, hip, 150, angle, 16)
        _line(d, knee, 140, angle * 0.6, 16)
    return head_c


def draw_prop(d, prop, x, y, t, font):
    bob = math.sin(t * 3) * 12
    y += bob
    if prop == "none":
        return
    glyph = {"question": "?", "exclaim": "!", "money": "$", "skull": "☠", "heart": "♥",
             "earth": "◍", "clock": "◷", "fire": "▲", "bulb": "✦"}[prop]
    colour = {"money": (30, 160, 80), "heart": (220, 50, 70), "fire": (240, 110, 30),
              "bulb": (245, 180, 0), "exclaim": (230, 60, 60)}.get(prop, (20, 20, 24))
    d.ellipse([x - 95, y - 95, x + 95, y + 95], fill=(245, 245, 247), outline=colour, width=8)
    d.text((x, y), glyph, font=font, fill=colour, anchor="mm")


def frame(scene, t, progress, title):
    """One picture of `scene`, `t` seconds in, `progress` 0..1 through its words."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    big, mid, small = _font(92), _font(64), _font(40)
    # a soft floor, and the stick man walking a little across it
    ground = 1500
    d.ellipse([W / 2 - 230, ground - 18, W / 2 + 230, ground + 18], fill=(236, 236, 240))
    cx = W / 2 + math.sin(t * 0.8) * 30 + (min(t, 3) * 25 if scene["pose"] == "run" else 0)
    head = draw_man(d, cx, ground, scene["pose"], t)
    draw_prop(d, scene["prop"], head[0] + 260, head[1] - 60, t, _font(130))
    # the caption: big, centred, words lighting up as they are said
    words = scene["caption"].split()
    lit = max(1, math.ceil(len(words) * min(1.0, progress * 1.15)))
    lines, cur = [], []
    for w in words:
        if len(" ".join(cur + [w])) > 16 and cur:
            lines.append(cur)
            cur = []
        cur.append(w)
    lines.append(cur)
    y, n = 330, 0
    rtl = LANG == "ar"
    for line in lines:
        text_w = d.textlength(" ".join(line), font=big)
        x = W / 2 - text_w / 2
        for w in (reversed(line) if rtl else line):
            n += 1
            colour = (20, 20, 24) if n <= lit else (205, 205, 212)
            d.text((x, y), w, font=big, fill=colour)
            x += d.textlength(w + " ", font=big)
        y += 112
    d.text((W / 2, 1780), title[:40], font=small, fill=(150, 150, 160), anchor="mm")
    return img


# -- voice and video -----------------------------------------------------------------

def _ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def speak(text, path, voice=VOICE):
    import asyncio
    import edge_tts
    asyncio.run(edge_tts.Communicate(text, voice).save(path))


def duration(path):
    out = subprocess.run([_ffmpeg(), "-i", path], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 3.0


def render(script, out_path, speak_fn=speak, work=None):
    """The whole video. Returns out_path."""
    work = work or tempfile.mkdtemp(prefix="short-")
    parts = []
    for i, scene in enumerate(script["scenes"]):
        audio = os.path.join(work, f"s{i}.mp3")
        speak_fn(scene["say"], audio)
        secs = duration(audio) + 0.25
        clip = os.path.join(work, f"s{i}.mp4")
        cmd = [_ffmpeg(), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS),
               "-i", "-", "-i", audio, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
               "-c:a", "aac", "-shortest", clip]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        count = int(secs * FPS)
        for f in range(count):
            t = f / FPS
            frame(scene, t, t / max(0.1, secs - 0.25), script.get("title", "")).save(proc.stdin, "PNG", compress_level=1)
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError("FFmpeg could not make a scene.")
        parts.append(clip)
    listing = os.path.join(work, "list.txt")
    with open(listing, "w", encoding="utf-8") as f:
        f.writelines(f"file '{p}'\n" for p in parts)
    subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listing,
                    "-c", "copy", out_path], check=True)
    return out_path


def folder():
    import files
    path = os.path.join(files.root(), "Shorts")
    os.makedirs(path, exist_ok=True)
    return path


def make(kind=None, topic="", think=None, speak_fn=speak, now=None):
    """Write, voice, draw and join one Short. Returns {path, title, notes}."""
    now = now or dt.datetime.now()
    kind = kind or kind_for(now.date())
    script = ask_script(kind, topic, think)
    slug = re.sub(r"[^\w\- ]+", "", script.get("title", "short"))[:50].strip() or "short"
    base = os.path.join(folder(), f"{now:%Y-%m-%d %H%M} {slug}")
    render(script, base + ".mp4", speak_fn)
    notes = (f"{script.get('title', '')}\n\n{script.get('description', '')}\n\n"
             + " ".join(script.get("hashtags", []) + ["#shorts"]))
    with open(base + ".txt", "w", encoding="utf-8") as f:
        f.write(notes)
    log.info("short made: %s", base)
    return {"path": base + ".mp4", "title": script.get("title", ""), "notes": base + ".txt", "kind": kind}


def make_in_background(kind=None, topic="", done=None):
    """Make one on a thread; `done(result_or_error)` hears how it went."""
    def run():
        try:
            result = make(kind, topic)
        except Exception as e:  # noqa: BLE001
            log.warning("short failed: %s", e)
            result = {"error": str(e) or type(e).__name__}
        if done:
            done(result)
    threading.Thread(target=run, daemon=True, name="short").start()
