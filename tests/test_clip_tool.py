import os

import tools


class FakeBuffer:
    def __init__(self, result):
        self.result = result
        self.asked = []

    def save(self, seconds=60, folder_path=None):
        self.asked.append(seconds)
        return self.result


def test_save_clip_hands_back_the_file(monkeypatch):
    buffer = FakeBuffer({"ok": True, "path": r"C:\Users\x\Videos\Apollo's Clips\Apollo 2026-09-20 02-11-07.mp4",
                         "seconds": 60.0, "megabytes": 96.0, "sound": True})
    tools.set_clip_buffer(buffer)
    result = tools.run("save_clip", {})
    assert result["ok"] is True and result["seconds"] == 60.0
    assert buffer.asked == [60]


def test_save_clip_passes_a_shorter_request(monkeypatch):
    buffer = FakeBuffer({"ok": True, "path": "x.mp4", "seconds": 15.0, "megabytes": 24.0, "sound": False})
    tools.set_clip_buffer(buffer)
    tools.run("save_clip", {"seconds": "15"})
    assert buffer.asked == [15]


def test_save_clip_reports_unavailable():
    tools.set_clip_buffer(None)
    result = tools.run("save_clip", {})
    assert result["ok"] is False and "recorder" in result["error"].lower()


def test_apollo_can_open_the_clips_folder(monkeypatch):
    """"Open my clips" has to land somewhere, even before there are any.

    The folder is made on demand when a clip is saved, so asking for it on a
    fresh machine would otherwise open nothing and say it worked.
    """
    opened = []
    monkeypatch.setattr(tools.pc_control, "open_path",
                        lambda target, want_folder=False: opened.append(target) or
                        {"ok": True, "opened": target})

    result = tools.run("open_clips", {}, tools.Context())

    assert result["ok"] is True
    assert opened and opened[0].endswith("Apollo's Clips")
    assert os.path.isdir(opened[0]), "the folder was not created first"
