import pytest

import lyla

SPENT = "429 RESOURCE_EXHAUSTED ... Please retry in 4h23m31.3s."


def test_a_spent_model_is_skipped_and_the_lite_ones_answer(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(lyla, "_spent", {})
    asked = []

    def gen(model, prompt, search, system=None):
        asked.append(model)
        if "lite" not in model:
            raise RuntimeError(SPENT)
        return "hello"

    monkeypatch.setattr(lyla, "_generate", gen)
    assert lyla.ask_gemini("hi", "sys") == "hello"
    assert asked[-1] == "gemini-flash-lite-latest"
    asked.clear()
    assert lyla.ask_gemini("hi again", "sys") == "hello"
    assert asked == ["gemini-flash-lite-latest"]           # the spent ones are not even asked


def test_all_spent_says_so_plainly(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(lyla, "_spent", {})
    monkeypatch.setattr(lyla, "_generate", lambda *a, **k: (_ for _ in ()).throw(RuntimeError(SPENT)))
    with pytest.raises(RuntimeError, match="free daily limit is used up"):
        lyla.ask_gemini("hi", "sys")
