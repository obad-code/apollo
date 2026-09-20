import overlay_content as oc


class Metrics(oc.Metrics):
    """Proportional-ish measuring, so the tests do not need a font."""

    def width_of(self, text):
        return len(text) * self.char_w


def test_is_rtl():
    assert oc.is_rtl("سهم إنفيديا صعد اليوم")
    assert oc.is_rtl("افتح المفكرة")
    assert not oc.is_rtl("open notepad")
    assert not oc.is_rtl("NVDA 222.27")
    assert oc.is_rtl("NVDA: سهم إنفيديا صعد 2.1% اليوم")     # mostly Arabic


def test_arabic_wraps_right_to_left():
    text = "سهم إنفيديا صعد اثنين فاصلة واحد بالمئة اليوم وهذا أداءه آخر أسبوعين كاملين"
    plan = oc.layout(oc.APOLLO, text, None, Metrics(8.0), 560)
    block = plan["blocks"][0]
    assert block["rtl"] is True
    assert len(block["lines"]) >= 2
    for line in block["lines"]:
        assert line["x"] >= oc.PAD_X
        assert line["x"] + len(line["text"]) * 8.0 <= 560 - oc.PAD_X + 1


def test_english_is_unchanged():
    plan = oc.layout(oc.USER, "open chrome and show me nvidia", None, Metrics(8.0), 560)
    block = plan["blocks"][0]
    assert block["rtl"] is False
    assert block["lines"][0]["text"] == "open chrome and show me nvidia"


def test_lines_carry_word_ends_for_the_reveal():
    plan = oc.layout(oc.APOLLO, "one two three", None, Metrics(8.0), 560)
    line = plan["blocks"][0]["lines"][0]
    assert line["words"][-1] == len(line["text"])
    assert line["words"][0] == 3                      # "one"
