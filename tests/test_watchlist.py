"""The stocks on the display, which Apollo can change by voice.

A list in a file rather than a constant in the source, so asking him to
follow Palantir survives a restart.
"""
import pytest

import watchlist


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(watchlist, "PATH", str(tmp_path / "watchlist.json"))
    watchlist._memo = None


def test_it_starts_as_the_built_in_list():
    assert watchlist.current() == list(watchlist.DEFAULT)


def test_adding_a_stock_keeps_it(monkeypatch):
    monkeypatch.setattr(watchlist.market, "resolve", lambda text: "PLTR")
    assert watchlist.add("palantir")["ok"] is True

    watchlist._memo = None                     # as if Apollo restarted
    assert "PLTR" in watchlist.current()


def test_adding_one_twice_is_not_an_error(monkeypatch):
    monkeypatch.setattr(watchlist.market, "resolve", lambda text: "NVDA")
    result = watchlist.add("nvidia")
    assert result["ok"] is True
    assert result.get("already") is True
    assert watchlist.current().count("NVDA") == 1


def test_removing_a_stock(monkeypatch):
    monkeypatch.setattr(watchlist.market, "resolve", lambda text: "TSLA")
    assert watchlist.remove("tesla")["ok"] is True
    assert "TSLA" not in watchlist.current()


def test_removing_one_that_is_not_there_says_so(monkeypatch):
    monkeypatch.setattr(watchlist.market, "resolve", lambda text: "PLTR")
    result = watchlist.remove("palantir")
    assert result["ok"] is False
    assert "PLTR" in result["error"]


def test_the_list_is_capped(monkeypatch):
    """The display has room for so many cards, and no more."""
    for i in range(40):
        monkeypatch.setattr(watchlist.market, "resolve", lambda text, i=i: f"S{i}")
        watchlist.add(f"stock {i}")
    assert len(watchlist.current()) <= watchlist.MAX


def test_a_name_it_cannot_resolve_is_refused(monkeypatch):
    def unknown(text):
        raise watchlist.market.MarketError("no such company")

    monkeypatch.setattr(watchlist.market, "resolve", unknown)
    result = watchlist.add("a company that does not exist")
    assert result["ok"] is False
    assert watchlist.current() == list(watchlist.DEFAULT)


def test_a_corrupt_file_falls_back_rather_than_failing(monkeypatch):
    import pathlib
    pathlib.Path(watchlist.PATH).write_text("{ not json", encoding="utf-8")
    watchlist._memo = None
    assert watchlist.current() == list(watchlist.DEFAULT)


def test_changes_made_at_once_all_stick(monkeypatch):
    """"Take off Apple, Tesla and Meta" arrives as three calls at once, on
    three threads. Each read the list, dropped its own, and saved - so the
    last save won and the other two came back."""
    import threading
    import time

    names = {"apple": "AAPL", "tesla": "TSLA", "meta": "META"}
    monkeypatch.setattr(watchlist.market, "resolve", lambda text: names[text])
    read = watchlist.current

    def slow_read():
        symbols = read()
        time.sleep(0.05)          # long enough for the others to read too
        return symbols

    monkeypatch.setattr(watchlist, "current", slow_read)
    threads = [threading.Thread(target=watchlist.remove, args=(name,)) for name in names]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    left = read()
    assert not {"AAPL", "TSLA", "META"} & set(left), left


def test_a_name_it_cannot_place_asks_for_the_english_one(monkeypatch):
    """You say it in Arabic, and the model passes it on as you said it. The
    market search only knows English names, so the refusal tells the model
    what to try instead - it reads the error and calls again."""
    def unknown(text):
        raise watchlist.market.MarketError("no such company")

    monkeypatch.setattr(watchlist.market, "resolve", unknown)
    result = watchlist.add("بالانتير")
    assert result["ok"] is False
    assert "English" in result["error"] and "ticker" in result["error"]
