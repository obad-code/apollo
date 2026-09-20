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
    r"(?<!\.)\b(?:story\.(?:title|source|age)"
    r"|post\.(?:text|age)"
    r"|quote\.(?:symbol|name)"
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
    return found


@pytest.mark.parametrize("index,expr", placeholders(), ids=lambda v: str(v)[:44])
def test_untrusted_values_are_escaped_before_they_become_markup(index, expr):
    assert "esc(" in expr, (
        f"`${{{expr}}}` puts a value Apollo did not write into the page as markup; "
        "wrap it in esc()")
