"""Changing the watchlist by voice: "add Palantir", "take off Apple and Tesla"."""
import time

import pytest

import apollo
import dataservice
import tools
import watchlist
from tools import Context


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(watchlist, "PATH", str(tmp_path / "watchlist.json"))
    watchlist._memo = None
    names = {"apple": "AAPL", "tesla": "TSLA", "palantir": "PLTR", "amd": "AMD"}

    def resolve(text):
        try:
            return names[text.lower()]
        except KeyError:
            raise watchlist.market.MarketError("no such company") from None

    monkeypatch.setattr(watchlist.market, "resolve", resolve)


def test_several_come_off_in_one_call():
    result = tools.run("unwatch_stock", {"companies": ["Apple", "Tesla"]}, Context())
    assert result["ok"] is True
    assert result["removed"] == ["AAPL", "TSLA"]
    assert not {"AAPL", "TSLA"} & set(watchlist.current())


def test_several_go_on_in_one_call():
    result = tools.run("watch_stock", {"companies": ["Palantir", "AMD"]}, Context())
    assert result["ok"] is True
    assert result["added"] == ["PLTR", "AMD"]
    assert watchlist.current()[-2:] == ["PLTR", "AMD"]


def test_one_name_as_a_plain_string_still_works():
    """The model sometimes sends one string where the schema says a list."""
    result = tools.run("watch_stock", {"company": "Palantir"}, Context())
    assert result["ok"] is True and result["added"] == ["PLTR"]


def test_the_ones_it_could_not_place_are_named_and_the_rest_still_happen():
    result = tools.run("watch_stock", {"companies": ["Palantir", "بالانتير"]}, Context())
    assert result["added"] == ["PLTR"]
    assert result["failed"][0]["company"] == "بالانتير"
    assert "English" in result["failed"][0]["error"]


def test_the_model_is_told_to_pass_english_names():
    for name in ("watch_stock", "unwatch_stock"):
        spec = tools.REGISTRY[name].parameters["properties"]["companies"]
        assert spec["type"] == "array"
        assert "English" in spec["description"], name


def test_a_change_asks_only_for_the_market_to_be_read_again():
    asked = []
    tools.run("unwatch_stock", {"companies": ["Apple"]},
              Context(refresh=lambda *keys: asked.append(keys) or True))
    assert asked == [("market",)]


def test_nothing_changed_asks_for_nothing():
    asked = []
    tools.run("unwatch_stock", {"companies": ["Palantir"]},      # not on the list
              Context(refresh=lambda *keys: asked.append(keys) or True))
    assert asked == []


class _Service:
    def __init__(self):
        self.poked = []

    def poke(self, *keys):
        self.poked.append(keys)

    def refresh(self, force=False):
        raise AssertionError("a tool call must not wait for the whole world to be fetched")


def test_the_display_refresh_does_not_hold_up_the_answer():
    """The forced refresh read every feed - nine stocks with valuations, four
    news topics, posts, weather - before the tool could answer: eight
    seconds warm, far longer when Yahoo was slow, and Apollo sat silent on
    "taking it off your watchlist" the whole time."""
    service = _Service()
    ui = apollo.WebReporter.__new__(apollo.WebReporter)
    ui._app = type("App", (), {"data": service})()
    assert ui.refresh("market") is True
    assert service.poked == [("market",)]


def test_a_poke_is_read_on_the_services_own_thread_and_soon(monkeypatch):
    service = dataservice.DataService()
    reads = []

    def read_market():
        reads.append(time.monotonic())
        return False

    for key in dataservice.INTERVALS:
        monkeypatch.setattr(service, "_read_" + key, lambda: False)
    monkeypatch.setattr(service, "_read_market", read_market)
    monkeypatch.setattr(dataservice.usage, "today", lambda: {})
    service.start()
    try:
        deadline = time.monotonic() + 2
        while not reads and time.monotonic() < deadline:
            time.sleep(0.01)
        assert reads, "the loop never read the market"
        before = len(reads)
        started = time.monotonic()
        service.poke("market")
        assert time.monotonic() - started < 0.05      # the caller does not wait
        deadline = time.monotonic() + 1
        while len(reads) == before and time.monotonic() < deadline:
            time.sleep(0.01)
        assert len(reads) > before, "the poke was not read within a second"
    finally:
        service.stop()
