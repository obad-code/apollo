import orb
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


def test_arabic_is_revealed_a_line_at_a_time_not_a_word(monkeypatch):
    """Arabic letters join, and the layout measures spans left to right.

    An RTL line is drawn from its right edge, so a span taken off the left
    cuts the wrong piece out of the rendered line - and because the letters
    join, what it shows are shapes that do not exist in the word. The reveal
    steps a whole line at a time instead.
    """
    drawn = []

    class Fake(orb.Orb):
        def __init__(self):
            pass

        def top_row_height(self):
            return 0

        def _blit(self, g, bitmap, dx, dy, sx, sy, sw, sh, attrs):
            drawn.append((sx, sw))

        def _fade_attrs(self, scale):
            return None

    plan = {"width": 400, "blocks": [{
        "kind": "text", "rtl": True,
        "lines": [{"text": "سهم إنفيديا أغلق اليوم", "x": 0, "y": 0,
                   "width": 300, "spans": [(0, 60), (60, 150), (150, 220), (220, 300)]}],
    }]}
    view = Fake()
    view._content = {"bitmap": None, "layout": plan, "at": 0.0}
    view._draw_body(None, 0, 0, 400, now=99.0, fade=1.0)

    assert drawn == [(0, 300)], f"an RTL line was cut into pieces: {drawn}"
