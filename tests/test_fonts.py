"""Apollo carries Thmanyah with him; both halves of him have to find it.

The overlay is drawn by GDI+ from the OTFs and the display is a web page
using the WOFF2s, so there are two independent ways for the face to go
missing - and both fail quietly, falling back to something that looks
almost right.
"""
import pathlib

import pytest

import orb

ROOT = pathlib.Path(__file__).resolve().parent.parent
OTF = ROOT / "ui" / "fonts" / "thmanyah"
WOFF = ROOT / "ui" / "full" / "fonts"


@pytest.mark.parametrize("weight,filename", sorted(orb.FONT_FILES.items()))
def test_the_overlay_has_the_weight_it_asks_for(weight, filename):
    assert (OTF / filename).exists(), f"{weight}: {filename} is not in the tree"


def test_the_display_has_the_same_weights():
    stems = {p.stem for p in OTF.glob("*.otf")}
    assert stems, "no OTFs at all"
    assert stems == {p.stem for p in WOFF.glob("*.woff2")}, (
        "the overlay and the display are carrying different weights")


def test_gdi_plus_can_load_them_and_name_them_as_the_overlay_expects():
    """GDI+ names a family with more than four weights in its own way.

    It is not guessable - 'thmanyah sans Med', not 'Medium' - and getting it
    wrong means a silent fall back to Segoe UI, so the names the overlay asks
    for are checked against what GDI+ actually reports.
    """
    import clr
    clr.AddReference("System.Drawing")
    import System.Drawing as D

    collection = D.Text.PrivateFontCollection()
    for filename in orb.FONT_FILES.values():
        collection.AddFontFile(str(OTF / filename))
    found = {family.Name for family in collection.Families}
    for weight, name in orb.FONT_FAMILIES.items():
        assert name in found, f"{weight} -> {name!r} not among {sorted(found)}"


def test_both_scripts_come_out_of_the_one_family():
    """The point of the family: Arabic and English in the same face."""
    import clr
    clr.AddReference("System.Drawing")
    import System.Drawing as D

    collection = D.Text.PrivateFontCollection()
    collection.AddFontFile(str(OTF / orb.FONT_FILES["regular"]))
    font = D.Font(collection.Families[0], 14.0, D.FontStyle.Regular,
                  D.GraphicsUnit.Point)
    bitmap = D.Bitmap(360, 60, D.Imaging.PixelFormat.Format32bppPArgb)
    graphics = D.Graphics.FromImage(bitmap)
    graphics.Clear(D.Color.White)
    brush = D.SolidBrush(D.Color.Black)
    graphics.DrawString("Apollo 222.27", font, brush, 4.0, 2.0)
    graphics.DrawString("سهم إنفيديا أغلق", font, brush, 4.0, 30.0)
    graphics.Dispose()

    def ink(y0, y1):
        return sum(1 for y in range(y0, y1) for x in range(360)
                   if bitmap.GetPixel(x, y).R < 128)

    assert ink(0, 28) > 100, "no Latin drawn"
    assert ink(30, 58) > 100, "no Arabic drawn"
