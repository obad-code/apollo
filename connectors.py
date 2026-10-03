"""Connectors: your email, messages, calendar and the rest, through MCP.

"شوف ايميلاتي المهمة", "what did Ahmed send me on Slack", "anything new in
my calendar today?" - Apollo hands a job like that to LYLA, and she does it
with Claude, which connects to the MCP servers you list and uses their tools
(Anthropic's MCP connector: the connection is made on Anthropic's side, so
nothing has to run on your PC).

The servers are listed in %LOCALAPPDATA%\\Apollo\\connectors.json:

    [
      {"name": "gmail",  "url": "https://<a remote MCP server>/mcp",
       "token_env": "GMAIL_MCP_TOKEN"},
      {"name": "slack",  "url": "https://<...>/mcp", "token_env": "SLACK_MCP_TOKEN"}
    ]

`token_env` names the environment variable that holds that server's token
(setx GMAIL_MCP_TOKEN "..."), so no token is ever written in a file. A server
with no token leaves it out.

Rules she works by: she reads and reports. Anything that sends, deletes,
moves or changes something is done only when your request asked for exactly
that, and Apollo has read it back to you first.

Model: CONNECTORS_MODEL, Claude Sonnet 5.5 by default - the everyday-cost
choice; set claude-opus-5-5 for the strongest.
"""

import json
import logging
import os
import re

log = logging.getLogger("apollo.connectors")

PATH = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                    "Apollo", "connectors.json")
MODEL = os.environ.get("CONNECTORS_MODEL") or "claude-sonnet-5-5"
BETA = "mcp-client-2025-11-20"

SYSTEM = (
    "You are LYLA, an agent of Apollo, the user's personal desktop assistant. You "
    "have the user's own accounts through the connected tools - email, messages, "
    "calendar, notes and whatever else is connected. Do the job you are given "
    "with them. Read freely; never send, reply, delete, archive, move, accept or "
    "change anything unless the job explicitly asks for exactly that action. "
    "Private content stays private: report only what the job needs.\n\n"
    "Answer in exactly this shape. The first line is `SUMMARY:` and two short "
    "sentences Apollo can say out loud, in the language the job was given in "
    "(Saudi dialect if Arabic). Then a blank line, then the details under plain "
    "headings - who, what, when - most important first. Under 350 words.")


def load(path=None):
    """The servers that can be used: [{name, url, token}]. Bad entries are skipped."""
    try:
        with open(path or PATH, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    servers = []
    for entry in data if isinstance(data, list) else []:
        if not isinstance(entry, dict):
            continue
        name = re.sub(r"[^a-z0-9_-]", "", str(entry.get("name", "")).lower())[:40]
        url = str(entry.get("url", "")).strip()
        if not name or not url.startswith("https://") or any(s["name"] == name for s in servers):
            continue
        token = os.environ.get(str(entry.get("token_env") or ""), "").strip()
        servers.append({"name": name, "url": url, "token": token})
    return servers


def request_for(task, servers, model=MODEL):
    """The Messages API request: every server, and a toolset for each."""
    mcp_servers = []
    for server in servers:
        one = {"type": "url", "url": server["url"], "name": server["name"]}
        if server.get("token"):
            one["authorization_token"] = server["token"]
        mcp_servers.append(one)
    return dict(
        model=model, max_tokens=16000, system=SYSTEM,
        betas=[BETA, "server-side-fallback-2026-07-01"], fallbacks="default",
        output_config={"effort": "medium"},
        mcp_servers=mcp_servers,
        tools=[{"type": "mcp_toolset", "mcp_server_name": s["name"]} for s in servers],
        messages=[{"role": "user", "content": task}])


def ask(task, servers=None, client=None):
    """Do one job with the connectors. Returns the answer text."""
    servers = load() if servers is None else servers
    if not servers:
        raise RuntimeError("No connectors are set up yet (connectors.json).")
    if client is None:
        import assistant
        client = assistant.client
    with client.beta.messages.stream(**request_for(task, servers)) as stream:
        message = stream.get_final_message()
    if message.stop_reason == "refusal":
        raise RuntimeError("Claude declined that one.")
    text = " ".join(b.text for b in message.content if b.type == "text").strip()
    if not text:
        raise RuntimeError("The connectors brought nothing back.")
    return text


def names():
    return [s["name"] for s in load()]
