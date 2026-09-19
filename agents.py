"""The seven agents, and the only door Claude is reachable through.

Apollo answers with one voice. Everything you say to it - chat, a quick
command, a question about your own code, anything at all - is answered by
Gemini Live in Puck's voice, because having the voice change depending on what
you happened to ask about is worse than any routing decision it could be
buying.

Claude has not gone anywhere; it is just no longer something a *conversation*
can reach. It now sits behind an agent, and an agent has to be called by name:

    LYLA · ATLAS · ECHO · NOVA · THE WORKSHOP · OPTIMO · HERMES

None of them are built yet. This module is the boundary they will be built
behind, and until then `handle` is a placeholder that passes the request to
Claude and says which agent was asked for. That is deliberate: the boundary is
worth having now, while there is exactly one call site to keep honest, rather
than after seven of them exist.

The rule that matters, and the one to keep when the real agents land:
`assistant.ask_claude` is called from here and from nowhere else.
"""

import logging
import re

log = logging.getLogger("apollo.agents")

LYLA = "LYLA"
ATLAS = "ATLAS"
ECHO = "ECHO"
NOVA = "NOVA"
WORKSHOP = "THE WORKSHOP"
OPTIMO = "OPTIMO"
HERMES = "HERMES"

NAMES = (LYLA, ATLAS, ECHO, NOVA, WORKSHOP, OPTIMO, HERMES)

# Four of these are ordinary English words - you can echo a sentiment, read an
# atlas, and hermes is a courier. Matching them anywhere in a sentence would
# hand casual conversation to Claude, which is the exact thing this change
# exists to stop. So a name only counts as a summons when it is used to
# *address* someone: at the very start of what you said, or straight after a
# word that means you are about to name somebody.
_ADDRESS = r"(?:^|\b(?:hey|ok|okay|hi|yo|ask|tell|get|use|switch\ to)\s+)"
_SPOKEN = {
    LYLA: r"lyla",
    ATLAS: r"atlas",
    ECHO: r"echo",
    NOVA: r"nova",
    # "the" is optional because nobody says the article reliably out loud, and
    # Whisper drops it about as often as they do.
    WORKSHOP: r"(?:the\s+)?workshop",
    OPTIMO: r"optimo",
    HERMES: r"hermes",
}
_TRIGGERS = {
    name: re.compile(_ADDRESS + rf"(?P<name>{pattern})\b", re.IGNORECASE | re.VERBOSE)
    for name, pattern in _SPOKEN.items()
}


def detect(text):
    """Which agent was called by name, or None. None means Gemini answers.

    None is not a fallback here, it is the normal case: the only way to reach
    Claude is to ask for an agent, so anything this does not recognise is a
    conversation and belongs to the voice you are already talking to.
    """
    said = (text or "").strip()
    if not said:
        return None
    for name, trigger in _TRIGGERS.items():
        if trigger.search(said):
            return name
    return None


def handle(name, text, ui, ask):
    """Run one agent turn. A placeholder until the agents themselves exist.

    `ask` is `assistant.ask_claude`, passed in rather than imported so that
    the direction of the dependency says what the rule is: agents reach for
    Claude, and nothing reaches past them to it.

    Returns the reply text for the caller to speak and show.
    """
    log.info("%s summoned: %r", name, text[:70])
    if ui is not None:
        ui.note(f"{name} is not built yet - answering as Claude for now.")
    return ask(text, ui)
