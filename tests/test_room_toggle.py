"""The button along the bottom of the display: LYLA's room shown or hidden,
and the choice kept - the next time the display opens, and after a restart."""
import pytest

import apollo
import panels
from test_sleep import make


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(panels, "PATH", str(tmp_path / "panels.json"))
    panels._memo = None


def test_the_button_hides_lylas_room_and_it_stays_hidden():
    api = apollo.Api(lambda: None)
    result = api.set_panel("lyla", False)
    assert result["ok"] is True and result["panels"]["lyla"] is False
    panels._memo = None                        # as if Apollo restarted
    assert panels.visible("lyla") is False


def test_the_button_brings_it_back():
    api = apollo.Api(lambda: None)
    api.set_panel("lyla", False)
    assert api.set_panel("lyla", True)["panels"]["lyla"] is True
    assert panels.visible("lyla") is True


def test_a_panel_the_display_does_not_have_is_refused():
    assert apollo.Api(lambda: None).set_panel("the fireplace", False)["ok"] is False


def test_the_display_opens_the_way_it_was_left(monkeypatch):
    app, log = make(monkeypatch)
    told = []
    app.ui.panels = told.append
    panels.hide("lyla")
    app.presence.toggle_peek()                 # Ctrl+`
    app.apply_mode()
    assert told and told[-1]["lyla"] is False
