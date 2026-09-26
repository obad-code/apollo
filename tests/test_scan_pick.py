"""Choosing a file to scan through File Explorer: the display fills the
screen, so there is nothing behind it to drag a file from. Choose file on
the scanner - or "scan a file" to Apollo - opens the open dialog over the
display, and what you pick is scanned like a drop."""
import pathlib
import threading

import apollo
import tools

FULL = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full"


class UI:
    alive = True

    def __init__(self):
        self.events = []
        self.done = threading.Event()

    def scan(self, event):
        self.events.append(event)
        if event["state"] == "done" and sum(e["state"] == "done" for e in self.events) >= self.want:
            self.done.set()


class Window:
    def __init__(self, chosen=None, fails=False):
        self.chosen, self.fails, self.asked = chosen, fails, []

    def create_file_dialog(self, kind, allow_multiple=False):
        self.asked.append(allow_multiple)
        if self.fails:
            raise RuntimeError("no dialog")
        return self.chosen


def app_with(monkeypatch, window, want=1):
    app = apollo.Apollo.__new__(apollo.Apollo)
    app.ui = UI()
    app.ui.want = want
    app.window = window
    app._scan_lock = threading.Lock()
    monkeypatch.setattr(apollo.scanner, "scan",
                        lambda path, on_step=None: {"name": path, "verdict": "clean"})
    return app


def test_what_you_pick_is_scanned(monkeypatch):
    app = app_with(monkeypatch, Window(("/home/me/a.txt", "/home/me/b.exe")), want=2)
    assert app.choose_and_scan() is True
    assert app.ui.done.wait(5)
    assert [e["name"] for e in app.ui.events if e["state"] == "scanning"] == ["a.txt", "b.exe"]
    assert app.window.asked == [True]                  # more than one may be picked


def test_a_dialog_closed_without_a_file_scans_nothing(monkeypatch):
    app = app_with(monkeypatch, Window(None))
    assert app.choose_and_scan() is False
    assert app.ui.events == []


def test_a_dialog_that_will_not_open_is_not_a_crash(monkeypatch):
    app = app_with(monkeypatch, Window(fails=True))
    assert app.choose_and_scan() is False


def test_without_a_display_there_is_no_dialog(monkeypatch):
    app = app_with(monkeypatch, None)
    assert app.choose_and_scan() is False


def test_asking_apollo_to_scan_a_file_brings_the_display_up_and_opens_it():
    asked = []
    ctx = tools.Context(display_hook=lambda request: asked.append(request) or True)
    out = tools.run("scan_file", {}, ctx)
    assert out["ok"] and asked == [{"action": "scan"}]
    assert apollo.Apollo._to_be_seen({"action": "scan"})
    assert "افحص ملف" in tools.REGISTRY["scan_file"].description


def test_the_scanner_has_a_choose_file_button_that_opens_the_dialog():
    html = (FULL / "index.html").read_text(encoding="utf-8")
    app = (FULL / "app.js").read_text(encoding="utf-8")
    assert 'id="scan-pick"' in html and "Choose file" in html
    assert "api.pick_file()" in app
    assert "if (asked.action === 'scan') pickFile();" in app
