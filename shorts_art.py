"""Optional: a Gemini picture for every scene (SHORTS_IMAGES=gemini), instead of the drawn ones.

Needs a Gemini key whose project has billing on (the free tier has no image quota).
Each picture's prompt stands completely alone, as the production notes say: the
fixed style, the hero spelled out in full (his locked look this video), any side
character spelled out, a concrete setting, the mood palette, one text element at
most (never in the picture - the captions are added here, so nothing is garbled),
and the vertical composition. If the model refuses (quota, billing), the scene is
drawn the usual way and the rest of the video still comes out.
"""

import logging
import os

import shorts_hero

log = logging.getLogger("apollo.shorts_art")

STYLE = ("2D flat vector illustration, cel-shaded, bold black outlines, polished modern animated "
         "explainer style, clean flat colours")
HERO = ("the protagonist: a round, slightly chubby character with a blank featureless pale-white face, "
        "full cheeks and a soft rounded jaw, NO nose at all, two simple round black dot eyes each with "
        "a tiny white glint, thin flat eyebrows, a single thin flat line for a mouth (no lips), a faint "
        "gray stubble shadow on the chin, a large rounded head")
OUTFITS = {1: "a plain worn sweater, jeans and scuffed sneakers", 2: "a button-down shirt and chinos",
           3: "a full navy suit with a tie", 4: "a well-tailored charcoal suit with a pocket square, quiet wealth, never flashy"}
BUILDS = {"stockier": "a stockier soft build", "average": "an average soft build", "slimmer": "a slimmer but still soft build"}
MOODS = {"warm": "warm gold and amber palette (comfort, progress)",
         "cool": "cool blue desaturated palette (stress, hardship)",
         "neutral": "neutral beige and cream palette (informational)",
         "night": "dark navy palette with one warm light source (high stakes, late night)"}
SIDE = {"boss": "a middle-aged boss in a grey shirt with tired eyes, tan skin", "friend": "a friendly young friend with warm brown hair and a hoodie",
        "landlord": "a stern older landlord with grey hair and a green cardigan", "banker": "a neat banker in a navy suit with slicked-back dark hair",
        "stranger": "a stranger with dark skin and short black hair in a grey jacket", "guard": "a prison guard in a blue uniform and cap",
        "prisoner": "a prisoner in an orange jumpsuit with a shaved head", "librarian": "an elderly librarian with grey hair, round spectacles and a plum cardigan",
        "doctor": "a doctor in a white coat with a stethoscope", "teacher": "a teacher with brown hair and a green sweater",
        "waiter": "a waiter in a white shirt and black apron", "pilot": "a pilot in a navy uniform with a peaked cap",
        "sailor": "a weathered sailor with a white beard and a blue jersey", "farmer": "a farmer with a straw hat and a brown vest",
        "elder": "a wise elderly man with white hair and a brown cardigan", "partner": "a warm partner with auburn hair and a soft pink sweater",
        "king": "a king with a grey beard, a gold crown and a crimson robe"}
PLACE = {
    "sea": "an open blue sea under a bright sky with a small sailboat, gulls and rolling waves", "beach": "a sandy beach at the edge of a calm blue sea",
    "desert": "rolling golden dunes under a huge sun with a lone cactus", "city": "a dense city street with tall buildings, lit windows and a grey road",
    "space": "deep space with a ringed planet, a small moon and twinkling stars", "night": "a quiet night with a crescent moon, stars and dark hills",
    "forest": "a dense green forest with tall trees, dappled light and a winding path", "mountains": "snow-capped grey mountains under a clear sky",
    "rain": "a grey rainy day with heavy clouds and slanting rain on wet ground", "underwater": "an underwater scene with fish, bubbles and swaying seaweed",
    "room": "a small plain apartment room with a window, a bed and a worn rug", "chart": "a big rising line chart with coins on a pale grid",
    "office": "a corporate office with a desk, a laptop and a big window over a city skyline", "bank": "a grand stone bank building with tall columns and steps",
    "library": "a tall old library with wooden shelves full of books, a rolling ladder and a reading lamp", "prison": "a grey concrete prison cell with steel bars, a narrow cot and a small barred window casting a beam of light",
    "cafe": "a warm cafe with a wooden counter, a coffee machine, pendant lamps and a window to the street",
    "airport": "an airport terminal with a huge window onto a plane, a departures board and rows of seats",
    "hospital": "a clean hospital room with a bed, a heart monitor and a red cross on the wall", "school": "a classroom with a green chalkboard, wooden desks and a wall clock",
    "cave": "a dark cave with stalactites, glowing blue crystals and a burning torch", "island": "a tiny desert island with one palm tree in a wide blue sea",
    "castle": "a stone castle with two towers, a red flag and green hills",
}


def prompt_for(scene, hero, last_text=""):
    """One compact, self-contained paragraph for one scene."""
    tier = scene.get("tier", 2)
    bits = [STYLE + ". Vertical 9:16 composition, no text and no letters anywhere in the picture."]
    if scene.get("show") != "env":
        bits.append(f"{HERO}, {shorts_hero_hair(hero)}, {BUILDS.get(hero['build'], BUILDS['average'])}, wearing {OUTFITS.get(tier, OUTFITS[2])}; "
                    f"he {POSES.get(scene.get('pose'), 'stands calmly')}"
                    + (f" holding {PROP.get(scene.get('prop'))}" if PROP.get(scene.get("prop")) else "") + ".")
    if scene.get("friend") in SIDE:
        bits.append(f"Beside him: {SIDE[scene['friend']]}, with a normal fully rendered face - a real nose, skin tone and a clear expression.")
    bits.append(f"Setting: {PLACE.get(scene.get('bg'), 'a plain softly lit studio')}.")
    bits.append(f"Lighting and colour: {MOODS.get(scene.get('grade'), MOODS['neutral'])}.")
    bits.append(f"The moment: {scene.get('say', '')}")
    bits.append("A small depth detail in the foreground, varied framing, clean and polished.")
    return " ".join(bits)


def shorts_hero_hair(hero):
    return f"{hero['hair']} hair in a {hero['style']} style"


POSES = {"sad": "slumps, sad", "shock": "freezes in shock, arms out", "cheer": "cheers with both arms up", "think": "ponders with a hand raised",
         "wave": "waves", "point": "points ahead", "run": "runs", "shrug": "shrugs", "pleased": "stands calmly", "stand": "stands calmly"}
PROP = {"book": "a book", "key": "a key", "coffee": "a coffee cup", "map": "a map", "phone": "a phone", "suitcase": "a suitcase",
        "trophy": "a trophy", "money": "a banknote", "bulb": "a glowing light bulb", "note": "a notepad and a pencil", "clock": "a clock",
        "heart": "a heart", "earth": "a globe", "fire": "a flame", "skull": "a skull"}


def generate(scene, hero, folder, make=None):
    """Draw this scene with Gemini; returns the image path. Raises if the model will not."""
    import images
    make = make or images.make
    os.makedirs(folder, exist_ok=True)
    made = make(prompt_for(scene, hero), save_to=folder)
    return made["path"]


def fits(path, size):
    """The picture cropped to fill `size` (cover), as a PIL image."""
    from PIL import Image
    img = Image.open(path).convert("RGB")
    w, h = size
    scale = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1), Image.LANCZOS)
    left, top = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))
