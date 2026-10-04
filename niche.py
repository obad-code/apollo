"""LYLA picks the channel's niche: the best ten niches for a faceless stick-man
Shorts channel right now, ranked, with the honest numbers and first video ideas.
You choose one ("نيش 3") and it becomes a standing instruction for every Short
(see shorts.set_style). Estimates are estimates: the model has no live data.
"""

import json
import os
import re

SYSTEM = (
    "You are a YouTube growth researcher for a FACELESS hand-drawn stick-man Shorts channel. "
    "Name the best niches for it right now. Avoid the oversaturated 'AI slop' categories that "
    "are flooded with mass-produced junk; prefer real audience demand, a repeatable story "
    "angle and a realistic way to earn. Nothing indecent or against Islam. Never invent "
    "precise numbers: give RPM as a realistic range and say it is an estimate. Answer ONLY "
    'with JSON: [{"niche": "...", "angle": "one line", "why_now": "the specific trend", '
    '"competition": "Low|Medium|High", "rpm_estimate": "range, estimate", "earn": "how it earns", '
    '"difficulty": "how hard to make daily", "ideas": ["video idea", "video idea", "video idea"]}] '
    "ordered best opportunity first.")


def path():
    import files
    return os.path.join(files.root(), "Shorts", "niches.json")


def ask(count=10, think=None):
    prompt = f"List the {count} best niches, ranked. Language of the text: English."
    if think is None:
        import lyla
        text, _ = lyla.think(prompt, SYSTEM)
    else:
        text = think(prompt)
    found = re.search(r"\[.*\]", text or "", re.S)
    if not found:
        raise RuntimeError("The niche list did not come back as JSON.")
    rows = [r for r in json.loads(found.group(0)) if str(r.get("niche", "")).strip()]
    if not rows:
        raise RuntimeError("The niche list was empty.")
    return rows[:count]


def render(rows):
    out = []
    for i, r in enumerate(rows, 1):
        out.append(f"{i}. {r['niche']} - {r.get('angle', '')}\n"
                   f"   Why now: {r.get('why_now', '')}\n"
                   f"   Competition: {r.get('competition', '?')} | RPM (estimate): {r.get('rpm_estimate', '?')} | "
                   f"Difficulty: {r.get('difficulty', '?')}\n"
                   f"   Earns: {r.get('earn', '')}\n"
                   f"   Ideas: " + " / ".join(r.get("ideas", [])[:3]))
    return "\n\n".join(out)


def save(rows):
    try:
        os.makedirs(os.path.dirname(path()), exist_ok=True)
        with open(path(), "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


def load():
    try:
        with open(path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def choose(number):
    """Make niche `number` (1-based, from the last list) the channel's niche."""
    import shorts
    rows = load()
    if not 1 <= number <= len(rows):
        return {"ok": False, "error": f"Pick 1 to {len(rows)}." if rows else "Ask for the niches first (niche)."}
    r = rows[number - 1]
    keep = [line for line in shorts.style_notes().splitlines() if not line.startswith("Channel niche:")]
    note = (f"Channel niche: {r['niche']} - {r.get('angle', '')}. Every Short belongs to this niche. "
            f"Example ideas: {'; '.join(r.get('ideas', [])[:3])}.")
    shorts.set_style("\n".join(keep + [note]), add=False)
    return {"ok": True, "result": f"The channel's niche is now: {r['niche']}"}
