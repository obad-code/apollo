"""Every script the display loads has to parse.

A backtick in a comment inside the shader's GLSL - which is itself a
template string - ended the string early, and the module failed to load:
no `window.apollo`, a display that never drew anything, and not one test
that noticed. node checks the syntax without running anything.
"""
import pathlib
import shutil
import subprocess

import pytest

PAGE = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full"
SCRIPTS = sorted(p for p in PAGE.glob("*.js"))
NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_the_script_parses(script, tmp_path):
    # .mjs, so node reads it as the module the page loads it as.
    copy = tmp_path / (script.stem + ".mjs")
    copy.write_text(script.read_text(encoding="utf-8"), encoding="utf-8")
    result = subprocess.run([NODE, "--check", str(copy)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
