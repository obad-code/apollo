"""How the intro leaves (ui/full/app.css): not a tube switching off into
the dark, but the boot screen blurring away while the display comes up out
of a blur under it - and neither for anyone who asked for less motion."""
import pathlib
import re

CSS = (pathlib.Path(__file__).resolve().parent.parent / "ui" / "full" / "app.css").read_text(encoding="utf-8")


def keyframes(name):
    found = re.search(r"@keyframes " + re.escape(name) + r"\s*\{(.*?)\n\}", CSS, re.S)
    assert found, f"no @keyframes {name}"
    return found.group(1)


def animation_of(selector):
    found = re.search(re.escape(selector) + r"\s*\{[^}]*animation:\s*([\w-]+)", CSS)
    assert found, f"{selector} has no animation"
    return found.group(1)


def test_the_boot_screen_blurs_away():
    leaving = keyframes(animation_of("#intro.off"))
    assert "blur(" in leaving and "opacity: 0" in leaving


def test_the_display_comes_up_out_of_a_blur():
    arriving = keyframes(animation_of("body.revealing #stage"))
    first = arriving.split("}")[0]
    assert "blur(" in first and "opacity: 0" in first


def test_no_tube_switching_off_any_more():
    assert "tube-off" not in CSS


def test_still_for_anyone_who_asked():
    still = CSS[CSS.index("@media (prefers-reduced-motion: reduce)"):]
    assert "#intro.off" in still and "body.revealing #stage" in still
