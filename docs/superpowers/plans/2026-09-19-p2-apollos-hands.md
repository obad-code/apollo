# P2 Apollo's Hands Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every ordinary voice request can *act*: Gemini Live gets Apollo's tools (PC control, markets, reminders) plus Google Search, hears you in Arabic or English through its own live transcript, and answers in the same voice.

**Architecture:** One registry (`tools.py`) declares every tool once for both Gemini and Claude and is the only place tool errors are caught. `pc_control.py` grows the Windows actions, `market.py` wraps Yahoo's chart feed, `turnview.py` composes what the overlay shows for a turn. `gemini_live.py` receives tool calls and runs them on a thread pool, gated so a turn that belongs to an agent never acts twice.

**Tech Stack:** Python 3.14, google-genai 2.24 (Live API), pycaw, psutil, tzdata, ctypes/Win32, pytest.

**Spec:** `docs/superpowers/specs/2026-09-19-apollo-jarvis-design.md` (§3, §4 P2)

## Probe results this plan rests on (2026-09-19)

| Finding | Evidence |
|---|---|
| `gemini-3.8-live` refused: "exceeded your current quota" | `probes/probe_live_models.py` |
| `gemini-2.5-flash-native-audio-latest` passes tools, Google Search (grounded), manual activity, both transcriptions; first audio 1.4–2.0 s | same |
| The latest model renamed a tool argument (`application_name` for `name`) | same |
| Input transcription streams while the chord is held, every 150–350 ms; last word ~0.2 s after release | `probes/probe_transcript_timing.py` |
| Yahoo chart + search answer in ~0.3 s; Stooq CSV endpoint is 404 | inline check |

## Global Constraints

- Model order: `gemini-2.5-flash-native-audio-latest`, then `gemini-2.5-flash-native-audio-preview-09-2025`; `APOLLO_GEMINI_MODEL` env var prepends one.
- `gemini_live.py` must not import `tools`, `pc_control` or `market` — it receives declarations and a callable.
- Tool handlers never raise past `tools.run`; every result is a JSON-serialisable dict with `ok`.
- Nothing in tests may press real keys, close real windows, change volume or power state: every side effect in `pc_control` goes through a module-level function (`_send`, `_post_close`, `_endpoint`, `_run`, `_try_start`, `_suspend`, `_lock`) that tests replace.
- Tests: `.venv/Scripts/python.exe -m pytest -q`; fixtures under `tests/fixtures/`.
- Commit after each task with the `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` trailer.

## Review Focus

1. A turn routed to an agent must not also run Gemini's tool call (double "open Chrome") — pinned in Task 6 (`test_tool_waits_for_gate_and_cancels_on_discard`).
2. The model approving its own power action in one breath — pinned in Task 1 (`test_confirm_needs_a_later_turn`, `test_confirm_expires`).
3. A single mis-named argument from the model still works; two unknowns do not guess — pinned in Task 1 (`test_one_misnamed_argument_is_mapped`, `test_two_unknowns_are_not_guessed`).
4. A market feed outage produces a spoken failure, not a crash or a made-up number — pinned in Task 3 (`test_both_hosts_down_raises_market_error`) and Task 4 (`test_market_error_becomes_failed_result`).
5. Closing "explorer" or the desktop must never post WM_CLOSE to the shell (which opens the shutdown dialog) — pinned in Task 2 (`test_shell_windows_are_never_closed`).

---

### Task 1: `tools.py` — the registry core

**Files:**
- Create: `tools.py` (core only; definitions arrive in Task 4)
- Test: `tests/test_tools.py`

**Interfaces:**
- Produces: `tools.Tool(name, description, parameters, handler, confirm=False)`; `tools.Context(show=None, activity=None, turn=None)` with `.show(visual)`, `.activity(text)`, `.turn`; `tools.register(tool)`; `tools.REGISTRY: dict`; `tools.new_user_turn() -> int`; `tools.current_turn() -> int`; `tools.coerce(tool, args) -> dict | str`; `tools.run(name, args, ctx=None) -> dict`; `tools.gemini_declarations() -> list[FunctionDeclaration]`; `tools.claude_tools() -> list[dict]`; `tools.CONFIRM` (`Confirmations.allow(name, args, turn) -> bool`, `.reset()`).
- Handler signature: `handler(ctx, **args) -> dict | str`.

- [ ] **Step 1: Failing tests** — `tests/test_tools.py`:

```python
# FILE: tests/test_tools.py
import pytest

import tools
from tools import Context, Tool


@pytest.fixture(autouse=True)
def clean_registry(monkeypatch):
    monkeypatch.setattr(tools, "REGISTRY", {})
    tools.CONFIRM.reset()
    yield


def obj(props, required=()):
    return {"type": "object", "properties": props, "required": list(required)}


def echo(ctx, **kw):
    return {"got": kw}


def test_unknown_tool_is_a_failed_result():
    assert tools.run("nope", {}) == {"ok": False, "error": "There is no tool called nope."}


def test_handler_gets_clean_args_and_ok_is_added():
    tools.register(Tool("t", "d", obj({"name": {"type": "string"}}, ["name"]), echo))
    assert tools.run("t", {"name": "Chrome"}) == {"ok": True, "got": {"name": "Chrome"}}


def test_one_misnamed_argument_is_mapped():
    tools.register(Tool("t", "d", obj({"name": {"type": "string"}}, ["name"]), echo))
    assert tools.run("t", {"application_name": "Notepad"})["got"] == {"name": "Notepad"}


def test_two_unknowns_are_not_guessed():
    tools.register(Tool("t", "d", obj({"name": {"type": "string"}}, ["name"]), echo))
    r = tools.run("t", {"a": "x", "b": "y"})
    assert r["ok"] is False and "name" in r["error"]


def test_types_and_enums_are_coerced():
    tools.register(Tool("t", "d", obj({
        "level": {"type": "integer"},
        "action": {"type": "string", "enum": ["snap_left", "set"]},
        "symbols": {"type": "array", "items": {"type": "string"}},
    }), echo))
    got = tools.run("t", {"level": "30.4", "action": "Snap Left", "symbols": "NVDA"})["got"]
    assert got == {"level": 30, "action": "snap_left", "symbols": ["NVDA"]}


def test_bad_enum_is_explained():
    tools.register(Tool("t", "d", obj({"action": {"type": "string", "enum": ["a", "b"]}}), echo))
    assert tools.run("t", {"action": "c"}) == {"ok": False, "error": "action must be one of: a, b."}


def test_handler_exception_becomes_failed_result():
    def boom(ctx):
        raise OSError("disk on fire")
    tools.register(Tool("t", "d", obj({}), boom))
    assert tools.run("t", {}) == {"ok": False, "error": "OSError: disk on fire"}


def test_string_results_are_wrapped():
    tools.register(Tool("ok", "d", obj({}), lambda ctx: "Launched Chrome."))
    tools.register(Tool("bad", "d", obj({}), lambda ctx: "Failed: nope."))
    assert tools.run("ok", {}) == {"ok": True, "result": "Launched Chrome."}
    assert tools.run("bad", {}) == {"ok": False, "result": "Failed: nope."}


def test_confirm_needs_a_later_turn():
    ran = []
    tools.register(Tool("power", "d", obj({"action": {"type": "string"}}, ["action"]),
                        lambda ctx, action: ran.append(action) or "done", confirm=True))
    first = tools.run("power", {"action": "shutdown", "confirmed": True}, Context(turn=5))
    assert first["ok"] is False and first["needs_confirmation"] is True
    again = tools.run("power", {"action": "shutdown", "confirmed": True}, Context(turn=5))
    assert again["needs_confirmation"] is True          # same turn: still no
    yes = tools.run("power", {"action": "shutdown", "confirmed": True}, Context(turn=6))
    assert yes == {"ok": True, "result": "done"} and ran == ["shutdown"]


def test_confirm_without_flag_never_runs():
    tools.register(Tool("power", "d", obj({"action": {"type": "string"}}, ["action"]),
                        lambda ctx, action: "done", confirm=True))
    tools.run("power", {"action": "restart"}, Context(turn=1))
    assert tools.run("power", {"action": "restart"}, Context(turn=2))["needs_confirmation"]


def test_confirm_expires():
    tools.register(Tool("power", "d", obj({"action": {"type": "string"}}, ["action"]),
                        lambda ctx, action: "done", confirm=True))
    tools.run("power", {"action": "sleep"}, Context(turn=1))
    late = tools.run("power", {"action": "sleep", "confirmed": True}, Context(turn=9))
    assert late["needs_confirmation"] is True


def test_declarations_add_confirmed_only_to_confirm_tools():
    tools.register(Tool("a", "d", obj({"x": {"type": "string"}}), echo))
    tools.register(Tool("b", "d", obj({"x": {"type": "string"}}), echo, confirm=True))
    decl = {d["name"]: d for d in tools.claude_tools()}
    assert "confirmed" not in decl["a"]["input_schema"]["properties"]
    assert decl["b"]["input_schema"]["properties"]["confirmed"]["type"] == "boolean"
    names = [d.name for d in tools.gemini_declarations()]
    assert names == ["a", "b"]


def test_user_turn_counter_increments():
    before = tools.current_turn()
    assert tools.new_user_turn() == before + 1
    assert Context().turn == before + 1
```

- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/test_tools.py -q` — Expected: collection error, `No module named 'tools'`.

- [ ] **Step 3: Implement** `tools.py`:

```python
# FILE: tools.py
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
    says in a few words what Apollo is doing ("fetching NVDA"), and `turn` is
    the user's turn number at the moment the call arrived.
    """

    def __init__(self, show=None, activity=None, turn=None):
        self.show = show or (lambda visual: None)
        self.activity = activity or (lambda text: None)
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
            if kind == "string" and not isinstance(value, str):
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
        log.exception("tool %s failed", name)
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
```

- [ ] **Step 4: Run** `.venv/Scripts/python.exe -m pytest tests/test_tools.py -q` — Expected: 14 passed.
- [ ] **Step 5: Commit** `git add tools.py tests/test_tools.py && git commit -m "Add the tool registry shared by Gemini and Claude"`

---

### Task 2: `pc_control.py` — the new Windows actions

**Files:**
- Modify: `pc_control.py` (append; existing functions unchanged except `open_app`, which switches to an already-open window first)
- Test: `tests/test_pc_control.py`

**Interfaces:**
- Produces: `resolve_url(site) -> str`; `open_url(site) -> str`; `parse_chord(keys) -> list[int]`; `press_keys(keys) -> str`; `type_text(text) -> str`; `media(action) -> str` (`play_pause|next|previous|stop`); `volume(action, level=None) -> dict` (`get|set|up|down|mute|unmute`); `top_windows() -> list[(hwnd, pid, title, cls)]`; `find_windows(app) -> list`; `close_app(name) -> str`; `window(action, app=None) -> str` (`minimize|maximize|restore|close|focus|snap_left|snap_right|show_desktop`); `lock_pc() -> str`; `system_power(action) -> str` (`sleep|restart|shutdown|sign_out`).
- Side-effect seams (tests replace): `_send(events)`, `_post_close(hwnd)`, `_show(hwnd, cmd)`, `_focus(hwnd)`, `_foreground()`, `_endpoint()`, `_run(argv)`, `_suspend()`, `_lock()`, `_process_names()`, `top_windows()`, `_try_start(target)`.

- [ ] **Step 1: Failing tests** — `tests/test_pc_control.py`:

```python
# FILE: tests/test_pc_control.py
import pytest

import pc_control as pc


@pytest.fixture
def sent(monkeypatch):
    log = []
    monkeypatch.setattr(pc, "_send", lambda events: log.extend(
        (e.u.ki.wVk, e.u.ki.wScan, e.u.ki.dwFlags) for e in events) or len(events))
    return log


def test_resolve_url():
    assert pc.resolve_url("YouTube") == "https://www.youtube.com"
    assert pc.resolve_url("the github website") == "https://github.com"
    assert pc.resolve_url("example.org/docs") == "https://example.org/docs"
    assert pc.resolve_url("https://x.com/home") == "https://x.com/home"
    assert pc.resolve_url("best pizza near me") == "https://www.google.com/search?q=best+pizza+near+me"
    assert pc.resolve_url("file:///C:/Windows/system32/cmd.exe").startswith("https://www.google.com/search?q=")


def test_open_url_starts_resolved_url(monkeypatch):
    started = []
    monkeypatch.setattr(pc, "_try_start", lambda t: started.append(t) or True)
    assert pc.open_url("reddit") == "Opened https://www.reddit.com."
    assert started == ["https://www.reddit.com"]


def test_parse_chord():
    assert pc.parse_chord("ctrl+shift+t") == [0x11, 0x10, ord("T")]
    assert pc.parse_chord("Alt + F4") == [0x12, 0x73]
    assert pc.parse_chord("win+left") == [0x5B, 0x25]
    assert pc.parse_chord("page down") == [0x22]
    with pytest.raises(ValueError):
        pc.parse_chord("ctrl+banana")


def test_press_keys_downs_then_ups_in_reverse(sent):
    assert pc.press_keys("ctrl+c") == "Pressed ctrl+c."
    assert [(vk, flags & pc.KEYEVENTF_KEYUP) for vk, _, flags in sent] == [
        (0x11, 0), (ord("C"), 0), (ord("C"), 2), (0x11, 2)]


def test_ctrl_alt_delete_is_refused(sent):
    assert pc.press_keys("ctrl+alt+delete").startswith("Failed")
    assert sent == []


def test_type_text_sends_unicode_including_arabic(sent):
    assert pc.type_text("Hi مرحبا\n") == "Typed 9 characters."
    scans = [scan for vk, scan, flags in sent if flags & pc.KEYEVENTF_UNICODE and not flags & pc.KEYEVENTF_KEYUP]
    assert "".join(map(chr, scans)) == "Hi مرحبا"
    assert (0x0D, 0, 0) in sent


def test_media_presses_the_media_key(sent):
    assert pc.media("next") == "Skipped to the next track."
    assert sent[0][0] == 0xB0


class FakeEndpoint:
    def __init__(self, level=0.5, muted=0):
        self.level, self.muted = level, muted

    def GetMasterVolumeLevelScalar(self):
        return self.level

    def SetMasterVolumeLevelScalar(self, v, ctx):
        self.level = v

    def GetMute(self):
        return self.muted

    def SetMute(self, m, ctx):
        self.muted = m


def test_volume(monkeypatch):
    ep = FakeEndpoint(0.5, 1)
    monkeypatch.setattr(pc, "_endpoint", lambda: ep)
    assert pc.volume("get") == {"ok": True, "level": 50, "muted": True}
    assert pc.volume("up")["level"] == 60 and ep.muted == 0
    assert pc.volume("set", 150)["level"] == 100
    assert pc.volume("down", 30)["level"] == 70
    assert pc.volume("mute")["muted"] is True
    assert pc.volume("set")["ok"] is False


WINDOWS = [(101, 7, "Untitled - Notepad", "Notepad"),
           (102, 8, "YouTube - Google Chrome", "Chrome_WidgetWin_1"),
           (103, 9, "Calculator", "ApplicationFrameWindow")]


@pytest.fixture
def desktop(monkeypatch):
    closed, shown, focused = [], [], []
    monkeypatch.setattr(pc, "top_windows", lambda: list(WINDOWS))
    monkeypatch.setattr(pc, "_process_names", lambda: {7: "notepad.exe", 8: "chrome.exe", 9: "applicationframehost.exe"})
    monkeypatch.setattr(pc, "_post_close", closed.append)
    monkeypatch.setattr(pc, "_show", lambda h, cmd: shown.append((h, cmd)))
    monkeypatch.setattr(pc, "_focus", focused.append)
    monkeypatch.setattr(pc, "_foreground", lambda: 102)
    return closed, shown, focused


def test_close_app_by_process_and_by_title(desktop):
    closed, _, _ = desktop
    assert pc.close_app("Notepad") == "Closing Notepad."
    assert pc.close_app("calculator") == "Closing calculator."
    assert closed == [101, 103]
    assert pc.close_app("spotify").startswith("Failed")


def test_shell_windows_are_never_closed(monkeypatch):
    monkeypatch.setattr(pc, "_process_names", lambda: {1: "explorer.exe"})
    monkeypatch.setattr(pc, "_user_windows", lambda: [
        (11, 1, "Program Manager", "Progman"), (12, 1, "", "Shell_TrayWnd"),
        (13, 1, "Downloads", "CabinetWClass")])
    closed = []
    monkeypatch.setattr(pc, "_post_close", closed.append)
    pc.close_app("file explorer")
    assert closed == [13]


def test_window_actions(desktop, sent):
    closed, shown, focused = desktop
    assert pc.window("minimize") == "Minimized the window."
    assert shown[-1] == (102, 6)
    pc.window("maximize", "notepad")
    assert shown[-1] == (101, 3)
    pc.window("snap_left", "chrome")
    assert focused[-1] == 102 and sent[0][0] == 0x5B
    assert pc.window("focus", "nothing open").startswith("Failed")


def test_open_app_switches_to_running_window(desktop, monkeypatch):
    _, _, focused = desktop
    started = []
    monkeypatch.setattr(pc, "_try_start", lambda t: started.append(t) or True)
    assert pc.open_app("notepad") == "Switched to notepad."
    assert focused == [101] and started == []


def test_power(monkeypatch):
    ran, other = [], []
    monkeypatch.setattr(pc, "_run", ran.append)
    monkeypatch.setattr(pc, "_suspend", lambda: other.append("sleep"))
    monkeypatch.setattr(pc, "_lock", lambda: other.append("lock"))
    assert pc.system_power("shutdown") == "Shutting down in 10 seconds. Say cancel shutdown to stop it."
    assert ran == [["shutdown", "/s", "/t", "10"]]
    pc.system_power("sleep")
    pc.lock_pc()
    assert other == ["sleep", "lock"]
```

- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/test_pc_control.py -q` — Expected: FAIL (`AttributeError: module 'pc_control' has no attribute ...`).

- [ ] **Step 3: Implement.** Replace `open_app` and append the new section to `pc_control.py`:

```python
# (pc_control.py) replace open_app with:
def open_app(target):
    """Switch to an app that is already open, or launch it.

    An app with a window already on screen is brought forward instead of
    started again - "open Spotify" means "show me Spotify", not "start a
    second one". Otherwise: known name, PATH lookup, then Start Menu search.
    """
    running = find_windows(target)
    if running:
        _focus(running[0][0])
        return f"Switched to {target}."

    key = target.strip().lower()
    tried = []
    if key in KNOWN_APPS:
        tried.append(KNOWN_APPS[key])
    tried.append(target)

    for candidate in tried:
        if _try_start(candidate):
            return f"Launched {target}."

    exe = shutil.which(target) or shutil.which(target + ".exe")
    if exe and _try_start(exe):
        return f"Launched {target}."

    shortcut = _find_start_menu_shortcut(target)
    if shortcut and _try_start(shortcut):
        return f"Launched {target}."

    return f"Failed: could not find an app called '{target}'."
```

```python
# (pc_control.py) appended:
# --- websites ---------------------------------------------------------------

KNOWN_SITES = {
    "youtube": "https://www.youtube.com", "gmail": "https://mail.google.com",
    "google": "https://www.google.com", "github": "https://github.com",
    "tradingview": "https://www.tradingview.com", "netflix": "https://www.netflix.com",
    "x": "https://x.com", "twitter": "https://x.com", "reddit": "https://www.reddit.com",
    "chatgpt": "https://chatgpt.com", "claude": "https://claude.ai",
    "instagram": "https://www.instagram.com", "whatsapp": "https://web.whatsapp.com",
    "spotify web": "https://open.spotify.com", "amazon": "https://www.amazon.com",
    "twitch": "https://www.twitch.tv", "discord web": "https://discord.com/app",
    "truth social": "https://truthsocial.com", "yahoo finance": "https://finance.yahoo.com",
    "playstation store": "https://store.playstation.com", "rockstar": "https://www.rockstargames.com",
}


def resolve_url(site):
    """A site name, domain or URL -> an https URL. Never anything but http(s)."""
    raw = (site or "").strip()
    key = raw.lower()
    for prefix in ("the ", "open "):
        key = key.removeprefix(prefix)
    for suffix in (" website", " site", " dot com", " homepage"):
        key = key.removesuffix(suffix)
    key = key.strip()
    if key in KNOWN_SITES:
        return KNOWN_SITES[key]
    if re.match(r"^https?://\S+$", raw, re.I):
        return raw
    if re.fullmatch(r"[\w-]+(\.[\w-]+)+(/\S*)?", key):
        return "https://" + key
    return "https://www.google.com/search?q=" + urllib.parse.quote_plus(raw)


def open_url(site):
    url = resolve_url(site)
    if not _try_start(url):
        return f"Failed: could not open {url}."
    return f"Opened {url}."


# --- the keyboard -----------------------------------------------------------
#
# Everything goes through SendInput, which injects into whatever window has
# focus - and that is always yours, because Apollo never takes focus.

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
MAX_TYPE = 2000

MODIFIERS = {"ctrl": 0x11, "control": 0x11, "shift": 0x10, "alt": 0x12,
             "win": 0x5B, "windows": 0x5B, "super": 0x5B}
NAMED_KEYS = {
    "enter": 0x0D, "return": 0x0D, "esc": 0x1B, "escape": 0x1B, "tab": 0x09,
    "space": 0x20, "backspace": 0x08, "delete": 0x2E, "del": 0x2E, "insert": 0x2D,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "page up": 0x21, "pagedown": 0x22,
    "page down": 0x22, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "printscreen": 0x2C, "print screen": 0x2C, "capslock": 0x14, "caps lock": 0x14,
    "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD, ";": 0xBA, "'": 0xDE,
    ",": 0xBC, ".": 0xBE, "/": 0xBF, "\\": 0xDC,
}
EXTENDED = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x5B}


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


def _key(vk=0, scan=0, flags=0):
    event = INPUT()
    event.type = INPUT_KEYBOARD
    if vk in EXTENDED:
        flags |= KEYEVENTF_EXTENDEDKEY
    event.u.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
    return event


def _send(events):
    """The one place that touches the real keyboard."""
    array = (INPUT * len(events))(*events)
    return ctypes.windll.user32.SendInput(len(events), array, ctypes.sizeof(INPUT))


def parse_chord(keys):
    """"ctrl+shift+t" -> [VK_CONTROL, VK_SHIFT, 'T']. ValueError on a key it doesn't know."""
    parts = [p.strip().lower() for p in re.split(r"\s*\+\s*", (keys or "").strip()) if p.strip()]
    if not parts:
        raise ValueError("No keys were given.")
    vks = []
    for part in parts:
        if part in MODIFIERS:
            vks.append(MODIFIERS[part])
        elif part in NAMED_KEYS:
            vks.append(NAMED_KEYS[part])
        elif re.fullmatch(r"f([1-9]|1\d|2[0-4])", part):
            vks.append(0x6F + int(part[1:]))
        elif len(part) == 1 and part.isascii() and part.isalnum():
            vks.append(ord(part.upper()))
        else:
            raise ValueError(f"I don't know the key '{part}'.")
    return vks


def _chord_events(vks):
    return [_key(vk) for vk in vks] + [_key(vk, flags=KEYEVENTF_KEYUP) for vk in reversed(vks)]


def press_keys(keys):
    try:
        vks = parse_chord(keys)
    except ValueError as e:
        return f"Failed: {e}"
    if {0x11, 0x12, 0x2E} <= set(vks):
        return "Failed: Windows doesn't let any program press Ctrl+Alt+Delete."
    _send(_chord_events(vks))
    return f"Pressed {keys}."


def _utf16_units(ch):
    raw = ch.encode("utf-16-le")
    return [int.from_bytes(raw[i:i + 2], "little") for i in range(0, len(raw), 2)]


def type_text(text):
    """Type into the focused window. Unicode, so Arabic types as Arabic."""
    text = (text or "")[:MAX_TYPE]
    events = []
    for ch in text:
        if ch == "\n":
            events += [_key(0x0D), _key(0x0D, flags=KEYEVENTF_KEYUP)]
            continue
        for unit in _utf16_units(ch):
            events += [_key(0, unit, KEYEVENTF_UNICODE),
                       _key(0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)]
    if events:
        _send(events)
    return f"Typed {len(text)} characters."


MEDIA = {"play_pause": (0xB3, "Toggled play and pause."),
         "next": (0xB0, "Skipped to the next track."),
         "previous": (0xB1, "Went back a track."),
         "stop": (0xB2, "Stopped playback.")}


def media(action):
    vk, said = MEDIA[action]
    _send(_chord_events([vk]))
    return said


# --- volume -----------------------------------------------------------------

def _endpoint():
    try:
        import comtypes
        comtypes.CoInitialize()
    except Exception:
        pass
    from pycaw.pycaw import AudioUtilities
    return AudioUtilities.GetSpeakers().EndpointVolume


def volume(action, level=None):
    ep = _endpoint()
    now = int(round(ep.GetMasterVolumeLevelScalar() * 100))
    if action == "get":
        return {"ok": True, "level": now, "muted": bool(ep.GetMute())}
    if action in ("mute", "unmute"):
        ep.SetMute(1 if action == "mute" else 0, None)
        return {"ok": True, "level": now, "muted": action == "mute"}
    if action == "set":
        if level is None:
            return {"ok": False, "error": "Say what level to set the volume to."}
        target = level
    else:
        step = level if level else 10
        target = now + step if action == "up" else now - step
    target = max(0, min(100, int(target)))
    ep.SetMasterVolumeLevelScalar(target / 100.0, None)
    if target > 0:
        ep.SetMute(0, None)
    return {"ok": True, "level": target, "muted": False}


# --- windows ----------------------------------------------------------------

SHELL_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}
PROCESS_NAMES = {
    "chrome": "chrome.exe", "google chrome": "chrome.exe", "edge": "msedge.exe",
    "microsoft edge": "msedge.exe", "firefox": "firefox.exe", "spotify": "spotify.exe",
    "notepad": "notepad.exe", "discord": "discord.exe", "steam": "steam.exe",
    "word": "winword.exe", "excel": "excel.exe", "powerpoint": "powerpnt.exe",
    "vs code": "code.exe", "vscode": "code.exe", "visual studio code": "code.exe",
    "file explorer": "explorer.exe", "explorer": "explorer.exe", "task manager": "taskmgr.exe",
    "paint": "mspaint.exe", "obs": "obs64.exe", "telegram": "telegram.exe",
    "whatsapp": "whatsapp.exe", "epic games": "epicgameslauncher.exe",
}
_user32 = ctypes.windll.user32
_EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _user_windows():
    """Every visible, titled, top-level window: (hwnd, pid, title, class)."""
    found = []

    def visit(hwnd, _):
        if not _user32.IsWindowVisible(hwnd):
            return True
        length = _user32.GetWindowTextLengthW(hwnd)
        title = ctypes.create_unicode_buffer(length + 1)
        _user32.GetWindowTextW(hwnd, title, length + 1)
        cls = ctypes.create_unicode_buffer(256)
        _user32.GetClassNameW(hwnd, cls, 256)
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if _user32.GetWindowLongW(hwnd, -20) & 0x80:      # WS_EX_TOOLWINDOW
            return True
        found.append((int(hwnd), pid.value, title.value, cls.value))
        return True

    _user32.EnumWindows(_EnumProc(visit), 0)
    return found


def top_windows():
    """Windows an app action may touch: the shell's own are never among them.

    WM_CLOSE to the desktop (Progman) opens the Shut Down Windows dialog, so
    it and the taskbar are filtered out here, before anything can target them.
    """
    return [w for w in _user_windows() if w[3] not in SHELL_CLASSES and w[2]]


def _process_names():
    import psutil
    names = {}
    for proc in psutil.process_iter(["name"]):
        names[proc.pid] = (proc.info.get("name") or "").lower()
    return names


def find_windows(app):
    """Windows belonging to `app`: by process name first, then by title."""
    key = (app or "").strip().lower()
    if not key:
        return []
    exe = PROCESS_NAMES.get(key, key if key.endswith(".exe") else key.replace(" ", "") + ".exe")
    names = _process_names()
    windows = top_windows()
    by_process = [w for w in windows if names.get(w[1], "") == exe]
    return by_process or [w for w in windows if key in w[2].lower()]


def _post_close(hwnd):
    _user32.PostMessageW(hwnd, 0x0010, 0, 0)      # WM_CLOSE: the app asks about unsaved work


def _show(hwnd, cmd):
    _user32.ShowWindow(hwnd, cmd)


def _foreground():
    return int(_user32.GetForegroundWindow() or 0)


def _focus(hwnd):
    """Bring a window forward from a background process.

    Windows refuses SetForegroundWindow to a process that isn't in the
    foreground unless the input queues are joined for the call - so they are,
    briefly, with the thread that owns the current foreground window.
    """
    if _user32.IsIconic(hwnd):
        _user32.ShowWindow(hwnd, 9)
    fg = _user32.GetForegroundWindow()
    fg_thread = _user32.GetWindowThreadProcessId(fg, None) if fg else 0
    me = ctypes.windll.kernel32.GetCurrentThreadId()
    joined = bool(fg_thread and fg_thread != me and _user32.AttachThreadInput(me, fg_thread, True))
    try:
        _user32.BringWindowToTop(hwnd)
        _user32.SetForegroundWindow(hwnd)
    finally:
        if joined:
            _user32.AttachThreadInput(me, fg_thread, False)


def close_app(name):
    windows = [w for w in find_windows(name) if w[3] not in SHELL_CLASSES]
    if not windows:
        return f"Failed: {name} isn't open."
    for hwnd, *_ in windows:
        _post_close(hwnd)
    return f"Closing {name}."


WINDOW_SAID = {"minimize": "Minimized the window.", "maximize": "Maximized the window.",
               "restore": "Restored the window.", "close": "Closing the window.",
               "focus": "Switched to it.", "snap_left": "Snapped it to the left.",
               "snap_right": "Snapped it to the right."}


def window(action, app=None):
    if action == "show_desktop":
        _send(_chord_events([0x5B, ord("D")]))
        return "Showing the desktop."
    if app:
        found = find_windows(app)
        if not found:
            return f"Failed: {app} isn't open."
        hwnd = found[0][0]
    else:
        hwnd = _foreground()
        if not hwnd:
            return "Failed: there's no window in front."
    if action == "minimize":
        _show(hwnd, 6)
    elif action == "maximize":
        _show(hwnd, 3)
    elif action == "restore":
        _show(hwnd, 9)
    elif action == "close":
        _post_close(hwnd)
    elif action == "focus":
        _focus(hwnd)
    elif action in ("snap_left", "snap_right"):
        _focus(hwnd)
        _send(_chord_events([0x5B, 0x25 if action == "snap_left" else 0x27]))
    return WINDOW_SAID[action]


# --- power ------------------------------------------------------------------

def _run(argv):
    subprocess.run(argv, check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _suspend():
    ctypes.windll.powrprof.SetSuspendState(False, True, False)


def _lock():
    _user32.LockWorkStation()


def lock_pc():
    _lock()
    return "Locked."


def system_power(action):
    if action == "sleep":
        _suspend()
        return "Going to sleep."
    if action == "sign_out":
        _run(["shutdown", "/l"])
        return "Signing out."
    if action == "restart":
        _run(["shutdown", "/r", "/t", "10"])
        return "Restarting in 10 seconds. Say cancel shutdown to stop it."
    if action == "shutdown":
        _run(["shutdown", "/s", "/t", "10"])
        return "Shutting down in 10 seconds. Say cancel shutdown to stop it."
    if action == "cancel":
        _run(["shutdown", "/a"])
        return "Cancelled."
    return f"Failed: unknown power action {action}."
```

Add to the imports at the top of `pc_control.py`: `import ctypes`, `import re`, `import subprocess`, `import urllib.parse`, `from ctypes import wintypes`. Add to its module docstring: "…and control the keyboard, media, volume, windows and power."

- [ ] **Step 4: Run** `.venv/Scripts/python.exe -m pytest tests/test_pc_control.py -q` — Expected: 13 passed.
- [ ] **Step 5: Commit** `git commit -am "pc_control: sites, keys, typing, media, volume, windows, power" && git add tests/test_pc_control.py && git commit --amend --no-edit`

---

### Task 3: `market.py` — quotes, history, market hours, TradingView

**Files:**
- Create: `market.py`, `tests/test_market.py`, `tests/fixtures/chart_nvda_5d.json`, `tests/fixtures/chart_gspc_1d.json`, `tests/fixtures/search_nvidia.json`
- Modify: `overlay_content.py` (public `clean_visual = _clean`)

**Interfaces:**
- Produces: `market.MarketError`; `resolve(text) -> str`; `parse_chart(data) -> dict` (`symbol, name, currency, exchange, price, previous_close, change, change_pct, points: [(ts, close)], time`); `quote(symbol) -> dict`; `history(symbol, period) -> dict` (points ≤ 64); `downsample(points, n)`; `market_status(now=None) -> {"open", "next", "label"}`; `tradingview_symbol(symbol, exchange="")`; `tradingview_url(symbol, exchange="")`; `visual_for(data, period) -> dict|None`; `fmt_price(x) -> str`; `WATCHLIST`, `INDICES`, `PERIODS`.
- Seam: `market._get_json(path, ttl)`; `market._open(url)` (network).

- [ ] **Step 1: Record fixtures** (network, once):

```bash
.venv/Scripts/python.exe - <<'EOF'
import json, urllib.request
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36"}
for name, path in [("chart_nvda_5d", "/v8/finance/chart/NVDA?range=5d&interval=30m"),
                   ("chart_gspc_1d", "/v8/finance/chart/%5EGSPC?range=1d&interval=5m"),
                   ("search_nvidia", "/v1/finance/search?q=nvidia&quotesCount=5&newsCount=0")]:
    with urllib.request.urlopen(urllib.request.Request("https://query1.finance.yahoo.com" + path, headers=UA), timeout=8) as r:
        json.dump(json.load(r), open(f"tests/fixtures/{name}.json", "w"), indent=1)
print("ok")
EOF
```

- [ ] **Step 2: Failing tests** — `tests/test_market.py`:

```python
# FILE: tests/test_market.py
import json
import os
from datetime import datetime

import pytest

import market

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture(name):
    with open(os.path.join(FIX, name + ".json"), encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    market._cache.clear()
    calls = []

    def fake_get(path, ttl):
        calls.append(path)
        if "/chart/NVDA" in path:
            return fixture("chart_nvda_5d")
        if "/chart/%5EGSPC" in path:
            return fixture("chart_gspc_1d")
        if "/search" in path:
            return fixture("search_nvidia")
        raise market.MarketError("no fixture")
    monkeypatch.setattr(market, "_get_json", fake_get)
    return calls


def test_parse_chart_reads_price_change_and_points():
    d = market.parse_chart(fixture("chart_nvda_5d"))
    assert d["symbol"] == "NVDA" and d["currency"] == "USD"
    assert d["price"] > 0 and d["previous_close"] > 0
    assert d["change"] == pytest.approx(d["price"] - d["previous_close"])
    assert len(d["points"]) > 10 and all(c is not None for _, c in d["points"])


def test_parse_chart_error_payload():
    with pytest.raises(market.MarketError):
        market.parse_chart({"chart": {"result": None, "error": {"description": "No data found"}}})


def test_resolve():
    assert market.resolve("Nvidia") == "NVDA"
    assert market.resolve("the S&P 500") == "^GSPC"
    assert market.resolve("إنفيديا") == "NVDA"
    assert market.resolve("TSLA") == "TSLA"
    assert market.resolve("nvidia corp") == "NVDA"          # via search fixture


def test_history_downsamples_to_64():
    d = market.history("NVDA", "5d")
    assert len(d["points"]) <= 64
    assert d["points"][-1] == market.parse_chart(fixture("chart_nvda_5d"))["points"][-1]


def test_downsample_keeps_ends():
    pts = [(i, float(i)) for i in range(200)]
    out = market.downsample(pts, 64)
    assert len(out) == 64 and out[0] == pts[0] and out[-1] == pts[-1]


def test_market_status_weekday_and_weekend():
    from zoneinfo import ZoneInfo
    ny = ZoneInfo("America/New_York")
    wed_noon = datetime(2026, 9, 16, 12, 0, tzinfo=ny)
    s = market.market_status(wed_noon)
    assert s["open"] is True and s["label"] == "NYSE closes in 4h 00m"
    sat = datetime(2026, 9, 19, 14, 0, tzinfo=ny)
    s = market.market_status(sat)
    assert s["open"] is False and s["next"].weekday() == 0 and s["label"].startswith("NYSE opens in")


def test_tradingview():
    assert market.tradingview_symbol("NVDA", "NMS") == "NASDAQ:NVDA"
    assert market.tradingview_symbol("^GSPC") == "SP:SPX"
    assert market.tradingview_symbol("2222.SR") == "TADAWUL:2222"
    assert market.tradingview_url("NVDA", "NMS") == "https://www.tradingview.com/chart/?symbol=NASDAQ%3ANVDA"


def test_visual_for_builds_chart_and_cards():
    v = market.visual_for(market.history("NVDA", "5d"), "5d")
    assert v["chart"]["label"] == "NVDA · 5D" and len(v["chart"]["points"]) >= 4
    assert [c["label"] for c in v["cards"]] == ["LAST", "5D", "HIGH", "LOW"]


def test_both_hosts_down_raises_market_error(monkeypatch):
    monkeypatch.undo()
    market._cache.clear()

    def refuse(url):
        raise OSError("offline")
    monkeypatch.setattr(market, "_open", refuse)
    with pytest.raises(market.MarketError):
        market.quote("NVDA")
```

- [ ] **Step 3: Run** `.venv/Scripts/python.exe -m pytest tests/test_market.py -q` — Expected: collection error, no module `market`.

- [ ] **Step 4: Implement** `market.py`, and add `clean_visual = _clean` (with a one-line docstring comment) after `_clean` in `overlay_content.py`:

```python
# FILE: market.py
"""Live prices and price history for Apollo's market tools and dashboard.

The source is Yahoo Finance's public chart endpoint: no key, no account, and
it answers in about 0.3 s from here. It is unofficial, so it is used with
care - two hosts serving the same data are tried in turn, answers are cached
(a minute while New York is trading, fifteen otherwise), and any failure
surfaces as a MarketError whose message is safe to speak. Nothing here ever
invents a number: no data means an error, not a guess.
"""

import json
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import overlay_content

HOSTS = ("https://query1.finance.yahoo.com", "https://query2.finance.yahoo.com")
HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")}
TIMEOUT = 6
NY = ZoneInfo("America/New_York")

PERIODS = {"1d": "5m", "5d": "30m", "1mo": "1d", "6mo": "1d", "1y": "1wk", "5y": "1mo"}
MAX_POINTS = 64

WATCHLIST = ("AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META")
INDICES = ("^GSPC", "^IXIC")

NAMES = {
    "apple": "AAPL", "microsoft": "MSFT", "nvidia": "NVDA", "tesla": "TSLA",
    "amazon": "AMZN", "google": "GOOGL", "alphabet": "GOOGL", "meta": "META",
    "facebook": "META", "netflix": "NFLX", "amd": "AMD", "intel": "INTC",
    "sony": "SONY", "disney": "DIS", "take two": "TTWO", "take-two": "TTWO",
    "rockstar": "TTWO", "palantir": "PLTR",
    "s&p 500": "^GSPC", "s&p": "^GSPC", "sp500": "^GSPC", "s and p": "^GSPC",
    "nasdaq": "^IXIC", "dow": "^DJI", "dow jones": "^DJI",
    "bitcoin": "BTC-USD", "ethereum": "ETH-USD", "gold": "GC=F", "oil": "CL=F",
    "crude": "CL=F", "brent": "BZ=F", "aramco": "2222.SR", "saudi aramco": "2222.SR",
    "tasi": "^TASI.SR", "al rajhi": "1120.SR",
    "ابل": "AAPL", "آبل": "AAPL", "أبل": "AAPL", "انفيديا": "NVDA", "إنفيديا": "NVDA",
    "تسلا": "TSLA", "مايكروسوفت": "MSFT", "امازون": "AMZN", "أمازون": "AMZN",
    "جوجل": "GOOGL", "قوقل": "GOOGL", "ميتا": "META", "ارامكو": "2222.SR",
    "أرامكو": "2222.SR", "بيتكوين": "BTC-USD", "الذهب": "GC=F", "ذهب": "GC=F",
    "النفط": "CL=F", "ناسداك": "^IXIC",
}

TV_SPECIAL = {"^GSPC": "SP:SPX", "^IXIC": "NASDAQ:IXIC", "^DJI": "DJ:DJI",
              "^NDX": "NASDAQ:NDX", "BTC-USD": "BITSTAMP:BTCUSD",
              "ETH-USD": "BITSTAMP:ETHUSD", "GC=F": "COMEX:GC1!", "CL=F": "NYMEX:CL1!",
              "BZ=F": "NYMEX:BB1!", "^TASI.SR": "TADAWUL:TASI"}
TV_EXCHANGE = {"NMS": "NASDAQ", "NGM": "NASDAQ", "NCM": "NASDAQ", "NAS": "NASDAQ",
               "NYQ": "NYSE", "NYS": "NYSE", "ASE": "AMEX", "PCX": "AMEX", "SAU": "TADAWUL"}


class MarketError(Exception):
    """A market lookup failed. The message is written to be spoken."""


_cache = {}
_lock = threading.Lock()


def _open(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS),
                                timeout=TIMEOUT) as r:
        return json.load(r)


def _get_json(path, ttl):
    now = time.monotonic()
    with _lock:
        hit = _cache.get(path)
        if hit and hit[0] > now:
            return hit[1]
    last = None
    for host in HOSTS:
        try:
            data = _open(host + path)
        except Exception as e:  # noqa: BLE001 - any failure means try the other host
            last = e
            continue
        with _lock:
            _cache[path] = (now + ttl, data)
        return data
    raise MarketError(f"The market feed didn't answer ({type(last).__name__}).")


def _ttl():
    return 60 if market_status()["open"] else 900


def resolve(text):
    """A name or ticker as spoken -> a Yahoo symbol."""
    raw = (text or "").strip()
    if not raw:
        raise MarketError("No stock was named.")
    key = raw.lower().removeprefix("the ").strip()
    for suffix in (" stock", " shares", " index", " price"):
        key = key.removesuffix(suffix)
    if key in NAMES:
        return NAMES[key]
    if re.fullmatch(r"\^?[A-Z0-9]{1,6}([.=-][A-Z0-9]{1,4})?", raw):
        return raw
    data = _get_json("/v1/finance/search?" + urllib.parse.urlencode(
        {"q": raw, "quotesCount": 5, "newsCount": 0}), ttl=86400)
    for q in data.get("quotes", []):
        if q.get("symbol") and q.get("quoteType") in (
                "EQUITY", "ETF", "INDEX", "CRYPTOCURRENCY", "FUTURE", "MUTUALFUND", "CURRENCY"):
            return q["symbol"]
    raise MarketError(f"I couldn't find a ticker for {raw}.")


def parse_chart(data):
    """Yahoo's chart JSON -> the handful of numbers Apollo uses."""
    try:
        result = data["chart"]["result"][0]
    except (KeyError, IndexError, TypeError):
        error = (((data or {}).get("chart") or {}).get("error") or {})
        raise MarketError(error.get("description") or "The market feed had nothing for that symbol.")
    meta = result.get("meta") or {}
    stamps = result.get("timestamp") or []
    closes = (((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or [])
    points = [(int(t), float(c)) for t, c in zip(stamps, closes) if c is not None]
    price = meta.get("regularMarketPrice") or (points[-1][1] if points else None)
    if price is None:
        raise MarketError("The feed has no price for that symbol right now.")
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    change = float(price) - float(prev) if prev else 0.0
    return {
        "symbol": meta.get("symbol") or "",
        "name": meta.get("shortName") or meta.get("longName") or meta.get("symbol") or "",
        "currency": meta.get("currency") or "",
        "exchange": meta.get("exchangeName") or "",
        "price": float(price),
        "previous_close": float(prev) if prev else None,
        "change": change,
        "change_pct": (change / float(prev) * 100.0) if prev else 0.0,
        "points": points,
        "time": int(meta.get("regularMarketTime") or (points[-1][0] if points else 0)),
    }


def _chart(symbol, period):
    path = (f"/v8/finance/chart/{urllib.parse.quote(symbol, safe='')}?"
            + urllib.parse.urlencode({"range": period, "interval": PERIODS[period]}))
    return parse_chart(_get_json(path, _ttl()))


def quote(symbol):
    """Today: price, change against yesterday's close, intraday points."""
    return _chart(symbol, "1d")


def history(symbol, period="5d"):
    """Over a period: change across it, and at most MAX_POINTS points."""
    data = _chart(symbol, period)
    data["points"] = downsample(data["points"], MAX_POINTS)
    return data


def downsample(points, n):
    if len(points) <= n:
        return list(points)
    step = (len(points) - 1) / (n - 1)
    return [points[round(i * step)] for i in range(n)]


def _span(delta):
    minutes = max(0, int(delta.total_seconds() // 60))
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


def market_status(now=None):
    """The NYSE regular session. Weekends are modelled; exchange holidays are not."""
    now = now.astimezone(NY) if now else datetime.now(NY)
    opens = now.replace(hour=9, minute=30, second=0, microsecond=0)
    closes = now.replace(hour=16, minute=0, second=0, microsecond=0)
    if now.weekday() < 5 and opens <= now < closes:
        return {"open": True, "next": closes, "label": "NYSE closes in " + _span(closes - now)}
    if now.weekday() < 5 and now < opens:
        nxt = opens
    else:
        day = now + timedelta(days=1)
        while day.weekday() >= 5:
            day += timedelta(days=1)
        nxt = day.replace(hour=9, minute=30, second=0, microsecond=0)
    return {"open": False, "next": nxt, "label": "NYSE opens in " + _span(nxt - now)}


def tradingview_symbol(symbol, exchange=""):
    if symbol in TV_SPECIAL:
        return TV_SPECIAL[symbol]
    if symbol.endswith(".SR"):
        return "TADAWUL:" + symbol[:-3]
    prefix = TV_EXCHANGE.get((exchange or "").upper())
    return f"{prefix}:{symbol}" if prefix else symbol


def tradingview_url(symbol, exchange=""):
    return ("https://www.tradingview.com/chart/?symbol="
            + urllib.parse.quote(tradingview_symbol(symbol, exchange), safe=""))


def fmt_price(x):
    return f"{x:,.2f}"


def visual_for(data, period):
    """Chart + cards for the overlay, from `quote` or `history` output."""
    closes = [c for _, c in data["points"]] or [data["price"]]
    label = "Today" if period == "1d" else period.upper()
    return overlay_content.clean_visual({
        "chart": {"points": closes, "label": f"{data['symbol']} · {period.upper()}",
                  "unit": "$" if data["currency"] == "USD" else ""},
        "cards": [{"label": "Last", "value": fmt_price(data["price"])},
                  {"label": label, "value": f"{data['change_pct']:+.1f}%"},
                  {"label": "High", "value": fmt_price(max(closes))},
                  {"label": "Low", "value": fmt_price(min(closes))}],
    })
```

- [ ] **Step 5: Run** `.venv/Scripts/python.exe -m pytest tests/test_market.py -q` — Expected: 10 passed. Then the full suite.
- [ ] **Step 6: Commit** `git add market.py overlay_content.py tests && git commit -m "Add market data: quotes, history, NYSE hours, TradingView links"`

---

### Task 4: Tool definitions — PC, reminders, markets

**Files:**
- Modify: `tools.py` (append the definitions section)
- Test: `tests/test_tool_definitions.py`

**Interfaces:**
- Consumes: Task 1 registry; Task 2 `pc_control` functions; Task 3 `market` functions; `reminders.add/describe_pending/cancel`.
- Produces: registered tools `open_app, close_app, open_website, open_path, media, volume, window, type_text, press_keys, lock_pc, system_power (confirm), set_reminder, list_reminders, cancel_reminder, stock_quote, show_stock_chart, open_tradingview`; `tools.TOOL_LABELS: dict[name, str]` (what the overlay says while a tool runs).

- [ ] **Step 1: Failing tests** — `tests/test_tool_definitions.py`:

```python
# FILE: tests/test_tool_definitions.py
import pytest

import market
import pc_control
import reminders
import tools
from tools import Context


def test_expected_tools_are_registered():
    assert {"open_app", "close_app", "open_website", "open_path", "media", "volume",
            "window", "type_text", "press_keys", "lock_pc", "system_power",
            "set_reminder", "list_reminders", "cancel_reminder", "stock_quote",
            "show_stock_chart", "open_tradingview"} <= set(tools.REGISTRY)
    assert tools.REGISTRY["system_power"].confirm is True
    assert all(name in tools.TOOL_LABELS for name in tools.REGISTRY)


def test_open_app_maps_to_pc_control(monkeypatch):
    monkeypatch.setattr(pc_control, "open_app", lambda name: f"Launched {name}.")
    assert tools.run("open_app", {"application_name": "Discord"}) == {"ok": True, "result": "Launched Discord."}


def test_volume_passes_level(monkeypatch):
    seen = []
    monkeypatch.setattr(pc_control, "volume", lambda action, level=None: seen.append((action, level)) or {"level": 40})
    assert tools.run("volume", {"action": "set", "level": "40"}) == {"ok": True, "level": 40}
    assert seen == [("set", 40)]


def fake_data(symbol, price=100.0, pct=1.5):
    return {"symbol": symbol, "name": symbol + " Inc", "currency": "USD", "exchange": "NMS",
            "price": price, "previous_close": price / (1 + pct / 100), "change": 1.0,
            "change_pct": pct, "points": [(i, price - 5 + i) for i in range(6)], "time": 0}


def test_show_stock_chart_shows_and_summarises(monkeypatch):
    monkeypatch.setattr(market, "resolve", lambda s: "NVDA")
    monkeypatch.setattr(market, "history", lambda s, p: fake_data(s))
    shown, doing = [], []
    r = tools.run("show_stock_chart", {"symbol": "nvidia", "period": "5D"},
                  Context(show=shown.append, activity=doing.append))
    assert r["ok"] and r["symbol"] == "NVDA" and r["period"] == "5d" and r["last"] == 100.0
    assert shown and shown[0]["chart"]["label"] == "NVDA · 5D"
    assert doing == ["charting NVDA"]


def test_stock_quote_several_shows_cards(monkeypatch):
    monkeypatch.setattr(market, "resolve", lambda s: s.upper())
    monkeypatch.setattr(market, "quote", lambda s: fake_data(s))
    shown = []
    r = tools.run("stock_quote", {"symbols": ["aapl", "tsla"]}, Context(show=shown.append))
    assert [q["symbol"] for q in r["quotes"]] == ["AAPL", "TSLA"]
    assert [c["label"] for c in shown[0]["cards"]] == ["AAPL", "TSLA"]


def test_market_error_becomes_failed_result(monkeypatch):
    def down(s):
        raise market.MarketError("The market feed didn't answer (URLError).")
    monkeypatch.setattr(market, "resolve", lambda s: s)
    monkeypatch.setattr(market, "quote", down)
    assert tools.run("stock_quote", {"symbols": ["NVDA"]}) == {
        "ok": False, "error": "The market feed didn't answer (URLError)."}


def test_open_tradingview(monkeypatch):
    monkeypatch.setattr(market, "resolve", lambda s: "NVDA")
    monkeypatch.setattr(market, "quote", lambda s: fake_data(s))
    opened = []
    monkeypatch.setattr(pc_control, "open_url", lambda u: opened.append(u) or f"Opened {u}.")
    assert tools.run("open_tradingview", {"symbol": "nvidia"})["ok"]
    assert opened == ["https://www.tradingview.com/chart/?symbol=NASDAQ%3ANVDA"]


def test_reminders_round_trip(monkeypatch, tmp_path):
    monkeypatch.setattr(reminders, "STORE", str(tmp_path / "r.json"))
    monkeypatch.setattr(reminders, "_reminders", None)
    assert tools.run("set_reminder", {"text": "stretch", "in_minutes": 30})["ok"]
    assert "stretch" in tools.run("list_reminders", {})["result"]
    assert tools.run("cancel_reminder", {"which": "stretch"}) == {"ok": True, "result": "Cancelled: stretch"}


def test_system_power_is_guarded(monkeypatch):
    tools.CONFIRM.reset()
    ran = []
    monkeypatch.setattr(pc_control, "system_power", lambda action: ran.append(action) or "ok")
    r = tools.run("system_power", {"action": "shutdown", "confirmed": True}, Context(turn=100))
    assert r["needs_confirmation"] and ran == []
```

- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/test_tool_definitions.py -q` — Expected: FAIL (tools not registered).

- [ ] **Step 3: Implement** — append to `tools.py`:

```python
# --- the tools ---------------------------------------------------------------
#
# Descriptions are written for the model: when to call the tool, not how it is
# built. Imports are here, below the registry, so the registry itself stays
# importable (and testable) without Windows or the network.

import market  # noqa: E402
import overlay_content  # noqa: E402
import pc_control  # noqa: E402
import reminders  # noqa: E402


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
       _obj({"action": _enum(["get", "set", "up", "down", "mute", "unmute"], "What to do"),
             "level": {"type": "integer", "description": "0-100"}}, ["action"]))
def _volume(ctx, action, level=None):
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
```

Also change `run` to translate a `market.MarketError` into `{"ok": False, "error": str(e)}` (no exception class name — the message is already speakable): in the `except` block, before the generic branch:

```python
    except Exception as e:  # noqa: BLE001 - a tool must never take a turn down
        if getattr(e, "speakable", False) or type(e).__name__ == "MarketError":
            return {"ok": False, "error": str(e)}
        log.exception("tool %s failed", name)
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
```

- [ ] **Step 4: Run** the new tests, then the full suite — Expected: all pass.
- [ ] **Step 5: Commit** `git commit -am "Register PC, reminder and market tools" && git add tests/test_tool_definitions.py && git commit --amend --no-edit`

---

### Task 5: `turnview.py` — what the overlay shows for a turn

**Files:**
- Create: `turnview.py`, `tests/test_turnview.py`

**Interfaces:**
- Produces: `turnview.TurnView` with `reset()`, `heard(text, final=False) -> frame`, `replied(text) -> frame`, `show(visual) -> frame`, `doing(text) -> frame`, `frame() -> (role, text, visual)`, attributes `you, reply, visual, activity`. Roles are `overlay_content.USER` / `APOLLO`.

- [ ] **Step 1: Failing tests**

```python
# FILE: tests/test_turnview.py
from overlay_content import APOLLO, USER
from turnview import TurnView


def test_your_words_then_the_reply():
    v = TurnView()
    assert v.heard("open chr") == (USER, "open chr", None)
    assert v.heard("open chrome") == (USER, "open chrome", None)
    assert v.replied("Opening") == (APOLLO, "Opening", None)
    assert v.replied("Opening Chrome.") == (APOLLO, "Opening Chrome.", None)


def test_visual_attaches_to_the_reply_even_before_words():
    v = TurnView()
    v.heard("show me nvidia")
    chart = {"chart": {"points": [1, 2, 3, 4]}}
    assert v.show(chart) == (APOLLO, "", chart)
    assert v.replied("Nvidia is up.") == (APOLLO, "Nvidia is up.", chart)


def test_final_transcript_after_reply_does_not_wipe_it():
    v = TurnView()
    v.replied("It's nine.")
    assert v.heard("what time is it", final=True) == (APOLLO, "It's nine.", None)
    assert v.you == "what time is it"


def test_new_live_words_after_a_reply_start_a_new_turn():
    v = TurnView()
    v.replied("It's nine.")
    assert v.heard("and tomor") == (USER, "and tomor", None)
    assert v.reply == ""


def test_activity_is_kept_until_the_reply():
    v = TurnView()
    v.doing("fetching NVDA")
    assert v.activity == "fetching NVDA"
    v.replied("Here")
    assert v.activity == ""
```

- [ ] **Step 2: Run** — Expected: no module `turnview`.
- [ ] **Step 3: Implement**

```python
# FILE: turnview.py
"""What the overlay shows for the turn in progress.

A turn now arrives in pieces from different threads: your words as Gemini
transcribes them, a chart pushed by a tool before a word of the answer
exists, the answer itself streaming in as it is spoken, and your final
transcript - which in always-listening lands *after* the answer. This is the
one place that decides what all of that adds up to on screen, so the rules
live somewhere they can be tested:

- your words show until there is an answer or something to look at;
- a chart or cards belong to the answer, and stay with it as it grows;
- your final transcript never wipes an answer that is already up;
- but fresh live words after an answer are a new turn, and replace it.
"""

from overlay_content import APOLLO, USER


class TurnView:
    def __init__(self):
        self.reset()

    def reset(self):
        self.you = ""
        self.reply = ""
        self.visual = None
        self.activity = ""

    def heard(self, text, final=False):
        if (self.reply or self.visual) and not final:
            self.reset()
        self.you = text or ""
        return self.frame()

    def replied(self, text):
        self.reply = text or ""
        self.activity = ""
        return self.frame()

    def show(self, visual):
        if visual:
            self.visual = visual
        return self.frame()

    def doing(self, text):
        self.activity = text or ""
        return self.frame()

    def frame(self):
        if self.reply or self.visual:
            return (APOLLO, self.reply, self.visual)
        return (USER, self.you, None)
```

- [ ] **Step 4: Run** — Expected: 5 passed.
- [ ] **Step 5: Commit** `git add turnview.py tests/test_turnview.py && git commit -m "Add TurnView: one place deciding what a turn shows"`

---

### Task 6: `gemini_live.py` — tools, live transcript, prompts, model fallback

**Files:**
- Modify: `gemini_live.py`
- Test: `tests/test_live_tools.py`

**Interfaces:**
- Consumes: nothing from other new modules (by constraint).
- Produces: `MODELS: tuple`; `system_instruction(now=None) -> str`; `LiveSession(on_audio=None, on_text=None, api_key=None, auto_vad=False, on_user_text=None, tools=None, on_tool_call=None, on_heard=None, on_activity=None, on_user_turn=None, models=None)`; `.model` (the one connected); `.heard_text(settle=0.35, timeout=1.5) -> str`; `.prompt(text) -> bool`; `.wait_for_audio(timeout=10) -> bool`; `on_text(full_reply_so_far)` fires only while audible; `on_heard(full_transcript_so_far)`; `on_activity(kind, detail)` with kind `"tool"` or `"search"`; `on_tool_call(name, args) -> dict`.

- [ ] **Step 1: Failing tests**

```python
# FILE: tests/test_live_tools.py
import threading
import time
from types import SimpleNamespace

import gemini_live


def session(**kw):
    s = gemini_live.LiveSession(api_key="test", **kw)
    s.replies = []
    s._reply_tool = lambda fc, result: s.replies.append((fc.id, fc.name, result))
    return s


def fc(name="open_app", args=None, id="c1"):
    return SimpleNamespace(id=id, name=name, args=args or {"name": "Notepad"})


def wait_for(pred, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.01)
    return False


def test_tool_runs_when_audible_and_result_is_sent():
    calls = []
    s = session(on_tool_call=lambda n, a: calls.append((n, a)) or {"ok": True})
    s._dispatch_tool(fc())
    assert wait_for(lambda: s.replies)
    assert calls == [("open_app", {"name": "Notepad"})]
    assert s.replies == [("c1", "open_app", {"ok": True})]


def test_tool_waits_for_gate_and_cancels_on_discard():
    calls = []
    s = session(on_tool_call=lambda n, a: calls.append(n) or {"ok": True})
    s._play_open.clear()                      # push-to-talk: route not decided yet
    s._dispatch_tool(fc())
    time.sleep(0.15)
    assert calls == [] and s.replies == []
    s.discard_reply()                         # the turn went to an agent
    assert wait_for(lambda: s.replies)
    assert calls == [] and s.replies[0][2]["ok"] is False


def test_tool_released_by_allow_reply():
    calls = []
    s = session(on_tool_call=lambda n, a: calls.append(n) or {"ok": True})
    s._play_open.clear()
    s._dispatch_tool(fc())
    time.sleep(0.1)
    s.allow_reply()
    assert wait_for(lambda: s.replies) and calls == ["open_app"]


def test_heard_streams_and_settles():
    heard = []
    s = session(on_heard=heard.append)
    s.begin_turn()
    for part in (" Open", " Chr", "ome."):
        s._note_heard(part)
    assert heard[-1] == "Open Chrome."
    t0 = time.monotonic()
    assert s.heard_text(settle=0.2, timeout=1.0) == "Open Chrome."
    assert time.monotonic() - t0 < 0.6


def test_heard_text_times_out_empty():
    s = session()
    s.begin_turn()
    assert s.heard_text(settle=0.1, timeout=0.3) == ""


def test_reply_text_only_emitted_when_audible():
    said = []
    s = session(on_text=said.append)
    s._play_open.clear()
    s._reply = ["Opening"]
    s._emit_reply()
    assert said == []
    s.allow_reply()
    assert said == ["Opening"]


def test_user_turn_callback_fires_on_begin_turn():
    turns = []
    s = session(on_user_turn=lambda: turns.append(1))
    s.begin_turn()
    assert turns == [1]


def test_prompt_without_session_is_false():
    assert session().prompt("hello") is False


def test_system_instruction_has_date_and_language_rule():
    from datetime import datetime
    text = gemini_live.system_instruction(datetime(2026, 9, 19, 21, 30))
    assert "Saturday 19 September 2026, 21:30" in text
    assert "Arabic" in text and "tool" in text


def test_models_order():
    assert gemini_live.MODELS[0] == "gemini-2.5-flash-native-audio-latest"
```

- [ ] **Step 2: Run** — Expected: failures (`_dispatch_tool`, `heard_text`, `system_instruction` missing).

- [ ] **Step 3: Implement** in `gemini_live.py`:

(a) Imports: add `import json`, `from concurrent.futures import ThreadPoolExecutor`, `from datetime import datetime`.

(b) Replace the `MODEL = ...` line with:
```python
# Measured 2026-09-19 (probes/probe_live_models.py): the "latest" alias passes
# every check Apollo needs and is the quickest to first audio; the September
# preview is the proven fallback. gemini-3.8-live exists but this key has no
# quota for it. APOLLO_GEMINI_MODEL puts another model at the front.
MODELS = tuple(filter(None, (os.environ.get("APOLLO_GEMINI_MODEL"),
                             "gemini-2.5-flash-native-audio-latest",
                             "gemini-2.5-flash-native-audio-preview-09-2025")))
MODEL = MODELS[0]
```

(c) Replace `SYSTEM_INSTRUCTION` with the text below and add `system_instruction()`:
```python
SYSTEM_INSTRUCTION = (
    "You are Apollo, a voice assistant running on the user's own Windows PC, "
    "answering out loud.\n\n"
    "Language: reply in the language the user just spoke. If they speak Arabic, "
    "answer in Arabic in their dialect (they are Saudi); if English, in English. "
    "Keep numbers as digits.\n\n"
    "Length: one or two sentences unless they ask for detail. No markdown, lists "
    "or emoji. Never read out a URL.\n\n"
    "Character: optimistic, game for a challenge, firm - lead with the move, "
    "answer straight, skip the hedging. Not cheerful filler, not bluster, not "
    "curt, and never longer.\n\n"
    "Doing things: you control this PC through your tools. When the user asks "
    "you to do something - open or close an app or website, play or skip music, "
    "change the volume, move or switch windows, type text, press keys, set a "
    "reminder - call the tool instead of describing it, then confirm in a few "
    "words. If a tool reports a failure, say so plainly.\n\n"
    "Live information: for anything current - prices, news, scores, weather, "
    "what someone posted - use Google Search or your market tools; never answer "
    "from memory. For a stock, index, crypto or commodity call show_stock_chart "
    "or stock_quote (they draw it on screen) and speak only the numbers they "
    "return. Open TradingView only when asked.\n\n"
    "Safety: sleep, restart, shut down and sign out need the user's explicit yes. "
    "Ask first; call system_power with confirmed=true only after they say yes.\n\n"
    "About the user: they follow Apple, Microsoft, Nvidia, Tesla, Amazon, "
    "Alphabet and Meta, the S&P 500 and Nasdaq, and care about Marvel, GTA 6, "
    "PlayStation, gaming and movies. They live in Riyadh."
)


def system_instruction(now=None):
    """The instruction plus the date and time, fixed when a session opens."""
    now = now or datetime.now()
    return SYSTEM_INSTRUCTION + f"\n\nRight now it is {now:%A %d %B %Y, %H:%M} in Riyadh."
```

(d) `_config(auto_vad=False, tools=None, instruction=None)`: input transcription in both modes, tools, instruction:
```python
        input_audio_transcription=types.AudioTranscriptionConfig(),
        tools=([types.Tool(function_declarations=list(tools))] if tools else [])
              + [types.Tool(google_search=types.GoogleSearch())],
        system_instruction=instruction or system_instruction(),
```
(and update its docstring's sentence about input transcription: it is on in both modes now, because it is Apollo's transcript of you — live words on screen and agent routing — in Arabic as well as English.)

(e) `LiveSession.__init__` gains the new parameters and state:
```python
    def __init__(self, on_audio=None, on_text=None, api_key=None,
                 auto_vad=False, on_user_text=None, tools=None,
                 on_tool_call=None, on_heard=None, on_activity=None,
                 on_user_turn=None, models=None):
        ...existing assignments...
        self._tools = list(tools or [])
        self._on_tool_call = on_tool_call
        self._on_heard = on_heard
        self._on_activity = on_activity
        self._on_user_turn = on_user_turn
        self._models = tuple(models or MODELS)
        self.model = None
        self._epoch = 0                 # bumped by discard_reply; see _tool_allowed
        self._cancelled = set()         # tool call ids the server withdrew
        self._last_heard = 0.0
        self._prompted = False          # the turn in flight was Apollo's own idea
        self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="apollo-tool")
```
In `close()` add `self._pool.shutdown(wait=False, cancel_futures=True)` after the thread join.

(f) `_main` connects with fallback:
```python
    async def _main(self):
        self._out_q = asyncio.Queue(maxsize=50)
        self._play_q = asyncio.Queue()
        self._turns = queue.Queue()
        self._stop = asyncio.Event()
        self._turn_over = asyncio.Event()

        client = genai.Client(api_key=self._api_key)
        last_error = None
        for model in self._models:
            connected = False
            try:
                async with client.aio.live.connect(
                        model=model, config=_config(self.auto_vad, self._tools)) as session:
                    connected = True
                    self.model = model
                    await self._serve(session)
                return
            except Exception as e:  # noqa: BLE001
                if connected:
                    raise
                last_error = e
                log.warning("model %s unavailable: %s", model, e)
        raise last_error or RuntimeError("no Gemini Live model is available")

    async def _serve(self, session):
        tasks = []
        try:
            self._session = session
            self._open_streams()
            self._ready.set()
            tasks = [
                asyncio.create_task(self._send_loop(), name="gemini-send"),
                asyncio.create_task(self._receive_loop(), name="gemini-recv"),
                asyncio.create_task(self._play_loop(), name="gemini-play"),
            ]
            done, _pending = await asyncio.wait(
                [asyncio.create_task(self._stop.wait()), *tasks],
                return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                if task in tasks and task.exception() is not None:
                    raise task.exception()
        finally:
            self._closing.set()
            self._mic_open.clear()
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            self._close_streams()
            self._session = None
```
Update the `log.info("connected: ...")` in `start()` to use `self.model`.

(g) Tools:
```python
    TOOL_GATE_TIMEOUT = 20.0

    def _dispatch_tool(self, call):
        """Run one tool call off the event loop, and answer it.

        In push-to-talk the model may call a tool before Apollo has read your
        transcript and decided the turn is Gemini's at all - "hey LYLA, open
        Chrome" must not open Chrome twice. So a call waits for the playback
        gate (`allow_reply`) and is cancelled if `discard_reply` comes first.
        """
        epoch = self._epoch
        name, args = call.name, dict(call.args or {})

        def work():
            if not self._tool_allowed(epoch):
                result = {"ok": False, "error": "Cancelled: this turn was handed to someone else."}
            elif self._on_tool_call is None:
                result = {"ok": False, "error": "No tools are available."}
            else:
                self._activity("tool", name)
                try:
                    result = self._on_tool_call(name, args)
                except Exception as e:  # noqa: BLE001
                    result = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            if call.id in self._cancelled:
                return
            self._reply_tool(call, result)

        self._pool.submit(work)

    def _tool_allowed(self, epoch):
        deadline = time.monotonic() + self.TOOL_GATE_TIMEOUT
        while not self._closing.is_set():
            if self._epoch != epoch:
                return False
            if self._play_open.is_set():
                return True
            if time.monotonic() > deadline:
                return False
            time.sleep(0.02)
        return False

    def _reply_tool(self, call, result):
        loop, session = self._loop, self._session
        if loop is None or loop.is_closed() or session is None:
            return
        payload = json.loads(json.dumps(result, default=str))
        response = types.FunctionResponse(id=call.id, name=call.name, response=payload)
        try:
            asyncio.run_coroutine_threadsafe(
                session.send_tool_response(function_responses=[response]), loop)
        except RuntimeError:
            pass

    def _activity(self, kind, detail=""):
        if self._on_activity is not None:
            try:
                self._on_activity(kind, detail)
            except Exception:
                pass
```
In `discard_reply()`, add `self._epoch += 1` as its first line.

(h) Receive loop — after the `if data := response.data:` block, before `content = response.server_content`:
```python
                if response.tool_call is not None:
                    for call in response.tool_call.function_calls or []:
                        self._dispatch_tool(call)
                    continue
                withdrawn = getattr(response, "tool_call_cancellation", None)
                if withdrawn is not None:
                    self._cancelled.update(withdrawn.ids or [])
                    continue
```
and inside the content handling, after the input transcription block:
```python
                turn = getattr(content, "model_turn", None)
                if turn is not None and any(getattr(p, "executable_code", None)
                                            for p in (turn.parts or [])):
                    self._activity("search", "")
```
and replace the output-transcription append block with:
```python
                if transcript is not None and transcript.text and not self._discarded:
                    self._reply.append(transcript.text)
                    self._emit_reply()
```

(i) Transcript, reply streaming, prompts:
```python
    def _note_heard(self, text):
        """Your own words, as the model transcribes them - both modes now."""
        first = not self._heard
        self._heard.append(text)
        self._last_heard = time.monotonic()
        self._in_flight = True
        if first and self.auto_vad and self._on_user_turn is not None:
            try:
                self._on_user_turn()
            except Exception:
                pass
        if self._on_heard is not None:
            try:
                self._on_heard("".join(self._heard).strip())
            except Exception:
                pass
        if not self.auto_vad or self._on_user_text is None or self._discarded:
            return
        try:
            if self._on_user_text("".join(self._heard).strip()):
                self.discard_reply()
        except Exception:
            pass          # a routing hiccup must not derail the conversation

    def heard_text(self, settle=0.35, timeout=1.5):
        """Push-to-talk: your words, once the transcript has stopped arriving.

        Measured: fragments stream while the chord is held, and the last one
        lands about 0.2 s after release - so this waits for `settle` seconds
        of quiet (or `timeout`) and returns the whole sentence, or "" if the
        model heard nothing.
        """
        start = time.monotonic()
        while True:
            now = time.monotonic()
            if self._heard and now - max(self._last_heard, start) >= settle:
                break
            if now - start >= timeout:
                break
            time.sleep(0.03)
        return "".join(self._heard).strip()

    def _emit_reply(self):
        if (self._on_text is not None and self._play_open.is_set()
                and not self._discarded and self._reply):
            try:
                self._on_text(self.reply_text())
            except Exception:
                pass

    def prompt(self, text):
        """Have Apollo say something nobody asked for - a reminder, the briefing."""
        loop, session = self._loop, self._session
        if loop is None or loop.is_closed() or session is None or self._closing.is_set():
            return False
        self._play_open.set()
        self._reply = []
        self._prompted = True
        content = types.Content(role="user", parts=[types.Part(text=text)])
        try:
            asyncio.run_coroutine_threadsafe(
                session.send_client_content(turns=content, turn_complete=True),
                loop).result(timeout=5)
            return True
        except Exception as e:  # noqa: BLE001
            log.warning("prompt failed: %s", e)
            self._prompted = False
            return False

    def wait_for_audio(self, timeout=10):
        """Block until reply audio has started playing. True if it did."""
        deadline = time.monotonic() + timeout
        while not self.playing and not self._closing.is_set():
            if time.monotonic() > deadline:
                return False
            time.sleep(0.03)
        return self.playing
```
`begin_turn()` additionally resets `self._heard = []`, `self._last_heard = 0.0`, `self._prompted = False`, and calls `self._on_user_turn()` (guarded) after `self._reply = []`. `allow_reply()` becomes `self._play_open.set(); self._emit_reply()`.
In `_finish_turn`, in the `auto_vad` branch, skip queueing a turn that Apollo prompted with nothing said:
```python
            prompted, self._prompted = self._prompted, False
            if self._turns is not None and (said or reply) and not (prompted and not said):
                self._turns.put((said, "" if discarded else reply))
```

- [ ] **Step 4: Run** `.venv/Scripts/python.exe -m pytest -q` — Expected: all pass (including Task 3 of P1's playback tests).
- [ ] **Step 5: Commit** `git commit -am "Gemini Live: tools, Google Search, live transcript, prompts, model fallback" && git add tests/test_live_tools.py && git commit --amend --no-edit`

---

### Task 7: Wire it into Apollo — assistant, reporter, overlay, reminders

**Files:**
- Modify: `assistant.py`, `apollo.py`
- Test: `tests/test_ptt_turn.py`, `tests/test_announce.py`

**Interfaces:**
- Consumes: Tasks 1–6.
- Produces: `assistant.WHISPER_SIZE = "small"`; `assistant.WhisperBackup` (`.transcribe(audio, **kw)`); `assistant.load_whisper() -> WhisperBackup`; `assistant.TURN_GATE: threading.Lock`; `assistant.tool_runner(ui) -> callable(name, args) -> dict`; `assistant.announce(ui, voice, instruction, fallback)`; `assistant.fire_reminder(ui, voice, reminder, late)`; `assistant.ACTIVITY_WORDS`; `Voice(ui, on_level=None, on_user_text=None, on_heard=None, on_reply=None, on_activity=None, run_tool=None)`; reporter methods `visual(visual)` and `activity(text)` on `ConsolePrinter` and `WebReporter`.

- [ ] **Step 1: Failing tests**

```python
# FILE: tests/test_ptt_turn.py
import numpy as np

import assistant


class UI:
    def __init__(self):
        self.statuses, self.turns, self.notes = [], [], []

    def status(self, s):
        self.statuses.append(s)

    def turn(self, who, text, visual=None):
        self.turns.append((who, text))

    def note(self, t):
        self.notes.append(t)

    def level(self, v):
        pass

    def partial(self, t):
        pass


class Capture:
    frames = []

    def start(self):
        pass

    def stop(self):
        return np.zeros(assistant.SAMPLE_RATE, dtype=np.float32)


class Live:
    def __init__(self, heard):
        self.heard, self.allowed, self.discarded = heard, 0, 0

    def begin_turn(self):
        pass

    def end_turn(self):
        pass

    def heard_text(self, **kw):
        return self.heard

    def allow_reply(self):
        self.allowed += 1

    def discard_reply(self):
        self.discarded += 1

    def wait_for_reply(self, timeout=60):
        return True

    def reply_text(self):
        return "Opening Chrome."


class Voice:
    def __init__(self, live):
        self.live, self.capture = live, Capture()


class NoWhisper:
    def transcribe(self, *a, **k):
        raise AssertionError("Whisper must not run when Gemini heard the turn")


class Whisper:
    def transcribe(self, audio, **kw):
        return iter([type("S", (), {"text": " open chrome"})()]), None


def test_gemini_transcript_routes_the_turn_without_whisper():
    ui, live = UI(), Live("open chrome")
    assistant.push_to_talk_turn(ui, NoWhisper(), Voice(live))
    assert ("You", "open chrome") in ui.turns and ("Apollo", "Opening Chrome.") in ui.turns
    assert live.allowed == 1


def test_whisper_is_the_backup_when_gemini_heard_nothing():
    ui, live = UI(), Live("")
    assistant.push_to_talk_turn(ui, Whisper(), Voice(live))
    assert ("You", "open chrome") in ui.turns


def test_agent_name_discards_gemini_reply(monkeypatch):
    ui, live = UI(), Live("hey lyla open chrome")
    asked = []
    monkeypatch.setattr(assistant, "answer_with_agent", lambda name, said, ui: asked.append(name))
    assistant.push_to_talk_turn(ui, NoWhisper(), Voice(live))
    assert live.discarded == 1 and live.allowed == 0 and asked == ["LYLA"]
```

```python
# FILE: tests/test_announce.py
import assistant


class UI:
    def __init__(self):
        self.statuses, self.turns = [], []

    def status(self, s):
        self.statuses.append(s)

    def turn(self, who, text, visual=None):
        self.turns.append((who, text))


class Live:
    def __init__(self, ok=True):
        self.ok, self.prompts = ok, []

    def prompt(self, text):
        self.prompts.append(text)
        return self.ok

    def wait_for_audio(self, timeout=10):
        return True

    def wait_until_quiet(self, timeout=60):
        return True


class Voice:
    def __init__(self, live, auto_vad=False):
        self.live, self.auto_vad = live, auto_vad


def test_reminder_is_spoken_by_gemini(monkeypatch):
    ui, live = UI(), Live()
    assistant.fire_reminder(ui, Voice(live), {"text": "stretch"}, late=False)
    assert "stretch" in live.prompts[0]
    assert ui.statuses == [assistant.SPEAKING, assistant.IDLE]


def test_reminder_falls_back_to_local_voice(monkeypatch):
    spoken = []
    monkeypatch.setattr(assistant, "speak", spoken.append)
    ui = UI()
    assistant.fire_reminder(ui, Voice(Live(ok=False)), {"text": "stretch"}, late=True)
    assert spoken == ["Reminder: stretch"]
    assert ui.turns == [("Apollo", "Reminder: stretch")]


def test_always_listening_returns_to_listening(monkeypatch):
    ui = UI()
    assistant.announce(ui, Voice(Live(), auto_vad=True), "say hi", "Hi")
    assert ui.statuses == [assistant.SPEAKING, assistant.LISTENING]
```

- [ ] **Step 2: Run** — Expected: failures (`fire_reminder`/`announce` missing; `push_to_talk_turn` still calls Whisper).

- [ ] **Step 3: Implement `assistant.py`:**

1. Imports: add `import tools`.
2. `WHISPER_SIZE = "small"       # multilingual (Arabic + English); a backup now - see WhisperBackup`.
3. Replace `load_whisper` with:
```python
class WhisperBackup:
    """Whisper, loaded in the background, for the rare turn Gemini missed.

    Gemini's own transcript is Apollo's transcript now (it streams while you
    hold the chord, and it understands Arabic). Whisper stays as the backup
    for a turn where that transcript never arrives, so it must not delay
    startup: the model loads on a thread of its own, the first run
    downloading it, and a transcription asked for before it is ready waits
    up to 20 s and then returns nothing.
    """

    def __init__(self, size=None):
        self._model = None
        self._ready = threading.Event()
        threading.Thread(target=self._load, args=(size or WHISPER_SIZE,),
                         daemon=True, name="whisper-load").start()

    def _load(self, size):
        try:
            self._model = WhisperModel(size, device="cpu", compute_type="int8")
        except Exception:
            self._model = None
        finally:
            self._ready.set()

    def transcribe(self, audio, **kw):
        if not self._ready.wait(timeout=20) or self._model is None:
            return iter(()), None
        return self._model.transcribe(audio, **kw)


def load_whisper():
    """The backup transcriber. Returns at once; the model loads behind it."""
    return WhisperBackup()
```
4. In `transcribe()`, `language="en"` → `language=None` (auto-detect; `small` is multilingual).
5. `capture_turn(live, capture)` drops its `on_partial`/`whisper` parameters and the `_follow_along` listener (partials now come from Gemini through `on_heard`); docstring updated to say so.
6. `push_to_talk_turn`:
```python
    if live is not None:
        audio = capture_turn(live, voice.capture)
    else:
        audio = record_while_held(HOTKEY, on_level=ui.level,
                                  on_partial=getattr(ui, "partial", None),
                                  whisper=whisper)
    ui.level(0.0)

    if audio is None or len(audio) < MIN_SECONDS * SAMPLE_RATE:
        ...unchanged...

    ui.status(THINKING)
    # Gemini's transcript first: it streamed while you spoke and settles about
    # a third of a second after you let go. Whisper only if it never came.
    said = live.heard_text() if live is not None else ""
    if not said and whisper is not None:
        said = transcribe(whisper, audio)
```
(rest unchanged).
7. Tool runner, announcements, reminders:
```python
# One lock for "a turn is in progress". The run loop holds it for every turn,
# and the reminder watcher takes it before speaking, so a reminder waits for
# your sentence to finish instead of talking over it.
TURN_GATE = threading.Lock()

# What the overlay says while a model-side search runs.
ACTIVITY_WORDS = {"search": "searching the web"}


def tool_runner(ui):
    """Build the callable Gemini's tool calls go through."""
    def run(name, args):
        ctx = tools.Context(show=getattr(ui, "visual", None),
                            activity=getattr(ui, "activity", None))
        return tools.run(name, args, ctx)
    return run


def announce(ui, voice, instruction, fallback):
    """Say something nobody asked for, in Apollo's own voice if it can."""
    live = voice.live if voice is not None else None
    held = LISTENING if (voice is not None and voice.auto_vad) else IDLE
    ui.status(SPEAKING)
    try:
        if live is not None and live.prompt(instruction):
            live.wait_for_audio(timeout=10)
            live.wait_until_quiet()
        else:
            ui.turn("Apollo", fallback)
            speak(fallback)
    finally:
        ui.status(held)


def fire_reminder(ui, voice, reminder, late):
    text = reminder.get("text", "")
    instruction = (f"A reminder the user set is due now: \"{text}\". Tell them in "
                   f"one short sentence, in the language they last spoke"
                   + (", and say it's a little late." if late else "."))
    announce(ui, voice, instruction, f"Reminder: {text}")
```
8. `Voice.__init__(self, ui, on_level=None, on_user_text=None, on_heard=None, on_reply=None, on_activity=None, run_tool=None)` stores them; `Voice.open` builds the session with:
```python
            live = gemini_live.LiveSession(
                on_audio=capture.feed, auto_vad=auto_vad,
                on_user_text=self.on_user_text, on_text=self.on_reply,
                on_heard=self.on_heard, on_user_turn=tools.new_user_turn,
                on_activity=self._activity, on_tool_call=self.run_tool,
                tools=tools.gemini_declarations() if self.run_tool else None)
```
and
```python
    def _activity(self, kind, detail):
        if self.on_activity is None:
            return
        words = tools.TOOL_LABELS.get(detail) if kind == "tool" else ACTIVITY_WORDS.get(kind)
        self.on_activity(words or detail)
```
9. `run_loop`: hold `TURN_GATE` around each turn:
```python
        if voice.ready and voice.auto_vad:
            with TURN_GATE:
                always_listening_turn(ui, voice)
            continue
        ...
        try:
            with TURN_GATE:
                push_to_talk_turn(ui, whisper, voice)
        finally:
            ui.status(IDLE)
```
Rule: always_listening_turn polls `next_turn` for 0.25 s inside the gate; the watcher waits at most one poll. Recorded as acceptable.
10. Claude path: `TOOLS = tools.claude_tools() + [<deep_research dict>, WEB_SEARCH]` (delete the `control_pc` entry); `_run_tool`:
```python
        if block.name == "deep_research":
            return deep_research(args.get("question", ""), ui)
        if block.name in tools.REGISTRY:
            return json.dumps(tools.run(block.name, args, tools.Context(
                show=getattr(ui, "visual", None), activity=getattr(ui, "activity", None))))
        return f"Failed: unknown tool '{block.name}'."
```
In `SYSTEM_PROMPT`, replace the paragraph starting "You can control the PC with the control_pc tool" with: "You can act on this PC through your tools - open and close apps, websites, files and folders, control media, volume and windows, type text, press keys, set reminders, and look up live market data. Whenever the request is really a command, call the tool instead of talking about it, then confirm in one short sentence what happened, or say briefly that it failed." Add to the first paragraph: "Reply in the language the user spoke - Arabic or English."
11. `ConsolePrinter` gains `def visual(self, visual): print(f"  [visual] {list((visual or {}).keys())}")` and `def activity(self, text): print(f"  ... {text}")`. Console `main()` passes `on_heard=ui.partial, on_reply=lambda t: None, on_activity=ui.activity, run_tool=tool_runner(ui)` and starts `reminders.start_watcher(lambda r, late: fire_reminder(ui, voice, r, late), TURN_GATE, lambda: False)`.

- [ ] **Step 4: Implement `apollo.py`:**

1. `import turnview` and `import reminders`.
2. `WebReporter.__init__` gains `on_visual=None, on_activity=None`; add:
```python
    def visual(self, visual):
        """A chart or cards from a tool. Native overlay only, like `partial`."""
        if self.on_visual is not None and visual:
            self.on_visual(visual)

    def activity(self, text):
        """What Apollo is doing right now, in a few words."""
        if self.on_activity is not None and text:
            self.on_activity(text)
        self._call("note", text)
```
3. `Apollo.__init__`: `self.view = turnview.TurnView()`.
4. `on_status`: when `delay == 0.0` (a fresh turn), also `self.view.reset()`.
5. `on_turn`, `on_partial`, new `on_visual`, `on_activity` all render through the view:
```python
    def _render(self, frame):
        if self.orb is None:
            return
        role, text, visual = frame
        if text or visual:
            self.orb.set_content(role, text, visual)

    def on_turn(self, speaker, text, visual=None):
        if not text:
            return
        if speaker == "You":
            self._render(self.view.heard(text, final=True))
        else:
            if visual:
                self.view.show(visual)
            self._render(self.view.replied(text))

    def on_partial(self, text):
        if text:
            self._render(self.view.heard(text))

    def on_visual(self, visual):
        self._render(self.view.show(visual))

    def on_activity(self, text):
        self.view.doing(text)
```
6. `on_loaded`: pass `on_visual=self.on_visual, on_activity=self.on_activity` to `WebReporter`.
7. `worker`: `whisper = assistant.load_whisper()` (no "Loading Whisper" note; it is background now). Build the voice with:
```python
        self.voice = assistant.Voice(
            ui, on_level=self.on_level,
            on_user_text=assistant.agent_interrupt(ui),
            on_heard=ui.partial,
            on_reply=lambda text: ui.turn("Apollo", text),
            on_activity=ui.activity,
            run_tool=assistant.tool_runner(ui))
```
and after `self.listen_toggle.start()`:
```python
        # Reminders you set by voice come back in Apollo's voice, and wait for
        # any turn in progress to finish first (see assistant.TURN_GATE).
        reminders.start_watcher(
            lambda reminder, late: assistant.fire_reminder(ui, self.voice, reminder, late),
            assistant.TURN_GATE, self.stopping.is_set)
```

- [ ] **Step 5: Run** the full suite — Expected: all pass. Update `tests/test_run_loop.py` only if its fakes need `heard_text` (they don't: always-listening path).
- [ ] **Step 6: Commit** `git add -A && git commit -m "Wire tools, live transcript, visuals and reminders into Apollo"`

---

### Task 8: Live acceptance run and README

**Files:**
- Create: `probes/probe_tools_live.py`
- Modify: `README.md`

- [ ] **Step 1: Write the probe** — drives a real `LiveSession` (push-to-talk mode, no microphone input needed) with text turns through `prompt()`, running the real tool registry except power (replaced by a recorder), and records every tool call, result and reply:

```python
# FILE: probes/probe_tools_live.py
"""End-to-end: does Gemini actually drive Apollo's tools?

Sends typed requests into a real Gemini Live session (the same one Apollo
uses) and lets it call the real tools - it WILL open and close Notepad, read
the volume, fetch market data and open a TradingView tab. Power actions are
replaced by a recorder, so nothing can sleep or shut the PC down.

Run:  .venv/Scripts/python.exe probes/probe_tools_live.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gemini_live  # noqa: E402
import pc_control  # noqa: E402
import tools  # noqa: E402

POWER = []
pc_control._run = lambda argv: POWER.append(argv)
pc_control._suspend = lambda: POWER.append("sleep")

STEPS = [
    "Open Notepad.",
    "Close Notepad.",
    "What's my volume at right now?",
    "Show me Nvidia's chart for the last five days.",
    "How are Apple and Tesla doing today?",
    "Remind me in 45 minutes to stretch.",
    "What reminders do I have?",
    "Cancel the stretch reminder.",
    "افتح المفكرة",
    "سكّر المفكرة",
    "Shut down the computer.",
    "Open the TradingView chart for Nvidia.",
]


def main():
    calls, shown = [], []

    def run_tool(name, args):
        result = tools.run(name, args, tools.Context(show=shown.append))
        calls.append((name, args, result))
        return result

    live = gemini_live.LiveSession(
        on_tool_call=run_tool, tools=tools.gemini_declarations(), auto_vad=False)
    live.start()
    print("model:", live.model)
    try:
        for step in STEPS:
            tools.new_user_turn()
            before = len(calls)
            t0 = time.monotonic()
            live.prompt(step)
            live.wait_for_audio(timeout=15)
            live.wait_until_quiet(timeout=40)
            time.sleep(0.5)
            print("=" * 70)
            print("USER :", step)
            for name, args, result in calls[before:]:
                print("TOOL :", name, args, "->", {k: result[k] for k in list(result)[:4]})
            print("SAID :", live.reply_text())
            print(f"TIME : {time.monotonic() - t0:.1f}s")
    finally:
        live.close()
    print("=" * 70)
    print("visuals shown:", len(shown), "| power calls (must be []):", POWER)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it** with keys loaded from the user environment. Expected: each English/Arabic step calls the matching tool with `ok: True`; the chart step shows a visual; "Shut down" returns `needs_confirmation` and `POWER == []`; Arabic steps are answered in Arabic.
- [ ] **Step 3: Smoke run** Apollo for ~40 s (keys from user env): Gemini connects with `native-audio-latest`, no tracebacks; quit with the chord.
- [ ] **Step 4: README** — update the intro diagram and "What it can do" to say that ordinary conversation now acts (tool list), that search and market data are live, that Apollo answers in Arabic or English, that reminders work by voice, the model list and `APOLLO_GEMINI_MODEL`, and that `gemini-3.8-live` needs billing enabled; the Files table gains `tools.py`, `market.py`, `turnview.py`, `presence.py`.
- [ ] **Step 5: Commit** `git add -A && git commit -m "Live acceptance probe and README for Apollo's hands"`
