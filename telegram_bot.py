"""Apollo on your phone, through a Telegram bot (free; no ports opened, no server).

Apollo asks Telegram for new messages every few seconds; only YOUR chat is
obeyed. You can message it:

    short about octopuses     (or: شورت عن الاخطبوط)   LYLA makes one Short
    today                     (or: ترند)               LYLA makes today's batch from the trends
    post 2                    (or: نزل 2)              post that one to YouTube
    skip                      (or: لا تنزل)            post nothing today
    status

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
        "post <number> - post that one\nskip - post nothing today\nstyle <instructions> - how every Short should be told\nstatus")
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
    for i, m in enumerate(made, 1):
        send_video(m["path"], f"{i}. {m['title']}")
    send(question)


def handle(text, make_short=None, make_batch=None, choose=None, status=None, set_style=None, find_niches=None, pick_niche=None):
    """What to do with one message; returns the reply. The doers are injectable."""
    t = (text or "").strip().translate(DIGITS)
    low = t.lower()
    if low in ("/start", "/help", "help", "مساعدة"):
        return HELP
    m = re.match(r"^/?(?:post|نزل|انشر)\s*(?:رقم\s*|number\s*|#)?(\d)\b", low)
    if m:
        r = choose(int(m.group(1)))
        return r.get("result") or r.get("error") or "Done."
    if re.match(r"^/?(skip|لا تنزل|لا تنشر)", low):
        return (choose(0).get("result") or "Nothing posted today.")
    if re.match(r"^/?(today|trends?|ترند|اليوم)\b", low):
        make_batch()
        return "LYLA is reading the trends and making today's Shorts - a few minutes. They'll arrive here."
    m = re.match(r"^/?(?:niche|نيش)\s*(\d*)\b", low)
    if m:
        if m.group(1):
            r = pick_niche(int(m.group(1)))
            return r.get("result") or r.get("error")
        find_niches()
        return "LYLA is researching the best niches - a minute or two. I'll send the list here."
    m = re.match(r"^/?(?:short|شورت|مقطع|سوي)\s*(?:about|عن)?\s*(.*)$", t, re.I | re.S)
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
        return status()
    return HELP


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
        choose=autopost.choose, status=status, set_style=lambda text, add=True: shorts.set_style(text, add) if text or not add else shorts.style_notes())


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
                            send(handle(body, **_wire()))
                        except Exception as e:  # noqa: BLE001
                            send(f"That failed: {e}")
            except Exception:  # noqa: BLE001
                log.info("telegram poll failed", exc_info=True)
                threading.Event().wait(10)
    threading.Thread(target=loop, daemon=True, name="telegram").start()
