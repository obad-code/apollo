"""Sound for the Shorts, made here from nothing (numpy): no files to download.

Accents that land on a cut or on a beat - whoosh, pop, ding, boom, riser,
click - and the sound of the place under the voice: sea, wind, rain, a city,
crickets, birds, deep water. `mix(voice_wav, out_wav, ...)` lays them under
the narrator.
"""

import math
import wave

import numpy as np

SR = 24000
GAIN_AMBIENT = 0.16
GAIN_ACCENT = 0.5


def _noise(n, seed=0):
    return np.random.default_rng(seed).standard_normal(n).astype(np.float32)


def _lowpass(x, alpha):
    """One-pole low-pass; alpha is a number or an array (the cutoff may sweep)."""
    out = np.empty_like(x)
    a = np.broadcast_to(np.asarray(alpha, dtype=np.float32), x.shape)
    y = 0.0
    for i in range(len(x)):
        y += a[i] * (x[i] - y)
        out[i] = y
    return out


def _env(n, attack, release):
    t = np.arange(n) / SR
    up = np.clip(t / max(attack, 1e-3), 0, 1)
    down = np.clip((n / SR - t) / max(release, 1e-3), 0, 1)
    return (up * down).astype(np.float32)


def _norm(x, peak=0.9):
    m = float(np.max(np.abs(x))) or 1.0
    return (x / m * peak).astype(np.float32)


# -- accents -------------------------------------------------------------------------
def whoosh(dur=0.45):
    n = int(SR * dur)
    sweep = 0.02 + 0.5 * np.sin(np.linspace(0, math.pi, n)) ** 2
    return _norm(_lowpass(_noise(n, 1), sweep) * _env(n, dur * 0.4, dur * 0.5))


def pop():
    n = int(SR * 0.12)
    t = np.arange(n) / SR
    return _norm(np.sin(2 * math.pi * (900 * np.exp(-t * 18)) * t * 1.0) * np.exp(-t * 30))


def ding():
    n = int(SR * 0.9)
    t = np.arange(n) / SR
    return _norm((np.sin(2 * math.pi * 1318 * t) + 0.4 * np.sin(2 * math.pi * 2637 * t)) * np.exp(-t * 5))


def boom():
    n = int(SR * 0.9)
    t = np.arange(n) / SR
    body = np.sin(2 * math.pi * (110 * np.exp(-t * 3) + 36) * t) * np.exp(-t * 4)
    return _norm(body + 0.4 * _lowpass(_noise(n, 2), 0.08) * np.exp(-t * 9))


def riser(dur=0.9):
    n = int(SR * dur)
    sweep = np.linspace(0.02, 0.6, n)
    return _norm(_lowpass(_noise(n, 3), sweep) * np.linspace(0.1, 1, n) ** 2)


def click():
    n = int(SR * 0.04)
    t = np.arange(n) / SR
    return _norm(np.sin(2 * math.pi * 2200 * t) * np.exp(-t * 120))


ACCENTS = {"whoosh": whoosh, "pop": pop, "ding": ding, "boom": boom, "riser": riser, "click": click}


# -- the sound of a place --------------------------------------------------------------
def ambient(place, secs):
    n = int(SR * secs)
    t = np.arange(n) / SR
    if place in ("sea", "beach"):
        swell = 0.55 + 0.45 * np.sin(2 * math.pi * 0.13 * t)
        return _norm(_lowpass(_noise(n, 4), 0.025) * swell * 3)
    if place in ("desert", "mountains"):
        gust = 0.5 + 0.5 * np.sin(2 * math.pi * 0.07 * t + 1)
        return _norm(_lowpass(_noise(n, 5), 0.015 + 0.02 * gust) * (0.4 + gust) * 3)
    if place == "rain":
        hiss = _noise(n, 6) - _lowpass(_noise(n, 6), 0.3)
        return _norm(hiss * (0.6 + 0.2 * np.sin(2 * math.pi * 0.3 * t)))
    if place == "city":
        hum = _lowpass(_noise(n, 7), 0.006) * 4
        honk = (np.sin(2 * math.pi * 420 * t) * ((t % 5.5) < 0.18) * 0.25).astype(np.float32)
        return _norm(hum) * 0.8 + honk
    if place == "night":
        chirp = np.sin(2 * math.pi * 4200 * t) * (np.sin(2 * math.pi * 9 * t) > 0.5) * (np.sin(2 * math.pi * 0.6 * t) > -0.3)
        return _norm(chirp.astype(np.float32)) * 0.5 + _norm(_lowpass(_noise(n, 8), 0.01)) * 0.3
    if place == "forest":
        out = _norm(_lowpass(_noise(n, 9), 0.012)) * 0.35
        rng = np.random.default_rng(10)
        for _ in range(int(secs * 1.6)):
            s = int(rng.uniform(0, max(1, n - SR * 0.2)))
            m = int(SR * 0.16)
            tt = np.arange(m) / SR
            f = rng.uniform(2600, 4200)
            out[s:s + m] += (np.sin(2 * math.pi * (f + 900 * tt * 6) * tt) * np.exp(-tt * 14) * 0.5)[:max(0, n - s)][:m]
        return out
    if place == "underwater":
        out = _norm(_lowpass(_noise(n, 11), 0.008)) * 0.7
        rng = np.random.default_rng(12)
        for _ in range(int(secs * 3)):
            s = int(rng.uniform(0, max(1, n - SR * 0.1)))
            m = int(SR * 0.07)
            tt = np.arange(m) / SR
            out[s:s + m] += (np.sin(2 * math.pi * (300 + 1500 * tt * 8) * tt) * np.exp(-tt * 40) * 0.45)[:max(0, n - s)][:m]
        return out
    if place == "space":
        return _norm(np.sin(2 * math.pi * 55 * t) * (0.6 + 0.4 * np.sin(2 * math.pi * 0.2 * t))
                     + 0.5 * np.sin(2 * math.pi * 82.4 * t + 1)) * 0.8
    if place == "chart":
        return np.zeros(n, dtype=np.float32)
    return np.zeros(n, dtype=np.float32)


# -- the mix ---------------------------------------------------------------------------
def read_wav(path):
    with wave.open(path, "rb") as w:
        raw = w.readframes(w.getnframes())
        return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0, w.getframerate()


def write_wav(path, x):
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def mix(voice_wav, out_wav, place="", cues=()):
    """The narrator, with the place under him and the accents on their beats.
    `cues` is [(seconds, accent name)]. Returns out_wav."""
    voice, rate = read_wav(voice_wav)
    if rate != SR:
        raise ValueError(f"voice must be {SR} Hz, not {rate}")
    n = len(voice)
    track = np.zeros(n, dtype=np.float32)
    bed = ambient(place, n / SR)
    if len(bed):
        fade = np.minimum(1.0, np.minimum(np.arange(n), np.arange(n)[::-1]) / (SR * 0.25)).astype(np.float32)
        track += bed[:n] * GAIN_AMBIENT * fade
    for at, name in cues:
        fn = ACCENTS.get(name)
        if not fn:
            continue
        s, hit = int(at * SR), fn()
        if s < n:
            track[s:s + len(hit)] += hit[:max(0, n - s)] * GAIN_ACCENT
    write_wav(out_wav, voice * 0.95 + track)
    return out_wav
