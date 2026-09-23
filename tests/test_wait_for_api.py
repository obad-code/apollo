"""Starting when the network is not up yet.

Apollo starts at sign-in, which is exactly when Wi-Fi is least likely to have
connected. The startup check treated "could not reach the API" the same as
"your key is wrong": it showed a note and the worker returned for good. Apollo
kept running with no voice, no data, no prayer reminders and no recap, and
never tried again.
"""
import pytest

import assistant


class Notes:
    def __init__(self):
        self.said = []

    def note(self, text, *args, **kwargs):
        self.said.append(text)


def failing(times, then=None):
    """A check that is offline `times` times, then does `then` (or passes)."""
    state = {"n": 0}

    def check():
        state["n"] += 1
        if state["n"] <= times:
            raise assistant.Offline("no network yet")
        if then is not None:
            raise then

    check.calls = state
    return check


def test_it_waits_for_the_network_instead_of_giving_up():
    slept = []
    check = failing(3)
    ok = assistant.wait_for_api(Notes(), check=check, sleep=slept.append)

    assert ok is True
    assert check.calls["n"] == 4, "it stopped trying before the network came up"
    assert len(slept) == 3


def test_the_waits_get_longer_but_not_endlessly():
    slept = []
    assistant.wait_for_api(Notes(), check=failing(12), sleep=slept.append)
    assert slept == sorted(slept), "the backoff went down"
    assert max(slept) <= 30, "it waited more than half a minute between tries"


def test_it_says_once_that_it_is_waiting():
    notes = Notes()
    assistant.wait_for_api(notes, check=failing(5), sleep=lambda s: None)
    assert len(notes.said) == 1, f"it said so {len(notes.said)} times"


def test_a_wrong_key_is_still_fatal_at_once():
    """Waiting will not fix a bad key; it has to say so immediately."""
    slept = []
    with pytest.raises(RuntimeError) as caught:
        assistant.wait_for_api(Notes(), check=failing(0, then=RuntimeError("bad key")),
                               sleep=slept.append)
    assert not isinstance(caught.value, assistant.Offline)
    assert slept == []


def test_quitting_while_it_waits_ends_the_wait():
    stops = iter([False, False, True])
    ok = assistant.wait_for_api(Notes(), check=failing(100), sleep=lambda s: None,
                                stop=lambda: next(stops))
    assert ok is False


def test_offline_is_what_a_connection_error_becomes(monkeypatch):
    import anthropic
    import httpx

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    def unreachable(model):
        raise anthropic.APIConnectionError(
            request=httpx.Request("GET", "https://api.anthropic.com"))

    monkeypatch.setattr(assistant.client.models, "retrieve", unreachable)
    with pytest.raises(assistant.Offline):
        assistant.check_api()
