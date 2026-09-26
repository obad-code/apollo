"""The boot screen is a real one: each check and each part of Apollo coming
up is a line on it as it happens, anything wrong is kept as an issue for
the System panel, and the screen goes once both the checks and the start
are done.
"""
import threading
import types

import apollo
import issues


class UI:
    alive = True

    def __init__(self):
        self.calls = []

    def boot(self, step):
        self.calls.append(("boot", step["id"], step["status"]))

    def boot_done(self, summary):
        self.calls.append(("done", summary))

    def issues(self, items):
        self.calls.append(("issues", [i["key"] for i in items]))

    def checked(self, summary):
        self.calls.append(("checked", summary))


def app_with_ui():
    app = apollo.Apollo.__new__(apollo.Apollo)
    app.ui = UI()
    app.boot_done_at = None
    app._boot_parts = set()
    app._boot_results = []
    app._boot_lock = threading.Lock()
    return app


def step(sid, status, detail=""):
    return {"id": sid, "label": sid.upper(), "status": status, "detail": detail}


def test_each_step_is_a_line_on_the_screen():
    app = app_with_ui()
    app.boot_step(step("mic", "ok", "TONOR"))
    assert ("boot", "mic", "ok") in app.ui.calls


def test_a_step_that_is_wrong_is_kept_as_an_issue_and_right_again_resolves_it():
    app = app_with_ui()
    app.boot_step(step("mic", "fail", "no microphone"))
    [kept] = issues.current()
    assert kept["key"] == "check:mic" and kept["level"] == "fail" and "no microphone" in kept["detail"]
    app.boot_step(step("mic", "ok"))
    assert issues.current() == []


def test_a_step_not_kept_is_only_a_line():
    app = app_with_ui()
    app.boot_step(step("voice", "fail"), keep=False)
    assert issues.current() == [] and ("boot", "voice", "fail") in app.ui.calls


def test_the_boot_is_done_when_both_the_checks_and_the_start_are():
    app = app_with_ui()
    app.boot_step(step("disk", "warn"))
    app.boot_step(step("mic", "fail"))
    app.boot_part_done("checks")
    assert app.boot_done_at is None
    app.boot_part_done("startup")
    assert app.boot_done_at is not None
    assert ("done", {"issues": 2, "fails": 1}) in app.ui.calls
    app.boot_part_done("startup")                      # once
    assert sum(1 for c in app.ui.calls if c[0] == "done") == 1


def test_checks_run_again_from_the_system_panel_say_when_they_are_done(monkeypatch):
    app = app_with_ui()
    monkeypatch.setattr(apollo.diagnostics, "run",
                        lambda report: [report(step("disk", "warn")) or step("disk", "warn")])
    app.run_checks()
    assert ("checked", {"issues": 1, "fails": 0}) in app.ui.calls
    assert app.boot_done_at is None, "not a boot"


def test_the_panel_dismisses_an_issue():
    issues.record("check:disk", "DISK", "", "warn")
    api = apollo.Api(lambda: None)
    assert api.dismiss_issue("check:disk") is True
    assert issues.current() == []


def test_a_recorder_that_died_is_an_issue(monkeypatch):
    app = apollo.Apollo.__new__(apollo.Apollo)
    app.presence = types.SimpleNamespace(asleep=False)

    class Recorder:
        running = False
        error = "gdigrab failed"

        def start(self):
            self.running = True

    app.clips = Recorder()
    app.keep_clips(1000.0, locked=False)
    [kept] = issues.current()
    assert kept["key"] == "clips" and "gdigrab failed" in kept["detail"]


def test_apollo_can_be_asked_what_is_wrong():
    import tools
    issues.record("check:mic", "MICROPHONE", "no microphone", "fail")
    result = tools.run("system_issues", {}, tools.Context())
    assert result["ok"] is True
    assert result["issues"][0]["what"] == "MICROPHONE" and "no microphone" in result["issues"][0]["detail"]
    issues.resolve("check:mic")
    assert tools.run("system_issues", {}, tools.Context())["issues"] == []


def test_the_display_opening_gets_the_list(monkeypatch):
    app = app_with_ui()
    issues.record("check:disk", "DISK", "", "warn")
    app.tell_issues(issues.current())
    assert ("issues", ["check:disk"]) in app.ui.calls
