"""The full display's faces (ui/full/app.css): Inter for everything, Melete
for Apollo's name, and IBM Plex Sans Arabic behind them for Arabic. Every face is
carried with the page - pywebview serves nothing above ui/full - and a
@font-face whose file is missing falls back without a word, so the display
looks almost right in the wrong typeface. This checks the files are there."""
import pathlib
import re

FULL = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full"
CSS = (FULL / "app.css").read_text(encoding="utf-8")

FACES = re.findall(r"@font-face\s*\{([^}]*)\}", CSS)


def faces(family):
    found = []
    for body in FACES:
        name = re.search(r'font-family:\s*"([^"]+)"', body)
        if name and name.group(1) == family:
            weight = re.search(r"font-weight:\s*([0-9 ]+);", body)
            url = re.search(r'url\("([^"]+)"\)', body)
            found.append((weight.group(1).strip() if weight else "", url.group(1) if url else ""))
    return found


def test_every_face_s_file_is_carried_with_the_page():
    urls = re.findall(r'url\("([^"]+)"\)', CSS)
    assert urls
    for url in urls:
        assert (FULL / url).is_file(), f"{url} is not under ui/full"


def test_inter_covers_every_weight_and_plex_arabic_every_one_used():
    assert [weight for weight, _ in faces("Inter")] == ["100 900"]
    weights = {weight for weight, _ in faces("IBM Plex Sans Arabic")}
    assert {"300", "400", "500", "600", "700"} <= weights


def test_melete_for_the_name():
    assert [weight for weight, _ in faces("Melete")] == ["500"]


def test_everything_is_set_in_inter_with_plex_arabic_behind_it_for_arabic():
    for token in ("--mono", "--hud", "--display"):
        stack = re.search(token + r":\s*([^;]+);", CSS).group(1)
        assert stack.strip().startswith('"Inter"'), token
        assert '"IBM Plex Sans Arabic"' in stack, token


def test_the_faces_licences_travel_with_them():
    assert (FULL / "fonts" / "inter" / "OFL.txt").is_file()
    assert (FULL / "fonts" / "plex-arabic" / "OFL.txt").is_file()
    assert (FULL / "fonts" / "melete" / "OFL.txt").is_file()
