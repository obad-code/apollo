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
