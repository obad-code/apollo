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
import os
import threading

SECONDS = 60           # how much of the past the buffer holds
FPS = 30
WIDTH, HEIGHT = 1920, 1080
CQ = "26"              # NVENC constant quality; lower is better and bigger
MAXRATE = "10M"
GOP = FPS              # a keyframe a second, so any second can start a clip
SLACK = 5              # seconds kept beyond SECONDS, so a save is never short
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
