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
