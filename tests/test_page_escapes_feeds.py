"""Nothing off the internet is written into the page as markup.

Headlines come from Google News, posts come from trumpstruth.org. Neither is
Apollo's to trust: a title containing `<img src=x onerror=...>` dropped into
innerHTML runs as script inside the window that holds your watchlist, your
usage and a bridge back into the app. The old page was React, which escaped
every value it rendered; the page that replaced it builds its own markup, so
the escaping has to be deliberate - and checked.
"""
import pathlib
import re

import pytest

APP = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full" / "app.js"

# Anything whose value came from a feed, a quote, or the assistant's reply.
# `(?<!\.)` keeps `state.topic` - the page's own index - out of it.
UNTRUSTED = re.compile(
    r"(?<!\.)\b(?:story\.(?:title|source|age|summary|image|link)"
    r"|post\.(?:text|age)"
    # The feed merges headlines and posts into one `item`. Renaming a field
    # must not quietly drop it out of this check - which is what happened
    # when it did, and the count fell from eleven to six without a failure.
    r"|item\.(?:title|source|age|summary|image|link|interest|id|label)"
    # The trading desk (trading.py): every name on it came off a source.
    r"|pick\.(?:ticker|name|summary|why)|final\.none|name\.(?:symbol|name)|mover\.(?:ticker|name)"
    r"|filing\.(?:ticker|company|link|filed)|headline\.(?:title|source|age|link)"
    r"|buy\.(?:ticker|company|industry|insider|title|traded)"
    r"|deal\.(?:ticker|member|chamber|amount|disclosed|link)|post\.(?:who|text)|reason"
    r"|quote\.(?:symbol|name|logo)"
    # LYLA's reports: her words, and the web's under them.
    r"|report\.(?:task|symbol|summary|report|brain)"
    # "Add a stock" lists what apollo.py suggests; a pick is data like a quote.
    r"|pick\.(?:symbol|name)"
    # The side panel's tabs: your record, your folders and repos, your ideas.
    r"|talk\.(?:you|apollo|who|time)"
    r"|session\.(?:title|project|prompt)"
    r"|folder\.(?:name|branch|last)"
    r"|repo\.(?:name|about)"
    r"|idea\.(?:text|age|id)"
    r"|reminder\.(?:text|due)"
    r"|trade\.(?:name|date)"
    # What Apollo found wrong with itself: exception text, paths, file names.
    r"|issue\.(?:title|detail|key)"
    # OSIRIS mode's world panel: the USGS's words and the headlines'.
    r"|quake\.(?:place|link|mag|when)"
    r"|market\.status"
    r"|weather\.text"
    r"|system\.gpu_name"
    r"|chosen|topic)\b"
)

PLACEHOLDER = re.compile(r"\$\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}")

# `cond ? 'a' : 'b'` - the condition may read anything, because what comes out
# is one of two strings the page wrote itself.
LITERAL_CHOICE = re.compile(r"""\?\s*(?:'[^']*'|"[^"]*")\s*:\s*(?:'[^']*'|"[^"]*")\s*$""")


def placeholders():
    text = APP.read_text(encoding="utf-8")
    found = [(i, expr) for i, expr in enumerate(PLACEHOLDER.findall(text))
             if UNTRUSTED.search(expr) and not LITERAL_CHOICE.search(expr)]
    assert found, "no untrusted values are interpolated at all - has the page changed shape?"
    # A floor, so a rename cannot shrink this check towards nothing in
    # silence: the feed's fields, an opened story's, the quotes' fields, and
    # the weather.
    assert len(found) >= 13, (
        f"only {len(found)} untrusted values found - has a field been renamed "
        "out of UNTRUSTED?")
    return found


@pytest.mark.parametrize("index,expr", placeholders(), ids=lambda v: str(v)[:44])
def test_untrusted_values_are_escaped_before_they_become_markup(index, expr):
    assert "esc(" in expr, (
        f"`${{{expr}}}` puts a value Apollo did not write into the page as markup; "
        "wrap it in esc()")
