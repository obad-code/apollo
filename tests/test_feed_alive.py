"""The right-hand side, alive: the feed's stories in their topics' colours
with a picture (or the topic's mark) each, the newest leading large, a
reading head moving down them, new ones sliding in and marked NEW; the
consoles at the column's foot, reading real numbers; and the scanner's line
folded away until a file is being scanned."""
import pathlib

FULL = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full"
APP = (FULL / "app.js").read_text(encoding="utf-8")
CSS = (FULL / "app.css").read_text(encoding="utf-8")


def test_each_topic_has_its_colour_and_its_mark():
    for topic in ("t-gaming", "t-marvel", "t-movies", "t-markets", "t-posts", "t-private-eye"):
        assert f".story.{topic} {{ --topic:" in CSS
    assert "const GLYPHS = {" in APP and "glyph(item.topic)" in APP


def test_the_newest_leads_and_the_rest_are_a_line_each():
    assert "const lead = !folded && drawn.length > 1;" in APP
    assert ".story.hero .thumb {" in CSS
    assert ".story .what { grid-column: 2; display: -webkit-box; overflow: hidden; -webkit-line-clamp: 1;" in CSS


def test_the_reading_head_new_arrivals_and_new_stories():
    assert "const READ_EVERY = 7000;" in APP and "function markReading()" in APP
    assert ".story.reading::after" in CSS and ".story.arriving" in CSS
    assert "<i class=\"new\">new</i>" in APP


def test_pictures_are_not_dotted_by_the_crt_mask():
    assert "#stories .story > :not(.thumb)" in CSS
    assert "#indices, #watchlist, #stories, #topics" not in CSS


def test_the_consoles_read_real_numbers():
    assert "import * as Lights from './consolelights.js';" in APP
    assert "Math.random()" not in APP[APP.index("(function consoles() {"):APP.index("/* --- the HUD")]


def test_the_scanner_folds_away_until_it_is_needed():
    assert ("body:not(.scan-open):not(.hud-free):not(.viewing):not(.ultra):not(.osiris-map) "
            "#stage > #scan-block { display: none; }") in CSS
