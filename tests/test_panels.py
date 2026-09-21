"""Which panels the display is showing, and how Apollo is told to change it.

Spoken names, not element ids: the user says "the stocks", "the news", "Lyla",
and the same panel has to answer to all of the words they might use for it.
"""
import pytest

import panels


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(panels, "PATH", str(tmp_path / "panels.json"))
    panels._memo = None


def test_everything_is_shown_to_start_with():
    for name in panels.PANELS:
        assert panels.visible(name) is True


@pytest.mark.parametrize("said,expected", [
    ("the stocks", "markets"),
    ("stock", "markets"),
    ("الأسهم", "markets"),
    ("market", "markets"),
    ("news", "feed"),
    ("the feed", "feed"),
    ("الأخبار", "feed"),
    ("lyla", "lyla"),
    ("ليلى", "lyla"),
    ("the clock", "clock"),
    ("prayer", None),
])
def test_a_spoken_name_finds_its_panel(said, expected):
    assert panels.resolve(said) == expected


def test_hiding_one_keeps_it_hidden():
    assert panels.hide("the stocks")["ok"] is True
    assert panels.visible("markets") is False

    panels._memo = None                        # as if Apollo restarted
    assert panels.visible("markets") is False


def test_showing_it_again():
    panels.hide("stocks")
    assert panels.show("stocks")["ok"] is True
    assert panels.visible("markets") is True


def test_a_panel_it_does_not_know_is_refused():
    result = panels.hide("the fireplace")
    assert result["ok"] is False
    assert "fireplace" in result["error"]
    # ...and it says what it does know, so the answer is useful.
    assert any(name in result["error"] for name in ("stocks", "markets"))


def test_the_state_the_page_is_given_covers_every_panel():
    panels.hide("news")
    state = panels.state()
    assert set(state) == set(panels.PANELS)
    assert state["feed"] is False and state["markets"] is True
