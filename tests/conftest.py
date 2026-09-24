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


@pytest.fixture(autouse=True)
def private_journal(tmp_path, monkeypatch):
    """Every test writes its record somewhere of its own, never into the
    real one under %LOCALAPPDATA%."""
    try:
        import journal
    except ImportError:          # before the module exists
        return
    monkeypatch.setattr(journal, "ROOT", str(tmp_path / "journal"))


@pytest.fixture(autouse=True)
def private_interests(tmp_path, monkeypatch):
    """...and its own profile: nothing here may read or change the real one."""
    try:
        import interests
    except ImportError:
        return
    monkeypatch.setattr(interests, "PATH", str(tmp_path / "profile.json"))


@pytest.fixture(autouse=True)
def private_finds(tmp_path, monkeypatch):
    """...and Private Eye its own finds."""
    try:
        import private_eye
    except ImportError:
        return
    monkeypatch.setattr(private_eye, "PATH", str(tmp_path / "finds.json"))


@pytest.fixture(autouse=True)
def private_ideas(tmp_path, monkeypatch):
    """...its own ideas, and no git or GitHub reached for the Projects tab."""
    try:
        import ideas
        import projects
    except ImportError:
        return
    monkeypatch.setattr(ideas, "PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setattr(projects, "snapshot",
                        lambda: {"sessions": [], "folders": [], "repos": []})
