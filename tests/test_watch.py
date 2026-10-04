import os
import subprocess

import watch


def test_a_video_is_reviewed_into_a_sheet_and_a_report(tmp_path):
    video = str(tmp_path / "clip.mp4")
    ff = watch._ffmpeg()
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=320x568:rate=10:duration=6",
                    "-f", "lavfi", "-i", "sine=frequency=300:duration=6", "-shortest", "-pix_fmt", "yuv420p", video], check=True)
    folder = watch.review(video, out_root=str(tmp_path / "out"))
    assert os.path.exists(os.path.join(folder, "sheet.png"))
    report = open(os.path.join(folder, "report.txt"), encoding="utf-8").read()
    assert "length: 6 s" in report and "cuts:" in report and "loudness:" in report


def test_caption_text_is_cleaned(tmp_path):
    vtt = tmp_path / "a.vtt"
    vtt.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:02.000\n<c>Hello</c> there\n\n00:00:02.000 --> 00:00:04.000\nHello there\nnext line\n", encoding="utf-8")
    assert watch.vtt_text(str(vtt)) == "Hello there next line"
