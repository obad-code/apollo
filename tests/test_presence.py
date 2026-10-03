import presence
from presence import IDLE, LISTENING, Presence, content_action

AFK = 2400


def test_peek_stays_open_through_input():
    p = Presence(AFK)
    p.toggle_peek()
    assert p.full
    for idle in (0.0, 0.1, 5.0, 0.0):          # typing, mouse moves
        assert p.check(idle) is False
    assert p.full


def test_peek_closes_only_on_second_toggle():
    p = Presence(AFK)
    p.toggle_peek()
    p.toggle_peek()
    assert not p.full


def test_afk_opens_and_input_closes():
    p = Presence(AFK)
    assert p.check(AFK + 1) is True and p.full
    assert p.check(0.2) is True and not p.full


def test_peek_survives_going_afk_and_coming_back():
    p = Presence(AFK)
    p.toggle_peek()
    p.check(AFK + 10)
    p.check(0.0)
    assert p.full


def test_peek_toggle_while_afk_closes():
    p = Presence(AFK)
    p.check(AFK + 1)
    assert p.full
    p.toggle_peek()          # opens peek (already full) ...
    p.toggle_peek()          # ... and closing it must close the AFK display too
    assert not p.full
    assert p.check(0.0) is False and not p.full


def test_content_fresh_turn_clears_now():
    assert content_action(IDLE, LISTENING, 4.0) == 0.0
    assert content_action(None, LISTENING, 4.0) == 0.0


def test_content_back_to_listening_after_reply_lingers():
    assert content_action("Speaking", LISTENING, 4.0) == 4.0
    assert content_action("Thinking", LISTENING, 4.0) == 4.0


def test_content_idle_lingers_and_repeats_do_nothing():
    assert content_action("Speaking", IDLE, 4.0) == 4.0
    assert content_action(LISTENING, LISTENING, 4.0) is None
    assert content_action(LISTENING, "Thinking", 4.0) is None


def test_phase_names_match_assistant():
    import assistant
    assert presence.IDLE == assistant.IDLE
    assert presence.LISTENING == assistant.LISTENING


# -- asleep: the idle screen --------------------------------------------------

def test_falls_asleep_after_the_idle_time_and_input_wakes_it():
    p = Presence(AFK)
    assert p.check(AFK - 1, now=100.0) is False and not p.asleep
    assert p.check(AFK + 1, now=101.0) is True
    assert p.asleep and p.full                # the idle screen is the display
    assert p.check(0.3, now=102.0) is True
    assert not p.asleep and not p.full        # back to the desktop


def test_asleep_over_the_dashboard_wakes_back_to_it():
    p = Presence(AFK)
    p.toggle_peek()
    p.check(AFK + 1, now=10.0)
    assert p.asleep and p.full
    p.check(0.0, now=11.0)
    assert not p.asleep and p.full            # the dashboard you left open


def test_a_voice_counts_as_someone_being_there():
    """Nothing reaches GetLastInputInfo when you speak, so the idle time keeps
    growing; `touch` is how a voice wakes the screen - and keeps it awake."""
    p = Presence(AFK)
    p.check(AFK + 5, now=500.0)
    assert p.asleep
    p.touch(500.5)
    assert p.check(AFK + 6, now=501.0) is True and not p.asleep
    assert p.check(AFK + 60, now=560.0) is False and not p.asleep
    # ...until the room is quiet for the whole idle time again.
    assert p.check(AFK * 2, now=500.5 + AFK + 1) is True and p.asleep


def test_a_full_screen_program_keeps_it_awake():
    """Ten quiet minutes is also most of a film. A full-screen player, a game
    or a slideshow is someone using the machine without touching it."""
    p = Presence(AFK)
    assert p.check(AFK + 1, now=1.0, screen_busy=True) is False
    assert not p.asleep and not p.full
    assert p.check(AFK + 2, now=2.0, screen_busy=False) is True and p.asleep


def test_already_asleep_is_not_woken_by_a_busy_screen():
    p = Presence(AFK)
    p.check(AFK + 1, now=1.0)
    assert p.check(AFK + 2, now=2.0, screen_busy=True) is False and p.asleep


def test_the_peek_chord_wakes_it():
    p = Presence(AFK)
    p.check(AFK + 1, now=1.0)
    p.toggle_peek()
    assert not p.asleep and p.full


# -- VoiceWake: enough voice, for long enough ----------------------------------

def test_a_click_or_a_cough_does_not_wake_it():
    wake = presence.VoiceWake(threshold=0.25, needed=4, window=6)
    for level in (0.9, 0.0, 0.0, 0.8, 0.0, 0.0, 0.0, 0.9):
        assert wake.feed(level) is False


def test_speaking_wakes_it_and_it_starts_over_after():
    wake = presence.VoiceWake(threshold=0.25, needed=4, window=6)
    heard = [wake.feed(level) for level in (0.4, 0.5, 0.1, 0.6, 0.7)]
    assert heard == [False, False, False, False, True]
    assert wake.feed(0.6) is False            # one wake per utterance


def test_a_held_idle_screen_is_only_left_by_back():
    p = presence.Presence(afk_seconds=600, hold=True)
    p.check(idle=700, now=1000.0)
    assert p.asleep and p.full
    assert p.check(idle=0, now=1001.0) is False and p.asleep      # the mouse moved: still idle
    p.touch(1002.0)
    assert p.check(idle=0, now=1003.0) is False and p.asleep      # a voice: still idle
    p.wake_now()
    assert not p.asleep and not p.full


def test_without_hold_the_mouse_still_wakes_it():
    p = presence.Presence(afk_seconds=600)
    p.check(idle=700, now=1000.0)
    p.check(idle=0, now=1001.0)
    assert not p.asleep
