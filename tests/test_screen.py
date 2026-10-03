"""Apollo's eyes: one screenshot, only when asked, and a model's answer."""
import pytest

import screen


def test_a_wide_screen_is_scaled_to_fit_in_even_numbers():
    assert screen.fit(2560, 1440) == (1600, 900)
    assert screen.fit(1280, 721) == (1280, 720)


def test_look_hands_the_picture_and_the_question_on(monkeypatch):
    seen = {}

    def ask(model, picture, question):
        seen.update(model=model, picture=picture, question=question)
        return "  A rising NVDA chart.  "
    assert screen.look("explain  this chart", grab=lambda: b"jpeg", ask=ask) == "A rising NVDA chart."
    assert seen["picture"] == b"jpeg" and seen["question"] == "explain this chart"


def test_the_next_model_answers_when_one_fails():
    calls = []

    def ask(model, picture, question):
        calls.append(model)
        if len(calls) == 1:
            raise RuntimeError("quota")
        return "ok"
    assert screen.look("x", grab=lambda: b"j", ask=ask) == "ok" and len(calls) == 2


def test_a_vague_question_still_asks_something():
    seen = {}
    screen.look("", grab=lambda: b"j", ask=lambda m, p, q: seen.setdefault("q", q) or "fine")
    assert seen["q"] == "What is on my screen?"


def test_no_answer_at_all_is_an_error():
    with pytest.raises(RuntimeError):
        screen.look("x", grab=lambda: b"j", ask=lambda m, p, q: "")
