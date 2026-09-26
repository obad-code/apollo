"""What the design check found in the display the cloud built, fixed:

- LYLA's bar moved by its width, a layout property, every frame; it moves
  by transform now.
- The modes along the bottom were 10px - under the 11px this display keeps
  to for anything you read or press.
- The trading desk's footnote was a sentence in small spaced capitals, and
  the agents' "pick one" line was spaced like a label; both read as text now.
- Four dots pulsed with nothing live behind them (the desk's head, the agent
  preview, the console's beacon, the dots under the wordmark); they are lit,
  not blinking.
- The desk's words were in Space Grotesk, the face every generated interface
  reaches for; they are in Thmanyah, Apollo's own.
"""
import pathlib
import re

FULL = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full"
CSS = (FULL / "app.css").read_text(encoding="utf-8")
LYLA = (FULL / "lyla.js").read_text(encoding="utf-8")


def rule(selector):
    found = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
    assert found, selector
    return found.group(1)


def test_lylas_bar_moves_by_transform_not_width():
    bar = rule("#lyla-bar")
    assert "transition: width" not in bar and "transform" in bar
    assert "style.width" not in LYLA.split("if (this.bar) {")[1].split("}")[0]


def test_the_modes_are_eleven_pixels_at_least():
    size = re.search(r"font-size:\s*(\d+)px", rule("#ultra-bar .mode")).group(1)
    assert int(size) >= 11


def test_the_desks_footnote_is_a_sentence_not_capitals():
    foot = rule(".desk-foot")
    assert "uppercase" not in foot
    assert int(re.search(r"(\d+)px\s+var", foot).group(1)) >= 12


def test_the_pick_line_is_not_spaced_like_a_label():
    assert "letter-spacing" not in rule("#agent-pick")


def test_no_dot_pulses_without_something_live():
    for selector in ("#wordmark .dots i", ".agent-live i", ".beacon"):
        assert "animation" not in rule(selector), selector
    head = re.search(r"\.desk-head b::before\s*\{([^}]*)\}", CSS).group(1)
    assert "animation" not in head


def test_the_desk_is_in_apollos_own_letters():
    assert "Space Grotesk" not in CSS
    assert '"Thmanyah"' in rule("#trading")
    assert not (FULL / "fonts" / "space-grotesk").exists()
