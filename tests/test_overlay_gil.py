"""Window changes must let go of Python while they wait.

Changing another thread's window - its style, its visibility, its place -
makes Windows send that thread a message and wait for the answer. pywin32's
wrappers wait holding the GIL. The window's thread is the WebView2 thread, and
it runs Python callbacks (every evaluate_js answer is one), so the moment it
needed the GIL while the watcher sat in SetWindowLong holding it, both
stopped for good: Apollo came up, said "API reachable", and never spoke.
ctypes' WinDLL releases the GIL for the length of the call, so the window's
thread can take it, answer, and let the call return.
"""
import ctypes

import pytest

import apollo


class _User32:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def call(*args):
            self.calls.append(name)
            return 1
        return call


@pytest.fixture
def user32(monkeypatch):
    def held(*args):
        raise AssertionError("a pywin32 call that waits on another thread's window, holding the GIL")

    for name in ("SetWindowLong", "ShowWindow", "SetWindowPos"):
        monkeypatch.setattr(apollo.win32gui, name, held)
    monkeypatch.setattr(apollo.win32gui, "FindWindow", lambda cls, title: 1234)
    monkeypatch.setattr(apollo.win32gui, "GetWindowLong", lambda hwnd, index: 0)
    monkeypatch.setattr(apollo.win32gui, "IsWindowVisible", lambda hwnd: True)
    fake = _User32()
    monkeypatch.setattr(apollo, "_user32", fake)
    return fake


def test_attaching_goes_through_ctypes(user32):
    overlay = apollo.Overlay()
    assert overlay.attach(tries=1, gap=0) is True
    assert {"ShowWindow", "SetWindowLongPtrW"} <= set(user32.calls)


def test_showing_hiding_and_clicking_go_through_ctypes(user32):
    overlay = apollo.Overlay()
    overlay.hwnd = 1234
    overlay.show_page(apollo.Overlay.FULL)
    overlay.set_clickable(False)
    overlay.hide_page()
    overlay.raise_above()
    assert {"ShowWindow", "SetWindowLongPtrW", "SetWindowPos"} <= set(user32.calls)


def test_the_real_library_releases_the_gil():
    """WinDLL does; PyDLL would not."""
    assert isinstance(apollo.user32_releasing_gil(), ctypes.WinDLL)
    assert not isinstance(apollo.user32_releasing_gil(), ctypes.PyDLL)
