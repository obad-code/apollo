"""Everything the display asks for has to live under the display.

pywebview roots its HTTP server at the page's own directory, so a reference
that climbs out of it - `../vendor/motion.js` - resolves in a browser and
404s in the window Apollo actually uses. That failure is quiet: the script
tag just does nothing, and the page comes up missing whatever depended on
it. This is the check that it cannot happen again.
"""
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = ROOT / "ui" / "full" / "index.html"
ROOTED_AT = PAGE.parent

# src="...", href="...", import ... from '...', and url(...) in the stylesheet,
# minus absolute and data URLs.
REFERENCE = re.compile(r"""(?:src|href)\s*=\s*["']([^"':#][^"']*)["']""")
IMPORT = re.compile(r"""^\s*import\s[^'"]*from\s+["'](\.[^"']+)["']""", re.M)
CSS_URL = re.compile(r"""url\(\s*["']?([^"'):]+)["']?\s*\)""")


def references():
    found = [(PAGE, ref) for ref in REFERENCE.findall(PAGE.read_text(encoding="utf-8"))]
    for script in sorted(ROOTED_AT.glob("*.js")):
        found += [(script, ref) for ref in IMPORT.findall(script.read_text(encoding="utf-8"))]
    # A @font-face whose file is missing fails silently: the browser falls
    # back and the display comes up in the wrong typeface, looking almost
    # right. Same for any other url() the stylesheet asks for.
    for sheet in sorted(ROOTED_AT.glob("*.css")):
        found += [(sheet, ref) for ref in CSS_URL.findall(sheet.read_text(encoding="utf-8"))]
    assert found, "the page references nothing at all - the patterns have gone stale"
    return found


@pytest.mark.parametrize("source,ref", references(), ids=lambda v: str(v)[-40:])
def test_every_reference_resolves_under_the_page(source, ref):
    target = (source.parent / ref).resolve()
    assert target.exists(), f"{source.name} asks for {ref}, which is not there"
    assert target.is_relative_to(ROOTED_AT), (
        f"{source.name} asks for {ref}, which is outside {ROOTED_AT.name}/ - "
        "pywebview's server cannot reach it")
