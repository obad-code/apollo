"""Apollo's crew: the four agents he hands work to.

    LYLA        research and media - finds things out, gathers sources,
                downloads videos (lyla.py, youtube.py)
    THEIA       the professor - takes any idea and analyses it: what it is,
                what is wrong with it, and the best way to do it
    MONEYPENNY  the markets desk - one stock or the whole watchlist: a
                verdict from Strong Buy to Sell, the reasons and the red flags
    Q           the quartermaster - turns a request for a new feature or a
                fix into a ticket for Claude to build (github_requests.py)

Each one is a `lyla.Desk`: a queue of jobs on a thread of its own, a card on
the display that shows each step, and a report Apollo passes on in his own
voice when the job is done. There is one voice: an agent never speaks, it
writes, and Apollo tells you.

Cost. THEIA does in one call what a team of three would do in three: she
analyses, then turns on her own analysis as a critic, then writes the plan
that survives it. That is most of a team's quality for the price of one
agent. `deep=True` (the user said "تحليل عميق" / "deep analysis") puts a
stronger model on it - Claude, if ANTHROPIC_API_KEY is set - and only then.
"""

import logging
import os

import lyla

log = logging.getLogger("apollo.crew")

LYLA = lyla.NAME
THEIA = "THEIA"
MONEYPENNY = "MONEYPENNY"
Q = "Q"
NAMES = (LYLA, THEIA, MONEYPENNY, Q)

ROLES = {
    LYLA: "Research & media",
    THEIA: "Professor · analyst",
    MONEYPENNY: "Markets desk",
    Q: "Quartermaster · builds",
}

_HERE = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Apollo")

# The cheap brain first, for every everyday job.
FAST_MODELS = tuple(filter(None, (os.environ.get("CREW_MODEL"),
                                  "gemini-flash-latest", "gemini-2.5-flash")))
DEEP_GEMINI = tuple(filter(None, (os.environ.get("CREW_DEEP_MODEL"),
                                  "gemini-pro-latest", "gemini-2.5-pro"))) + FAST_MODELS
DEEP_CLAUDE = os.environ.get("THEIA_CLAUDE_MODEL") or "claude-opus-5-5"
FAST_CLAUDE = os.environ.get("CREW_CLAUDE_MODEL") or "claude-sonnet-5-5"

SUMMARY_RULE = (
    "Answer in exactly this shape. The first line is `SUMMARY:` and two short "
    "sentences Apollo can say out loud, in the language the job was given in "
    "(Saudi dialect if it was Arabic). Then a blank line, then the report: short "
    "sections under plain headings.")

THEIA_SYSTEM = (
    "You are THEIA, the professor of Apollo's crew - an analyst who can take any "
    "idea, plan, product, claim, decision or question and think it through "
    "properly. You work in three passes and show all three:\n"
    "1. ANALYSIS - what it really is, how it works, the facts and numbers that "
    "matter, what it depends on.\n"
    "2. CRITIQUE - now argue against your own analysis as a sharp critic would: "
    "the weak assumptions, the risks, what is missing, what would make it fail, "
    "the strongest case against it.\n"
    "3. THE BEST WAY - what survives the critique: the best approach or "
    "decision, concrete steps in order, and what to watch.\n"
    "End with a VERDICT line and a CONFIDENCE of low, medium or high, with the "
    "reason. Be concrete, use the sources you were given and search for the "
    "rest, and say where facts came from. Under 500 words.\n\n" + SUMMARY_RULE)

MONEYPENNY_SYSTEM = (
    "You are MONEYPENNY, the markets desk of Apollo's crew. You read stocks for "
    "the user and give a straight verdict. For each stock you are given, cover: "
    "what the company does; how the price has moved; valuation; what insiders, "
    "members of Congress and traders are doing with it; the news and the "
    "catalysts coming up.\n"
    "Then, for each stock:\n"
    "- VERDICT: one of STRONG BUY, BUY, HOLD, TRIM, SELL - and CONFIDENCE: low, "
    "medium or high.\n"
    "- WHY BUY: the reasons for it.\n"
    "- RED FLAGS: the reasons not to buy, or to take money out - debt, falling "
    "revenue, insiders selling, lawsuits, dilution, a crowded trade, anything.\n"
    "When asked about several stocks or the watchlist, end with a ranking: which "
    "are strongest, and which the user should consider pulling money out of "
    "first, and why.\n"
    "Be concrete - numbers, dates, names - and say where each fact came from. "
    "This is a read, not financial advice: say so once, at the end. Under 450 "
    "words.\n\n" + SUMMARY_RULE)

Q_SYSTEM = (
    "You are Q, the quartermaster of Apollo's crew. The user asked for something "
    "to be added to Apollo or fixed in him. Write it up as a clear ticket for "
    "the engineer (Claude) who will build it: a short title, what the user "
    "wants in their words, what it should do, how to tell it works, and any "
    "detail they gave. Do not invent requirements they did not ask for.\n\n"
    "Answer in exactly this shape. The first line is `SUMMARY:` and one short "
    "sentence Apollo can say out loud, in the user's language. The second line "
    "is `TITLE:` and the ticket's title in English, under 70 characters. Then a "
    "blank line, then the ticket body in Markdown.")


# -- what each one reads ---------------------------------------------------------

def watchlist_symbols(most=8):
    try:
        import watchlist
        return [s for s in watchlist.current() if isinstance(s, str)][:most]
    except Exception:  # noqa: BLE001 - no watchlist is no stocks to read
        log.debug("watchlist unreadable", exc_info=True)
        return []


def moneypenny_facts(job, step):
    """One stock, or every stock on the watchlist when the job is about it."""
    if job.get("symbol"):
        return lyla.stock_facts(job["symbol"], step)
    symbols = job.get("symbols") or []
    if not symbols:
        return lyla.general_facts(job["task"], step)
    facts = {"stocks": {}, "sources": {}}
    for symbol in symbols:
        read = lyla.stock_facts(symbol, step)
        facts["sources"].update({f"{symbol}:{k}": v for k, v in read.pop("sources", {}).items()})
        facts["stocks"][symbol] = read
    return facts


def theia_facts(job, step):
    return lyla.general_facts(job["task"], step)


def q_facts(job, step):
    step("Writing the ticket")
    return {"sources": {}}


# -- how each one thinks -----------------------------------------------------------

def _claude(prompt, system, model=None):
    import assistant
    return assistant.ask_once(system, prompt, max_tokens=4000, model=model or DEEP_CLAUDE)


def thinker(system, deep_capable=False):
    """`think(prompt)` for a desk. A deep job (prompt marked by `deep_prompt`)
    goes to Claude when there is a key for it, else to Gemini's pro model."""
    def think(prompt):
        if deep_capable and prompt.startswith(DEEP_MARK):
            prompt = prompt[len(DEEP_MARK):]
            if os.environ.get("ANTHROPIC_API_KEY"):
                try:
                    return _claude(prompt, system), "Claude"
                except Exception as e:  # noqa: BLE001 - Gemini is still there
                    log.info("THEIA: Claude did not answer (%s); asking Gemini", e)
            return lyla.ask_gemini(prompt, system, DEEP_GEMINI), "Gemini Pro"
        if os.environ.get("ANTHROPIC_API_KEY"):
            try:
                return _claude(prompt, system, FAST_CLAUDE), "Claude"
            except Exception as e:  # noqa: BLE001 - Gemini is still there
                log.info("Claude did not answer (%s); asking Gemini", e)
        return lyla.think(prompt, system, FAST_MODELS)
    return think


DEEP_MARK = "[[deep]]\n"


def prompt_for(job, facts):
    text = lyla.prompt_for(job, facts)
    return (DEEP_MARK + text) if job.get("deep") else text


class CrewDesk(lyla.Desk):
    """A desk whose prompt can carry the deep flag."""

    def prompt_for(self, job, facts):
        return prompt_for(job, facts)

    def run(self, job):
        result = super().run(job)
        if job.get("idea") and job.get("ok"):          # THEIA's read of an idea is kept on the idea
            try:
                import ideas
                ideas.attach(job["idea"], job.get("summary", ""), job.get("report", ""))
            except Exception:  # noqa: BLE001
                log.info("idea analysis not kept", exc_info=True)
        return result


def q_think(prompt):
    """Q writes the ticket, then files it: what Apollo says is the ticket's
    number, and the report is the ticket itself with its link."""
    import github_requests
    text, brain = lyla.think(prompt, Q_SYSTEM, FAST_MODELS)
    summary, rest = lyla.split(text)
    title = ""
    lines = rest.splitlines()
    if lines and lines[0].upper().startswith("TITLE:"):
        title, rest = lines[0][6:].strip(), "\n".join(lines[1:]).strip()
    made = github_requests.file_issue(title or summary, rest)
    return (f"SUMMARY: {summary} Ticket #{made['number']} is filed for Claude.\n\n"
            f"{rest}\n\n{made['url']}"), brain


def _desk(name, system, facts, deep=False, think=None):
    return CrewDesk(think=think or thinker(system, deep), facts=facts, name=name,
                    path=os.path.join(_HERE, f"{name.lower()}_reports.json"))


def lyla_think(prompt):
    """LYLA thinks the way she always has - unless the job is for the
    connectors, which go through Claude and your MCP servers."""
    if prompt.startswith(CONNECT_MARK):
        import connectors
        task = prompt[len(CONNECT_MARK):]
        return connectors.ask(task), "Claude · connectors"
    return lyla.think(prompt)


CONNECT_MARK = "[[connectors]]\n"


class LylaDesk(lyla.Desk):
    """LYLA's desk: a connectors job goes straight to them, with no reading;
    a Short is made here, step by step, so its card shows how it is going."""

    def _niche(self, job):
        import time as _t
        import niche
        started = _t.monotonic()
        self._tell(job, stage="received", text=job["task"], by="Apollo")
        try:
            self._tell(job, stage="step", text="Researching niches")
            rows = niche.ask()
            niche.save(rows)
            job.update(ok=True, brain="Gemini", sources={}, report=niche.render(rows),
                       summary=f"Best niche now: {rows[0]['niche']} - say \"niche 1\" to pick it, or another number.")
        except Exception as e:  # noqa: BLE001
            log.warning("niche research failed: %s", e)
            job.update(ok=False, summary="", report="", error=str(e) or type(e).__name__)
        job["took"] = int((_t.monotonic() - started) * 1000)
        job["done"] = _t.time()
        if job["ok"]:
            self._tell(job, stage="done", text=job["summary"], report=job["report"], ms=job["took"], brain="Gemini")
            lyla.keep_file(job)
            self.reports.insert(0, {k: job.get(k, "") for k in ("task", "symbol", "summary", "report",
                                                                 "brain", "asked", "done", "took", "file", "link",
                                                                 "video", "preview")})
            del self.reports[lyla.KEEP:]
            lyla._save_reports(self.reports, self.path)
        else:
            self.last_error = {"when": job["done"], "why": job["error"], "task": job["task"]}
            self.failures = (self.failures + [job["done"]])[-50:]
            self._tell(job, stage="error", text=job["error"])
        self._pass_on(job)

    def run(self, job):
        if job.get("niche"):
            return self._niche(job)
        if not job.get("short"):
            return super().run(job)
        import time as _t
        import shorts
        started = _t.monotonic()
        self._tell(job, stage="received", text=job["task"], by="Apollo")
        try:
            step = lambda text: self._tell(job, stage="step", text=text)  # noqa: E731
            if job.get("batch"):
                import autopost
                step("Reading today's trends")
                made = []
                for n, pick in enumerate(autopost.pick_topics(job["batch"]), 1):
                    step(f"Short {n} ({pick.get('world') or pick['kind']}): {pick['topic'] or pick['kind']}")
                    try:
                        made.append(shorts.make(pick["kind"], pick["topic"], step=step, world=pick.get("world", "")))
                    except Exception as e:  # noqa: BLE001 - one bad Short never costs the rest
                        log.warning("short %d failed: %s", n, e)
                        if n == job["batch"] and not made:
                            raise
                autopost.offer(made)
                if made:
                    job["video"], job["preview"] = made[0]["path"], made[0].get("preview", "")
                job.update(ok=True, brain="Gemini", sources={}, ask_pick=True,
                           summary=autopost.question(made),
                           report="\n".join(f"{i + 1}. {m['title']}  -  {m['path']}" for i, m in enumerate(made)))
            else:
                import autopost
                made = shorts.make(job.get("kind") or None, job.get("topic", ""), step=step)
                job["video"], job["preview"] = made["path"], made.get("preview", "")
                autopost.offer([made])                  # waits for your word: post, private draft, or keep the file
                job.update(ok=True, brain="Gemini", sources={}, ask_pick=True,
                           summary=autopost.question([made]),
                           report=f"Saved to {made['path']}\n\nTitle, description and hashtags: {made['notes']}")
        except Exception as e:  # noqa: BLE001
            log.warning("short failed: %s", e)
            job.update(ok=False, summary="", report="", error=str(e) or type(e).__name__)
        job["took"] = int((_t.monotonic() - started) * 1000)
        job["done"] = _t.time()
        if job["ok"]:
            self._tell(job, stage="done", text=job["summary"], report=job["report"], ms=job["took"], brain="Gemini")
            lyla.keep_file(job)
            self.reports.insert(0, {k: job.get(k, "") for k in ("task", "symbol", "summary", "report",
                                                                 "brain", "asked", "done", "took", "file", "link",
                                                                 "video", "preview")})
            del self.reports[lyla.KEEP:]
            lyla._save_reports(self.reports, self.path)
        else:
            self.last_error = {"when": job["done"], "why": job["error"], "task": job["task"]}
            self.failures = (self.failures + [job["done"]])[-50:]
            self._tell(job, stage="error", text=job["error"])
        self._pass_on(job)

    def prompt_for(self, job, facts):
        if job.get("connectors"):
            return CONNECT_MARK + job["task"]
        return lyla.prompt_for(job, facts)

    def _read(self, job, step):
        if job.get("connectors"):
            step("Opening your connectors")
            return {"sources": {}}
        return super()._read(job, step)


THEIA_DESK = _desk(THEIA, THEIA_SYSTEM, theia_facts, deep=True)
TEAM = os.environ.get("MONEYPENNY_TEAM", "1").strip().lower() not in ("0", "false", "no", "off")


class MoneypennyDesk(CrewDesk):
    """MONEYPENNY runs an analyst team (trading_team.py, after TradingAgents):
    four analysts, a bull/bear debate, a research manager, a trader and a risk
    team - and she makes the final call. MONEYPENNY_TEAM=0 has her work alone."""

    _job = None

    def run(self, job):
        self._job = job
        result = super().run(job)
        if job.get("ok") and job.get("symbol") and job.get("verdict"):
            try:                                  # kept, so her calls can be graded later (calls.py)
                import analysis
                import calls
                calls.record(job["symbol"], job["verdict"], analysis.analyse(job["symbol"]).get("price"))
            except Exception:  # noqa: BLE001
                log.debug("call not kept", exc_info=True)
        return result

    def prompt_for(self, job, facts):
        import calls
        return super().prompt_for(job, facts) + calls.lessons_prompt()

    def team_think(self, prompt):
        import trading_team
        deep = prompt.startswith(DEEP_MARK)
        facts = prompt[len(DEEP_MARK):] if deep else prompt

        def ask(text, system):
            return thinker(system, deep)((DEEP_MARK + text) if deep else text)

        def step(text):
            if self._job is not None:
                self._tell(self._job, stage="step", text=text)

        symbol = (self._job or {}).get("symbol")
        final = None
        if symbol and trading_team.installed():
            try:
                final, brain, notes = trading_team.with_real(symbol, facts, ask, MONEYPENNY_SYSTEM, step)
            except Exception as e:  # noqa: BLE001 - the built-in team still answers
                log.warning("TradingAgents failed on %s: %s", symbol, e)
                step(f"TradingAgents failed ({e}); the built-in team takes it")
        if final is None:
            final, brain, notes = trading_team.debate(facts, ask, MONEYPENNY_SYSTEM, step)
            if symbol:                       # said plainly, so it is never taken for TradingAgents' work
                final += ("\n\nNote: this call is from MONEYPENNY's built-in team - TradingAgents "
                          + ("failed on this stock." if trading_team.installed() else "is not installed (run update.bat)."))
        return final + trading_team.appendix(notes), brain


MONEYPENNY_DESK = MoneypennyDesk(think=None, facts=moneypenny_facts, name=MONEYPENNY,
                                 path=os.path.join(_HERE, f"{MONEYPENNY.lower()}_reports.json"))
MONEYPENNY_DESK.think = MONEYPENNY_DESK.team_think if TEAM else thinker(MONEYPENNY_SYSTEM)
Q_DESK = _desk(Q, Q_SYSTEM, q_facts, think=q_think)

lyla.DESK = LylaDesk(think=lyla_think)

DESKS = {LYLA: lyla.DESK, THEIA: THEIA_DESK, MONEYPENNY: MONEYPENNY_DESK, Q: Q_DESK}


def desk(name):
    return DESKS.get(str(name or "").strip().upper())


def configure(tell=None, report=None, gate=None):
    """Wire every desk's card and Apollo's voice in. `report(job)` gets the
    job, which carries `agent` - whose it was."""
    for one in DESKS.values():
        one.configure(tell=tell, report=report, gate=gate)


def status():
    """Each agent: what it is on, how many wait, its latest reports."""
    out = {}
    for name, one in DESKS.items():
        working = one.current
        out[name] = {"role": ROLES[name],
                     "working": {"task": working["task"], "symbol": working.get("symbol", "")}
                                if working else None,
                     "waiting": one.waiting,
                     "reports": one.reports[:8]}
    return out



# -- the crew's board: what agents mode shows behind the agents ------------------

def board(now=None, journal_day=None, spend=None, problems=None, alerts_state=None):
    """Everything agents mode's dashboard draws, from what Apollo actually
    knows: each agent's state, today's jobs by hour, the latest jobs, the
    day's spend by model, the tools used, issues and alerts. The readers are
    arguments so tests can hand in their own."""
    import datetime as dt
    now = now or dt.datetime.now()
    start = dt.datetime.combine(now.date(), dt.time()).timestamp()
    agents, jobs = {}, []
    hours = {name: [0] * 24 for name in NAMES}
    failed = 0
    for name, one in DESKS.items():
        working = one.current
        agents[name] = {"role": ROLES[name], "waiting": one.waiting,
                        "working": working["task"] if working else "",
                        "steps": list(getattr(one, "steps", [])),
                        "error": getattr(one, "last_error", None),
                        "failed_today": sum(1 for t in getattr(one, "failures", []) if t >= start),
                        "last_done": max((float(r.get("done") or 0) for r in one.reports), default=0),
                        "avg_ms": int(sum(r.get("took", 0) for r in one.reports[:10])
                                      / max(1, len(one.reports[:10]))),
                        "done_today": 0}
        for report in one.reports:
            done = float(report.get("done") or 0)
            jobs.append({"agent": name, "task": report.get("task", ""),
                         "summary": report.get("summary", ""), "took": report.get("took", 0),
                         "brain": report.get("brain", ""), "done": done,
                         "file": report.get("file", ""), "link": report.get("link", ""), "report": (report.get("report", "") or "")[:6000],
                         "symbol": report.get("symbol", ""), "verdict": report.get("verdict", ""), "tone": report.get("tone", ""),
                         "video": report.get("video", ""), "preview": report.get("preview", ""), "took_ms": report.get("took", 0)})
            if done >= start:
                agents[name]["done_today"] += 1
                hours[name][dt.datetime.fromtimestamp(done).hour] += 1
    jobs.sort(key=lambda j: -j["done"])

    if journal_day is None:
        import journal
        journal_day = journal.day(now.date())
    tools_used = {}
    for entry in journal_day:
        if entry.get("kind") == "tool" and entry.get("name"):
            tools_used[entry["name"]] = tools_used.get(entry["name"], 0) + 1
    if spend is None:
        import usage
        spend = usage.today()
    if problems is None:
        import issues
        problems = issues.current()
    if alerts_state is None:
        import alerts
        watcher = alerts.WATCHER
        alerts_state = {"watching": watcher is not None,
                        "sent_hour": len(watcher.sent) if watcher else 0}
    for issue in problems:
        failed += 1 if issue.get("level") == "fail" else 0
    for name in agents:
        agents[name]["results"] = [j for j in jobs if j["agent"] == name][:6]
    return {"agents": agents, "hours": hours, "jobs": jobs[:8],
            "tools": sorted(tools_used.items(), key=lambda t: -t[1])[:6],
            "spend": spend, "issues": {"count": len(problems), "failing": failed,
                                       "top": [i.get("title", "") for i in problems[:3]]},
            "alerts": alerts_state, "now": now.timestamp(),
            "brains": {"Gemini": bool(os.environ.get("GEMINI_API_KEY")),
                       "Claude": bool(os.environ.get("ANTHROPIC_API_KEY")),
                       "Hermes": lyla.hermes_settings() is not None}}


def check():
    """Can the crew think? One tiny question to each brain they use, and
    what each said - so a dead key shows as a reason, not as silence."""
    out = {}
    for label, call in (("Gemini", lambda: lyla.ask_gemini("Reply with OK.", "Reply with OK.", FAST_MODELS)),
                        ("Hermes", lambda: lyla.ask_hermes("Reply with OK.", lyla.hermes_settings())
                         if lyla.hermes_settings() else None),
                        ("Claude", lambda: _claude("Reply with OK.", "Reply with OK.")
                         if os.environ.get("ANTHROPIC_API_KEY") else None)):
        try:
            answer = call()
            out[label] = {"ok": answer is not None, "why": "" if answer is not None else "not set up"}
        except Exception as e:  # noqa: BLE001
            out[label] = {"ok": False, "why": str(e)[:200] or type(e).__name__}
    return out
