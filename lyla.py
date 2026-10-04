"""LYLA's desk: the research Apollo hands her, done while you carry on.

You ask Apollo for something that takes looking into - "analyse NVDA for
me", "ابي تحليل لسهم انفيديا" - and instead of going quiet for a minute he
hands it to LYLA (the `ask_lyla` tool) and is free again at once: you can
give him the next thing straight away. She works on a thread of her own, one
job at a time, her card on the display showing each step. When she is done
Apollo tells you what she found, in his own voice - waiting for any turn in
progress to finish first, the way a reminder does - and her write-up is kept
(REPORTS) for the display and for "what did LYLA find?".

She works for Apollo; she does not drive him. She has no tools that touch
the PC or the display and never asks for the screen: she reads - the price,
the trading desk, what traders are saying, insiders' trades, the news, the
web - and writes, and that is all. What is done with what she finds is
Apollo's call, and yours.

Her brain, the first that answers:

  Hermes   Nous Research's open-source agent (hermes-agent), when you run
           its API server (`hermes gateway`) and tell Apollo where it is:
           HERMES_URL (http://127.0.0.1:8642) and HERMES_KEY (the
           API_SERVER_KEY in ~/.hermes/.env). Hermes itself is free; point
           it at Gemini and it costs what Gemini costs.
  Gemini   Otherwise Gemini itself, with Google Search, on the
           GEMINI_API_KEY Apollo already has. LYLA_MODEL puts a model of
           your choice at the front.

Nothing here raises into Apollo: a source that fails is left out of what
she read, and a job that fails is reported as failed.
"""

import datetime
import itertools
import json
import logging
import os
import queue
import re
import threading
import time
import urllib.request

log = logging.getLogger("apollo.lyla")

NAME = "LYLA"
MODELS = tuple(filter(None, (os.environ.get("LYLA_MODEL"),
                             "gemini-flash-latest", "gemini-2.5-flash")))
# Each model has its own free daily allowance, so when the main ones are used up the lighter
# ones still answer. A model that says its quota is spent is skipped until it said to retry.
LITE = ("gemini-flash-lite-latest", "gemini-3.5-flash-lite")   # 2.5 Flash Lite is closed to new users
_spent = {}


def _quota_wait(error):
    """Seconds until a model's quota comes back, if `error` says it is spent; else 0."""
    text = str(error)
    if "RESOURCE_EXHAUSTED" not in text and "429" not in text:
        return 0
    found = re.search(r"retry in (?:(\d+)h)?(?:(\d+)m)?([\d.]+)s", text)
    if not found:
        return 60
    h, m, sec = found.groups()
    return int(h or 0) * 3600 + int(m or 0) * 60 + float(sec)
HERMES_TIMEOUT = 600       # an agent that searches can take its time
REPORTS = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                       "Apollo", "lyla_reports.json")
KEEP = 20                  # reports kept, newest first

SYSTEM = (
    "You are LYLA, the research agent of Apollo, a personal desktop assistant. "
    "Apollo hands you research jobs; you do them and write up what you found for "
    "him to pass on. You cannot act on the user's computer and never try to: you "
    "read and you write. Use what you were given and search the web for the rest. "
    "Be concrete - numbers, dates, names - and say where each fact came from. "
    "For a stock, cover: what the company does; how the price has moved; what "
    "insiders, members of Congress and traders are doing with it; the news and "
    "the catalysts coming up; the risks; and a lean - bullish, neutral or bearish "
    "- with the reasons for it. A stock read is a read, not advice: say so once, "
    "at the end.\n\n"
    "Answer in exactly this shape. The first line is `SUMMARY:` and two short "
    "sentences Apollo can say out loud, in the language the job was given in. "
    "Then a blank line, then the report: short sections under plain headings, "
    "under 350 words.")


# -- what she reads ------------------------------------------------------------------

def _attempt(read, sources, name):
    try:
        value = read()
    except Exception as e:  # noqa: BLE001 - a source that fails is left out
        log.info("LYLA: %s failed: %s", name, e)
        sources[name] = "down"
        return None
    sources[name] = "ok" if value else "empty"
    return value


def stock_facts(symbol, step=lambda text: None):
    """Everything Apollo can read about one ticker, for her to start from.

    Each source on its own - one that is down is marked so and skipped.
    `step` is told what she is reading, for her card."""
    import feeds
    import insiders
    import market
    import trading

    sources = {}
    step(f"Reading {symbol}: price and valuation")
    price = _attempt(lambda: market.history(symbol, "1mo"), sources, "price")
    facts = {"symbol": symbol, "sources": sources}
    if price:
        points = price.pop("points", [])
        facts["price"] = {k: price[k] for k in ("name", "currency", "price", "change_pct") if k in price}
        facts["price"]["month_change_pct"] = facts["price"].pop("change_pct", None)
        if points:
            closes = [p for _, p in points]
            facts["price"]["month_high"], facts["price"]["month_low"] = max(closes), min(closes)
    facts["valuation"] = _attempt(lambda: market.fundamentals(symbol), sources, "valuation")

    try:
        import analysis
        counted = analysis.analyse(symbol)
        if counted.get("ok"):
            facts["counted_verdict"] = {k: counted[k] for k in ("verdict", "tone", "green", "red", "numbers", "about")}
    except Exception:  # noqa: BLE001
        pass

    step(f"Reading {symbol}: the trading desk")
    board = _attempt(trading.board, sources, "desk")
    if board:
        facts["on_the_desk"] = trading.on_the_desk(symbol, board)
    step(f"Reading {symbol}: what traders are saying")
    facts["chatter"] = _attempt(lambda: trading.chatter(symbol), sources, "chatter")

    key = insiders.api_key()
    if key:
        step(f"Reading {symbol}: insiders' trades")
        today = insiders._today()
        rows = _attempt(lambda: insiders.fetch(symbol, key, today - datetime.timedelta(days=insiders.DAYS)),
                        sources, "insiders")
        if rows is not None:
            facts["insiders"] = insiders.summary(symbol, rows, today=today)

    step(f"Reading {symbol}: the news")
    name = (facts.get("price") or {}).get("name") or symbol
    facts["news"] = _attempt(lambda: [{"title": s["title"], "source": s.get("source", ""),
                                       "age": s.get("age", "")}
                                      for s in feeds.search(f'"{name}" OR {symbol} stock when:7d', 8)],
                             sources, "news")
    return facts


def general_facts(task, step=lambda text: None):
    """For a job that is not one stock: the latest headlines on it."""
    import feeds

    sources = {}
    step("Reading the news on it")
    news = _attempt(lambda: [{"title": s["title"], "source": s.get("source", "")}
                             for s in feeds.search(task, 8)], sources, "news")
    return {"news": news, "sources": sources}


def prompt_for(job, facts):
    return (f"The job, as the user gave it to Apollo: {job['task']}\n"
            + (f"The stock: {job['symbol']}\n" if job.get("symbol") else "")
            + f"Today is {datetime.date.today().isoformat()}.\n\n"
            "What Apollo's own sources have on it (JSON; a source marked down "
            "was unreachable):\n"
            + json.dumps(facts, default=str, ensure_ascii=False)[:24000])


def split(text):
    """Her answer -> (the two sentences to say, the report). A reply without
    the SUMMARY line is still used: its first two sentences are said."""
    text = (text or "").strip()
    found = re.match(r"\s*\**SUMMARY:?\**\s*(.+?)(?:\n\s*\n|\n|$)(.*)", text, re.S | re.I)
    if found:
        return found.group(1).strip(), found.group(2).strip() or found.group(1).strip()
    sentences = re.split(r"(?<=[.!?؟])\s+", text)
    return " ".join(sentences[:2]).strip(), text


# -- her brain -----------------------------------------------------------------------

def hermes_settings():
    """Where Hermes' API server is, and its key - or None to use Gemini."""
    url = (os.environ.get("HERMES_URL") or "").strip().rstrip("/")
    key = (os.environ.get("HERMES_KEY") or "").strip()
    if not url or not key:
        return None
    return {"url": url, "key": key, "model": os.environ.get("HERMES_MODEL") or "hermes-agent"}


def _post(url, payload, key, timeout):
    """The one call to Hermes. Tests replace this."""
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def ask_hermes(prompt, settings, system=None):
    """Hermes, through the OpenAI-style chat endpoint of its API server. It
    runs its own tools - its searches, its skills - before it answers."""
    answer = _post(settings["url"] + "/v1/chat/completions",
                   {"model": settings["model"],
                    "messages": [{"role": "system", "content": system or SYSTEM},
                                 {"role": "user", "content": prompt}]},
                   settings["key"], HERMES_TIMEOUT)
    return answer["choices"][0]["message"]["content"]


def _generate(model, prompt, search, system=None):
    """The one call to Gemini. Tests replace this."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=(os.environ.get("GEMINI_CREW_KEY") or os.environ.get("GEMINI_API_KEY")))
    config = types.GenerateContentConfig(
        system_instruction=system or SYSTEM, temperature=0.4,
        tools=[types.Tool(google_search=types.GoogleSearch())] if search else None)
    return client.models.generate_content(model=model, contents=prompt, config=config).text


def ask_gemini(prompt, system=None, models=None):
    """Gemini with Google Search, on each model in turn; without the search
    as a last try, since the search is the part a free key can run out of."""
    if not (os.environ.get("GEMINI_CREW_KEY") or os.environ.get("GEMINI_API_KEY")):
        raise RuntimeError("LYLA needs GEMINI_API_KEY (or Hermes) to think with.")
    last, quota = None, None
    models = tuple(models or MODELS)
    now = time.time()
    tries = [*((m, True) for m in models), (models[0], False), *((m, True) for m in LITE if m not in models)]
    for model, search in tries:
        if _spent.get(model, 0) > now:
            continue                                   # its free quota is used up; do not even ask
        try:
            text = _generate(model, prompt, search, system) if system else _generate(model, prompt, search)
        except Exception as e:  # noqa: BLE001 - the next model may answer
            log.info("LYLA: %s%s failed: %s", model, " with search" if search else "", str(e)[:200])
            wait = _quota_wait(e)
            if wait:
                _spent[model] = now + wait
                quota = e
            elif "NOT_FOUND" in str(e) and "model" in str(e).lower():
                _spent[model] = now + 7 * 86400          # retired or unknown: stop asking it for a week
            last = e
            continue
        if text and text.strip():
            return text
    if quota is not None:
        back = min((t for t in _spent.values() if t > now), default=now)
        raise RuntimeError("Gemini's free daily limit is used up on every model - it comes back in about "
                           f"{max(1, round((back - now) / 3600))} h. Enabling billing on the Gemini key lifts it.")
    raise RuntimeError(f"Gemini did not answer: {str(last)[:300]}")


def think(prompt, system=None, models=None):
    """Her answer, and which brain gave it: Hermes if it is set up and
    answering, Gemini otherwise. Another agent passes its own `system`."""
    settings = hermes_settings()
    if settings is not None:
        try:
            return (ask_hermes(prompt, settings, system) if system
                    else ask_hermes(prompt, settings)), "Hermes"
        except Exception as e:  # noqa: BLE001 - Gemini is still there
            log.info("Hermes did not answer (%s); asking Gemini", e)
    try:
        if system or models:
            return ask_gemini(prompt, system, models), "Gemini"
        return ask_gemini(prompt), "Gemini"
    except Exception as e:  # noqa: BLE001 - Claude is the last brain standing
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise
        log.info("Gemini did not answer (%s); asking Claude", e)
        import assistant
        return assistant.ask_once(system or SYSTEM, prompt, max_tokens=3000), "Claude"


# -- the desk ------------------------------------------------------------------------

def _resolve(stock):
    import market
    return market.resolve(stock)


def load_reports(path=None):
    try:
        with open(path or REPORTS, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _save_reports(reports, path):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(reports[:KEEP], f, ensure_ascii=False, indent=1)
    except OSError:
        log.info("LYLA: could not keep her reports", exc_info=True)


class Desk:
    """Her jobs, one at a time, on a thread of her own.

    `tell(event)` is her card on the display - {agent, stage, text, ...} as
    answer_with_agent sends it, with the job's `task` and `symbol`.
    `report(job)` is Apollo passing on what she found (or that she could
    not); it runs holding `gate`, so it waits for any turn in progress.
    `think(prompt)`, `facts(job, step)` and `resolve(stock)` are what she
    thinks with, reads and finds a ticker with, replaceable in tests.
    """

    def __init__(self, tell=None, report=None, gate=None, think=think, facts=None,
                 resolve=None, path=None, name=NAME):
        self.name = name
        self.tell_card = tell
        self.report = report
        self.gate = gate
        self.think = think
        self.facts = facts or self._read
        self.resolve = resolve or _resolve
        self.path = path or REPORTS
        self.reports = load_reports(self.path)
        self.jobs = queue.Queue()
        self.current = None
        self.last_error = None          # (when, why) of the last failed job
        self.failures = []              # when each job failed, for the board
        self._ids = itertools.count(1)
        self._thread = None
        self._lock = threading.Lock()

    def configure(self, tell=None, report=None, gate=None):
        """Wire her card and Apollo's voice in, once they exist."""
        self.tell_card, self.report, self.gate = tell, report, gate
        return self

    @property
    def waiting(self):
        return self.jobs.qsize()

    def take(self, task, stock="", **extra):
        """A job from Apollo - with the stock it is about, as it was said,
        if it is about one. Returns at once with where it stands in line.
        `extra` rides along on the job for an agent's own reader."""
        job = {"id": next(self._ids), "task": " ".join(str(task).split()),
               "stock": " ".join(str(stock or "").split()), "symbol": "", "asked": time.time(),
               "agent": self.name, **extra}
        ahead = self.waiting + (self.current is not None)
        self.jobs.put(job)
        with self._lock:
            if self._thread is None:
                self._thread = threading.Thread(target=self._work, daemon=True,
                                                name=f"{self.name.lower()}-desk")
                self._thread.start()
        return {"job": job["id"], "ahead": ahead}

    def _tell(self, job, **event):
        # What the board shows of the job in hand: each step, with its time.
        if event.get("stage") == "received":
            self.steps = []
        self.steps = (getattr(self, "steps", []) + [{"stage": event.get("stage"),
                      "text": str(event.get("text", ""))[:140], "t": time.time()}])[-12:]
        if self.tell_card is None:
            return
        try:
            self.tell_card({"agent": self.name, "task": job["task"], "symbol": job["symbol"],
                            "job": job["id"], **event})
        except Exception:  # noqa: BLE001 - a card that cannot be told never costs the job
            log.debug("LYLA's card failed", exc_info=True)

    def prompt_for(self, job, facts):
        """The prompt for one job; another agent's desk can add to it."""
        return prompt_for(job, facts)

    def _read(self, job, step):
        return stock_facts(job["symbol"], step) if job["symbol"] else general_facts(job["task"], step)

    def _work(self):
        while True:
            try:
                job = self.jobs.get(timeout=30)
            except queue.Empty:
                with self._lock:            # the next job starts her again
                    if self.jobs.empty():
                        self._thread = None
                        return
                continue
            self.current = job
            try:
                self.run(job)
            finally:
                self.current = None

    def run(self, job):
        """One job, start to finish, and Apollo told how it went."""
        started = time.monotonic()
        self._tell(job, stage="received", text=job["task"], by="Apollo")
        try:
            if job["stock"]:
                self._tell(job, stage="step", text=f"Finding the ticker for {job['stock']}")
                try:
                    job["symbol"] = self.resolve(job["stock"]) or ""
                except Exception as e:  # noqa: BLE001 - read it by name instead
                    log.info("%s: no ticker for %r (%s)", self.name, job["stock"], e)
                    job["symbol"] = ""
            facts = self.facts(job, lambda text: self._tell(job, stage="step", text=text))
            counted = facts.get("counted_verdict") or {}
            job["verdict"], job["tone"] = counted.get("verdict", ""), counted.get("tone", "")
            self._tell(job, stage="asking", text="Writing it up")
            answer, brain = self.think(self.prompt_for(job, facts))
            summary, report = split(answer)
            job.update(ok=True, summary=summary, report=report, brain=brain,
                       sources=facts.get("sources", {}))
        except Exception as e:  # noqa: BLE001 - a failed job is reported, not raised
            log.warning("%s's job failed: %s", self.name, e)
            job.update(ok=False, summary="", report="", error=str(e) or type(e).__name__)
        job["took"] = int((time.monotonic() - started) * 1000)
        job["done"] = time.time()
        if job["ok"]:
            self._tell(job, stage="done", text=job["summary"], report=job["report"],
                       ms=job["took"], brain=job["brain"])
            keep_file(job)
            self.reports.insert(0, {k: job.get(k, "") for k in ("task", "symbol", "summary", "report",
                                                                 "brain", "asked", "done", "took",
                                                                 "file", "link", "verdict", "tone")})
            del self.reports[KEEP:]
            _save_reports(self.reports, self.path)
        else:
            self.last_error = {"when": job["done"], "why": job["error"], "task": job["task"]}
            self.failures = (self.failures + [job["done"]])[-50:]
            self._tell(job, stage="error", text=job["error"])
        self._pass_on(job)

    def _pass_on(self, job):
        if job.get("telegram"):              # asked from the phone: the answer goes back there too
            try:
                import telegram_bot
                telegram_bot.send_report(f"{self.name}: " + (job.get("summary", "") + "\n\n" + job.get("report", "")
                                                           if job.get("ok") else f"that failed - {job.get('error', '')}"))
            except Exception:  # noqa: BLE001
                log.info("telegram report failed", exc_info=True)
        if self.report is None:
            return
        try:
            if self.gate is None:
                self.report(job)
            else:
                with self.gate:
                    self.report(job)
        except Exception:  # noqa: BLE001 - her thread outlives a report that fails
            log.warning("%s's report failed", self.name, exc_info=True)


def keep_file(job):
    """Every finished job as a file you can open: Documents\\Apollo\\Crew\\
    <AGENT>\\<date> <task>.md - and its first link (Q's ticket) on the job."""
    found = re.search(r"https?://\S+", job.get("report", "") or "")
    job["link"] = found.group(0).rstrip(").,]") if found else ""
    try:
        import files
        stamp = time.strftime("%Y-%m-%d %H-%M", time.localtime(job.get("done") or time.time()))
        slug = re.sub(r"[^\w\s-]", "", job.get("task", ""))[:50].strip() or "job"
        text = (f"# {job.get('agent', NAME)}: {job.get('task', '')}\n\n"
                f"**{job.get('summary', '')}**\n\n{job.get('report', '')}\n")
        job["file"] = files.write(f"Crew/{job.get('agent', NAME)}/{stamp} {slug}.md", text)["path"]
    except Exception:  # noqa: BLE001 - the report is still kept in the app
        job["file"] = ""
        log.info("could not keep %s's report as a file", job.get("agent"), exc_info=True)


DESK = Desk()      # crew.py puts LYLA's own desk here
