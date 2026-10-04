"""Pictures Apollo makes: a diagram, a poster, "show me what a black hole
looks like" - drawn by Gemini's image model and put in the explanation box.

Uses the GEMINI_API_KEY Apollo already has. APOLLO_IMAGE_MODEL puts another
model first. Every picture is also saved to Pictures\\Apollo, so it is yours
after the box has gone.
"""

import base64
import datetime
import logging
import os
import re

log = logging.getLogger("apollo.images")

# Gemini 2.5 Flash Image was shut down on 2 October 2026; 3.1 Flash Image (Nano Banana 2) took its place.
MODELS = tuple(filter(None, (os.environ.get("APOLLO_IMAGE_MODEL"),
                             "gemini-3.1-flash-image-preview", "gemini-3-pro-image-preview")))
LARGEST = 6 * 1024 * 1024        # bytes; a picture past this is not put on the page


def folder():
    return os.path.join(os.path.expanduser("~"), "Pictures", "Apollo")


def _generate(model, prompt):
    """The one call to Gemini. Returns (bytes, mime). Tests replace this."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=(os.environ.get("GEMINI_CREW_KEY") or os.environ.get("GEMINI_API_KEY")))
    response = client.models.generate_content(
        model=model, contents=prompt,
        config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]))
    for candidate in response.candidates or []:
        for part in (candidate.content.parts if candidate.content else []) or []:
            data = getattr(part, "inline_data", None)
            if data is not None and data.data:
                return data.data, data.mime_type or "image/png"
    raise RuntimeError("the model drew nothing")


def make(prompt, generate=None, save_to=None, now=None):
    """Draw `prompt`. Returns {src (a data: address), path, mime}."""
    prompt = " ".join(str(prompt or "").split())
    if not prompt:
        raise ValueError("Nothing to draw was given.")
    if not (os.environ.get("GEMINI_CREW_KEY") or os.environ.get("GEMINI_API_KEY")) and generate is None:
        raise RuntimeError("Drawing needs GEMINI_API_KEY.")
    generate = generate or _generate
    last = None
    for model in MODELS:
        try:
            data, mime = generate(model, prompt)
            break
        except Exception as e:  # noqa: BLE001 - the next model may draw it
            log.info("image model %s failed: %s", model, e)
            last = e
    else:
        raise RuntimeError(f"No picture came back: {last}")
    if len(data) > LARGEST:
        raise RuntimeError("The picture came back too large to show.")
    ext = {"image/jpeg": ".jpg", "image/webp": ".webp"}.get(mime, ".png")
    stamp = (now or datetime.datetime.now()).strftime("%Y-%m-%d %H%M%S")
    name = re.sub(r"[^\w\- ]+", "", prompt)[:48].strip() or "picture"
    out = save_to or folder()
    path = os.path.join(out, f"{stamp} {name}{ext}")
    try:
        os.makedirs(out, exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(data)
    except OSError:
        log.info("could not keep the picture", exc_info=True)
        path = ""
    src = f"data:{mime};base64," + base64.b64encode(data).decode("ascii")
    return {"src": src, "path": path, "mime": mime}
