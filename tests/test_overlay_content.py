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


def test_a_stock_answer_lays_out_as_one_card_not_a_chart_and_four_tiles():
    """Asking about a stock turns the card into that stock's card.

    The generic chart-plus-cards shape says the same things in more space:
    a label, a plot, then Last / Today / High / Low as four tiles. The stock
    block is one row of identity and price, the curve, and the valuation.
    """
    metrics = overlay_content.Metrics(8.0, overlay_content.LINE_H)
    visual = {"stock": {"symbol": "NVDA", "name": "NVIDIA", "price": 222.27,
                        "change_pct": 1.34, "points": [200.0, 210.0, 222.27],
                        "logo": r"C:\x\NVDA.png", "target": 327.7,
                        "upside": 47.43, "pe": 28.1, "unit": "$"}}
    plan = overlay_content.layout("apollo", "Nvidia closed at 222.27.",
                                  visual, metrics, 378)

    kinds = [b["kind"] for b in plan["blocks"]]
    assert "stock" in kinds, kinds
    assert "chart" not in kinds and "cards" not in kinds, (
        "the stock block did not replace the generic chart and tiles")

    block = next(b for b in plan["blocks"] if b["kind"] == "stock")
    assert block["symbol"] == "NVDA"
    assert block["points"] == [200.0, 210.0, 222.27]
    assert block["target"] == 327.7
    assert block["h"] > 60
    assert plan["height"] >= block["y"] + block["h"]


def test_a_stock_block_is_dropped_when_it_will_not_fit():
    """The same rule the chart follows: better no visual than a clipped one."""
    metrics = overlay_content.Metrics(8.0, overlay_content.LINE_H)
    visual = {"stock": {"symbol": "NVDA", "name": "NVIDIA", "price": 1.0,
                        "change_pct": 0.0, "points": [1.0, 2.0], "logo": None,
                        "target": None, "upside": None, "pe": None, "unit": "$"}}
    plan = overlay_content.layout("apollo", "A very long answer. " * 12,
                                  visual, metrics, 380, max_height=150)

    assert "stock" not in [b["kind"] for b in plan["blocks"]]
    assert plan["height"] <= 150
