"""The double voice, the self-hearing and the typed "dddd" (Windows only)."""
import numpy as np

import gemini_live
import pc_control


def test_quiet_echo_is_not_loud_but_a_voice_is():
    quiet = (np.sin(np.arange(1600) / 5) * 800).astype(np.int16).tobytes()
    voice = (np.sin(np.arange(1600) / 5) * 12000).astype(np.int16).tobytes()
    assert not gemini_live.loud(quiet, 0.06)
    assert gemini_live.loud(voice, 0.06)
    assert not gemini_live.loud(b"", 0.06)


def test_typing_waits_for_the_chord_to_be_let_go():
    held = {"n": 3}

    def down(vk):
        return held["n"] > 0

    def sleep(_):
        held["n"] -= 1

    assert pc_control.wait_for_release(timeout=5, down=down, sleep=sleep)
    assert held["n"] == 0


def test_typing_gives_up_while_a_modifier_stays_down():
    assert not pc_control.wait_for_release(timeout=0, down=lambda vk: vk == 0x11,
                                           sleep=lambda _: None)
