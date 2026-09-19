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
