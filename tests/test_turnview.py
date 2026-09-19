from overlay_content import APOLLO, USER
from turnview import TurnView


def test_your_words_then_the_reply():
    v = TurnView()
    assert v.heard("open chr") == (USER, "open chr", None)
    assert v.heard("open chrome") == (USER, "open chrome", None)
    assert v.replied("Opening") == (APOLLO, "Opening", None)
    assert v.replied("Opening Chrome.") == (APOLLO, "Opening Chrome.", None)


def test_visual_attaches_to_the_reply_even_before_words():
    v = TurnView()
    v.heard("show me nvidia")
    chart = {"chart": {"points": [1, 2, 3, 4]}}
    assert v.show(chart) == (APOLLO, "", chart)
    assert v.replied("Nvidia is up.") == (APOLLO, "Nvidia is up.", chart)


def test_final_transcript_after_reply_does_not_wipe_it():
    v = TurnView()
    v.replied("It's nine.")
    assert v.heard("what time is it", final=True) == (APOLLO, "It's nine.", None)
    assert v.you == "what time is it"


def test_new_live_words_after_a_reply_start_a_new_turn():
    v = TurnView()
    v.replied("It's nine.")
    assert v.heard("and tomor") == (USER, "and tomor", None)
    assert v.reply == ""


def test_activity_is_kept_until_the_reply():
    v = TurnView()
    v.doing("fetching NVDA")
    assert v.activity == "fetching NVDA"
    v.replied("Here")
    assert v.activity == ""
