"""Trading mode in its own style: its own colours - the market's greens on
ink, the ground behind the desk going over to them - and its own letters,
Space Grotesk for the words and Martian Mono for the tickers and figures,
carried with Apollo like the rest of its fonts."""
import pathlib
import re

FULL = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full"
CSS = (FULL / "app.css").read_text(encoding="utf-8")
SHADER = (FULL / "shader.js").read_text(encoding="utf-8")
APP = (FULL / "app.js").read_text(encoding="utf-8")


def block(selector):
    found = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
    assert found, selector
    return found.group(1)


def test_its_own_letters_are_bundled_with_their_licences():
    for family, folder in (("Space Grotesk", "space-grotesk"), ("Martian Mono", "martian-mono")):
        assert f'font-family: "{family}"' in CSS
        assert list((FULL / "fonts" / folder).glob("*.woff2"))
        assert "Open Font License" in (FULL / "fonts" / folder / "OFL.txt").read_text(encoding="utf-8")


def test_the_desk_is_set_in_them():
    desk = block("#trading")
    assert '"Space Grotesk"' in desk and '"Martian Mono"' in desk
    assert "font-family: var(--desk-words)" in desk


def test_the_screen_takes_the_markets_colours_while_the_desk_is_up():
    palette = block("body.trading:not(.ultra):not(.osiris-map)")
    for token in ("--amber:", "--cream:", "--caption:", "--panel:", "--up:", "--down:"):
        assert token in palette
    assert "#FFC15E" not in palette                   # not Apollo's amber


def test_the_ground_goes_green_behind_it():
    assert "uniform float market;" in SHADER
    assert "market(on)" in SHADER
    assert re.search(r"shader\.market\(state\.view === 'trading'", APP)
