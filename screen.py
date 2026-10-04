"""Apollo's eyes: what is on your screen, looked at when you ask.

"وش هذا؟", "explain this chart", "what does this error mean", "is this a
good entry on Nvidia?" - Apollo takes one screenshot of the screen as it is,
hands it to Gemini with your question, and says what it sees. The chart
you are looking at, the page you are reading, the error on screen.

One picture, only when asked; nothing is kept and nothing is sent anywhere
but to Gemini with that one question. The capture is FFmpeg's own Windows
screen grabber, through the `av` package the clip buffer already uses, so
nothing new needs installing; the picture is sent as a JPEG, at most
SHOT_WIDTH pixels wide.
"""

import fractions
import logging
import os

log = logging.getLogger("apollo.screen")

SHOT_WIDTH = 1600
MODELS = tuple(filter(None, (os.environ.get("APOLLO_VISION_MODEL"),
                             "gemini-flash-latest", "gemini-2.5-flash")))

SYSTEM = (
    "You are Apollo's eyes. You are given a screenshot of the user's screen and "
    "their question about it. Answer the question from what is on the screen: "
    "read the chart, the text, the error, the page - be specific (numbers, names, "
    "the exact message). If the question is vague (\"what's this?\"), say what is "
    "in the middle of the screen and what matters about it. For a stock chart: "
    "the trend, the levels, what stands out - a read, not advice. Answer in the "
    "language of the question, in at most four short sentences, for speaking "
    "out loud. Never read out a URL.")


def fit(width, height, most=SHOT_WIDTH):
    """A size no wider than `most`, the same shape, in even numbers."""
    if width <= most:
        w, h = width, height
    else:
        w, h = most, round(height * most / width)
    return w - w % 2, h - h % 2


def capture():
    """The screen, now, as JPEG bytes. Raises if it cannot be had."""
    import av

    container = av.open("desktop", format="gdigrab", options={"framerate": "5", "draw_mouse": "1"})
    try:
        frame = next(container.decode(video=0))
    finally:
        container.close()
    width, height = fit(frame.width, frame.height)
    frame = frame.reformat(width=width, height=height, format="yuvj420p")
    encoder = av.CodecContext.create("mjpeg", "w")
    encoder.width, encoder.height = width, height
    encoder.pix_fmt = "yuvj420p"
    encoder.time_base = fractions.Fraction(1, 5)
    encoder.options = {"q:v": "4"}
    packets = list(encoder.encode(frame)) + list(encoder.encode(None))
    data = b"".join(bytes(p) for p in packets)
    if not data:
        raise RuntimeError("the screen came back empty")
    return data


def _ask(model, picture, question):
    """The one call to Gemini. Tests replace this."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=(os.environ.get("GEMINI_CREW_KEY") or os.environ.get("GEMINI_API_KEY")))
    response = client.models.generate_content(
        model=model,
        contents=[types.Part.from_bytes(data=picture, mime_type="image/jpeg"), question],
        config=types.GenerateContentConfig(system_instruction=SYSTEM, temperature=0.3))
    return response.text


def look(question, grab=capture, ask=_ask):
    """What Apollo sees on the screen, as an answer to `question`."""
    question = " ".join(str(question or "").split()) or "What is on my screen?"
    if not (os.environ.get("GEMINI_CREW_KEY") or os.environ.get("GEMINI_API_KEY")) and ask is _ask:
        raise RuntimeError("Looking at the screen needs GEMINI_API_KEY.")
    picture = grab()
    last = None
    for model in MODELS:
        try:
            answer = ask(model, picture, question)
        except Exception as e:  # noqa: BLE001 - the next model may answer
            log.info("vision model %s failed: %s", model, e)
            last = e
            continue
        if answer and answer.strip():
            return answer.strip()
    raise RuntimeError(f"Nothing came back about the screen: {last}")
