import pytest

import pc_control as pc


@pytest.fixture
def sent(monkeypatch):
    log = []
    monkeypatch.setattr(pc, "wait_for_release", lambda *a, **k: True)
    monkeypatch.setattr(pc, "_send", lambda events: log.extend(
        (e.u.ki.wVk, e.u.ki.wScan, e.u.ki.dwFlags) for e in events) or len(events))
    return log


def test_resolve_url():
    assert pc.resolve_url("YouTube") == "https://www.youtube.com"
    assert pc.resolve_url("the github website") == "https://github.com"
    assert pc.resolve_url("example.org/docs") == "https://example.org/docs"
    assert pc.resolve_url("https://x.com/home") == "https://x.com/home"
    assert pc.resolve_url("best pizza near me") == "https://www.google.com/search?q=best+pizza+near+me"
    assert pc.resolve_url("file:///C:/Windows/system32/cmd.exe").startswith("https://www.google.com/search?q=")


def test_open_url_starts_resolved_url(monkeypatch):
    started = []
    monkeypatch.setattr(pc, "_try_start", lambda t: started.append(t) or True)
    assert pc.open_url("reddit") == "Opened https://www.reddit.com."
    assert started == ["https://www.reddit.com"]


def test_parse_chord():
    assert pc.parse_chord("ctrl+shift+t") == [0x11, 0x10, ord("T")]
    assert pc.parse_chord("Alt + F4") == [0x12, 0x73]
    assert pc.parse_chord("win+left") == [0x5B, 0x25]
    assert pc.parse_chord("page down") == [0x22]
    with pytest.raises(ValueError):
        pc.parse_chord("ctrl+banana")


def test_press_keys_downs_then_ups_in_reverse(sent):
    assert pc.press_keys("ctrl+c") == "Pressed ctrl+c."
    assert [(vk, flags & pc.KEYEVENTF_KEYUP) for vk, _, flags in sent] == [
        (0x11, 0), (ord("C"), 0), (ord("C"), 2), (0x11, 2)]


def test_ctrl_alt_delete_is_refused(sent):
    assert pc.press_keys("ctrl+alt+delete").startswith("Failed")
    assert sent == []


def test_type_text_sends_unicode_including_arabic(sent):
    assert pc.type_text("Hi مرحبا\n") == "Typed 9 characters."
    scans = [scan for vk, scan, flags in sent if flags & pc.KEYEVENTF_UNICODE and not flags & pc.KEYEVENTF_KEYUP]
    assert "".join(map(chr, scans)) == "Hi مرحبا"
    assert (0x0D, 0, 0) in sent


def test_media_presses_the_media_key(sent):
    assert pc.media("next") == "Skipped to the next track."
    assert sent[0][0] == 0xB0


class FakeEndpoint:
    def __init__(self, level=0.5, muted=0):
        self.level, self.muted = level, muted

    def GetMasterVolumeLevelScalar(self):
        return self.level

    def SetMasterVolumeLevelScalar(self, v, ctx):
        self.level = v

    def GetMute(self):
        return self.muted

    def SetMute(self, m, ctx):
        self.muted = m


def test_volume(monkeypatch):
    ep = FakeEndpoint(0.5, 1)
    monkeypatch.setattr(pc, "_endpoint", lambda: ep)
    assert pc.volume("get") == {"ok": True, "level": 50, "muted": True}
    assert pc.volume("up")["level"] == 60 and ep.muted == 0
    assert pc.volume("set", 150)["level"] == 100
    assert pc.volume("down", 30)["level"] == 70
    assert pc.volume("mute")["muted"] is True
    assert pc.volume("set")["ok"] is False


WINDOWS = [(101, 7, "Untitled - Notepad", "Notepad"),
           (102, 8, "YouTube - Google Chrome", "Chrome_WidgetWin_1"),
           (103, 9, "Calculator", "ApplicationFrameWindow")]


@pytest.fixture
def desktop(monkeypatch):
    closed, shown, focused = [], [], []
    monkeypatch.setattr(pc, "top_windows", lambda: list(WINDOWS))
    monkeypatch.setattr(pc, "_process_names", lambda: {7: "notepad.exe", 8: "chrome.exe", 9: "applicationframehost.exe"})
    monkeypatch.setattr(pc, "_post_close", closed.append)
    monkeypatch.setattr(pc, "_show", lambda h, cmd: shown.append((h, cmd)))
    monkeypatch.setattr(pc, "_focus", focused.append)
    monkeypatch.setattr(pc, "_foreground", lambda: 102)
    return closed, shown, focused


def test_close_app_by_process_and_by_title(desktop):
    closed, _, _ = desktop
    assert pc.close_app("Notepad") == "Closing Notepad."
    assert pc.close_app("calculator") == "Closing calculator."
    assert closed == [101, 103]
    assert pc.close_app("spotify").startswith("Failed")


def test_shell_windows_are_never_closed(monkeypatch):
    monkeypatch.setattr(pc, "_process_names", lambda: {1: "explorer.exe"})
    monkeypatch.setattr(pc, "_user_windows", lambda: [
        (11, 1, "Program Manager", "Progman"), (12, 1, "", "Shell_TrayWnd"),
        (13, 1, "Downloads", "CabinetWClass")])
    closed = []
    monkeypatch.setattr(pc, "_post_close", closed.append)
    pc.close_app("file explorer")
    assert closed == [13]


def test_window_actions(desktop, sent):
    closed, shown, focused = desktop
    assert pc.window("minimize") == "Minimized the window."
    assert shown[-1] == (102, 6)
    pc.window("maximize", "notepad")
    assert shown[-1] == (101, 3)
    pc.window("snap_left", "chrome")
    assert focused[-1] == 102 and sent[0][0] == 0x5B
    assert pc.window("focus", "nothing open").startswith("Failed")


def test_open_app_switches_to_running_window(desktop, monkeypatch):
    _, _, focused = desktop
    started = []
    monkeypatch.setattr(pc, "_try_start", lambda t: started.append(t) or True)
    assert pc.open_app("notepad") == "Switched to notepad."
    assert focused == [101] and started == []


def test_power(monkeypatch):
    ran, other = [], []
    monkeypatch.setattr(pc, "_run", ran.append)
    monkeypatch.setattr(pc, "_suspend", lambda: other.append("sleep"))
    monkeypatch.setattr(pc, "_lock", lambda: other.append("lock"))
    assert pc.system_power("shutdown") == "Shutting down in 10 seconds. Say cancel shutdown to stop it."
    assert ran == [["shutdown", "/s", "/t", "10"]]
    pc.system_power("sleep")
    pc.lock_pc()
    assert other == ["sleep", "lock"]
