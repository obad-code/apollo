"""Two decisions apollo.py makes many times a second, kept free of windows.

When is the full display open, and what does a change of phase do to the
words hanging under the overlay's mesh? Both used to live inside `Apollo`,
which cannot be built without a WebView2 window, so neither could be tested -
and both had bugs that only showed up in use: CTRL+` closed itself the moment
you touched the keyboard, and in always-listening every answer was wiped a
quarter of a second after it appeared.
"""

from collections import deque

IDLE = "Idle"             # the same strings as assistant.IDLE / LISTENING;
LISTENING = "Listening"   # a test holds them in step without importing it


class Presence:
    """Whether the full display is up, and whether Apollo is asleep on it.

    Two independent reasons for the display. CTRL+` (`peek_open`) is yours:
    it stays until you press the chord again, whatever you do in between.
    Being away (`afk_open`) is the machine's: after `afk_seconds` without
    input Apollo falls `asleep` - the display becomes the idle screen, over
    whatever was there - and the very next keypress, mouse move or voice
    wakes it. Asleep over the dashboard wakes back to the dashboard; asleep
    over the desktop wakes back to the desktop.
    """

    def __init__(self, afk_seconds):
        self.afk_seconds = afk_seconds
        self.peek_open = False
        self.afk_open = False
        self.asleep = False
        self._touched = None      # the last sign of you that was not input
        self._slept_at = None     # when you asked it to sleep; see `sleep_now`

    @property
    def full(self):
        return self.peek_open or self.afk_open

    def toggle_peek(self):
        self.peek_open = not self.peek_open
        # The chord is a keypress, so it is also you coming back.
        self.asleep = False
        if not self.peek_open:
            # Pressing the chord to close is an answer to "is it open?", not
            # to "which reason opened it?" - so it closes whichever it was.
            self.afk_open = False

    def touch(self, now):
        """Someone is here who has not touched anything: a voice, a turn.

        GetLastInputInfo only counts keys and the mouse, so without this the
        idle time keeps growing while you talk to Apollo from across the room.
        """
        self._touched = now

    # How long after an asked-for sleep a sign of you still counts as the
    # asking: letting go of the chord you pressed to say it.
    GRACE = 0.5

    def sleep_now(self, now):
        """Asleep at once, because you asked - by voice, or by locking the PC.

        Everything up to now was part of asking: the chord, your sentence,
        Apollo saying it will. So only something after `now` wakes it.
        """
        self.asleep = True
        self._slept_at = now
        if not self.peek_open:
            self.afk_open = True

    def check(self, idle, now=None, screen_busy=False):
        """Feed seconds-since-last-input. True if `full` or `asleep` changed.

        `screen_busy` - a full-screen program is up - keeps Apollo from
        falling asleep, because ten quiet minutes is also most of a film. It
        never wakes an Apollo that is already asleep.
        """
        if self._touched is not None and now is not None:
            idle = min(idle, max(0.0, now - self._touched))
        before = (self.full, self.asleep)
        if self._slept_at is not None and now is not None:
            if now - idle <= self._slept_at + self.GRACE:
                return False                  # nothing since you asked
            self._slept_at = None
        if idle < self.afk_seconds:
            self.asleep = False
        elif not self.asleep and not screen_busy:
            self.asleep = True
        if not self.peek_open:
            self.afk_open = self.asleep
        return (self.full, self.asleep) != before


class VoiceWake:
    """Whether the microphone has heard someone speaking, rather than a noise.

    Fed the 0-1 level of each 100 ms block. `needed` loud blocks among the
    last `window` is a sentence starting; a door, a click or a cough is one
    or two blocks and does not get there. It answers True once per
    utterance and starts counting again.
    """

    def __init__(self, threshold=0.3, needed=4, window=6):
        self.threshold = threshold
        self.needed = needed
        self._recent = deque(maxlen=window)

    def feed(self, level):
        self._recent.append(level >= self.threshold)
        if sum(self._recent) >= self.needed:
            self._recent.clear()
            return True
        return False


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
