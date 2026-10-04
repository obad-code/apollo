"""System Check: one button that looks over the whole of Apollo and fixes
what is safe to fix by itself.

What it looks at - Apollo only:
    the boot checks (diagnostics.py): keys, network, microphone, speakers,
    disk, saved files, clip encoder, last run, self test, data sources;
    whether the crew can think (one tiny "Reply with OK." to each brain);
    Gemini's daily quota - which models are spent and for how long;
    every agent's code loads (MONEYPENNY, THEIA, Q, LYLA, the digest...);
    TradingAgents installed or not;
    how many errors Apollo logged today, by part (counts, never the text).

What it may fix by itself - only inside Apollo's own folder
(%LOCALAPPDATA%\\Apollo), and nothing is ever deleted without a copy:
    a saved file that no longer reads is moved aside (name.broken-<time>)
    so that part starts clean instead of failing again and again;
    half-written leftovers (*.tmp) from a save that was cut off are removed;
    Gemini models whose quota has come back are asked again.

Privacy: it reads no file outside Apollo's folder, never reads your mail,
messages, screen or projects, never shows a key's value (only whether it
is set), and sends nothing anywhere - the result stays on this PC
(syscheck.json).
"""

import datetime as dt
import importlib
import json
import os
import re
import time

import diagnostics

OK, WARN, FAIL = diagnostics.OK, diagnostics.WARN, diagnostics.FAIL
APOLLO_DIR = diagnostics.APOLLO_DIR
PATH = os.path.join(APOLLO_DIR, "syscheck.json")

AGENTS = (("crew", "THE CREW"), ("lyla", "LYLA"), ("trading_team", "MONEYPENNY'S TEAM"),
          ("ideas", "THEIA - IDEAS"), ("myprojects", "THEIA - PROJECTS"), ("qfixes", "Q - FIXES"),
          ("digest", "DAILY SUMMARY"), ("alerts", "ALERTS"), ("telegram_bot", "TELEGRAM"),
          ("shorts", "SHORTS"))
_LOGLINE = re.compile(r"^(\d{4}-\d{2}-\d{2})\S*\s+\S*\s*(ERROR|CRITICAL)\s+(\S+?):")


def _row(cid, label, status, detail, fixed=""):
    return {"id": cid, "label": label, "status": status, "detail": str(detail)[:200], "fixed": fixed}


def check_agents(load=importlib.import_module):
    out = []
    for module, label in AGENTS:
        try:
            load(module)
            out.append(_row("agent:" + module, label, OK, "loads"))
        except Exception as e:  # noqa: BLE001 - a part that will not load is the finding
            out.append(_row("agent:" + module, label, FAIL, f"{type(e).__name__}: {e}"))
    return out


def check_brains(check=None):
    if check is None:
        import crew
        check = crew.check
    out = []
    for name, r in check().items():
        why = r.get("why", "")
        status = OK if r.get("ok") else (WARN if why == "not set up" else FAIL)
        out.append(_row("brain:" + name.lower(), f"BRAIN - {name.upper()}", status, "answers" if r.get("ok") else why))
    return out


def check_quota(spent=None, now=None):
    if spent is None:
        import lyla
        spent = lyla._spent
    now = now or time.time()
    busy = {m: t for m, t in spent.items() if t > now}
    if not busy:
        return [_row("quota", "GEMINI QUOTA", OK, "no model is spent")]
    soonest = min(busy.values()) - now
    names = ", ".join(sorted(busy))
    return [_row("quota", "GEMINI QUOTA", WARN,
                 f"spent: {names} - back in about {max(1, round(soonest / 3600))} h "
                 "(free daily limit; the agents wait for it)")]


def check_trading_agents(installed=None):
    if installed is None:
        import trading_team
        installed = trading_team.installed
    return [_row("tradingagents", "TRADINGAGENTS", OK, "installed") if installed()
            else _row("tradingagents", "TRADINGAGENTS", WARN, "not installed - the built-in team runs instead")]


def check_log(log_path=None, today=None):
    """Errors Apollo logged today, counted by part - never the lines themselves."""
    today = (today or dt.date.today()).isoformat()
    counts = {}
    try:
        with open(log_path or diagnostics.LOG_PATH, encoding="utf-8", errors="ignore") as f:
            for line in f:
                m = _LOGLINE.match(line)
                if m and m.group(1) == today:
                    part = m.group(3).replace("apollo.", "")
                    counts[part] = counts.get(part, 0) + 1
    except OSError:
        return [_row("log", "TODAY'S ERRORS", OK, "no log yet")]
    if not counts:
        return [_row("log", "TODAY'S ERRORS", OK, "none")]
    top = sorted(counts.items(), key=lambda kv: -kv[1])[:5]
    total = sum(counts.values())
    return [_row("log", "TODAY'S ERRORS", WARN if total < 20 else FAIL,
                 f"{total} today - " + ", ".join(f"{p} {n}" for p, n in top))]


# -- the safe fixes: only inside Apollo's folder ------------------------------------------

def _inside(path, folder):
    real, root = os.path.realpath(path), os.path.realpath(folder)
    return os.path.commonpath([real, root]) == root


def fix_files(folder=None, now=None):
    """Broken saved files moved aside (kept), cut-off *.tmp leftovers removed."""
    folder = folder or APOLLO_DIR
    now = now or time.time()
    moved, removed = [], []
    for base, _dirs, names in os.walk(folder):
        for name in names:
            path = os.path.join(base, name)
            if not _inside(path, folder) or os.path.islink(path):
                continue
            if name.endswith(".tmp") and now - os.path.getmtime(path) > 600:
                os.remove(path)
                removed.append(name)
            elif name.endswith(".json"):
                try:
                    with open(path, encoding="utf-8") as f:
                        json.load(f)
                except (ValueError, UnicodeDecodeError):
                    os.replace(path, f"{path}.broken-{int(now)}")
                    moved.append(name)
                except OSError:
                    pass
    out = []
    if moved:
        out.append(_row("fix:files", "BROKEN FILES", OK, "moved aside, kept as .broken: " + ", ".join(moved[:6]),
                        fixed="moved aside"))
    if removed:
        out.append(_row("fix:tmp", "LEFTOVERS", OK, f"{len(removed)} half-written file(s) removed", fixed="cleaned"))
    return out


def fix_quota(spent=None, now=None):
    if spent is None:
        import lyla
        spent = lyla._spent
    now = now or time.time()
    back = [m for m, t in list(spent.items()) if t <= now]
    for m in back:
        spent.pop(m, None)
    return [_row("fix:quota", "GEMINI QUOTA", OK, "asking again: " + ", ".join(back), fixed="reset")] if back else []


# -- the whole run ---------------------------------------------------------------------------

def run(path=PATH, parts=None):
    """Fixes first, then every check. Returns {at, rows, ok, warn, fail, fixed}; kept in syscheck.json."""
    parts = parts or (fix_files, fix_quota,
                      lambda: [dict(r, fixed="") for r in diagnostics.run(timeout=10)],
                      check_brains, check_quota, check_agents, check_trading_agents, check_log)
    rows = []
    for part in parts:
        try:
            rows += part()
        except Exception as e:  # noqa: BLE001 - one part breaking never stops the check
            rows.append(_row("part", getattr(part, "__name__", "CHECK").upper(), FAIL, f"{type(e).__name__}: {e}"))
    result = {"at": time.time(), "rows": rows,
              "ok": sum(r["status"] == OK and not r["fixed"] for r in rows),
              "warn": sum(r["status"] == WARN for r in rows),
              "fail": sum(r["status"] == FAIL for r in rows),
              "fixed": sum(bool(r["fixed"]) for r in rows)}
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)
    except OSError:
        pass
    return result


def last(path=PATH):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None
