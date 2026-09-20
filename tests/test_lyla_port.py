"""LYLA is a thousand hand-placed pixels, and she was moved, not rewritten.

`ui/full/lyla.js` was lifted out of `ui/legacy/index.html` byte for byte, with
only the names that reached into the old React component rewritten. This test
is what stops the two drifting apart without anyone noticing: a stray edit to
her sprite in one file and not the other shows up here, not on screen three
weeks later.
"""
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
LEGACY = ROOT / "ui" / "legacy" / "index.html"
MODULE = ROOT / "ui" / "full" / "lyla.js"

# Her room: stations() through drawBubble. Her readouts: drawLylaHealth and
# drawLylaIcon, which live with the old HUD's methods.
BLOCKS = ((941, 2403), (793, 834))

RENAMES = (
    ("this.lylaRef.current", "this.canvas"),
    ("this.lylaLabelRef.current", "this.label"),
    ("this.ringRef.current", "this.ring"),
    ("this.lylaIconRef.current", "this.icon"),
    ("this.lylaHpRef.current", "this.bar"),
    ("this.lylaPctRef.current", "this.pct"),
    ("this.state.phase", "this.phase"),
    ("this.props.", "this.opts."),
    ("this.sfx(", "this.sound("),
)


def ported(first, last):
    """The legacy lines as they should read after the move (1-based, inclusive)."""
    lines = LEGACY.read_text(encoding="utf-8").split("\n")
    text = "\n".join(lines[first - 1:last])
    for old, new in RENAMES:
        text = text.replace(old, new)
    return text


@pytest.mark.parametrize("first,last", BLOCKS)
def test_lyla_moved_house_without_changing(first, last):
    assert ported(first, last) in MODULE.read_text(encoding="utf-8")


def test_lyla_reaches_for_nothing_that_stayed_behind():
    """No `this.state`, `this.props`, `this.sfx` or a React ref survives the move."""
    stragglers = re.findall(r"this\.(?:state|props|sfx|\w*Ref)\b",
                            MODULE.read_text(encoding="utf-8"))
    assert not stragglers, f"still tied to the old component: {sorted(set(stragglers))}"
