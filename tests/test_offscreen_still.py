"""Nothing on the display moves while it is hidden.

The display is hidden by Windows (ShowWindow SW_HIDE), not by the browser, so
to WebView2 the page is still visible: measured on 26 September 2026 with the
display away and only the orb up, nine CSS animations and five SVGs' SMIL
animations (LYLA's agent map) were still running - no frames of the page's
own, the shader stopped as it should - and the GPU drew them for nobody, some
23% of it. Paused while hidden, they carry on from where they were when the
display is back, so nothing you see is different.
"""
import pathlib
import re

UI = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full"


def test_every_css_animation_is_paused_offscreen():
    css = (UI / "app.css").read_text(encoding="utf-8")
    rule = re.search(r"body\.offscreen \*,\s*body\.offscreen \*::before,\s*body\.offscreen \*::after\s*"
                     r"\{\s*animation-play-state:\s*paused\s*!important;?\s*\}", css)
    assert rule, "no rule pauses every animation while the display is hidden"


def mode_function():
    js = (UI / "app.js").read_text(encoding="utf-8")
    start = js.index("  mode(name) {")
    return js[start:js.index("\n  },", start)]


def test_svg_animations_are_paused_offscreen_and_resumed_on_it():
    body = mode_function()
    assert "pauseAnimations()" in body and "unpauseAnimations()" in body
