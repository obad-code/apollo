"""A file dropped on the display is scanned (scanner.py): the page is told
it has started, each step as it goes, and the report at the end."""
import threading

import apollo
import scanner


class UI:
    alive = True

    def __init__(self):
        self.events = []
        self.done = threading.Event()

    def scan(self, event):
        self.events.append(event)
        if event["state"] in ("done", "error"):
            self.done.set()


def app_with(monkeypatch, report=None):
    app = apollo.Apollo.__new__(apollo.Apollo)
    app.ui = UI()
    app._scan_lock = threading.Lock()

    def fake_scan(path, on_step=None):
        on_step("reading it")
        return report or {"name": "a.txt", "verdict": "clean", "headline": "Nothing wrong found."}

    monkeypatch.setattr(apollo.scanner, "scan", fake_scan)
    return app


def drop(*paths):
    return {"type": "drop", "dataTransfer": {"files": [
        {"name": p.split("\\")[-1], "pywebviewFullPath": p} for p in paths]}}


def test_a_dropped_file_is_scanned_and_the_page_hears_every_step(monkeypatch):
    app = app_with(monkeypatch)
    app.on_drop(drop(r"C:\Users\Admin\Downloads\a.txt"))
    assert app.ui.done.wait(5)
    states = [e["state"] for e in app.ui.events]
    assert states == ["scanning", "step", "done"]
    assert app.ui.events[0]["name"] == "a.txt"
    assert app.ui.events[-1]["report"]["verdict"] == "clean"


def test_several_are_scanned_one_after_another(monkeypatch):
    app = app_with(monkeypatch)
    app.on_drop(drop(r"C:\a.txt", r"C:\b.txt"))
    for _ in range(50):
        if sum(1 for e in app.ui.events if e["state"] == "done") == 2:
            break
        threading.Event().wait(0.05)
    assert [e["name"] for e in app.ui.events if e["state"] == "scanning"] == ["a.txt", "b.txt"]


def test_a_drop_with_no_file_in_it_says_so(monkeypatch):
    app = app_with(monkeypatch)
    app.on_drop({"type": "drop", "dataTransfer": {"files": [{"name": "x"}]}})
    assert app.ui.events and app.ui.events[0]["state"] == "error"


def test_the_page_is_told():
    class Window:
        scripts = []

        def evaluate_js(self, script):
            self.scripts.append(script)

    ui = apollo.WebReporter.__new__(apollo.WebReporter)
    ui.window, ui.alive = Window(), True
    ui.scan({"state": "scanning", "name": "a.txt"})
    assert ui.window.scripts[-1].startswith("window.apollo.scan && window.apollo.scan(")


def test_the_real_scanner_is_what_runs():
    assert apollo.scanner is scanner
