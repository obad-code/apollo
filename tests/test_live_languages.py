"""Arabic and English, and nothing else.

Left to detect the language itself, Gemini's transcription of you wandered:
the log has "ఆ మనం చూస్త" (Telugu) and "ครับ" (Thai) for what was Arabic
speech or a noise in the room, routed on as if you had said it. You speak
Saudi Arabic and English; the transcription is told so, the model is told
to answer in nothing else, and a line in any other script is not taken as
something you said.
"""
import agents
import gemini_live


def transcription():
    return gemini_live._config().input_audio_transcription


def test_transcription_is_limited_to_arabic_and_english():
    assert transcription().language_codes == ["ar-SA", "en-US"]


def test_the_names_you_call_are_in_its_vocabulary():
    vocabulary = transcription().custom_vocabulary
    for name in ("Apollo", "LYLA", "OSIRIS", *agents.NAMES):
        assert name in vocabulary


def test_both_modes_get_it():
    assert gemini_live._config(auto_vad=True).input_audio_transcription.language_codes == \
        ["ar-SA", "en-US"]


def test_the_model_is_told_to_answer_in_nothing_else():
    text = gemini_live.SYSTEM_INSTRUCTION
    assert "only Arabic or English" in text


def test_other_scripts_are_foreign():
    assert gemini_live.foreign("ఆ మనం చూస్త")
    assert gemini_live.foreign("ครับ")
    assert gemini_live.foreign("我想要")


def test_arabic_english_and_both_are_not():
    assert not gemini_live.foreign("الو تسمعني")
    assert not gemini_live.foreign("Apollo, open Chrome")
    assert not gemini_live.foreign("افتح لي TradingView")
    assert not gemini_live.foreign("Café 27GX700A")
    assert not gemini_live.foreign("  ... 42 ")       # nothing to judge by


def session():
    live = gemini_live.LiveSession.__new__(gemini_live.LiveSession)
    live._heard = []
    live._last_heard = 0.0
    live._in_flight = False
    live._discarded = False
    live.auto_vad = True
    live._on_user_turn = None
    live._on_user_text = None
    live.shown = []
    live._on_heard = live.shown.append
    return live


def test_a_foreign_line_is_not_taken_as_something_you_said():
    live = session()
    live._note_heard("ఆ మనం చూస్త")
    assert live._heard == [] and live.shown == []


def test_arabic_is():
    live = session()
    live._note_heard("الو تسمعني")
    assert live.shown == ["الو تسمعني"]
