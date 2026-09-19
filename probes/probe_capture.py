"""What does a desktop replay buffer actually cost on this machine?

Captures the screen through FFmpeg's Desktop Duplication filter (`ddagrab`,
which is the GPU's own capture path), encodes it with NVENC, and reports the
frame rate it really achieved, the CPU it burned, the bitrate, and how much
memory 60 seconds of those packets would need.

Two paths are measured, because GPU-side scaling (`scale_d3d11`) fails on this
driver ("Could not create the texture"):

  native  - 2560x1440 downloaded as BGRA, encoded straight from bgr0
  1080p   - the same, scaled on the CPU with swscale, encoded from nv12

Run:  .venv/Scripts/python.exe probes/probe_capture.py [seconds]
"""

import fractions
import os
import sys
import time

import av
import av.logging
import psutil

av.logging.set_level(av.logging.ERROR)

FPS = 30
GOP = FPS          # a keyframe a second, so a clip can start anywhere
BITRATE = "12M"


def graph(scale_to=None):
    g = av.filter.Graph()
    nodes = [g.add("ddagrab", f"output_idx=0:framerate={FPS}:draw_mouse=1"),
             g.add("hwdownload")]
    if scale_to:
        nodes += [g.add("format", "bgra"),
                  g.add("scale", f"{scale_to[0]}:{scale_to[1]}"),
                  g.add("format", "nv12")]
    else:
        nodes += [g.add("format", "bgr0")]
    nodes.append(g.add("buffersink"))
    for a, b in zip(nodes, nodes[1:]):
        a.link_to(b)
    g.configure()
    return g


def encoder(width, height, pix_fmt):
    enc = av.CodecContext.create("h264_nvenc", "w")
    enc.width, enc.height, enc.pix_fmt = width, height, pix_fmt
    enc.time_base = fractions.Fraction(1, FPS)
    enc.framerate = fractions.Fraction(FPS, 1)
    enc.gop_size = GOP
    enc.options = {"preset": "p4", "tune": "hq", "rc": "vbr", "cq": "23",
                   "b": BITRATE, "maxrate": "20M", "bufsize": "24M"}
    enc.open()
    return enc


def measure(label, seconds, scale_to=None):
    proc = psutil.Process(os.getpid())
    g = graph(scale_to)
    first = g.pull()
    enc = encoder(first.width, first.height, first.format.name)
    packets, frames, nbytes, keys = 0, 0, 0, 0
    proc.cpu_percent(None)
    start = time.monotonic()
    while time.monotonic() - start < seconds:
        frame = g.pull()
        frame.pts = frames
        frame.time_base = enc.time_base
        for p in enc.encode(frame):
            packets += 1
            nbytes += p.size
            keys += bool(p.is_keyframe)
        frames += 1
    for p in enc.encode(None):
        packets += 1
        nbytes += p.size
    cpu = proc.cpu_percent(None)
    elapsed = time.monotonic() - start
    per_second = nbytes / elapsed
    print(f"{label:7} {first.width}x{first.height} {first.format.name:5} "
          f"{frames / elapsed:5.1f} fps  cpu {cpu:5.1f}% of one core  "
          f"{per_second * 8 / 1e6:5.1f} Mbps  60s buffer = {per_second * 60 / 1e6:5.0f} MB  "
          f"keyframes {keys}")
    return {"w": first.width, "h": first.height, "fps": frames / elapsed, "cpu": cpu,
            "mb60": per_second * 60 / 1e6}


if __name__ == "__main__":
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
    print(f"cpu count {psutil.cpu_count()}, measuring {seconds:.0f}s each")
    measure("native", seconds)
    measure("1080p", seconds, scale_to=(1920, 1080))
