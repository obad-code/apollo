"""Company marks, fetched once and kept.

They are third-party trademarks fetched from someone else's server, so they
are cached outside the repository's history and Apollo tolerates their
absence: a stock card without a mark is a stock card, a card that waits on a
network fetch to paint is a stall.
"""
import pathlib

import pytest

import logos


@pytest.fixture(autouse=True)
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(logos, "CACHE", tmp_path)
    logos._misses.clear()
    return tmp_path


def test_a_mark_is_fetched_once_and_then_read_from_disk(cache, monkeypatch):
    calls = []

    def fetch(url):
        calls.append(url)
        return b"\x89PNG\r\n\x1a\n" + b"x" * 200

    monkeypatch.setattr(logos, "_download", fetch)

    first = logos.path_for("NVDA")
    second = logos.path_for("NVDA")

    assert first == second
    assert pathlib.Path(first).exists()
    assert len(calls) == 1, "the mark was fetched twice"
    assert "NVDA" in calls[0]


def test_a_symbol_with_no_mark_is_not_asked_for_twice(cache, monkeypatch):
    calls = []

    def fetch(url):
        calls.append(url)
        raise OSError("404")

    monkeypatch.setattr(logos, "_download", fetch)

    assert logos.path_for("NOPE") is None
    assert logos.path_for("NOPE") is None
    assert len(calls) == 1, "a symbol with no mark was asked for again"


def test_anything_that_is_not_an_image_is_refused(cache, monkeypatch):
    """The endpoint answers 200 with an HTML error page for some symbols."""
    monkeypatch.setattr(logos, "_download", lambda url: b"<!doctype html><html>")
    assert logos.path_for("WEIRD") is None
    assert not list(cache.iterdir()), "a non-image was written to the cache"


def test_a_symbol_cannot_escape_the_cache_directory(cache, monkeypatch):
    """The symbol comes off a feed, and it names a file on disk."""
    monkeypatch.setattr(logos, "_download", lambda url: b"\x89PNG\r\n\x1a\n" + b"x" * 200)
    assert logos.path_for("../../etc/passwd") is None
    assert logos.path_for("BRK.B") is not None, "a real symbol with a dot was refused"
