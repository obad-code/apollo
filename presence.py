"""Two decisions apollo.py makes many times a second, kept free of windows.

When is the full display open, and what does a change of phase do to the
words hanging under the overlay's mesh? Both used to live inside `Apollo`,
which cannot be built without a WebView2 window, so neither could be tested -
and both had bugs that only showed up in use: CTRL+` closed itself the moment
you touched the keyboard, and in always-listening every answer was wiped a
quarter of a second after it appeared.
"""

IDLE = "Idle"             # the same strings as assistant.IDLE / LISTENING;
LISTENING = "Listening"   # a test holds them in step without importing it


class Presence:
    """Whether the full display is up, and why.

    Two independent reasons. CTRL+` (`peek_open`) is yours: it stays until
    you press the chord again, whatever you do in between. Being away
    (`afk_open`) is the machine's: it opens after `afk_seconds` without input
    and closes on the very next keypress or mouse move.
    """

    def __init__(self, afk_seconds):
        self.afk_seconds = afk_seconds
        self.peek_open = False
        self.afk_open = False

    @property
    def full(self):
        return self.peek_open or self.afk_open

    def toggle_peek(self):
        self.peek_open = not self.peek_open
        if not self.peek_open:
            # Pressing the chord to close is an answer to "is it open?", not
            # to "which reason opened it?" - so it closes whichever it was.
            self.afk_open = False

    def check(self, idle):
        """Feed seconds-since-last-input. True if `full` changed."""
        before = self.full
        if not self.peek_open:
            self.afk_open = idle >= self.afk_seconds
        return self.full != before


def content_action(prev, state, linger):
    """What a phase change does to the overlay's words.

    Returns the delay before they collapse, or None to leave them alone.
    A repeated phase is never an event - that repetition, four times a
    second in always-listening, is what used to wipe every answer.
    """
    if state == prev:
        return None
    if state == LISTENING:
        # From rest it is a fresh turn: the last answer goes now. From
        # speaking or thinking it is always-listening settling back after a
        # reply: the reply stays up long enough to read.
        return 0.0 if prev in (None, IDLE) else linger
    if state == IDLE:
        return linger
    return None
