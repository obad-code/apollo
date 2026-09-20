"""What a laid-out answer carries, beyond the text itself."""
import overlay_content


def test_each_line_carries_where_its_words_sit_in_pixels():
    """The reveal arrives a word at a time, so it needs each word's box.

    Character offsets are not enough: the painter blits a rectangle out of a
    pre-rendered bitmap, and to cut one word out of a line it needs that
    word's left and right edge in pixels.
    """
    metrics = overlay_content.Metrics(8.0, overlay_content.LINE_H)
    plan = overlay_content.layout("apollo", "one two three", None, metrics, 400)
    line = plan["blocks"][0]["lines"][0]

    assert len(line["spans"]) == 3, line["spans"]
    assert line["spans"][0][0] == 0
    for (x0, x1) in line["spans"]:
        assert x1 > x0
    assert line["spans"][0][1] <= line["spans"][1][0]
    assert line["spans"][-1][1] <= line["width"] + 1
