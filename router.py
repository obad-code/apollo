"""Which backend answers this turn. There is now only one question to ask.

This used to be a keyword check: words like "refactor" or "architecture" sent
a turn to Claude, everything else to Gemini Live. It worked, and it was the
wrong idea, for a reason that has nothing to do with how accurate the keywords
were. The two backends speak in different voices - Puck for Gemini, Fish or
VoiceBox for Claude - so the rule was not choosing a model, it was choosing
which of two people answered you, based on whether your sentence happened to
contain a technical word. Ask about your weekend and get one voice; ask about
your code and get another. No amount of tuning the word list fixes that.

So conversation has one voice now. Every spoken turn - casual, technical,
simple, hard - goes to Gemini Live and comes back in Puck's. Claude is still
there and still does everything it did, but it is reached by *summoning an
agent by name*, not by saying a word that sounds difficult:

    LYLA · ATLAS · ECHO · NOVA · THE WORKSHOP · OPTIMO · HERMES

That check lives in `agents.detect`, and this module is a thin wrapper over
it. There is deliberately no `CLAUDE` route left to return: the only way to
get there is `AGENT`, which carries the name of whoever was called.
"""

import logging
from collections import namedtuple

import agents

log = logging.getLogger("apollo.router")

GEMINI = "gemini"
AGENT = "agent"

# Where it goes, why, and - if an agent was summoned - which one.
Route = namedtuple("Route", "name why agent")


def route_request(text):
    """Decide where one turn goes. Returns a Route.

    Gemini is not the default so much as the answer: conversation is what this
    assistant is, and conversation has one voice. The only thing that diverts
    a turn is calling one of the seven by name.
    """
    said = (text or "").strip()
    if not said:
        return Route(GEMINI, "nothing said", None)

    if (name := agents.detect(said)) is not None:
        return Route(AGENT, f"{name} summoned by name", name)

    return Route(GEMINI, "conversation", None)


def log_route(route, text):
    """One line per turn saying where it went and why."""
    label = "GEMINI LIVE" if route.name == GEMINI else f"AGENT {route.agent}"
    said = text if len(text) <= 70 else text[:67] + "..."
    log.info("-> %-11s  %-72s (%s)", label, repr(said), route.why)
