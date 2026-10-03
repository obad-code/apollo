"""LYLA's downloads: a YouTube video (or its sound) saved to your PC.

"ليلى نزلي هالمقطع", "LYLA, download the new GTA trailer" - a link or just
what to search for. It runs on a thread of its own, so Apollo is free at
once, and when the file is saved he says so.

It needs yt-dlp: `pip install yt-dlp` into Apollo's .venv (or yt-dlp.exe on
PATH). ffmpeg on PATH is better still - with it a video comes in the best
quality as one .mp4 and sound comes as .mp3; without it, the best single
file there is. Videos go to Videos\\Apollo, sound to Music\\Apollo.

Only what you ask for, and only for you: this is for saving things to watch
later, not for re-publishing anybody's work.
"""

import logging
import os
import queue
import re
import shutil
import subprocess
import threading
import time

log = logging.getLogger("apollo.youtube")

_URL = re.compile(r"^https?://(www\.|m\.|music\.)?(youtube\.com|youtu\.be)/", re.I)


def folder(audio_only=False):
    home = os.path.expanduser("~")
    return os.path.join(home, "Music" if audio_only else "Videos", "Apollo")


def target_for(what):
    """A YouTube link as it is, anything else as a search for the top result."""
    what = " ".join(str(what or "").split())
    if not what:
        raise ValueError("Nothing to download was given.")
    if _URL.match(what):
        return what
    if re.match(r"^https?://", what, re.I):
        raise ValueError("That is not a YouTube link.")
    return f"ytsearch1:{what}"


def options(audio_only, has_ffmpeg, out_dir):
    """yt-dlp settings for one download."""
    opts = {"outtmpl": os.path.join(out_dir, "%(title).120B [%(id)s].%(ext)s"),
            "noplaylist": True, "quiet": True, "no_warnings": True,
            "restrictfilenames": False, "windowsfilenames": True}
    if audio_only:
        opts["format"] = "bestaudio/best"
        if has_ffmpeg:
            opts["postprocessors"] = [{"key": "FFmpegExtractAudio",
                                       "preferredcodec": "mp3", "preferredquality": "192"}]
    else:
        opts["format"] = ("bv*[height<=1080]+ba/b[height<=1080]/b" if has_ffmpeg
                          else "b[ext=mp4]/b")
        if has_ffmpeg:
            opts["merge_output_format"] = "mp4"
    return opts


def available():
    """'module', 'exe' or None - how yt-dlp can be reached."""
    try:
        import yt_dlp  # noqa: F401
        return "module"
    except ImportError:
        return "exe" if shutil.which("yt-dlp") else None


def _run_module(target, opts):
    import yt_dlp
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(target, download=True)
        if info and info.get("entries"):
            info = info["entries"][0]
        path = None
        downloads = (info or {}).get("requested_downloads") or []
        if downloads:
            path = downloads[-1].get("filepath")
        return {"title": (info or {}).get("title", ""), "path": path or ydl.prepare_filename(info)}


def _run_exe(target, opts):
    args = ["yt-dlp", "--no-playlist", "-o", opts["outtmpl"], "-f", opts["format"],
            "--print", "after_move:filepath", "--print", "title"]
    if opts.get("merge_output_format"):
        args += ["--merge-output-format", opts["merge_output_format"]]
    if opts.get("postprocessors"):
        args += ["-x", "--audio-format", "mp3"]
    done = subprocess.run(args + [target], capture_output=True, text=True, timeout=1800,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if done.returncode != 0:
        raise RuntimeError((done.stderr or "yt-dlp failed").strip().splitlines()[-1][:200])
    lines = [line for line in done.stdout.splitlines() if line.strip()]
    return {"title": lines[0] if len(lines) > 1 else "", "path": lines[-1] if lines else ""}


class Downloads:
    """One download at a time, in order. `report(job)` says how it went."""

    def __init__(self, run=None, report=None, gate=None, tell=None):
        self.run = run
        self.report = report
        self.gate = gate
        self.tell = tell
        self.jobs = queue.Queue()
        self._thread = None
        self._lock = threading.Lock()

    def configure(self, report=None, gate=None, tell=None):
        self.report, self.gate, self.tell = report, gate, tell
        return self

    def take(self, what, audio_only=False):
        """Queue a download. Raises ValueError for something it cannot take."""
        how = available() if self.run is None else "given"
        if how is None:
            raise RuntimeError("yt-dlp is not installed. In Apollo's folder run: "
                               ".venv\\Scripts\\pip install yt-dlp")
        job = {"what": str(what), "target": target_for(what), "audio": bool(audio_only),
               "asked": time.time(), "agent": "LYLA"}
        ahead = self.jobs.qsize()
        self.jobs.put(job)
        with self._lock:
            if self._thread is None:
                self._thread = threading.Thread(target=self._work, daemon=True, name="lyla-downloads")
                self._thread.start()
        return {"ahead": ahead, "folder": folder(audio_only)}

    def _work(self):
        while True:
            try:
                job = self.jobs.get(timeout=30)
            except queue.Empty:
                with self._lock:
                    if self.jobs.empty():
                        self._thread = None
                        return
                continue
            self.do(job)

    def _card(self, job, **event):
        if self.tell is None:
            return
        try:
            self.tell({"agent": "LYLA", "task": f"Download: {job['what']}", "symbol": "", **event})
        except Exception:  # noqa: BLE001
            log.debug("download card failed", exc_info=True)

    def do(self, job):
        out_dir = folder(job["audio"])
        self._card(job, stage="received", text=job["what"], by="Apollo")
        try:
            os.makedirs(out_dir, exist_ok=True)
            opts = options(job["audio"], bool(shutil.which("ffmpeg")), out_dir)
            self._card(job, stage="step", text="Downloading from YouTube")
            run = self.run or (_run_module if available() == "module" else _run_exe)
            got = run(job["target"], opts)
            job.update(ok=True, title=got.get("title", ""), path=got.get("path", ""))
            self._card(job, stage="done", text=f"Saved {job['title'] or 'it'}")
        except Exception as e:  # noqa: BLE001 - a failed download is reported, not raised
            log.warning("download failed: %s", e)
            job.update(ok=False, error=str(e) or type(e).__name__)
            self._card(job, stage="error", text=job["error"])
        if self.report is not None:
            try:
                if self.gate is None:
                    self.report(job)
                else:
                    with self.gate:
                        self.report(job)
            except Exception:  # noqa: BLE001
                log.warning("download report failed", exc_info=True)
        return job


DOWNLOADS = Downloads()
