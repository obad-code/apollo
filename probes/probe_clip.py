"""Does the replay buffer actually record this screen, and what does it cost?

Run:  .venv/Scripts/python.exe probes/probe_clip.py [seconds] [save_seconds]
It records for `seconds`, then saves the last `save_seconds` to
Videos\\Apollo's Clips and checks the file decodes.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import av  # noqa: E402
import psutil  # noqa: E402

import clips  # noqa: E402

record = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
save_seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 6.0

process = psutil.Process()
buffer = clips.ReplayBuffer().start()
process.cpu_percent(None)
time.sleep(record)
cpu = process.cpu_percent(None)
status = buffer.status()
print(f"source {status['source']} | {status['fps']} fps | holding {status['seconds']}s "
      f"| {buffer.frames} frames | cpu {cpu:.0f}% of one core "
      f"| ram {process.memory_info().rss / 1e6:.0f} MB")

result = buffer.save(save_seconds) if hasattr(buffer, "save") else None
buffer.stop()
if result and result.get("ok"):
    path = result["path"]
    back = av.open(path)
    video = sum(1 for _ in back.decode(video=0))
    audio = 0
    if any(s.type == "audio" for s in back.streams):
        back.seek(0)
        audio = sum(1 for _ in back.decode(audio=0))
    print(f"saved {path} {os.path.getsize(path) / 1e6:.1f} MB "
          f"{float(back.duration or 0) / 1e6:.1f}s video {video} audio {audio}")
    back.close()
else:
    print("save:", result)
