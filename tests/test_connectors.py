"""LYLA's connectors: the MCP servers in connectors.json, through Claude."""
import json
from types import SimpleNamespace

import pytest

import connectors
import crew


def write(tmp_path, entries):
    path = tmp_path / "connectors.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return str(path)


def test_servers_come_from_the_file_and_tokens_from_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("GMAIL_MCP_TOKEN", "secret")
    path = write(tmp_path, [
        {"name": "Gmail", "url": "https://mail.example/mcp", "token_env": "GMAIL_MCP_TOKEN"},
        {"name": "plain", "url": "http://not-https.example/mcp"},
        {"name": "gmail", "url": "https://dupe.example/mcp"},
        "junk"])
    assert connectors.load(path) == [{"name": "gmail", "url": "https://mail.example/mcp",
                                      "token": "secret"}]


def test_a_missing_file_is_no_connectors(tmp_path):
    assert connectors.load(str(tmp_path / "none.json")) == []


def test_every_server_gets_its_toolset():
    request = connectors.request_for("check mail", [
        {"name": "gmail", "url": "https://a/mcp", "token": "t"},
        {"name": "slack", "url": "https://b/mcp", "token": ""}])
    assert connectors.BETA in request["betas"]
    assert request["mcp_servers"][0]["authorization_token"] == "t"
    assert "authorization_token" not in request["mcp_servers"][1]
    assert request["tools"] == [{"type": "mcp_toolset", "mcp_server_name": "gmail"},
                                {"type": "mcp_toolset", "mcp_server_name": "slack"}]


class Stream:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self.message


def client_answering(message, seen):
    def stream(**request):
        seen.update(request)
        return Stream(message)
    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)))


def test_ask_returns_the_text(monkeypatch):
    seen = {}
    message = SimpleNamespace(stop_reason="end_turn", content=[
        SimpleNamespace(type="mcp_tool_use"), SimpleNamespace(type="text", text="SUMMARY: 2 new.")])
    text = connectors.ask("new mail?", [{"name": "gmail", "url": "https://a/mcp", "token": ""}],
                          client=client_answering(message, seen))
    assert text == "SUMMARY: 2 new." and seen["messages"][0]["content"] == "new mail?"


def test_ask_needs_a_connector():
    with pytest.raises(RuntimeError, match="No connectors"):
        connectors.ask("x", [])


def test_a_connectors_job_skips_the_reading_and_goes_to_them(tmp_path, monkeypatch):
    asked = []
    monkeypatch.setattr(connectors, "ask", lambda task: asked.append(task) or "SUMMARY: Done.")
    desk = crew.LylaDesk(think=crew.lyla_think, path=str(tmp_path / "r.json"))
    desk.run({"id": 1, "task": "any mail from Ahmed", "stock": "", "symbol": "",
              "connectors": True, "agent": "LYLA", "asked": 0})
    assert asked == ["any mail from Ahmed"]
    assert desk.reports[0]["brain"] == "Claude · connectors"
