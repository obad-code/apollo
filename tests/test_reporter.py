import apollo


class FakeWindow:
    def __init__(self):
        self.calls = []

    def evaluate_js(self, js):
        self.calls.append(js)


class FakeOverlay:
    def raise_above(self):
        pass


def make():
    seen = []
    ui = apollo.WebReporter(FakeWindow(), FakeOverlay(), on_status=seen.append,
                            on_turn=lambda *a: None, on_level=lambda v: None,
                            on_partial=lambda t: None)
    ui.quiet = False
    return ui, seen


def test_repeated_status_is_forwarded_once():
    ui, seen = make()
    for _ in range(40):
        ui.status("Listening")
    assert seen == ["Listening"]
    assert ui.window.calls == ['window.apollo.status("Listening")']


def test_transitions_still_forwarded():
    ui, seen = make()
    for s in ("Listening", "Thinking", "Speaking", "Idle", "Listening"):
        ui.status(s)
    assert seen == ["Listening", "Thinking", "Speaking", "Idle", "Listening"]


def test_idle_after_quiet_period_reaches_page():
    ui, seen = make()
    ui.quiet = True
    ui.status("Speaking")
    ui.status("Idle")
    ui.quiet = False
    ui.status("Idle")
    assert ui.window.calls[-1] == 'window.apollo.status("Idle")'


def test_streaming_updates_never_block_on_the_page():
    """Reply fragments and activity arrive on Gemini's event loop thread; a
    page call there (evaluate_js blocks until the page answers) would stall
    the loop that is receiving the voice's audio."""
    turns, doing = [], []
    ui = apollo.WebReporter(FakeWindow(), FakeOverlay(), on_status=lambda s: None,
                            on_turn=lambda *a: turns.append(a), on_level=lambda v: None,
                            on_partial=lambda t: None, on_activity=doing.append)
    ui.quiet = False
    ui.stream_reply("Opening Chr")
    ui.activity("searching the web")
    assert ui.window.calls == []
    assert turns == [("Apollo", "Opening Chr", None)] and doing == ["searching the web"]
