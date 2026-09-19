"""Apollo's replay buffer: the last minute of your screen, held in memory.

Nothing reaches the disk until you ask for it. The buffer keeps H.264 packets
and raw system audio in RAM - about 100 MB for sixty seconds - and a save
copies the tail of both into an MP4 in `Videos\\Apollo's Clips`.

Measured on this machine (probes/probe_capture.py), which is why the defaults
are what they are:

    capture   ddagrab (the GPU's own desktop duplication) when it starts,
              otherwise gdigrab, which costs more CPU but always works
    encode    h264_nvenc, 1080p30, cq 26 -> 12.8 Mbps, 70% of ONE core
              (~6% of this 12-thread machine), 96 MB per 60 s
    native    2560x1440 would be 26 Mbps and 195 MB per 60 s, for detail
              nobody watching a clip needs

Two findings are baked into the code rather than left to be rediscovered:
the mp4 muxer only accepts these packets when the encoder does NOT set the
global-header flag (it extracts SPS/PPS from the in-band stream instead), and
a clip has to start on a keyframe or it opens as grey mush.
"""

import collections
import datetime
import fractions
import logging
import os
import threading
import time

import av
import av.logging

SECONDS = 60           # how much of the past the buffer holds
FPS = 30
WIDTH, HEIGHT = 1920, 1080
CQ = "26"              # NVENC constant quality; lower is better and bigger
MAXRATE = "10M"
GOP = FPS              # a keyframe a second, so any second can start a clip
SLACK = 5              # seconds kept beyond SECONDS, so a save is never short
STALE_AFTER = 5        # a buffer older than this is not "just now" any more
FOLDER_NAME = "Apollo's Clips"


def folder():
    """Where clips go: Videos\\Apollo's Clips, created on demand."""
    return os.path.join(os.path.expanduser("~"), "Videos", FOLDER_NAME)


def clip_path(when=None, folder_path=None):
    """A sortable filename for a clip saved now."""
    when = when or datetime.datetime.now()
    directory = folder_path or folder()
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, when.strftime("Apollo %Y-%m-%d %H-%M-%S.mp4"))


class Ring:
    """The last `seconds` of anything, keyed by when it arrived.

    A deque rather than a list because both ends move constantly, and the
    pruning is by time rather than by count: the video ring holds one item per
    frame, the audio ring one per 1024 samples, and neither should have to
    know the other's rate.
    """

    def __init__(self, seconds=SECONDS, slack=SLACK):
        self.seconds = seconds
        self.slack = slack
        self._items = collections.deque()
        self._lock = threading.Lock()

    def add(self, item, when):
        with self._lock:
            self._items.append((item, when))
            horizon = when - (self.seconds + self.slack)
            while self._items and self._items[0][1] < horizon:
                self._items.popleft()

    def items(self):
        """Everything held, oldest first, without the timestamps."""
        with self._lock:
            return [item for item, _ in self._items]

    def stamped(self):
        with self._lock:
            return list(self._items)

    def newest(self):
        with self._lock:
            return self._items[-1] if self._items else None

    def span(self):
        with self._lock:
            if len(self._items) < 2:
                return 0.0
            return self._items[-1][1] - self._items[0][1]


def window(packets, start):
    """The packets to write for a clip beginning at `start` (a wall time).

    Video only decodes from a keyframe, so this backs up to the newest
    keyframe at or before `start` - which is why the encoder is told to make
    one every second. Asking for more than the buffer holds gives everything
    it has; a buffer with no keyframe in it gives nothing rather than mush.
    """
    first = None
    for index, (_payload, _pts, keyframe, when) in enumerate(packets):
        if not keyframe:
            continue
        if when <= start or first is None:
            first = index
        if when > start:
            break
    return list(packets[first:]) if first is not None else []


log = logging.getLogger("apollo.clips")
av.logging.set_level(av.logging.ERROR)


class VideoSource:
    """The desktop, as frames already scaled and converted for the encoder.

    Two ways in, and only one of them is safe here: see `open`.
    """

    def __init__(self, name, graph, container=None):
        self.name = name
        self._graph = graph
        self._container = container

    @classmethod
    def open(cls):
        """Whichever capture this machine can be trusted with.

        gdigrab, unless APOLLO_CAPTURE says otherwise. This is not a
        preference: when ddagrab fails to start it does not raise, it hangs
        inside FFmpeg *holding the GIL*, which freezes every thread in Apollo
        - the voice, the hotkeys, the overlay. Measured here with a second
        (virtual) display adapter present: the main thread stops printing and
        never resumes, and no watchdog can help, because a watchdog also needs
        the GIL. So the GPU path is opt-in, for a machine where it has been
        proven, and gdigrab - two thirds of a core - is what ships.
        """
        if os.environ.get("APOLLO_CAPTURE", "").lower() == "ddagrab":
            return cls.dda()
        return cls.gdi()

    @classmethod
    def dda(cls):
        graph = av.filter.Graph()
        nodes = [graph.add("ddagrab", f"output_idx=0:framerate={FPS}:draw_mouse=1"),
                 graph.add("hwdownload"),
                 graph.add("format", "bgra"),
                 graph.add("scale", f"{WIDTH}:{HEIGHT}"),
                 graph.add("format", "nv12"),
                 graph.add("buffersink")]
        for a, b in zip(nodes, nodes[1:]):
            a.link_to(b)
        graph.configure()
        return cls("ddagrab", graph)

    @classmethod
    def gdi(cls):
        container = av.open("desktop", format="gdigrab",
                            options={"framerate": str(FPS), "draw_mouse": "1"})
        graph = av.filter.Graph()
        nodes = [graph.add_buffer(template=container.streams.video[0]),
                 graph.add("scale", f"{WIDTH}:{HEIGHT}"),
                 graph.add("format", "nv12"),
                 graph.add("buffersink")]
        for a, b in zip(nodes, nodes[1:]):
            a.link_to(b)
        graph.configure()
        return cls("gdigrab", graph, container)

    def frames(self):
        if self._container is None:
            while True:
                yield self._graph.pull()
        else:
            for raw in self._container.decode(video=0):
                self._graph.push(raw)
                yield self._graph.pull()

    def close(self):
        if self._container is not None:
            try:
                self._container.close()
            except Exception:
                pass


def _open_source():
    return VideoSource.open()


def _open_encoder(width, height):
    encoder = av.CodecContext.create("h264_nvenc", "w")
    encoder.width, encoder.height, encoder.pix_fmt = width, height, "nv12"
    encoder.time_base = fractions.Fraction(1, FPS)
    encoder.framerate = fractions.Fraction(FPS, 1)
    encoder.gop_size = GOP
    # No global-header flag on purpose: the mp4 muxer builds the header from
    # the in-band SPS/PPS, and with the flag set the file does not decode.
    # No B-frames. They would buy a few percent of size and cost exactly what
    # a replay buffer cannot afford: packets leaving the encoder out of order,
    # so a tail cut at a keyframe hands the muxer decreasing timestamps.
    encoder.options = {"preset": "p4", "tune": "hq", "rc": "vbr", "cq": CQ,
                       "b": MAXRATE, "maxrate": MAXRATE, "bufsize": MAXRATE,
                       "bf": "0"}
    encoder.open()
    return encoder


class ReplayBuffer:
    """Captures and encodes continuously; keeps the last `seconds` in memory."""

    def __init__(self, seconds=SECONDS):
        self.seconds = seconds
        self.video = Ring(seconds)
        self.audio = None
        self.frames = 0
        self.saved_today = 0
        self.last_saved = None
        self.error = None
        self.source_name = None
        self.started_at = None
        self._thread = None
        self._stopping = threading.Event()

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.running:
            return self
        self._stopping.clear()
        self.error = None
        self.audio = AudioRing(self.seconds).start()
        self._thread = threading.Thread(target=self._run, daemon=True, name="clips")
        self._thread.start()
        return self

    def stop(self, timeout=3.0):
        self._stopping.set()
        if self._thread is not None:
            self._thread.join(timeout)
        if self.audio is not None:
            self.audio.stop()
            self.audio = None

    def save(self, seconds=SECONDS, folder_path=None):
        """Write the last `seconds` to an MP4. Never raises."""
        return _save(self, seconds, folder_path)

    def _run(self):
        source = encoder = None
        try:
            source = _open_source()
            self.source_name = source.name
            self.started_at = time.monotonic()
            for frame in source.frames():
                if self._stopping.is_set():
                    break
                if encoder is None:
                    encoder = _open_encoder(frame.width if hasattr(frame, "width") else WIDTH,
                                            frame.height if hasattr(frame, "height") else HEIGHT)
                frame.pts = self.frames
                frame.time_base = fractions.Fraction(1, FPS)
                now = time.monotonic()
                for packet in encoder.encode(frame):
                    self.video.add((bytes(packet), packet.pts, bool(packet.is_keyframe), now), now)
                self.frames += 1
        except Exception as e:  # noqa: BLE001 - a dead recorder must not kill Apollo
            self.error = f"{e}"
            log.warning("replay buffer stopped: %s", e)
        finally:
            if source is not None:
                source.close()

    def status(self):
        return {"ok": self.error is None and self.running,
                "source": self.source_name,
                "seconds": round(self.video.span(), 1),
                "frames": self.frames,
                "fps": round(self.frames / (time.monotonic() - self.started_at), 1)
                        if self.started_at else 0.0,
                "saved_today": self.saved_today,
                "sound": self.audio is not None and self.audio.error is None,
                "error": self.error}


AUDIO_CHUNK = 1024


class AudioRing:
    """System audio, as WASAPI loopback, in the same shape as the video ring.

    This is what the speakers are playing, not the microphone: a clip carries
    the game, the video, the call - never the room. It is optional; if the
    loopback cannot be opened the clip is saved without sound.
    """

    def __init__(self, seconds=SECONDS):
        self.ring = Ring(seconds)
        self.rate = 48000
        self.channels = 2
        self.error = None
        self._audio = None
        self._stream = None

    def start(self):
        try:
            import pyaudiowpatch as pyaudio
            self._audio = pyaudio.PyAudio()
            wasapi = self._audio.get_host_api_info_by_type(pyaudio.paWASAPI)
            speakers = self._audio.get_device_info_by_index(wasapi["defaultOutputDevice"])
            device = next(info for info in self._audio.get_loopback_device_info_generator()
                          if speakers["name"] in info["name"])
            self.rate = int(device["defaultSampleRate"])
            self.channels = int(device["maxInputChannels"])

            def feed(data, _count, _time, _status):
                # PyAudio wants a (data, flag) pair back; returning the flag
                # alone raises a bare SystemError out of the callback thread.
                self.ring.add(data, time.monotonic())
                return (None, pyaudio.paContinue)

            self._stream = self._audio.open(
                format=pyaudio.paInt16, channels=self.channels, rate=self.rate,
                input=True, frames_per_buffer=AUDIO_CHUNK,
                input_device_index=device["index"], stream_callback=feed)
            self._stream.start_stream()
        except Exception as e:  # noqa: BLE001 - a clip without sound beats no clip
            self.error = f"{e}"
            log.info("no system audio for clips: %s", e)
        return self

    def stop(self):
        for closer in (getattr(self._stream, "stop_stream", None),
                       getattr(self._stream, "close", None),
                       getattr(self._audio, "terminate", None)):
            try:
                if closer:
                    closer()
            except Exception:
                pass
        self._stream = self._audio = None


def audio_slice(chunks, start, end, rate, channels):
    """The chunks stamped inside [start, end], in order.

    A chunk is stamped when it arrived, so it holds the ~21 ms *before* its
    stamp: taking only those stamped inside the window can start the sound a
    chunk late, never a chunk early, so it cannot run ahead of the picture.
    """
    return [(payload, when) for payload, when in chunks if start <= when <= end]


def audio_track(chunks, start, end, rate, channels):
    """One continuous PCM track for [start, end], silence where nothing came.

    WASAPI loopback delivers nothing at all while the speakers are silent, so
    the captured chunks are not a continuous recording - they are the noisy
    parts, with gaps. Concatenating them would pull every sound to the front
    of the clip and out of sync with the picture; each chunk is placed where
    it actually happened instead, and the gaps stay quiet.
    """
    import numpy as np

    taken = audio_slice(chunks, start, end, rate, channels)
    if not taken:
        return b""
    total = max(1, int(round((end - start) * rate)))
    track = np.zeros((total, channels), dtype=np.int16)
    for payload, when in taken:
        block = np.frombuffer(payload, dtype=np.int16)
        usable = (len(block) // channels) * channels
        block = block[:usable].reshape(-1, channels)
        # The stamp is the END of the chunk: it holds the audio just before it.
        offset = int(round((when - start) * rate)) - len(block)
        offset = max(0, min(total - 1, offset))
        room = min(len(block), total - offset)
        if room > 0:
            track[offset:offset + room] = block[:room]
    return track.tobytes()


def _write(path, packets, pcm, rate, channels):
    """Mux the clip. Video packets are copied as they are; audio is encoded."""
    # The file is written as "<name>.mp4.part" and renamed on success, so the
    # format cannot be inferred from the extension - it is named here.
    output = av.open(path, "w", format="mp4")
    try:
        video = output.add_mux_stream("h264", rate=FPS, width=WIDTH, height=HEIGHT,
                                      time_base=fractions.Fraction(1, FPS))
        audio = None
        if pcm:
            audio = output.add_stream("aac", rate=rate,
                                      layout="stereo" if channels == 2 else "mono")
            audio.bit_rate = 160000

        base = packets[0][1]
        for payload, pts, keyframe, _when in packets:
            packet = av.Packet(payload)
            packet.stream = video
            packet.pts = packet.dts = pts - base
            # In the encoder's own units. Without this the mp4 muxer reads
            # them in its 1/15360 base: a clip then claims to be 0.05 s long
            # and plays at several thousand frames a second.
            packet.time_base = fractions.Fraction(1, FPS)
            if keyframe:
                packet.is_keyframe = True
            output.mux(packet)

        if audio is not None:
            import numpy as np
            samples = np.frombuffer(pcm, dtype=np.int16)
            usable = (len(samples) // channels) * channels
            samples = samples[:usable].reshape(-1, channels)
            size = audio.codec_context.frame_size or 1024
            for start in range(0, max(0, len(samples) - size), size):
                block = samples[start:start + size].reshape(1, -1).copy()
                frame = av.AudioFrame.from_ndarray(
                    block, format="s16", layout="stereo" if channels == 2 else "mono")
                frame.sample_rate = rate
                frame.pts = start
                frame.time_base = fractions.Fraction(1, rate)
                output.mux(audio.encode(frame))
            output.mux(audio.encode(None))
    finally:
        output.close()


def _save(buffer, seconds, folder_path):
    if buffer.error:
        return {"ok": False, "error": f"The screen recorder isn't running: {buffer.error}"}
    packets = buffer.video.stamped()
    if not packets:
        return {"ok": False, "error": "There's nothing recorded yet."}

    now = time.monotonic()
    # Capture can stop without raising - a display mode change, a device lost.
    # The packets would still be there, minutes old, and a clip of them shows
    # whatever was on screen back then as if it had just happened.
    age = now - packets[-1][1]
    if age > STALE_AFTER:
        return {"ok": False,
                "error": f"The screen recorder stopped {int(age)} seconds ago, so "
                         f"there's nothing recent to clip."}

    start = now - seconds
    chosen = window([item for item, _ in packets], start)
    if not chosen:
        return {"ok": False, "error": "That clip has no complete frame in it yet."}

    span = chosen[-1][3] - chosen[0][3]
    pcm = b""
    rate, channels = 48000, 2
    if buffer.audio is not None and buffer.audio.error is None:
        rate, channels = buffer.audio.rate, buffer.audio.channels
        pcm = audio_track(buffer.audio.ring.stamped(), chosen[0][3], chosen[-1][3], rate, channels)

    path = clip_path(folder_path=folder_path)
    temporary = path + ".part"
    try:
        _write(temporary, chosen, pcm, rate, channels)
        os.replace(temporary, path)
    except Exception as e:  # noqa: BLE001
        try:
            os.remove(temporary)
        except OSError:
            pass
        return {"ok": False, "error": f"The clip couldn't be written: {e}"}

    buffer.saved_today += 1
    buffer.last_saved = path
    return {"ok": True, "path": path, "folder": os.path.dirname(path),
            "seconds": round(span, 1),
            "megabytes": round(os.path.getsize(path) / 1e6, 1),
            "sound": bool(pcm)}
