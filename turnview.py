"""What the overlay shows for the turn in progress.

A turn now arrives in pieces from different threads: your words as Gemini
transcribes them, a chart pushed by a tool before a word of the answer
exists, the answer itself streaming in as it is spoken, and your final
transcript - which in always-listening lands *after* the answer. This is the
one place that decides what all of that adds up to on screen, so the rules
live somewhere they can be tested:

- your words show until there is an answer or something to look at;
- a chart or cards belong to the answer, and stay with it as it grows;
- your final transcript never wipes an answer that is already up;
- but fresh live words after an answer are a new turn, and replace it.
"""

from overlay_content import APOLLO, USER


class TurnView:
    def __init__(self):
        self.reset()

    def reset(self):
        self.you = ""
        self.reply = ""
        self.visual = None
        self.activity = ""

    def heard(self, text, final=False):
        if (self.reply or self.visual) and not final:
            self.reset()
        self.you = text or ""
        return self.frame()

    def replied(self, text):
        self.reply = text or ""
        self.activity = ""
        return self.frame()

    def show(self, visual):
        if visual:
            self.visual = visual
        return self.frame()

    def doing(self, text):
        self.activity = text or ""
        return self.frame()

    def frame(self):
        if self.reply or self.visual:
            return (APOLLO, self.reply, self.visual)
        return (USER, self.you, None)
