"""Apollo's name under the ring, as the old display had it: a neon sign in
Melete - 19px, spaced a fifth of a letter apart, #FFF0CE - each letter
pulsing on its own a little after the one before, and one of them, the
first O, a tube on its way out. It stands aside while Apollo is listening,
thinking or speaking, and it holds still for anyone who asked for less
motion and while nobody can see it."""
import pathlib
import re

FULL = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full"
HTML = (FULL / "index.html").read_text(encoding="utf-8")
CSS = (FULL / "app.css").read_text(encoding="utf-8")


def sign():
    block = re.search(r'<div id="wordmark"[^>]*>(.*?)</div>', HTML, re.S)
    assert block, "the name under the ring is not a sign any more"
    return block.group(1)


def rule(selector):
    found = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
    assert found, f"no rule for {selector}"
    return found.group(1)


def test_the_letters_spell_the_name_and_the_first_o_is_failing():
    letters = re.findall(r'<b( class="bad")?>([A-Z])</b>', sign())
    assert "".join(ch for _, ch in letters) == "APOLLO"
    assert [i for i, (bad, _) in enumerate(letters) if bad] == [2]


def test_set_in_melete_as_the_old_display_had_it():
    style = rule("#wordmark .letters")
    assert '"Melete"' in style and '"Inter"' in style
    assert "font-size: 19px" in style
    assert "letter-spacing: 0.2em" in style
    assert "#FFF0CE" in style
    assert "font-weight: 500" in style


def test_each_letter_pulses_a_little_after_the_one_before():
    delays = [float(d) for d in re.findall(
        r"#wordmark \.letters b:nth-child\(\d\)\s*\{\s*animation-delay:\s*([0-9.]+)s", CSS)]
    assert delays == sorted(delays) and len(delays) == 5
    steps = {round(b - a, 2) for a, b in zip(delays, delays[1:])}
    assert steps <= {0.18, 0.36}
    assert "@keyframes ap-sign " in CSS or "@keyframes ap-sign{" in CSS
    assert "@keyframes ap-sign-bad" in CSS


def test_it_stands_aside_while_apollo_is_busy():
    busy = re.search(r"body\.listening #wordmark,\s*body\.answering #wordmark\s*\{([^}]*)\}", CSS)
    assert busy and "opacity: 0" in busy.group(1)


def test_it_holds_still_when_asked_or_unseen():
    assert re.search(r"prefers-reduced-motion[^{]*\{[^@]*#wordmark", CSS, re.S)
    assert re.search(r"body\.(offscreen|asleep)[^{]*#wordmark[^{]*\{[^}]*animation-play-state:\s*paused", CSS)
