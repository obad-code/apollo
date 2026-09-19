"""What hangs under the mesh, and how tall it makes the overlay.

Two jobs, both deliberately free of any drawing code so they can be tested
without a screen: read a reply and work out what it actually contains, then
lay that out into positioned blocks and one total height. `orb.py` paints the
result; nothing here knows GDI+ exists.

The height is the point. Apollo's overlay has no panel and no box - it is a
figure floating on the desktop - so there is no frame to hold a fixed size and
nothing to hide unused space inside. Whatever this module says the content is
tall is exactly how far the window grows downward, which is why the layout is
computed from the wrapped text, the real number of data points and the real
number of cards rather than from a template.

Where the data comes from
-------------------------

A spoken reply is prose; prose does not contain a series. So Apollo may append
one machine-readable line to a reply, introduced by `VIS_TAG`, which is
stripped before the reply is spoken or displayed and parsed here into a chart
and/or cards. It is optional by design: an ordinary answer carries no tag and
renders as text alone, which keeps the common case honest - the overlay grows
"just enough to fit the wrapped text, then stops".

Anything malformed in that block is dropped rather than raised. It arrives
from a language model, so it is treated as untrusted input: every string is
length-capped, every number must be finite, and a block that survives with
nothing usable in it is discarded entirely. A bad tag costs the user a chart,
never an exception in the middle of a turn.
"""

import json
import math
import re

# Whose words are on screen. The roles differ only in colour and in whether
# the caret keeps blinking after the text has landed; the layout is identical.
USER, APOLLO = "user", "apollo"

# Introduces the optional machine-readable tail of a reply. Spelled with
# brackets rather than as a fenced block because the model is told everywhere
# else never to use markdown, and a fence would contradict that instruction.
VIS_TAG = "[[apollo:vis]]"

# Caps. All of these bound what one reply can put on screen, since the reply
# is written by a model and the overlay has no scrollbar to rescue an
# over-long one.
MAX_TEXT = 600          # characters of reply text kept; the rest is elided
MAX_POINTS = 64         # data points in a chart
MIN_POINTS = 4          # fewer than this is not a series, it is a fact
MAX_CARDS = 6
MAX_LABEL = 28          # characters in a card label or chart title
MAX_VALUE = 14          # characters in a card value


# --- reading a reply -------------------------------------------------------

def split_reply(reply):
    """Split a raw reply into (what to say, what to draw).

    The spoken half never contains the tag, so the voice is unaffected by
    anything in this file. `None` for the second half means "text only".
    """
    if not reply:
        return "", None

    index = reply.find(VIS_TAG)
    if index < 0:
        return reply.strip(), infer_visual(reply)

    spoken = reply[:index].strip()
    return spoken, parse_visual(reply[index + len(VIS_TAG):])


def parse_visual(raw):
    """Parse the tag's payload. None if there is nothing usable in it."""
    text = (raw or "").strip()
    if not text:
        return None

    # Tolerate a fence even though the prompt asks for none: the cost of
    # accepting one is three lines, and the cost of rejecting one is a chart
    # the user asked for silently not appearing.
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]

    # The model sometimes keeps talking after the JSON. Take the first
    # balanced object and ignore the rest.
    text = _first_object(text)
    if not text:
        return None

    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    return _clean(data)


def _first_object(text):
    """The first balanced {...} in `text`, or "" if there is none."""
    start = text.find("{")
    if start < 0:
        return ""
    depth, in_string, escaped = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return ""


def _clean(data):
    """Validate a parsed block. None if nothing survives."""
    chart = _clean_chart(data.get("chart"))
    cards = _clean_cards(data.get("cards"))
    if chart is None and not cards:
        return None
    return {"chart": chart, "cards": cards}


# The same validation, for visuals built in code rather than parsed from a
# reply: a tool's chart still has to clear every cap a model's would.
clean_visual = _clean


def _clean_chart(chart):
    if not isinstance(chart, dict):
        return None

    points = []
    for value in (chart.get("points") or [])[:MAX_POINTS]:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None                      # a series with a hole is not a series
        value = float(value)
        if not math.isfinite(value):
            return None
        points.append(value)

    if len(points) < MIN_POINTS:
        return None

    return {
        "points": points,
        "label": _text(chart.get("label"), MAX_LABEL),
        "unit": _text(chart.get("unit"), 4),
    }


def _clean_cards(cards):
    if not isinstance(cards, list):
        return []
    out = []
    for card in cards[:MAX_CARDS]:
        if not isinstance(card, dict):
            continue
        label = _text(card.get("label"), MAX_LABEL)
        value = _text(card.get("value"), MAX_VALUE)
        if label and value:
            out.append({"label": label.upper(), "value": value})
    # One card is a sentence's worth of information and reads better as part
    # of the sentence, so it is not worth a box of its own.
    return out if len(out) >= 2 else []


def _text(value, limit):
    """A model-supplied string, made safe to draw: one line, length-capped."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = f"{value:g}"
    if not isinstance(value, str):
        return ""
    value = " ".join(value.split())          # newlines and runs of spaces out
    return value[:limit].strip()


# The separator between two members of a spoken series, and the numbers
# themselves. "12, 15, 18 and 21" is a series; "twelve, fifteen" is words and
# is deliberately not matched.
_SEP = re.compile(r"\s*,\s*(?:and\s+)?|\s+and\s+")
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def infer_visual(text):
    """A chart read straight out of prose, when the prose really is a series.

    The fallback for when Apollo answers with numbers but no tag. Kept
    deliberately narrow: only a comma-or-and separated run of at least
    `MIN_POINTS` bare numbers counts, because the failure mode that matters is
    an ordinary sentence sprouting a chart. No card is ever inferred - prose
    with a colon in it is far too common to read as a table.
    """
    if not text:
        return None

    best, position = [], 0
    while position < len(text):
        first = _NUMBER.search(text, position)
        if not first:
            break
        run, end = [float(first.group())], first.end()
        while True:
            separator = _SEP.match(text, end)
            if not separator:
                break
            following = _NUMBER.match(text, separator.end())
            if not following:
                break
            run.append(float(following.group()))
            end = following.end()
        if len(run) > len(best):
            best = run
        position = max(end, first.end())

    if len(best) < MIN_POINTS:
        return None
    return {"chart": {"points": best[:MAX_POINTS], "label": "", "unit": ""},
            "cards": []}


# --- laying it out ---------------------------------------------------------

# Every measurement below is in pixels at the overlay's own scale. They are
# module constants rather than arguments because there is exactly one overlay
# and one place that draws it; a caller that wants a different size is a
# caller that wants a different design.
PAD_X = 22              # left and right margin of the content column
LINE_H = 19             # one line of body text
GAP = 15                # between blocks
CHART_H = 90
CHART_GUTTER = 48       # right strip reserved for the min/max labels, so the
                        # plot line can never run underneath them
CARD_H = 52
CARD_GAP = 10
CARD_MIN_W = 132        # narrower than this and a value starts to clip
BOTTOM_PAD = 18         # so the last line is not flush with nothing


class Metrics:
    """Font measurements the layout needs, taken once by the painter.

    Only `char_w` is needed for wrapping because the overlay's face is
    monospace - the same face the rest of the app renders in. That is what
    lets the typing reveal be a multiplication instead of a per-frame text
    measurement (see `orb.Orb._draw_content`).
    """

    def __init__(self, char_w, line_h=LINE_H):
        self.char_w = float(char_w)
        self.line_h = int(line_h)


def wrap(text, columns):
    """Wrap to `columns` characters, breaking a word only if it cannot fit."""
    if columns < 1:
        return []
    lines = []
    for paragraph in (text or "").split("\n"):
        words = paragraph.split()
        if not words:
            continue
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if len(candidate) <= columns:
                current = candidate
                continue
            if current:
                lines.append(current)
            while len(word) > columns:        # a URL, or a long number
                lines.append(word[:columns])
                word = word[columns:]
            current = word
        if current:
            lines.append(current)
    return lines


def elide(text, limit=MAX_TEXT):
    """Cap the text a single turn can put on screen."""
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[:limit - 1].rstrip(" ,.;:") + "…"


def layout(role, text, visual, metrics, width, max_height=None):
    """Position everything and measure the whole.

    Returns a dict with `blocks`, `height`, `chars` (how many characters the
    typing reveal has to get through before the chart and cards are due) and
    `width`. An empty result - no text, nothing to draw - has height 0, which
    is what collapses the overlay back to the bare mesh.

    `max_height`, when given, is a hard ceiling: blocks that would cross it
    are dropped rather than clipped, because half a chart is worse than none.
    """
    text = elide(text)
    inner = max(40, int(width) - PAD_X * 2)
    columns = max(8, int(inner // metrics.char_w))

    blocks = []
    y = 0

    lines = wrap(text, columns)
    if lines:
        start = 0
        laid = []
        for line in lines:
            # Centred on the same axis as the mesh above it, the way the full
            # display centres its transcript and its answer. Left-aligned in a
            # column this wide reads as a stray paragraph rather than as
            # something hanging off the figure.
            x = int(round((width - len(line) * metrics.char_w) / 2.0))
            laid.append({"text": line, "x": max(PAD_X, x), "y": y,
                         "start": start})
            # +1 for the space the wrap consumed, so the reveal advances
            # through the gap between lines at the same rate as through a
            # word. Without it the caret pauses at every line end.
            start += len(line) + 1
            y += metrics.line_h
        blocks.append({"kind": "text", "role": role, "lines": laid})

    chars = len(text)
    visual = visual or {}
    chart = visual.get("chart")
    cards = visual.get("cards") or []

    if chart:
        top = y + GAP
        if max_height is None or top + CHART_H <= max_height:
            blocks.append({
                "kind": "chart", "x": PAD_X, "y": top,
                "w": inner, "h": CHART_H,
                "plot_w": max(40, inner - CHART_GUTTER),
                "points": chart["points"], "label": chart.get("label", ""),
                "unit": chart.get("unit", ""),
            })
            y = top + CHART_H

    if cards:
        top = y + GAP
        rows = _card_rows(cards, inner, top)
        height = (rows[-1]["y"] + rows[-1]["h"] - top) if rows else 0
        if rows and (max_height is None or top + height <= max_height):
            blocks.append({"kind": "cards", "rows": rows})
            y = top + height

    height = y + BOTTOM_PAD if blocks else 0
    if max_height is not None:
        height = min(height, max_height)
    return {"blocks": blocks, "height": int(height), "chars": chars,
            "width": int(width)}


def _card_rows(cards, inner, top):
    """Place cards across, or stacked when across would squeeze them.

    Across reads as a row of readouts, which is what two or three short facts
    are. Once they no longer fit at `CARD_MIN_W` the same facts become full
    width rows instead - same styling, more room - rather than being allowed
    to clip.
    """
    across = len(cards)
    while across > 1 and (inner - CARD_GAP * (across - 1)) / across < CARD_MIN_W:
        across -= 1

    rows = []
    if across <= 1:
        for i, card in enumerate(cards):
            rows.append({"x": PAD_X, "y": top + i * (CARD_H + CARD_GAP),
                         "w": inner, "h": CARD_H, "wide": True, **card})
        return rows

    width = (inner - CARD_GAP * (across - 1)) / across
    for i, card in enumerate(cards):
        column, row = i % across, i // across
        rows.append({
            "x": int(PAD_X + column * (width + CARD_GAP)),
            "y": top + row * (CARD_H + CARD_GAP),
            "w": int(width), "h": CARD_H, "wide": False, **card,
        })
    return rows
