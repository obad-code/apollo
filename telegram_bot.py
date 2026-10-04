"""Apollo on your phone, through a Telegram bot (free; no ports opened, no server).

Apollo asks Telegram for new messages every few seconds; only YOUR chat is
obeyed. You can message it:

    short about octopuses     (or: شورت عن الاخطبوط)   LYLA makes one Short
    today                     (or: ترند)               LYLA makes today's batch from the trends
    post 2                    (or: نزل 2)              post that one to YouTube
    skip                      (or: لا تنزل)            post nothing today
    status
    anything else, typed or as a VOICE NOTE: Apollo answers it (text and a
    voice note back), or hands it to LYLA, THEIA, MONEYPENNY or Q and sends
    what they find here.

Setup (once):
    1. In Telegram, message @BotFather -> /newbot -> keep the token it gives you.
    2. setx APOLLO_TELEGRAM_TOKEN "<the token>"      (never paste it in a chat)
    3. Restart Apollo, open your new bot and send /id - it replies with your
       chat number. Then: setx APOLLO_TELEGRAM_CHAT "<that number>" and restart.
When LYLA's Shorts are ready they arrive in the chat as videos, with the question.
"""

import json
import logging
import os
import re
import threading
import urllib.parse
import urllib.request
import uuid

log = logging.getLogger("apollo.telegram")

HELP = ("short about <topic> - one Short\ntoday - today's Shorts from the trends\n"
        "post - post the Short that is ready (post 2 for a number, post all)\ndraft - save it on YouTube as a private draft\nskip - post nothing today\nstyle <instructions> - how every Short should be told\nstatus")
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def token():
    return os.environ.get("APOLLO_TELEGRAM_TOKEN", "").strip()


def chat():
    return os.environ.get("APOLLO_TELEGRAM_CHAT", "").strip()


def ready():
    return bool(token() and chat())


def _call(method, data=None, files=None, timeout=40):
    url = f"https://api.telegram.org/bot{token()}/{method}"
    if files:
        boundary = uuid.uuid4().hex
        body = b""
        for k, v in (data or {}).items():
            body += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
        for k, path in files.items():
            with open(path, "rb") as f:
                body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{os.path.basename(path)}"\r\n'
                         "Content-Type: application/octet-stream\r\n\r\n").encode() + f.read() + b"\r\n"
        body += f"--{boundary}--\r\n".encode()
        req = urllib.request.Request(url, body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})
    else:
        req = urllib.request.Request(url, urllib.parse.urlencode(data or {}).encode())
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - fixed https host
        return json.loads(r.read())


def send(text, to=None):
    if not ready() and not to:
        return False
    try:
        _call("sendMessage", {"chat_id": to or chat(), "text": text[:4000]})
        return True
    except Exception:  # noqa: BLE001
        log.info("telegram send failed", exc_info=True)
        return False


def send_video(path, caption="", to=None):
    if not ready() and not to:
        return False
    try:
        _call("sendVideo", {"chat_id": to or chat(), "caption": caption[:900]}, files={"video": path}, timeout=180)
        return True
    except Exception:  # noqa: BLE001
        log.info("telegram video failed", exc_info=True)
        return False


def send_report(text):
    """A long report, in the chat, in pieces Telegram accepts."""
    for i in range(0, len(text), 3800):
        send(text[i:i + 3800])


def offer_shorts(made, question):
    """Today's Shorts, as videos in the chat, then the question."""
    import shorts
    for i, m in enumerate(made, 1):
        send_video(m["path"], f"{i}. {m['title']}\n(build {shorts.VERSION})")
    send(question)


def handle(text, make_short=None, make_batch=None, choose=None, status=None, set_style=None, find_niches=None, pick_niche=None, choose_all=None):
    """What to do with one message; returns the reply. The doers are injectable."""
    t = (text or "").strip().translate(DIGITS)
    low = t.lower()
    if low in ("/start", "/help", "help", "مساعدة"):
        return HELP
    if re.match(r"^/?(post all|نزل الكل|نزل الاثنين|انشر الكل|انشر الاثنين)", low):
        r = choose_all()
        return r.get("result") or r.get("error") or "Done."
    if re.match(r"^/?(post|نزله|نزل|انشره|انشر)\s*$", low):
        r = choose(1)
        return r.get("result") or r.get("error") or "Done."
    if re.match(r"^/?(draft|private|درافت|مسودة|خله درافت|خله مسودة)", low):
        r = choose(1, privacy="private")
        return r.get("result") or r.get("error") or "Done."
    m = re.match(r"^/?(?:post|نزل|انشر)\s*(?:رقم\s*|number\s*|#)?(\d)\b", low)
    if m:
        r = choose(int(m.group(1)))
        return r.get("result") or r.get("error") or "Done."
    if re.match(r"^/?(skip|keep|لا|لا تنزل|لا تنشر|لا تنزله)(\s+(شي|شيء|اليوم))?\s*$", low):
        return (choose(0).get("result") or "Nothing posted today.")
    if re.match(r"^/?(today|trends?|ترند|مقاطع اليوم)\s*$", low):
        make_batch()
        return "LYLA is reading the trends and making today's Shorts - a few minutes. They'll arrive here."
    m = re.match(r"^/?(?:niche|نيش)\s*(\d*)\b", low)
    if m:
        if m.group(1):
            r = pick_niche(int(m.group(1)))
            return r.get("result") or r.get("error")
        find_niches()
        return "LYLA is researching the best niches - a minute or two. I'll send the list here."
    m = re.match(r"^/?(?:short|شورت|سوي مقطع|سوي شورت|مقطع)(?:\s+|$)(?:about\s+|عن\s+)?(.*)$", t, re.I | re.S)
    if m:
        make_short(m.group(1).strip())
        return "LYLA is on it - a few minutes. I'll send it here."
    m = re.match(r"^/?(?:style|ستايل|اسلوب)\s*(.*)$", t, re.I | re.S)
    if m:
        if not m.group(1).strip():
            return "Style notes: " + (set_style(None, True) or "none yet") + "\n(style clear = wipe them)"
        if m.group(1).strip().lower() in ("clear", "مسح"):
            set_style("", False)
            return "Style notes cleared."
        return "Saved. From the next Short: " + set_style(m.group(1))
    if low in ("/status", "status", "الحالة"):
        import shorts
        return f"{status()}\nbuild: {shorts.VERSION}"
    return None                      # not a command: Apollo answers it (converse)


# -- talking to Apollo, by text or by voice ------------------------------------------------

TALK = (
    "You are Apollo, the user's own assistant, answering them on Telegram. Reply in the language "
    "and dialect they used (Gulf Arabic if they wrote Arabic). Be short and direct - this may be "
    "played back as a voice note. Use search for anything current. If the request is a job for "
    "one of your crew - LYLA (research, YouTube Shorts, downloads), THEIA (deep analysis of an "
    "idea or plan), MONEYPENNY (a stock or the watchlist), Q (something to add to or fix in "
    "Apollo) - or they name one, answer ONLY with JSON: {\"agent\": NAME, \"task\": the job in "
    "their words, \"stock\": the company or ticker if any}. Otherwise answer normally, no JSON.")


def converse(text, think=None, take=None):
    """Apollo's answer to anything that is not a command: a reply, or a job handed to the crew."""
    if think is None:
        import lyla
        think = lambda prompt: lyla.think(prompt, TALK)[0]  # noqa: E731 - Gemini, then Claude if Gemini is out
    answer = (think(text) or "").strip()
    found = re.search(r"\{.*\}", answer, re.S)
    if found:
        try:
            job = json.loads(found.group(0))
        except ValueError:
            job = None
        name = str((job or {}).get("agent", "")).upper().replace(" ", "")
        if job and name in ("LYLA", "THEIA", "MONEYPENNY", "Q"):
            if take is None:
                import crew
                take = lambda n, task, stock: crew.desk(n).take(task, stock, telegram=True)  # noqa: E731
            take(name, job.get("task") or text, job.get("stock") or "")
            return f"{name} is on it - I'll send what comes back here."
    return answer or "I didn't catch that - say it again?"


def transcribe(audio_bytes, mime="audio/ogg"):
    """What was said in a voice note, word for word (Gemini)."""
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    last = None
    for model in ("gemini-flash-latest", "gemini-2.5-flash"):
        try:
            out = client.models.generate_content(model=model, contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type=mime),
                "Transcribe this voice note exactly, in the language spoken. Answer with the words only."])
            if out.text and out.text.strip():
                return out.text.strip()
        except Exception as e:  # noqa: BLE001 - the next model may answer
            last = e
    raise RuntimeError(f"Could not hear the voice note: {last}")


def _download(file_id):
    path = _call("getFile", {"file_id": file_id})["result"]["file_path"]
    with urllib.request.urlopen(f"https://api.telegram.org/file/bot{token()}/{path}", timeout=60) as r:  # noqa: S310
        return r.read()


def send_voice(text, to=None):
    """Apollo's reply as a voice note (edge-tts, free) - as a plain audio file if it cannot be one."""
    import asyncio
    import subprocess
    import tempfile
    import edge_tts
    arabic = bool(re.search(r"[؀-ۿ]", text))
    voice = os.environ.get("APOLLO_TELEGRAM_VOICE") or ("ar-SA-HamedNeural" if arabic else "en-US-GuyNeural")
    folder = tempfile.mkdtemp(prefix="apollo-tg-")
    mp3, ogg = os.path.join(folder, "reply.mp3"), os.path.join(folder, "reply.ogg")
    asyncio.run(edge_tts.Communicate(re.sub(r"[*_#`>]", "", text)[:1500], voice).save(mp3))
    try:
        import imageio_ffmpeg
        flags = {"creationflags": 0x08000000} if os.name == "nt" else {}
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", mp3, "-c:a", "libopus", "-b:a", "32k", ogg],
                       capture_output=True, check=True, **flags)
        _call("sendVoice", {"chat_id": to or chat()}, files={"voice": ogg}, timeout=120)
    except Exception:  # noqa: BLE001 - no opus encoder: send it as an audio file
        _call("sendAudio", {"chat_id": to or chat()}, files={"audio": mp3}, timeout=120)


def reply_to(msg, wire=None, talk=converse, hear=None, voice=None):
    """One message from you: a command, something to answer, or a voice note."""
    wire = _wire() if wire is None else wire
    note = msg.get("voice") or msg.get("audio")
    if note:
        said = (hear or (lambda n: transcribe(_download(n["file_id"]), n.get("mime_type") or "audio/ogg")))(note)
        answer = handle(said, **wire) or talk(said)
        send(f"🎙 {said}\n\n{answer}")
        try:
            (voice or send_voice)(answer)
        except Exception:  # noqa: BLE001 - the text already went
            log.info("voice reply failed", exc_info=True)
        return answer
    body = msg.get("text") or ""
    answer = handle(body, **wire) or talk(body)
    send(answer)
    return answer


def _wire():
    import autopost
    import crew
    import shorts

    def status():
        data = autopost.load()
        return f"{data.get('status', 'nothing yet')}" + (f": {data.get('posted')}" if data.get("posted") else "")

    return dict(
        make_short=lambda topic: shorts.make_in_background(None, topic),
        make_batch=lambda: crew.desk("LYLA").take("Make today's Shorts from the trends", short=True, batch=autopost.COUNT),
        find_niches=lambda: crew.desk("LYLA").take("Find the best niches for the channel", niche=True),
        pick_niche=__import__("niche").choose,
        choose=autopost.choose, choose_all=autopost.choose_all, status=status, set_style=lambda text, add=True: shorts.set_style(text, add) if text or not add else shorts.style_notes())


def start(stopping):
    """Listen on a thread of its own until `stopping()`. Does nothing without a token."""
    if not token():
        return
    def loop():
        offset = 0
        while not stopping():
            try:
                for u in _call("getUpdates", {"timeout": 25, "offset": offset}, timeout=40).get("result", []):
                    offset = u["update_id"] + 1
                    msg = u.get("message") or {}
                    who = str((msg.get("chat") or {}).get("id", ""))
                    body = msg.get("text") or ""
                    if body.strip().lower() == "/id":
                        send(f"Your chat number: {who}", to=who)
                    elif chat() and who == chat():
                        try:
                            reply_to(msg)
                        except Exception as e:  # noqa: BLE001
                            send(f"That failed: {e}")
            except Exception:  # noqa: BLE001
                log.info("telegram poll failed", exc_info=True)
                threading.Event().wait(10)
    threading.Thread(target=loop, daemon=True, name="telegram").start()
