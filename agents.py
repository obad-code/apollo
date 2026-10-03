"""The crew's names, as you say them.

Apollo has one voice, and it is his. You can call an agent by name -
"THEIA, حللي هالفكرة", "Moneypenny, how's Nvidia", "LYLA download this" - and
Apollo hears it like anything else you say: he hands the job to that agent
with the agent's tool (see `crew` and the ask_* tools) and tells you in his
own voice when it is done.

This used to be different. A name was a summons that took the turn away from
Gemini and gave it to Claude, who answered in a second voice (Fish or
VoiceBox). That is what "two voices answering, repeating each other" was:
the two paths raced whenever the name was made out late. So a name no longer
changes who speaks; it only says who should do the work, and Apollo - who
heard it - decides, with your word winning.

`detect` stays: it says which agent was named, for the log and the display.
`handle` stays for the old Claude path's tests and anything that still calls
it, and `assistant.ask_claude` is still reached from here and nowhere else.
"""

import logging
import re

log = logging.getLogger("apollo.agents")

LYLA = "LYLA"
THEIA = "THEIA"
MONEYPENNY = "MONEYPENNY"
Q = "Q"

NAMES = (LYLA, THEIA, MONEYPENNY, Q)

# A name only counts when it is used to *address* an agent: at the start of
# what you said, or straight after a word that means you are about to name
# one. "Q" in particular is a letter before it is a name.
_ADDRESS = r"(?:^|\b(?:hey|ok|okay|hi|yo|ask|tell|get|use|switch\ to|يا|خل|قل\ ل|خلي)\s*)"
_SPOKEN = {
    LYLA: r"(?:lyla|layla|leila|ليلى|ليلا|ليله)",
    THEIA: r"(?:theia|thea|tia|ثيا|ثيّا|تيا)",
    MONEYPENNY: r"(?:money\s*penny|moneypenny|موني\s*بيني|ميني\s*بيني|مني\s*بني)",
    Q: r"(?:q|cue|كيو)",
}
_TRIGGERS = {
    name: re.compile(_ADDRESS + rf"(?P<name>{pattern})(?![\w])", re.IGNORECASE | re.VERBOSE)
    for name, pattern in _SPOKEN.items()
}


def detect(text):
    """Which agent was named, or None."""
    said = (text or "").strip()
    if not said:
        return None
    for name, trigger in _TRIGGERS.items():
        if trigger.search(said):
            return name
    return None


def handle(name, text, ui, ask):
    """Put one turn to Claude in an agent's name. Kept for the old path."""
    log.info("%s summoned: %r", name, text[:70])
    return ask(text, ui)
