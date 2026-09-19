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
