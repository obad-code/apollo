"""The explanation box (explain.js) and what fills it."""
import base64
import json
import pathlib
import subprocess

import pytest

import images

FULL = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full"


def run(tmp_path, body):
    script = tmp_path / "t.mjs"
    script.write_text(f"import * as E from '{(FULL / 'explain.js').as_uri()}';\n"
                      f"const out = (() => {{ {body} }})();\nconsole.log(JSON.stringify(out));",
                      encoding="utf-8")
    done = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_only_made_pictures_and_https_are_shown(tmp_path):
    got = run(tmp_path, """return [E.safeSrc('data:image/png;base64,iVBORw0KGgo='),
        E.safeSrc('https://x.example/a.png'), E.safeSrc('javascript:alert(1)'),
        E.safeSrc('data:text/html;base64,PHNjcmlwdD4='), E.safeSrc('http://x/a.png')];""")
    assert got == ["data:image/png;base64,iVBORw0KGgo=", "https://x.example/a.png", "", "", ""]


def test_steps_are_numbered_and_escaped(tmp_path):
    html = run(tmp_path, "return E.markup({title: 'How <it> works', steps: [{title: 'One', text: 'a & b'}, 'Two']});")
    assert "How &lt;it&gt; works" in html and "a &amp; b" in html
    assert '<span class="ex-num">01</span>' in html and '<span class="ex-num">02</span>' in html


def test_a_chart_uses_the_displays_own_drawing(tmp_path):
    html = run(tmp_path, "return E.markup({chart: {points: [1, 2], label: 'NVDA'}}, () => '<svg></svg>');")
    assert '<div class="ex-chart"><span class="ex-chart-label">NVDA</span><svg></svg></div>' == html


def test_the_corner_is_measured_from_the_layout(tmp_path):
    shift = run(tmp_path, """
        const core = { offsetLeft: 800, offsetTop: 300, offsetWidth: 320, offsetHeight: 200,
                       offsetParent: { offsetLeft: 40, offsetTop: 20, offsetParent: null } };
        return E.cornerShift(core, { x: 100, y: 80, scale: .3 });""")
    assert shift == {"dx": 100 - 1000, "dy": 80 - 420, "scale": 0.3}


def test_a_picture_is_kept_and_handed_back_as_data(tmp_path):
    png = b"\\x89PNG fake"
    made = images.make("a black hole", generate=lambda model, prompt: (png, "image/png"),
                       save_to=str(tmp_path))
    assert made["src"] == "data:image/png;base64," + base64.b64encode(png).decode()
    assert pathlib.Path(made["path"]).read_bytes() == png


def test_the_next_model_draws_when_one_fails(tmp_path):
    calls = []

    def generate(model, prompt):
        calls.append(model)
        if len(calls) == 1:
            raise RuntimeError("quota")
        return b"x", "image/jpeg"
    made = images.make("a cat", generate=generate, save_to=str(tmp_path))
    assert len(calls) == 2 and made["path"].endswith(".jpg")


def test_nothing_to_draw_is_refused():
    with pytest.raises(ValueError):
        images.make("  ", generate=lambda m, p: (b"", "image/png"))
