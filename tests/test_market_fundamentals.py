"""What a stock is worth, beyond what it costs today.

The chart endpoint Apollo already uses carries no valuation at all. These
come from Yahoo's quoteSummary, which since 2023 refuses every request that
does not carry a crumb and the cookie it was minted with.
"""
import pytest

import market


SUMMARY = {"quoteSummary": {"result": [{
    "financialData": {
        "targetMeanPrice": {"raw": 327.7}, "targetHighPrice": {"raw": 515.0},
        "targetLowPrice": {"raw": 180.0}, "numberOfAnalystOpinions": {"raw": 59},
        "recommendationKey": "strong_buy"},
    "summaryDetail": {"trailingPE": {"raw": 28.099874}, "forwardPE": {"raw": 14.173006}},
    "defaultKeyStatistics": {"trailingEps": {"raw": 7.91}},
}]}}


@pytest.fixture(autouse=True)
def clear_cache():
    market._cache.clear()
    market._crumb = None
    yield
    market._cache.clear()
    market._crumb = None


def test_fundamentals_reads_the_target_and_the_multiple(monkeypatch):
    monkeypatch.setattr(market, "_summary_json", lambda symbol: SUMMARY)
    data = market.fundamentals("NVDA")

    assert data["target"] == 327.7
    assert data["target_high"] == 515.0
    assert data["target_low"] == 180.0
    assert data["analysts"] == 59
    assert data["recommendation"] == "strong buy"
    assert data["pe"] == 28.1
    assert data["forward_pe"] == 14.17
    assert data["eps"] == 7.91


def test_a_stock_with_no_earnings_has_no_multiple(monkeypatch):
    """A company that loses money has no P/E. It must not read as zero."""
    monkeypatch.setattr(market, "_summary_json", lambda symbol: {"quoteSummary": {"result": [{
        "financialData": {"targetMeanPrice": {"raw": 12.0}},
        "summaryDetail": {}, "defaultKeyStatistics": {}}]}})
    data = market.fundamentals("XYZ")

    assert data["pe"] is None
    assert data["target"] == 12.0


def test_a_feed_that_says_nothing_is_not_an_error(monkeypatch):
    """The card shows a dash where a number is missing; it does not fail."""
    def boom(symbol):
        raise market.MarketError("nope")

    monkeypatch.setattr(market, "_summary_json", boom)
    assert market.fundamentals("NVDA") == market.NO_FUNDAMENTALS


def test_the_upside_is_measured_against_the_price():
    assert market.upside(327.7, 222.27) == pytest.approx(47.4, abs=0.1)
    assert market.upside(None, 222.27) is None
    assert market.upside(327.7, 0) is None
