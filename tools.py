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
    says in a few words what Apollo is doing ("fetching NVDA"), `refresh()`
    asks the data service to read the world again and push it to the display,
    and `turn` is the user's turn number at the moment the call arrived.
    """

    def __init__(self, show=None, activity=None, turn=None, refresh=None):
        self.show = show or (lambda visual: None)
        self.activity = activity or (lambda text: None)
        # False by default, so a tool that changes the display can tell the
        # difference between "refreshed" and "there was nothing to refresh".
        self.refresh = refresh or (lambda: False)
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
import clips  # noqa: E402
import feeds  # noqa: E402
import market  # noqa: E402
import overlay_content  # noqa: E402
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
        quotes.append(market.quote(symbol))
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


@_tool("watch_stock", "adding it to your watchlist",
       "Add a company to the watchlist on the display. Use this when the user "
       "asks to follow, watch, track or add a stock. Give the company name or "
       "ticker as the user said it.",
       _obj({"company": {"type": "string",
                         "description": "The company name or ticker"}},
            ("company",)))
def _watch_stock(ctx, company=""):
    ctx.activity("adding it to your watchlist")
    result = watchlist.add(company)
    if result.get("ok"):
        ctx.refresh()
    return result


@_tool("unwatch_stock", "taking it off your watchlist",
       "Remove a company from the watchlist on the display. Use this when the "
       "user asks to stop following, unfollow, drop or remove a stock.",
       _obj({"company": {"type": "string",
                         "description": "The company name or ticker"}},
            ("company",)))
def _unwatch_stock(ctx, company=""):
    ctx.activity("taking it off your watchlist")
    result = watchlist.remove(company)
    if result.get("ok"):
        ctx.refresh()
    return result


@_tool("refresh_display", "refreshing the display",
       "Fetch everything on the display again right now - prices, news, "
       "weather. Use this when the user asks to refresh, update or reload.",
       _obj({}))
def _refresh_display(ctx):
    ctx.activity("refreshing the display")
    if not ctx.refresh():
        return {"ok": False, "error": "The display isn't running right now."}
    return {"ok": True, "refreshed": True}


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
