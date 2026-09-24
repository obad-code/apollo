import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def no_live_prices(monkeypatch):
    """The Finnhub key is saved in the Windows environment, and a quote with
    it in reach goes to Finnhub for the price. No test should."""
    import live
    monkeypatch.delenv(live.KEY_NAME, raising=False)
    monkeypatch.setattr(live, "_saved_key", lambda: None)
    monkeypatch.setattr(live, "_feed", None)
