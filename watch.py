"""Look at a video without playing it: a contact sheet of frames, its pace, its sound level, its words.

    .venv\\Scripts\\python.exe watch.py "https://youtu.be/XXXX"      (or a video file)

Saves, in Documents\\Apollo\\Reviews\\<title>\\ :
    sheet.png     24 frames spread over the whole video
    report.txt    length, size, how often it cuts (the pace), loudness, and the captions' text
Send those two to Claude: pictures and text are what it can read. Apollo's own Shorts get a
"preview.png" the same way.

Only for studying a reference for yourself - not for re-publishing anybody's work. Needs
yt-dlp for links (pip install yt-dlp) and FFmpeg (it comes with imageio-ffmpeg).
"""

import os
import re
import subprocess
import sys
import tempfile

NOWIN = {"creationflags": 0x08000000} if os.name == "nt" else {}


def _ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _run(args):
    return subprocess.run([_ffmpeg(), "-hide_banner", *args], capture_output=True, text=True, **NOWIN).stderr


def _fetch(source, work):
    """(video path, title, caption text) for a file or a YouTube link."""
    if os.path.exists(source):
        return source, os.path.splitext(os.path.basename(source))[0], ""
    import yt_dlp
    opts = {"outtmpl": os.path.join(work, "v.%(ext)s"), "noplaylist": True, "quiet": True, "no_warnings": True,
            "format": "b[height<=480]/worst", "writeautomaticsub": True, "writesubtitles": True,
            "subtitleslangs": ["en", "ar"], "ffmpeg_location": os.path.dirname(_ffmpeg())}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(source, download=True)
        video = ydl.prepare_filename(info)
    caps = ""
    for name in sorted(os.listdir(work)):
        if name.endswith(".vtt"):
            caps = vtt_text(os.path.join(work, name))
            break
    return video, info.get("title") or "video", caps


def vtt_text(path):
    """The spoken words of a .vtt caption file, without times, tags or repeats."""
    out, last = [], ""
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = re.sub(r"<[^>]+>", "", line).strip()
            if not line or "-->" in line or line.startswith(("WEBVTT", "Kind:", "Language:")) or line == last:
                continue
            out.append(line)
            last = line
    return " ".join(out)


def facts(video):
    log = _run(["-i", video])
    dur = re.search(r"Duration: (\d+):(\d+):([\d.]+)", log)
    seconds = int(dur.group(1)) * 3600 + int(dur.group(2)) * 60 + float(dur.group(3)) if dur else 0.0
    size = re.search(r"Video:.*?, (\d{2,5})x(\d{2,5})", log)
    shots = _run(["-i", video, "-vf", "select='gt(scene,0.35)',showinfo", "-an", "-f", "null", "-"])
    cuts = len(re.findall(r"pts_time:", shots))
    vol = _run(["-i", video, "-vn", "-af", "volumedetect", "-f", "null", "-"])
    mean = re.search(r"mean_volume: (-?[\d.]+) dB", vol)
    peak = re.search(r"max_volume: (-?[\d.]+) dB", vol)
    return {"seconds": seconds, "size": f"{size.group(1)}x{size.group(2)}" if size else "?", "cuts": cuts,
            "mean_db": float(mean.group(1)) if mean else None, "peak_db": float(peak.group(1)) if peak else None}


def review(source, out_root=None):
    out_root = out_root or os.path.join(os.path.expanduser("~"), "Documents", "Apollo", "Reviews")
    with tempfile.TemporaryDirectory(prefix="watch-") as work:
        video, title, caps = _fetch(source, work)
        folder = os.path.join(out_root, re.sub(r"[^\w\- ]+", "", title)[:60].strip() or "video")
        os.makedirs(folder, exist_ok=True)
        info = facts(video)
        sheet = os.path.join(folder, "sheet.png")
        rate = 24 / max(2.0, info["seconds"])
        _run(["-y", "-i", video, "-vf", f"fps={rate:.4f},scale=320:-1,tile=6x4:padding=6:color=white", "-frames:v", "1", sheet])
        shot = info["seconds"] / (info["cuts"] + 1) if info["seconds"] else 0
        lines = [f"title: {title}", f"length: {info['seconds']:.0f} s   size: {info['size']}",
                 f"cuts: {info['cuts']}  ->  a new shot about every {shot:.1f} s",
                 f"loudness: mean {info['mean_db']} dB, peak {info['peak_db']} dB (voice-led videos sit near -16 to -20 mean)",
                 "", "captions / transcript:", caps or "(none found)"]
        with open(os.path.join(folder, "report.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    return folder


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    print("Saved in:", review(sys.argv[1]))
