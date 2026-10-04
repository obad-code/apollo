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
CAMS = ("close", "push", "fisheye", "pull", "shake", "pan", "wide")
PROPS = ("none", "question", "exclaim", "bulb", "money", "clock", "skull", "heart", "earth", "fire")

SYSTEM = (
    "You write YouTube Shorts scripts for a stick-man animation channel. 35-50 seconds "
    "spoken. The first line is a hook that stops the scroll. Short punchy sentences. No "
    "music, nothing indecent, nothing against Islam. Answer ONLY with JSON: "
    '{"title": "...", "description": "...", "hashtags": ["#..."], "scenes": [{"say": '
    '"what the narrator says", "caption": "3-6 key words", "pose": one of '
    + json.dumps(POSES) + ', "prop": one of ' + json.dumps(PROPS) + ', "cam": one of ' + json.dumps(CAMS)
    + "}]} with 6 to 9 scenes. The camera must keep moving: open on a close-up or fisheye "
    "for the hook, never the same cam twice in a row, shake for shocks.")


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
    for i, s in enumerate(scenes):
        if s.get("cam") not in CAMS or (i and s["cam"] == scenes[i - 1]["cam"]):
            s["cam"] = CAMS[i % len(CAMS)]
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


SS = 1.25         # the world is drawn this much bigger, so a close-up stays sharp
INK = (24, 24, 30)
SKIN = (255, 255, 255)
# background gradients (top, bottom) and ray colour, by mood
LOOKS = {
    "shock": ((255, 120, 70), (200, 40, 60), (255, 170, 110)),
    "cheer": ((255, 214, 80), (255, 140, 60), (255, 236, 140)),
    "sad": ((120, 140, 190), (50, 60, 100), (140, 160, 205)),
    "think": ((150, 110, 230), (60, 40, 140), (175, 140, 245)),
    "run": ((90, 210, 200), (30, 120, 150), (130, 230, 220)),
    "point": ((100, 190, 255), (40, 90, 200), (140, 210, 255)),
    "wave": ((110, 220, 150), (30, 140, 110), (150, 235, 180)),
    "shrug": ((250, 170, 190), (170, 70, 130), (255, 190, 205)),
    "stand": ((120, 200, 255), (60, 100, 220), (150, 215, 255)),
}
_cache = {}


class Pen:
    """An ImageDraw that scales everything by k, so the drawing code stays in
    plain 1080x1920 numbers while the picture is drawn bigger."""

    def __init__(self, d, k):
        self.d, self.k = d, k

    def _p(self, pts):
        if pts and isinstance(pts[0], (int, float)):
            pts = list(zip(pts[::2], pts[1::2]))
        return [(x * self.k, y * self.k) for x, y in pts]

    def _w(self, width):
        return max(1, round(width * self.k))

    def line(self, pts, fill=None, width=1):
        pts = self._p(pts)
        w = self._w(width)
        self.d.line(pts, fill=fill, width=w)
        r = w / 2 - 0.5    # round caps: a stick man is made of sausages, not planks
        for x, y in pts:
            self.d.ellipse([x - r, y - r, x + r, y + r], fill=fill)

    def ellipse(self, box, fill=None, outline=None, width=1):
        (x0, y0), (x1, y1) = self._p([(box[0], box[1]), (box[2], box[3])])
        self.d.ellipse([x0, y0, x1, y1], fill=fill, outline=outline, width=self._w(width))

    def arc(self, box, start, end, fill=None, width=1):
        (x0, y0), (x1, y1) = self._p([(box[0], box[1]), (box[2], box[3])])
        self.d.arc([x0, y0, x1, y1], start, end, fill=fill, width=self._w(width))

    def text(self, xy, text, font=None, fill=None, anchor=None):
        (x, y), = self._p([xy])
        if hasattr(font, "font_variant"):
            font = font.font_variant(size=max(1, int(font.size * self.k)))
        self.d.text((x, y), text, font=font, fill=fill, anchor=anchor)


def limbs(pose, t):
    """Angles (degrees from straight down) of left arm, right arm, left leg,
    right leg, and a small hop in px, for `pose` at time `t` seconds."""
    s = math.sin(t * 5.0)
    table = {
        "stand": (18 + 4 * s, -18 - 4 * s, 7, -7, 0),
        "wave": (18, -140 + 28 * math.sin(t * 8), 7, -7, 0),
        "point": (18, -95 + 4 * s, 7, -7, 0),
        "think": (18, -155, 7, -7, 0),
        "shock": (125 + 6 * s, -125 - 6 * s, 16, -16, abs(math.sin(t * 7)) * 14),
        "run": (45 * s, -45 * s, 30 * s, -30 * s, abs(s) * 8),
        "cheer": (150 + 8 * s, -150 - 8 * s, 12, -12, abs(math.sin(t * 6)) * 14),
        "sad": (6, -6, 4, -4, 0),
        "shrug": (65 + 4 * s, -65 - 4 * s, 7, -7, 0),
    }
    return table.get(pose, table["stand"])


def _line(d, a, length, angle, width=14):
    rad = math.radians(angle)
    b = (a[0] + length * math.sin(rad), a[1] + length * math.cos(rad))
    d.line([a, b], fill=INK, width=width)
    return b


def draw_man(d, cx, ground, pose, t, talking=False):
    la, ra, ll, rl, jump = limbs(pose, t)
    breathe = math.sin(t * 2.2) * 4
    hip = (cx, ground - 300 - jump)
    neck = (cx, hip[1] - 260 + breathe)
    sad = pose == "sad"
    head_c = (neck[0] + math.sin(t * 1.6) * 6, neck[1] - 80 + (12 if sad else 0))
    d.line([hip, neck], fill=INK, width=18)
    shoulder = (neck[0], neck[1] + 30)
    for angle in (la, ra):
        elbow = _line(d, shoulder, 120, angle, 16)
        _line(d, elbow, 110, angle * 0.8, 16)
    for angle in (ll, rl):
        knee = _line(d, hip, 150, angle, 18)
        _line(d, knee, 140, angle * 0.6, 18)
    r = 82
    d.ellipse([head_c[0] - r, head_c[1] - r, head_c[0] + r, head_c[1] + r], outline=INK, width=14, fill=SKIN)
    # eyes: big, with pupils that look about; a blink now and then; huge when shocked
    shut = (t % 3.3) < 0.12
    ew = 20 if pose == "shock" else 15
    look = math.sin(t * 0.9) * 5
    for side in (-1, 1):
        ex, ey = head_c[0] + side * 31, head_c[1] - 8
        if shut:
            d.line([ex - ew, ey, ex + ew, ey], fill=INK, width=6)
        else:
            d.ellipse([ex - ew, ey - ew, ex + ew, ey + ew], fill="white", outline=INK, width=5)
            pr = 8 if pose == "shock" else 10
            d.ellipse([ex + look - pr, ey - pr, ex + look + pr, ey + pr], fill=INK)
        # brows say the mood
        tilt = {"shock": -16, "sad": 14, "think": 8, "cheer": -6}.get(pose, 0) * side
        d.line([ex - 18, ey - 30 + tilt * 0.6, ex + 18, ey - 30 - tilt * 0.6], fill=INK, width=7)
    mx, my = head_c[0], head_c[1] + 38
    open_ = abs(math.sin(t * 13)) if talking else 0
    if pose == "shock" or (talking and open_ > 0.45):
        h = 14 + 22 * (open_ if talking else 1)
        d.ellipse([mx - 18, my - 6, mx + 18, my - 6 + h], fill=INK)
    elif pose in ("cheer", "wave"):
        d.arc([mx - 32, my - 28, mx + 32, my + 16], 20, 160, fill=INK, width=7)
    elif sad:
        d.arc([mx - 28, my + 2, mx + 28, my + 36], 200, 340, fill=INK, width=7)
    else:
        d.line([mx - 20, my + 4, mx + 20, my + 4], fill=INK, width=7)
    return head_c


def draw_prop(d, prop, x, y, t, font):
    bob = math.sin(t * 3) * 12
    y += bob
    if prop == "none":
        return
    glyph = {"question": "?", "exclaim": "!", "money": "$", "skull": "☠", "heart": "♥",
             "earth": "◍", "clock": "◷", "fire": "▲", "bulb": "✦"}[prop]
    colour = {"money": (30, 160, 80), "heart": (220, 50, 70), "fire": (240, 110, 30),
              "bulb": (245, 180, 0), "exclaim": (230, 60, 60)}.get(prop, INK)
    d.ellipse([x - 95, y - 95, x + 95, y + 95], fill=(250, 250, 252), outline=colour, width=9)
    d.text((x, y), glyph, font=font, fill=colour, anchor="mm")


def _background(pose, size):
    key = (pose, size)
    if key not in _cache:
        from PIL import Image, ImageOps
        top, bottom, _ = LOOKS.get(pose, LOOKS["stand"])
        _cache[key] = ImageOps.colorize(Image.linear_gradient("L").resize(size), top, bottom)
    return _cache[key].copy()


def _ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def camera(cam, t, p, head, body):
    """Where the camera looks: (zoom, focus x, focus y, bulge), in 1080x1920 numbers."""
    punch = 1 + 0.30 * _ease(1 - t / 0.28) if t < 0.28 else 1      # every cut starts with a punch-in
    bulge = 0.0
    if cam == "close":
        z, f = 1.9 + 0.35 * _ease(p), (head[0], head[1] + 30)
    elif cam == "push":
        z, f = 1.0 + 0.55 * _ease(p), (body[0], body[1] + (head[1] - body[1]) * _ease(p))
    elif cam == "pull":
        z, f = 2.0 - 0.95 * _ease(p), (head[0], head[1] + 120 * _ease(p))
    elif cam == "fisheye":
        z, f, bulge = 1.55 + 0.2 * math.sin(t * 2), (head[0], head[1] + 40), 0.55 + 0.15 * math.sin(t * 3)
    elif cam == "shake":
        z, f = 1.3, (body[0] + math.sin(t * 47) * 16, body[1] + math.cos(t * 39) * 16)
    elif cam == "pan":
        z, f = 1.45, (W * (0.3 + 0.4 * _ease(p)), body[1] - 60)
    else:
        z, f = 1.0, (W / 2, H / 2)
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
    world = _background(pose, (int(W * SS), int(H * SS)))
    raw = ImageDraw.Draw(world)
    # light rays behind him when the mood is loud
    if pose in ("shock", "cheer") or scene["prop"] in ("fire", "money"):
        ray = LOOKS.get(pose, LOOKS["stand"])[2]
        ox, oy = W / 2 * SS, 760 * SS
        for i in range(14):
            a0 = t * 0.35 + i * (math.pi * 2 / 14)
            a1 = a0 + math.pi / 14
            raw.polygon([(ox, oy)] + [(ox + math.cos(a) * 2600 * SS, oy + math.sin(a) * 2600 * SS) for a in (a0, a1)], fill=ray)
    d = Pen(raw, SS)
    ground = 1500
    shade = tuple(int(c * 0.55) for c in LOOKS.get(pose, LOOKS["stand"])[1])
    d.ellipse([W / 2 - 240, ground - 20, W / 2 + 240, ground + 20], fill=shade)
    cx = W / 2 + math.sin(t * 0.7) * 14
    head = draw_man(d, cx, ground, pose, t, talking=progress < 1)
    draw_prop(d, scene["prop"], head[0] + 215, head[1] - 150, t, _font(130))
    # the camera: crop the big world to a window and scale it to the screen
    z, fx, fy, bulge = camera(scene.get("cam", "wide"), t, progress, head, (cx, 1000))
    cw, ch = W / z, H / z
    left = min(max(fx - cw / 2, 0), W - cw)
    top = min(max(fy - ch / 2, 0), H - ch)
    img = world.resize((W, H), Image.BILINEAR, box=(left * SS, top * SS, (left + cw) * SS, (top + ch) * SS))
    if bulge:
        try:
            img = _bulge(img, bulge)
        except ImportError:
            pass
    # the caption sits on the screen, never zoomed: big, outlined, spoken words in yellow
    d = ImageDraw.Draw(img)
    big, small = _font(100), _font(38)
    words = scene["caption"].split()
    lit = max(1, math.ceil(len(words) * min(1.0, progress * 1.15)))
    lines, cur = [], []
    for w in words:
        if len(" ".join(cur + [w])) > 15 and cur:
            lines.append(cur)
            cur = []
        cur.append(w)
    lines.append(cur)
    y, n = 1560, 0
    rtl = LANG == "ar"
    for line in lines:
        text_w = d.textlength(" ".join(line), font=big)
        x = W / 2 - text_w / 2
        for w in (reversed(line) if rtl else line):
            n += 1
            colour = (255, 221, 40) if n <= lit else (255, 255, 255)
            d.text((x, y), w, font=big, fill=colour, stroke_width=9, stroke_fill=(15, 15, 20))
            x += d.textlength(w + " ", font=big)
        y += 120
    d.text((W / 2, 1850), title[:40], font=small, fill=(255, 255, 255), anchor="mm", stroke_width=3, stroke_fill=(15, 15, 20))
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


def render(script, out_path, speak_fn=speak, work=None, step=lambda t: None):
    """The whole video. Returns out_path."""
    work = work or tempfile.mkdtemp(prefix="short-")
    parts = []
    for i, scene in enumerate(script["scenes"]):
        step(f"Scene {i + 1} of {len(script['scenes'])}: voice and drawing")
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


def make(kind=None, topic="", think=None, speak_fn=speak, now=None, step=lambda t: None):
    """Write, voice, draw and join one Short. Returns {path, title, notes}."""
    now = now or dt.datetime.now()
    kind = kind or kind_for(now.date())
    for need in ("PIL", "edge_tts", "imageio_ffmpeg"):
        try:
            __import__(need)
        except ImportError as e:
            raise RuntimeError("Missing a library: run  python -m pip install pillow edge-tts imageio-ffmpeg") from e
    step(f"Writing the script ({kind})")
    script = ask_script(kind, topic, think)
    slug = re.sub(r"[^\w\- ]+", "", script.get("title", "short"))[:50].strip() or "short"
    base = os.path.join(folder(), f"{now:%Y-%m-%d %H%M} {slug}")
    render(script, base + ".mp4", speak_fn, step=step)
    step("Joining the scenes")
    notes = (f"{script.get('title', '')}\n\n{script.get('description', '')}\n\n"
             + " ".join(script.get("hashtags", []) + ["#shorts"]))
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
