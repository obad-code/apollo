"""Apollo's checks of itself, as it comes up.

Quick and all at once - each on a thread of its own, the lot given a few
seconds - and each said on the boot screen the moment it lands: the keys,
the network, the microphone and the speakers, the disk, the files Apollo
keeps, the clip encoder, whether it crashed last time, a self-test of the
functions that read what it keeps, and the sources the display reads.
Anything wrong goes to issues.py for the System panel (apollo.py does that).

A check returns (status, detail): OK, WARN (something works less well) or
FAIL (something does not work). One that raises is a FAIL with the reason;
one that has not answered by the deadline is a WARN, and the boot goes on
without it.
"""

import json
import os
import queue
import re
import shutil
import socket
import threading
import time
import urllib.request

OK, WARN, FAIL = "ok", "warn", "fail"

APOLLO_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Apollo")
LOG_PATH = os.path.join(APOLLO_DIR, "apollo.log")
CRASH_PATH = os.path.join(APOLLO_DIR, "crash.log")
SEEN_PATH = os.path.join(APOLLO_DIR, "diagnostics.json")

TIMEOUT = 6.0            # seconds the whole lot is given


def check_keys(env=None):
    """The keys Apollo runs on. No Gemini key is no voice at all."""
    env = os.environ if env is None else env
    if not env.get("GEMINI_API_KEY"):
        return FAIL, "no GEMINI_API_KEY - Apollo has no voice"
    missing = [name for name, what in (("ANTHROPIC_API_KEY", "agents and learning are off"),
                                       ("FINNHUB_API_KEY", "prices refresh once a minute"))
               if not env.get(name)]
    if missing:
        return WARN, "; ".join(f"no {name}" for name in missing)
    return OK, "all there"


def check_network(host="generativelanguage.googleapis.com", port=443, timeout=3.0):
    try:
        socket.create_connection((host, port), timeout=timeout).close()
    except OSError as e:
        return FAIL, f"offline - Google did not answer ({type(e).__name__})"
    return OK, "online"


def _listed(kind):
    """The default device's name, or an exception if there is none."""
    import sounddevice as sd
    return str(sd.query_devices(kind=kind).get("name", ""))


def _opens(kind):
    """Open the device the way Apollo does, and let it go at once: a device
    can be listed and still refuse every program (a Bluetooth pair gone
    quiet answers MME error 1)."""
    import sounddevice as sd
    stream = (sd.RawInputStream if kind == "input" else sd.RawOutputStream)(
        samplerate=16000 if kind == "input" else 24000, channels=1, dtype="int16")
    stream.close()


def _device(kind):
    what = "microphone" if kind == "input" else "speakers"
    try:
        name = _listed(kind)
    except Exception as e:  # noqa: BLE001 - PortAudio says why in its own words
        return FAIL, f"no {what} ({e})"
    try:
        _opens(kind)
    except Exception as e:  # noqa: BLE001
        return FAIL, f"{name[:30]} will not open ({str(e)[-40:]})"
    return OK, name[:40]


def check_mic():
    return _device("input")


def check_speakers():
    return _device("output")


def check_disk(folder=None):
    folder = folder or APOLLO_DIR
    target = folder if os.path.isdir(folder) else os.path.expanduser("~")
    free = shutil.disk_usage(target).free / 2**30
    if free < 2:
        return FAIL, f"{free:.1f} GB free - clips and logs will fail"
    if free < 10:
        return WARN, f"{free:.0f} GB free"
    return OK, f"{free:.0f} GB free"


def check_state(folder=None):
    """Every file Apollo keeps still reads: a damaged one is the layout, the
    watchlist or the ideas quietly starting again from nothing."""
    folder = folder or APOLLO_DIR
    try:
        names = sorted(n for n in os.listdir(folder) if n.endswith(".json"))
    except OSError:
        return OK, "nothing kept yet"
    bad = []
    for name in names:
        try:
            with open(os.path.join(folder, name), encoding="utf-8") as handle:
                json.load(handle)
        except (OSError, ValueError, UnicodeDecodeError):
            bad.append(name)
    if bad:
        return WARN, "unreadable: " + ", ".join(bad)
    return OK, f"{len(names)} files read"


def check_encoder():
    """The GPU's H.264 encoder the replay buffer records with."""
    try:
        import av
        av.codec.Codec("h264_nvenc", "w")
    except Exception:  # noqa: BLE001 - no NVENC in this FFmpeg, or no NVIDIA card
        return WARN, "no NVENC encoder - clips cannot record"
    return OK, "NVENC"


_CRITICAL = re.compile(r"\sCRITICAL\s+\S+:\s*(.*)")


def check_last_run(log_path=None, crash_path=None, seen_path=None):
    """Whether Apollo crashed the last time it ran: an exception nobody
    caught, in the log between the last two starts, or a crash inside a DLL,
    which only shows as crash.log growing (apollo.watch_crashes)."""
    log_path, crash_path = log_path or LOG_PATH, crash_path or CRASH_PATH
    seen_path = seen_path or SEEN_PATH
    try:
        with open(log_path, encoding="utf-8", errors="replace") as handle:
            lines = handle.read().splitlines()
    except OSError:
        lines = []
    starts = [i for i, line in enumerate(lines) if "apollo: started, pid" in line]
    previous = lines[starts[-2]:starts[-1]] if len(starts) >= 2 else []
    crashed = [m.group(1) for m in map(_CRITICAL.search, previous) if m]

    try:
        size = os.path.getsize(crash_path)
    except OSError:
        size = 0
    try:
        with open(seen_path, encoding="utf-8") as handle:
            seen = int(json.load(handle).get("crash_size", size))
    except (OSError, ValueError, AttributeError, TypeError):
        seen = size                  # nothing to compare with: from now on
    try:
        with open(seen_path, "w", encoding="utf-8") as handle:
            json.dump({"crash_size": size}, handle)
    except OSError:
        pass

    if crashed:
        return FAIL, f"crashed last time: {crashed[0][:80]}"
    if size > seen:
        return FAIL, "crashed last time inside a DLL - see crash.log"
    return OK, "clean"


def _self_tests():
    """The functions that read what Apollo keeps, each run once."""
    import displays
    import ideas
    import interests
    import issues
    import panels
    import private_eye
    import reminders
    import trading
    import watchlist
    return (("layout", displays.state), ("watchlist", watchlist.current),
            ("interests", interests.load), ("ideas", ideas.all), ("reminders", reminders.pending),
            ("panels", panels.state), ("finds", private_eye.load), ("issues", issues.current),
            ("trading", lambda: trading.verdict(trading.conclude())))


SELF_TESTS = None          # None: the real ones (_self_tests); the tests put their own


def check_self():
    tests = SELF_TESTS if SELF_TESTS is not None else _self_tests()
    broken = []
    for name, fn in tests:
        try:
            fn()
        except Exception as e:  # noqa: BLE001 - that it broke, and how, is the result
            broken.append(f"{name} ({type(e).__name__})")
    if broken:
        return FAIL, "broke: " + ", ".join(broken)
    return OK, f"{len(tests)} passed"


SOURCES = (("prices", "https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=1d&interval=1d"),
           ("weather", "https://api.open-meteo.com/v1/forecast?latitude=24.7&longitude=46.7"
                       "&current=temperature_2m"))


def check_sources(timeout=4.0):
    """The display's own sources answer."""
    down = []
    for name, url in SOURCES:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Apollo"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                response.read(256)
        except Exception:  # noqa: BLE001 - down is down, whatever the reason
            down.append(name)
    if down:
        return WARN, "not answering: " + ", ".join(down)
    return OK, "answering"


CHECKS = (
    ("keys", "API KEYS", check_keys),
    ("network", "NETWORK", check_network),
    ("mic", "MICROPHONE", check_mic),
    ("speakers", "SPEAKERS", check_speakers),
    ("disk", "DISK", check_disk),
    ("state", "SAVED STATE", check_state),
    ("encoder", "CLIP ENCODER", check_encoder),
    ("lastrun", "LAST RUN", check_last_run),
    ("self", "SELF TEST", check_self),
    ("sources", "DATA SOURCES", check_sources),
)


def run(report=None, timeout=TIMEOUT):
    """Every check at once. `report(result)` as each lands; returns them all,
    in CHECKS' order. A result: {id, label, status, detail}."""
    landed = queue.Queue()
    checks = list(CHECKS)

    def one(cid, label, fn):
        try:
            status, detail = fn()
        except Exception as e:  # noqa: BLE001 - a check that breaks is a failure, not a crash
            status, detail = FAIL, f"{type(e).__name__}: {e}"[:120]
        landed.put({"id": cid, "label": label, "status": status, "detail": str(detail)})

    for cid, label, fn in checks:
        threading.Thread(target=one, args=(cid, label, fn), daemon=True,
                         name=f"check-{cid}").start()

    results = {}
    deadline = time.monotonic() + timeout
    while len(results) < len(checks):
        left = deadline - time.monotonic()
        if left <= 0:
            break
        try:
            result = landed.get(timeout=left)
        except queue.Empty:
            break
        results[result["id"]] = result
        if report is not None:
            report(result)
    for cid, label, _fn in checks:
        if cid not in results:
            results[cid] = {"id": cid, "label": label, "status": WARN,
                            "detail": f"no answer in {timeout:.0f} s"}
            if report is not None:
                report(results[cid])
    return [results[cid] for cid, _label, _fn in checks]
