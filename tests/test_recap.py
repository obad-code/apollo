"""The day's recap: no longer something that happens to you when Apollo
starts, which you could not get a word in over - it is there when you ask
for it ("brief me"), as an ordinary answer, and Ctrl+Alt cuts it off like
any other."""
import threading
from types import SimpleNamespace

import apollo
import tools


class _Schedule:
    def due(self, **_):
        return True

    def done(self):
        pass


def test_it_does_not_start_by_itself(monkeypatch):
    app = apollo.Apollo.__new__(apollo.Apollo)
    app.ui = SimpleNamespace(quiet=False)
    app.voice = object()
    app.briefing_thread = None
    app.turn_busy = False
    app.last_engaged = 0.0
    app.schedule = _Schedule()
    started = []
    monkeypatch.setattr(apollo.assistant, "talk_held", lambda: False)
    monkeypatch.setattr(threading.Thread, "start", lambda self: started.append(self.name))
    app.check_briefing(idle=0.0)
    assert started == []


def test_it_is_still_there_when_you_ask_for_it():
    assert "daily_briefing" in tools.REGISTRY


def test_the_talk_chord_cuts_apollo_off_mid_sentence():
    # Pressing Ctrl+Alt while he is talking - the recap you asked for, or
    # anything else - stops the speakers at once rather than at the end of
    # the sentence.
    import gemini_live

    live = gemini_live.LiveSession.__new__(gemini_live.LiveSession)
    cut = []
    live.hush = lambda: cut.append(True)
    live._on_user_turn = None
    live._loop = None
    live._play_open, live._reply_done, live._mic_open = (threading.Event() for _ in range(3))
    live._mark = lambda _: None
    live.begin_turn()
    assert cut == [True]
