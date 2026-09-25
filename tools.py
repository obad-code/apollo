"""Everything Apollo can *do*, declared once for both of its minds.

Gemini Live (the voice) and Claude (behind the agents) both call tools, and
they must call the same ones: a capability added here is available to
whichever model answers, with no second copy to drift. Each tool is a name, a
description written for the model, a JSON schema and a handler. Handlers take
`ctx` plus plain keyword arguments and return a dict (or a status string);
`run` is their only caller and the only place their errors are caught, so a
failing handler becomes a sentence the model can say rather than an
exception in the middle of a turn.

Tool calls come from a language model and are treated as untrusted input.
Unknown arguments are dropped, one mis-named string argument is mapped onto
the one the schema is missing (measured: the current native-audio model
sometimes sends `application_name` for `name`), values are coerced to the
schema's types, and anything that can end your session needs `confirmed:
true` in a turn *after* the one in which Apollo asked - see `Confirmations`.
"""

import json
import os
import logging
import threading
from dataclasses import dataclass
from typing import Callable

log = logging.getLogger("apollo.tools")


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict           # a JSON schema of type "object"
    handler: Callable          # handler(ctx, **args) -> dict | str
    confirm: bool = False      # needs a spoken yes first; see Confirmations


REGISTRY = {}

_turn = 0
_turn_lock = threading.Lock()


def new_user_turn():
    """The user has started speaking again. Returns the new turn number."""
    global _turn
    with _turn_lock:
        _turn += 1
        return _turn


def current_turn():
    return _turn


class Context:
    """What a handler may reach besides its arguments.

    `show(visual)` puts a chart or cards on the overlay, `activity(text)`
    says in a few words what Apollo is doing ("fetching NVDA"), `refresh(*keys)`
    asks the data service to read those parts of the world again (all of it,
    with none named) and push them to the display - without waiting for it,
    `panels(state)` tells the display which of its panels to show, `story(n)`
    opens the feed's nth story on it and says what that story is, `stock(sym)`
    does the same for a stock on the watchlist, `osiris(on)` opens or closes
    OSIRIS inside the display, `display(request)` asks ultra mode's displays
    for something - on or off, one expanded, one shown or hidden - and `turn`
    is the user's turn number at the moment the call arrived.
    """

    def __init__(self, show=None, activity=None, turn=None, refresh=None,
                 panels_hook=None, story_hook=None, stock_hook=None, idle_hook=None,
                 tab_hook=None, away_hook=None, osiris_hook=None, display_hook=None):
        self.show = show or (lambda visual: None)
        self.activity = activity or (lambda text: None)
        # False by default, so a tool that changes the display can tell the
        # difference between "refreshed" and "there was nothing to refresh".
        self.refresh = refresh or (lambda *keys: False)
        self.panels = panels_hook or (lambda state: None)
        self.story = story_hook or (lambda number: None)
        self.stock = stock_hook or (lambda symbol: None)
        self.idle = idle_hook or (lambda: False)
        self.tab = tab_hook or (lambda name: None)
        self.away = away_hook or (lambda: False)
        self.osiris = osiris_hook or (lambda on: False)
        self.display = display_hook or (lambda request: False)
        self.turn = current_turn() if turn is None else turn


def register(tool):
    REGISTRY[tool.name] = tool
    return tool


def schema_for_model(tool):
    """The schema the model sees: a confirm tool also gets `confirmed`."""
    schema = json.loads(json.dumps(tool.parameters))
    if tool.confirm:
        schema.setdefault("properties", {})["confirmed"] = {
            "type": "boolean",
            "description": ("True only when the user has just said yes to this "
                            "exact action. Never set it on the first call."),
        }
    return schema


def gemini_declarations():
    from google.genai import types
    return [types.FunctionDeclaration(name=t.name, description=t.description,
                                      parameters_json_schema=schema_for_model(t))
            for t in REGISTRY.values()]


def claude_tools():
    return [{"name": t.name, "description": t.description,
             "input_schema": schema_for_model(t)} for t in REGISTRY.values()]


def coerce(tool, args):
    """Clean a model's arguments against the schema. A dict, or an error string."""
    props = tool.parameters.get("properties", {})
    required = list(tool.parameters.get("required", []))
    known = set(props) | ({"confirmed"} if tool.confirm else set())
    clean = {k: v for k, v in args.items() if k in known}
    extras = [v for k, v in args.items() if k not in known]
    missing = [r for r in required if r not in clean]

    if len(missing) == 1 and len(extras) == 1:
        clean[missing[0]] = extras[0]
        missing = []
    if missing:
        return "Missing " + ", ".join(missing) + "."

    for key, spec in props.items():
        if key not in clean:
            continue
        value, kind = clean[key], spec.get("type")
        try:
            if kind == "string" and isinstance(value, list):
                # Measured: asked for one chart the model sent `symbols:
                # ["NVDA"]`. str() of that is "['NVDA']", which a name search
                # resolved to a leveraged NVDA fund - a wrong chart, spoken
                # with confidence. One item means that item.
                value = str(value[0]) if len(value) == 1 else ", ".join(map(str, value))
            elif kind == "string" and not isinstance(value, str):
                value = str(value)
            elif kind == "integer":
                value = int(round(float(value)))
            elif kind == "number":
                value = float(value)
            elif kind == "boolean" and not isinstance(value, bool):
                value = str(value).strip().lower() in ("true", "yes", "1")
            elif kind == "array" and not isinstance(value, list):
                value = [value]
        except (TypeError, ValueError):
            return f"{key} should be a {kind}."
        if "enum" in spec:
            wanted = {str(e).lower(): e for e in spec["enum"]}
            match = wanted.get(str(value).strip().lower().replace(" ", "_").replace("-", "_"))
            if match is None:
                return f"{key} must be one of: {', '.join(spec['enum'])}."
            value = match
        clean[key] = value

    if "confirmed" in clean:
        clean["confirmed"] = clean["confirmed"] is True or str(clean["confirmed"]).lower() == "true"
    return clean


class Confirmations:
    """What Apollo has asked you to confirm, and in which of your turns.

    A confirm tool runs only when it is called with confirmed=true for an
    action that was already asked about in an EARLIER turn of yours - your
    "yes" is a new turn, and that is what lets the second call through. The
    first call, flag or no flag, only records the question, so the model can
    never ask and answer in one breath. A question goes stale after two of
    your turns.
    """

    WINDOW = 2

    def __init__(self):
        self._asked = {}
        self._lock = threading.Lock()

    def reset(self):
        with self._lock:
            self._asked.clear()

    def allow(self, name, args, turn):
        key = (name, tuple(sorted((k, repr(v)) for k, v in args.items() if k != "confirmed")))
        with self._lock:
            asked = self._asked.get(key)
            if (args.get("confirmed") is True and asked is not None
                    and asked < turn <= asked + self.WINDOW):
                del self._asked[key]
                return True
            if asked is None or turn > asked + self.WINDOW:
                self._asked[key] = turn
            return False


CONFIRM = Confirmations()


def _as_result(value):
    if isinstance(value, dict):
        value.setdefault("ok", True)
        return json.loads(json.dumps(value, default=str))
    text = str(value)
    return {"ok": not text.startswith("Failed"), "result": text}


def run(name, args=None, ctx=None):
    """Run one tool call. Always returns a dict; never raises."""
    ctx = ctx or Context()
    tool = REGISTRY.get(name)
    if tool is None:
        return {"ok": False, "error": f"There is no tool called {name}."}
    clean = coerce(tool, dict(args or {}))
    if isinstance(clean, str):
        return {"ok": False, "error": clean}
    if tool.confirm and not CONFIRM.allow(name, clean, ctx.turn):
        return {"ok": False, "needs_confirmation": True,
                "error": ("Not done. Ask the user to confirm this exact action out "
                          "loud, and call again with confirmed=true only after they "
                          "say yes.")}
    clean.pop("confirmed", None)
    # Into the day's record (journal.py): what Apollo was asked to do says
    # as much about what you care about as what you said.
    journal.write("tool", name=name, args=clean)
    try:
        return _as_result(tool.handler(ctx, **clean))
    except Exception as e:  # noqa: BLE001 - a tool must never take a turn down
        if getattr(e, "speakable", False):          # already a sentence
            return {"ok": False, "error": str(e)}
        log.exception("tool %s failed", name)
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# --- the tools ---------------------------------------------------------------
#
# Descriptions are written for the model: when to call the tool, not how it is
# built. Imports are here, below the registry, so the registry itself stays
# importable (and testable) without Windows or the network.

import briefing  # noqa: E402
import ideas  # noqa: E402
import insiders  # noqa: E402
import journal  # noqa: E402
import private_eye  # noqa: E402
import clips  # noqa: E402
import displays  # noqa: E402
import feeds  # noqa: E402
import live  # noqa: E402
import market  # noqa: E402
import overlay_content  # noqa: E402
import panels  # noqa: E402
import prayer  # noqa: E402
import pc_control  # noqa: E402
import reminders  # noqa: E402
import watchlist  # noqa: E402


def _obj(props, required=()):
    return {"type": "object", "properties": props, "required": list(required)}


def _str(description):
    return {"type": "string", "description": description}


def _enum(values, description):
    return {"type": "string", "enum": list(values), "description": description}


TOOL_LABELS = {}


def _tool(name, label, description, parameters, confirm=False):
    def wrap(fn):
        TOOL_LABELS[name] = label
        register(Tool(name, description, parameters, fn, confirm))
        return fn
    return wrap


@_tool("open_app", "opening",
       "Open an application on the user's PC by name (Chrome, Spotify, Discord, Steam, "
       "VS Code, Notepad...). Switches to it if it is already open.",
       _obj({"name": _str("The app's name as the user said it")}, ["name"]))
def _open_app(ctx, name):
    ctx.activity(f"opening {name}")
    return pc_control.open_app(name)


@_tool("close_app", "closing",
       "Close an application's windows by name. The app still asks about unsaved work.",
       _obj({"name": _str("The app's name")}, ["name"]))
def _close_app(ctx, name):
    return pc_control.close_app(name)


@_tool("open_website", "opening",
       "Open a website in the user's browser: a site name (YouTube, Gmail, Reddit), a "
       "domain, a full URL, or a phrase to search Google for.",
       _obj({"site": _str("Site name, domain, URL or search phrase")}, ["site"]))
def _open_website(ctx, site):
    return pc_control.open_url(site)


@_tool("open_path", "opening",
       "Open a file or folder: a full path, a standard folder (Desktop, Downloads, "
       "Documents...) or a name to search for in the user's folders.",
       _obj({"target": _str("Path or name"), "kind": _enum(["file", "folder"], "What it is")},
            ["target", "kind"]))
def _open_path(ctx, target, kind):
    return pc_control.open_path(target, want_folder=(kind == "folder"))


@_tool("media", "media",
       "Control whatever is playing (Spotify, YouTube...): play or pause, next, previous, stop.",
       _obj({"action": _enum(pc_control.MEDIA, "What to do")}, ["action"]))
def _media(ctx, action):
    return pc_control.media(action)


@_tool("volume", "volume",
       "Read or change the PC's volume. level is 0-100 for set, or the step for up/down "
       "(default 10).",
       _obj({"action": _enum(["get", "set", "up", "down", "mute", "unmute"],
                             "What to do (default get)"),
             "level": {"type": "integer", "description": "0-100"}}))
def _volume(ctx, action="get", level=None):
    return pc_control.volume(action, level)


@_tool("window", "arranging windows",
       "Minimize, maximize, restore, close, focus or snap a window. With no app it acts "
       "on the window in front. show_desktop minimizes everything.",
       _obj({"action": _enum(["minimize", "maximize", "restore", "close", "focus",
                              "snap_left", "snap_right", "show_desktop"], "What to do"),
             "app": _str("Which app's window (optional)")}, ["action"]))
def _window(ctx, action, app=None):
    return pc_control.window(action, app)


@_tool("type_text", "typing",
       "Type text into the window the user is working in, exactly as given.",
       _obj({"text": _str("The text to type")}, ["text"]))
def _type_text(ctx, text):
    return pc_control.type_text(text)


@_tool("press_keys", "pressing keys",
       "Press a key or shortcut in the window in front, like 'ctrl+t', 'alt+tab', 'f5', "
       "'win+e', 'ctrl+shift+esc'.",
       _obj({"keys": _str("Keys joined with +")}, ["keys"]))
def _press_keys(ctx, keys):
    return pc_control.press_keys(keys)


@_tool("lock_pc", "locking", "Lock the PC (the user signs back in with their PIN).", _obj({}))
def _lock_pc(ctx):
    return pc_control.lock_pc()


@_tool("system_power", "power",
       "Sleep, restart, shut down or sign out - or cancel a pending restart/shutdown. "
       "Always ask the user to confirm first; call with confirmed=true only after they "
       "say yes.",
       _obj({"action": _enum(["sleep", "restart", "shutdown", "sign_out", "cancel"],
                             "What to do")}, ["action"]), confirm=True)
def _system_power(ctx, action):
    return pc_control.system_power(action)


@_tool("set_reminder", "setting a reminder",
       "Set a reminder. Give in_minutes for 'in 20 minutes', or when as an ISO 8601 "
       "local time like 2026-09-20T09:00:00 for a clock time.",
       _obj({"text": _str("What to remind them of"),
             "in_minutes": {"type": "number", "description": "Minutes from now"},
             "when": _str("ISO 8601 local time")}, ["text"]))
def _set_reminder(ctx, text, in_minutes=None, when=None):
    return reminders.add(text, when=when, in_minutes=in_minutes)


@_tool("list_reminders", "checking reminders", "List the reminders still waiting.", _obj({}))
def _list_reminders(ctx):
    return reminders.describe_pending()


@_tool("cancel_reminder", "cancelling a reminder",
       "Cancel a reminder by words from its text, its number, or 'all'.",
       _obj({"which": _str("Words from the reminder, its id, or 'all'")}, ["which"]))
def _cancel_reminder(ctx, which):
    return reminders.cancel(which)


def _summary(data):
    return {k: data[k] for k in ("symbol", "name", "price", "change", "change_pct", "currency")}


@_tool("stock_quote", "fetching prices",
       "Live price and today's change for one or more stocks, indices, crypto or "
       "commodities (tickers or names: NVDA, Apple, S&P 500, bitcoin, gold). Shows them "
       "on screen. Speak only the numbers this returns.",
       _obj({"symbols": {"type": "array", "items": {"type": "string"},
                         "description": "Tickers or names"}}, ["symbols"]))
def _stock_quote(ctx, symbols):
    quotes = []
    for raw in symbols[:6]:
        symbol = market.resolve(raw)
        ctx.activity(f"fetching {symbol}")
        # Up to the trade where it can be: the stream's price, or Finnhub's.
        quotes.append(live.freshen(market.quote(symbol)))
    if len(quotes) == 1:
        ctx.show(market.visual_for(quotes[0], "1d"))
    else:
        ctx.show(overlay_content.clean_visual({"cards": [
            {"label": q["symbol"], "value": f"{market.fmt_price(q['price'])} {q['change_pct']:+.1f}%"}
            for q in quotes]}))
    return {"quotes": [_summary(q) for q in quotes],
            "market": market.market_status()["label"]}


@_tool("show_stock_chart", "charting",
       "Draw a price chart on screen for a stock, index, crypto or commodity over a "
       "period, and get its numbers. Use for 'show me', 'chart', 'how has X done'.",
       _obj({"symbol": _str("Ticker or name"),
             "period": _enum(list(market.PERIODS), "How far back (default 5d)")}, ["symbol"]))
def _show_stock_chart(ctx, symbol, period="5d"):
    symbol = market.resolve(symbol)
    ctx.activity(f"charting {symbol}")
    data = market.history(symbol, period)
    ctx.show(market.visual_for(data, period))
    closes = [c for _, c in data["points"]] or [data["price"]]
    return {"symbol": symbol, "name": data["name"], "period": period,
            "last": data["price"], "currency": data["currency"],
            "change_pct_over_period": round(data["change_pct"], 2),
            "high": max(closes), "low": min(closes)}


@_tool("open_tradingview", "opening TradingView",
       "Open the full interactive TradingView chart for a symbol in the browser. Only when "
       "the user asks for TradingView.",
       _obj({"symbol": _str("Ticker or name")}, ["symbol"]))
def _open_tradingview(ctx, symbol):
    symbol = market.resolve(symbol)
    exchange = market.quote(symbol)["exchange"]
    return pc_control.open_url(market.tradingview_url(symbol, exchange))


_CLIP_BUFFER = None


def set_clip_buffer(buffer):
    """Apollo hands its replay buffer here once it is running."""
    global _CLIP_BUFFER
    _CLIP_BUFFER = buffer


# Measured against the Live API on 2026-09-20, and the reason this description
# reads so plainly: with "Save what just happened on screen ... Use for 'clip
# that', 'save the last minute', 'record that'." the server closed the whole
# session with "1011 Internal error occurred" the moment the model went to call
# it - every time, in any language, with the tool declared alone or with the
# others. The same tool, the same prompts and the same argument types work with
# the wording below. See probes/probe_tool_description.py.
@_tool("save_clip", "saving the clip",
       "Save the last N seconds of the screen to a video file. N is the seconds "
       "argument, 60 if the user does not say.",
       _obj({"seconds": {"type": "integer",
                         "description": "How far back to save, 5-60 (default 60)"}}))
def _save_clip(ctx, seconds=60):
    if _CLIP_BUFFER is None:
        return {"ok": False, "error": "The screen recorder isn't running, so there's "
                                      "nothing to clip."}
    ctx.activity("saving the clip")
    result = _CLIP_BUFFER.save(max(5, min(60, int(seconds))))
    if result.get("ok"):
        ctx.show(overlay_content.clean_visual({"cards": [
            {"label": "Clip", "value": f"{result['seconds']:.0f}s saved"},
            {"label": "Size", "value": f"{result['megabytes']:.0f} MB"}]}))
    return result


def _in_ultra_mode(ctx, said, shown):
    """In ultra mode, hiding or showing is done to its displays - all but
    Lyla, who is the normal display's alone. None when it is not for them."""
    if not displays.ultra():
        return None
    display = displays.resolve(said)
    if display is None:
        return None
    if ctx.display({"action": "show" if shown else "hide", "id": display}) is False:
        return {"ok": False, "error": "The display isn't up to do that right now."}
    return {"ok": True, "display": display, "name": displays.name(display), "shown": shown}


@_tool("hide_panel", "clearing it off the display",
       "Take a panel off the full display - the stocks, the news feed, the "
       "clock, the status dots, the system gauges, Lyla's room, or Apollo's own "
       "ring. Hiding Lyla gives her room back to the stocks and the ring. In "
       "ultra mode it takes one of its displays off instead - projects, ideas, "
       "talks, OSIRIS and the rest. Use this when the user asks to hide, "
       "remove or close part of the display. Pass what they called it.",
       _obj({"panel": {"type": "string",
                       "description": "What the user called the panel"}},
            ("panel",)))
def _hide_panel(ctx, panel=""):
    ctx.activity("clearing it off the display")
    done = _in_ultra_mode(ctx, panel, False)
    if done is not None:
        return done
    result = panels.hide(panel)
    if result.get("ok"):
        ctx.panels(result["panels"])
    return result


@_tool("show_panel", "putting it back on the display",
       "Put a panel back on the full display after it was hidden - in ultra "
       "mode, one of its displays. Use this when the user asks to show, bring "
       "back or restore part of it.",
       _obj({"panel": {"type": "string",
                       "description": "What the user called the panel"}},
            ("panel",)))
def _show_panel(ctx, panel=""):
    ctx.activity("putting it back on the display")
    done = _in_ultra_mode(ctx, panel, True)
    if done is not None:
        return done
    result = panels.show(panel)
    if result.get("ok"):
        ctx.panels(result["panels"])
    return result


@_tool("ultra_mode", "getting the displays ready",
       "Switch Apollo's full display into ultra mode, the work mode: every "
       "display on the screen at once as tiles - the stocks, the feed, the "
       "OSIRIS map, projects, ideas, the system and today - which the user "
       "can move, resize, hide and expand. Use this when the user asks for "
       "ultra mode, work mode or the expanded display, or to get the screen "
       "ready for work - \"الوضع الموسع\", \"وضع الشغل\", \"جهز الشاشة "
       "للشغل\". on=false puts the normal display back. Confirm in a few words.",
       _obj({"on": {"type": "boolean",
                    "description": "True for ultra mode, false for the normal display"}},
            ("on",)))
def _ultra_mode(ctx, on=True):
    wanted = bool(on)
    ctx.activity("getting the displays ready" if wanted else "putting the display back")
    if ctx.display({"action": "ultra", "on": wanted}) is False:
        return {"ok": False, "error": "The display isn't up to go into ultra mode right now."}
    return {"ok": True, "ultra": wanted}


# What "put everything back" sounds like: every display back in the grid.
_EVERYTHING = {"", "all", "everything", "every display", "all displays", "all of them",
               "grid", "the grid", "كل", "الكل", "كلها", "كل الشاشات", "الشبكة"}


@_tool("focus_display", "putting it on your screen",
       "Put one display on the user's screen: the full display comes up in "
       "ultra mode with that display expanded large and every other display "
       "minimized beside it. Use this when the user asks to put, pull up, "
       "bring up, expand or focus something on their screen - \"حط المشاريع "
       "على الشاشة\", \"كبر الأخبار\", \"put OSIRIS on my screen\". Pass what "
       "they called it: the stocks, the news, OSIRIS or the map, projects, "
       "ideas, talks, the system, today, or Apollo. \"all\" puts every "
       "display back in the grid.",
       _obj({"display": _str("What the user called the display, or all")}, ("display",)))
def _focus_display(ctx, display=""):
    said = str(display or "").strip()
    everything = said.lower() in _EVERYTHING
    wanted = None if everything else displays.resolve(said)
    if not everything and wanted is None:
        return displays.unknown(said)
    ctx.activity("putting it on your screen")
    if ctx.display({"action": "focus", "id": wanted}) is False:
        return {"ok": False, "error": "The display isn't up to do that right now."}
    if wanted is None:
        return {"ok": True, "all": True}
    return {"ok": True, "display": wanted, "name": displays.name(wanted)}


@_tool("open_story", "opening it on the display",
       "Open one story from the news feed on the full display, by the number "
       "it has there (01, 02...), to show its picture and summary. Use this "
       "when the user asks to open, show or read story N, or the Nth "
       "headline. 0 closes the story that is open. Returns the story's title "
       "and summary - tell the user about it in a sentence or two.",
       _obj({"number": {"type": "integer",
                        "description": "The story's number on the display; 0 closes it"}},
            ("number",)))
def _open_story(ctx, number=0):
    ctx.activity("opening it on the display")
    try:
        number = int(number)
    except (TypeError, ValueError):
        return {"ok": False, "error": f"'{number}' is not a story number."}
    found = ctx.story(number)
    if not found:
        if number == 0:
            return {"ok": True, "closed": True}
        return {"ok": False, "error": f"There is no story {number} on the display."}
    if number == 0:
        return {"ok": True, "closed": True}
    return {"ok": True, "number": number, "title": found.get("title", ""),
            "source": found.get("source", ""), "summary": found.get("summary", "")}


_COMPANIES = {"type": "array", "items": {"type": "string"},
              "description": ("The companies, each by its English name or its "
                              "ticker (Palantir or PLTR, never بالانتير) - "
                              "translate a name the user said in Arabic")}


def _change_watchlist(ctx, companies, change, done):
    """One call for however many were named, each changed on its own."""
    changed, already, failed = [], [], []
    for company in companies[:watchlist.MAX]:
        result = change(str(company))
        if result.get("already"):
            already.append(result["symbol"])
        elif result.get("ok"):
            changed.append(result["symbol"])
        else:
            failed.append({"company": company, "error": result.get("error", "")})
    if changed:
        # Asked for, not waited on: the stock's card follows a moment later.
        ctx.refresh("market")
    result = {"ok": bool(changed or already), done: changed,
              "watchlist": watchlist.current()}
    if already:
        result["already"] = already
    if failed:
        result["failed"] = failed
    return result


@_tool("watch_stock", "adding it to your watchlist",
       "Add companies to the watchlist on the display. Use this when the user "
       "asks to follow, watch, track or add a stock - all of the ones they "
       "named, in one call.",
       _obj({"companies": _COMPANIES}, ("companies",)))
def _watch_stock(ctx, companies=()):
    ctx.activity("adding it to your watchlist")
    return _change_watchlist(ctx, companies, watchlist.add, "added")


@_tool("unwatch_stock", "taking it off your watchlist",
       "Remove companies from the watchlist on the display. Use this when the "
       "user asks to stop following, unfollow, drop or remove a stock - all "
       "of the ones they named, in one call.",
       _obj({"companies": _COMPANIES}, ("companies",)))
def _unwatch_stock(ctx, companies=()):
    ctx.activity("taking it off your watchlist")
    return _change_watchlist(ctx, companies, watchlist.remove, "removed")


@_tool("open_stock", "opening it on the display",
       "Open one stock from the watchlist on the full display, out of its "
       "card: its chart, price, move, target and P/E. Use this when the user "
       "asks to open, show or look at one of their stocks on the display. An "
       "empty company closes the stock that is open.",
       _obj({"company": _str("The company by its English name or its ticker "
                             "(Nvidia or NVDA), empty to close")},
            ("company",)))
def _open_stock(ctx, company=""):
    ctx.activity("opening it on the display")
    company = str(company or "").strip()
    if not company:
        ctx.stock("")
        return {"ok": True, "closed": True}
    try:
        symbol = market.resolve(company)
    except Exception:  # noqa: BLE001
        return {"ok": False, "error": f"I couldn't find a stock called {company}. "
                                      "Try its English name or its ticker."}
    shown = ctx.stock(symbol)
    if not shown:
        return {"ok": False, "error": f"{symbol} isn't on the watchlist. Add it "
                                      "with watch_stock first if the user wants it."}
    return {"ok": True, **{key: shown.get(key) for key in (
        "symbol", "name", "price", "change_pct", "target", "upside", "pe")
        if shown.get(key) is not None}}


@_tool("save_idea", "keeping that idea",
       "Keep an idea for a new project, or a thing to remember to build, on "
       "the Ideas list. Use this when the user says they have an idea, says "
       "\"فكرة\", \"سجل فكرة\" or \"idea:\", or asks you to remember "
       "something they want to make. Save it in their own words, then confirm "
       "in a few words.",
       _obj({"text": _str("The idea, in the user's words")}, ("text",)))
def _save_idea(ctx, text=""):
    if not str(text).strip():
        return {"ok": False, "error": "There was no idea in that."}
    idea = ideas.add(text)
    ctx.refresh("ideas")
    return {"ok": True, "saved": idea["text"], "count": len(ideas.all())}


@_tool("list_ideas", "reading your ideas",
       "The user's saved project ideas, newest first and numbered. Use this "
       "when they ask what ideas they have, or what they wanted to build.",
       _obj({}))
def _list_ideas(ctx):
    kept = ideas.all()
    return {"ok": True, "ideas": [{"number": n, "text": i["text"], "age": i["age"]}
                                  for n, i in enumerate(kept, 1)]}


@_tool("drop_idea", "crossing it off",
       "Take one idea off the list, by its number from list_ideas - when the "
       "user says it is done, dropped or not wanted any more.",
       _obj({"number": {"type": "integer", "description": "The idea's number"}}, ("number",)))
def _drop_idea(ctx, number=0):
    kept = ideas.all()
    if not 1 <= int(number) <= len(kept):
        return {"ok": False, "error": f"There is no idea number {number}."}
    ideas.remove(kept[int(number) - 1]["id"])
    ctx.refresh("ideas")
    return {"ok": True, "dropped": kept[int(number) - 1]["text"]}


@_tool("panel_tab", "switching the panel",
       "Show one tab of the full display's side panel: stocks, talks (recent "
       "conversations with Apollo), projects (Claude Code sessions, project "
       "folders, GitHub repos) or ideas (saved ideas and reminders). Brings "
       "the display up if it is not.",
       _obj({"tab": _enum(("stocks", "talks", "projects", "ideas"), "Which tab")}, ("tab",)))
def _panel_tab(ctx, tab="stocks"):
    ctx.tab(tab)
    return {"ok": True, "tab": tab}


@_tool("going_out", "seeing you off",
       "The user is leaving the house: the PC stays up with the Claude app "
       "open so they can reach it from their phone, until they are back at "
       "it. Use this when they say they are going out or leaving - \"أنا "
       "طالع\", \"رايح برا\", \"I'm heading out\". Wish them well in a few "
       "words.",
       _obj({}))
def _going_out(ctx):
    if ctx.away() is False:
        return {"ok": False, "error": "Away mode isn't available right now."}
    return {"ok": True, "away": True}


@_tool("osiris", "opening OSIRIS",
       "Open or close OSIRIS inside Apollo - the open-source intelligence map "
       "at osirisai.live: live flights and ships, naval and air traffic, CCTV "
       "cameras, live news, earthquakes, incidents around the world, undersea "
       "cables, day and night. Opening it brings up Apollo's display with the "
       "map laid into it and Apollo dressed in OSIRIS's gold and cyan; closing "
       "it puts Apollo back. Use this when the user asks for OSIRIS, the world "
       "map or the intelligence map - \"افتح اوزيرس\", \"سكر اوزيرس\". Say in "
       "a few words that it is up, or closed.",
       _obj({"open": {"type": "boolean",
                      "description": "True to open OSIRIS, false to close it"}}, ("open",)))
def _osiris(ctx, open=True):  # noqa: A002 - the model's word for it
    wanted = bool(open)
    ctx.activity("opening OSIRIS" if wanted else "closing OSIRIS")
    if ctx.osiris(wanted) is False:
        return {"ok": False, "error": "The display isn't up to hold OSIRIS right now."}
    return {"ok": True, "open": wanted}


@_tool("idle_mode", "going idle",
       "Put Apollo into idle mode now: the screen becomes the idle screen - the "
       "name, the time and a fact - until the user touches a key or the mouse "
       "or speaks. Use this when they ask for idle mode, to sleep, to rest or "
       "to go quiet, or say \"ادخل وضع الخمول\" or \"نام\". Confirm in two "
       "or three words.",
       _obj({}))
def _idle_mode(ctx):
    if ctx.idle() is False:
        return {"ok": False, "error": "Idle mode isn't available right now."}
    return {"ok": True, "idle": True}


@_tool("insider_trades", "checking the insiders",
       "What a company's directors and officers have bought and sold of its "
       "stock on the open market over the last 90 days, from their SEC Form 4 "
       "filings: totals, and the latest few with who, when and how much. US "
       "stocks only. Use this when the user asks about insider buying or "
       "selling, or whether the people running a company are buying.",
       _obj({"company": _str("The company by its English name or its ticker")}, ("company",)))
def _insider_trades(ctx, company=""):
    import datetime as _dt

    symbol = market.resolve(company)
    ctx.activity(f"checking {symbol}'s insiders")
    key = insiders.api_key()
    if not key:
        return {"ok": False, "error": "Insider trades need the Finnhub key, and there isn't one."}
    today = insiders._today()
    rows = insiders.fetch(symbol, key, today - _dt.timedelta(days=insiders.DAYS))
    s = insiders.summary(symbol, rows, today=today)
    return {"ok": True, "symbol": symbol, "days": s["days"], "bought": s["buys"],
            "sold": s["sells"], "latest": s["latest"][:3]}


@_tool("next_earnings", "checking the earnings date",
       "When a company next reports its earnings: the date, the weekday, how "
       "many days away, and whether the date is still an estimate. Use this "
       "when the user asks when a stock reports, or about its earnings date "
       "or results day.",
       _obj({"company": _str("The company by its English name or its ticker")},
            ("company",)))
def _next_earnings(ctx, company=""):
    import datetime as _dt

    symbol = market.resolve(company)
    ctx.activity(f"checking {symbol}'s earnings")
    found = market.fundamentals(symbol, timeout=market.TURN_TIMEOUT)
    if not found.get("earnings"):
        return {"ok": False, "error": f"No earnings date is out for {symbol} yet."}
    day = _dt.date.fromisoformat(found["earnings"])
    return {"ok": True, "symbol": symbol, "date": day.isoformat(),
            "weekday": day.strftime("%A"), "days_away": (day - _dt.date.today()).days,
            "estimate": bool(found.get("earnings_estimate"))}


@_tool("private_eye_finds", "checking Private Eye",
       "What Private Eye - Apollo's scout, which searches the web every few "
       "hours for what the user cares about - has found lately, best first and "
       "numbered. Use this when the user asks what Private Eye found, or what "
       "is new about the things they follow. Tell them the best one or two in "
       "a sentence each.",
       _obj({}))
def _private_eye_finds(ctx):
    ctx.activity("checking Private Eye")
    finds = private_eye.load()
    if not finds:
        return {"ok": True, "finds": [], "note": "Private Eye has not found anything new yet."}
    return {"ok": True, "finds": [
        {"number": n, "title": f.get("title", ""), "source": f.get("source", ""),
         "about": f.get("interest", ""), "age": f.get("age", ""),
         "summary": (f.get("summary") or "")[:240]}
        for n, f in enumerate(finds, 1)]}


@_tool("rate_find", "noting that",
       "Tell Private Eye whether one of its finds, by its number, was useful, so "
       "it learns what the user wants. Use this when the user says a find is "
       "useful, interesting or \"مهم\" (useful=true), or not useful, not for "
       "them or \"مو مهم\" (useful=false).",
       _obj({"number": {"type": "integer", "description": "The find's number"},
             "useful": {"type": "boolean", "description": "Whether it was useful"}},
            ("number", "useful")))
def _rate_find(ctx, number=0, useful=True):
    finds = private_eye.load()
    if not 1 <= int(number) <= len(finds):
        return {"ok": False, "error": f"There is no find number {number}."}
    find = private_eye.rate(finds[int(number) - 1]["id"], bool(useful))
    if find is None:
        return {"ok": False, "error": "That find is gone already."}
    ctx.refresh("finds")
    return {"ok": True, "about": find.get("interest", ""), "useful": bool(useful)}


@_tool("refresh_display", "refreshing the display",
       "Fetch everything on the display again right now - prices, news, "
       "weather. Use this when the user asks to refresh, update or reload.",
       _obj({}))
def _refresh_display(ctx):
    ctx.activity("refreshing the display")
    if not ctx.refresh():
        return {"ok": False, "error": "The display isn't running right now."}
    # Under way rather than done: the service reads it on its own thread.
    return {"ok": True, "refreshing": True}


@_tool("prayer_times", "checking the prayer times",
       "Today's prayer times for Riyadh, and which one is next. Use this "
       "whenever the user asks about a prayer, about Athan, or how long "
       "until one.",
       _obj({}))
def _prayer_times(ctx):
    ctx.activity("checking the prayer times")
    today = prayer.times()
    if not today:
        return {"ok": False, "error": "I couldn't reach the prayer times just now."}
    name, when = prayer.next_prayer()
    minutes = None
    if when is not None:
        minutes = int(round((when - __import__("datetime").datetime.now())
                            .total_seconds() / 60.0))
    ctx.show(overlay_content.clean_visual({"cards": [
        {"label": key, "value": value.strftime("%H:%M")}
        for key, value in sorted(today.items(), key=lambda kv: kv[1])]}))
    return {"ok": True,
            "times": {k: v.strftime("%H:%M") for k, v in today.items()},
            "next": name, "next_at": when.strftime("%H:%M") if when else None,
            "minutes_away": minutes, "city": prayer.CITY,
            "method": "Umm al-Qura"}


@_tool("open_clips", "opening your clips",
       "Open the folder where saved screen clips are kept, in File Explorer. "
       "Use this when the user asks to see, open or find their clips.",
       _obj({}))
def _open_clips(ctx):
    folder = clips.folder()
    # Made on demand when a clip is saved, so on a machine that has never
    # saved one there would be nothing to open and nothing to say about it.
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError as e:
        return {"ok": False, "error": f"Couldn't reach the clips folder: {e}"}
    ctx.activity("opening your clips")
    return pc_control.open_path(folder, want_folder=True)


@_tool("get_news", "reading the news",
       "Headlines on a topic the user follows (gaming, marvel, movies, markets) or any "
       "phrase. Speak only what this returns.",
       _obj({"topic": _str("Topic or search phrase"),
             "limit": {"type": "integer", "description": "How many, 1-8 (default 4)"}},
            ["topic"]))
def _get_news(ctx, topic, limit=4):
    ctx.activity(f"reading {topic} news")
    items = feeds.headlines(topic, limit=max(1, min(8, int(limit))))
    if not items:
        return {"ok": False, "error": f"No headlines came back for {topic}."}
    return {"ok": True, "topic": topic,
            "headlines": [{k: item[k] for k in ("title", "source", "age")} for item in items]}


@_tool("get_posts", "checking posts",
       "Donald Trump's recent Truth Social posts, market-moving ones first. Use when the "
       "user asks what he posted or said.",
       _obj({"hours": {"type": "integer", "description": "How far back, 1-72 (default 24)"}}))
def _get_posts(ctx, hours=24):
    ctx.activity("checking posts")
    items = feeds.posts(hours=max(1, min(72, int(hours))), limit=5)
    if not items:
        return {"ok": False, "error": "Nothing has been posted in that window."}
    return {"ok": True, "posts": [{"text": p["text"][:400], "age": p["age"],
                                   "market_moving": p["market"]} for p in items]}


@_tool("daily_briefing", "putting the briefing together",
       "The user's daily recap: date, Riyadh weather, their watchlist, headlines on what "
       "they follow, recent posts, reminders. Use for 'brief me', 'what did I miss', "
       "'catch me up'.",
       _obj({}))
def _daily_briefing(ctx):
    ctx.activity("putting the briefing together")
    payload = briefing.compose()
    ctx.show(overlay_content.clean_visual({"cards": _briefing_cards(payload)}))
    return {"ok": True, "brief": briefing.spoken(payload)}


def _briefing_cards(payload):
    cards = []
    sky = payload.get("weather") or {}
    if sky:
        cards.append({"label": "Riyadh", "value": f"{sky.get('temp')}C {sky.get('text', '')}"[:14]})
    for quote in (payload.get("market") or {}).get("indices", [])[:2]:
        cards.append({"label": quote["symbol"].lstrip("^"),
                      "value": f"{quote['change_pct']:+.1f}%"})
    posts = payload.get("posts") or []
    if posts:
        cards.append({"label": "Posts", "value": f"{len(posts)} new"})
    return cards
