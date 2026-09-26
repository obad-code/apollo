"""Trading mode's board (trading.py): each source parsed from what it really
sends (the samples below are cut down from live responses), the next picks
concluded from where the signals agree, X kept to its daily reads, and no
source able to take the board down."""
import json

import pytest

import trading

OPENINSIDER_BUYS = """<table class="tinytable"><thead><tr>
<th>X</th><th>Filing&nbsp;Date</th><th>Trade&nbsp;Date</th><th>Ticker</th><th>Company&nbsp;Name</th>
<th>Insider&nbsp;Name</th><th>Title</th><th>Trade&nbsp;Type&nbsp;&nbsp;</th><th>Price</th><th>Qty</th>
<th>Owned</th><th>&Delta;Own</th><th>Value</th><th>1d</th><th>1w</th><th>1m</th><th>6m</th></tr></thead>
<tbody><tr style="background:#ffffff">
<td align=right></td><td align=right><div><a href="http://www.sec.gov/x.xml" title="SEC Form 4">2026-09-25 17:19:48</a></div></td>
<td align=right><div>2026-09-24</div></td><td><b> <a href="/URG" onmouseover="Tip('<img src=\\'https://x/c.ashx?chart=URG\\' alt=\\'\\' width=\\'360px\\'>', DELAY, 1)" onmouseout="UnTip()">URG</a></b></td>
<td><a href="/URG">Ur-Energy Inc</a></td><td><a href="/insider/Walle-Jade/1" title="0 direct shares">Walle Jade</a></td>
<td>VP FINANCE</td><td>P - Purchase</td><td align=right>$1.14</td><td align=right>+96,556</td>
<td align=right>424,037</td><td align=right>+29%</td><td align=right>+$110,071</td>
<td align=right></td><td align=right></td><td align=right></td><td align=right></td></tr>
</tbody></table>"""

OPENINSIDER_CLUSTERS = """<table class="tinytable"><thead><tr>
<th>X</th><th>Filing&nbsp;Date</th><th>Trade&nbsp;Date</th><th>Ticker</th><th>Company&nbsp;Name</th>
<th>Industry</th><th>Ins</th><th>Trade&nbsp;Type&nbsp;&nbsp;</th><th>Price</th><th>Qty</th>
<th>Owned</th><th>&Delta;Own</th><th>Value</th><th>1d</th><th>1w</th><th>1m</th><th>6m</th></tr></thead>
<tbody><tr><td align=right>M</td><td align=right><div><a href="/SKIL">2026-09-25 16:19:57</a></div></td>
<td align=right><div>2026-09-15</div></td><td><b> <a href="/SKIL" onmouseover="Tip('<img src=\\'q\\'>', DELAY, 1)">SKIL</a></b></td>
<td><a href="/SKIL">Skillsoft Corp.</a></td><td><a href="/industry/x">Prepackaged Software</a></td><td>3</td>
<td>P - Purchase</td><td align=right>$5.74</td><td align=right>+65,918</td><td align=right>515,003</td>
<td align=right>+15%</td><td align=right>+$2,378,651</td><td align=right></td><td align=right></td>
<td align=right></td><td align=right></td></tr></tbody></table>"""

CONGRESS = json.dumps({"total": 2, "trades": [
    {"member": "John Boozman", "chamber": "Senate", "trade_type": "sell", "amount": "$1,001 - $15,000",
     "tx_date": "2026-08-27", "disclosed": "2026-09-11", "asset": "iShares Core S&P 500 ETF",
     "ticker": "IVV", "link": "https://efdsearch.senate.gov/x"},
    {"member": "Jane Roe", "chamber": "House", "trade_type": "purchase", "amount": "$50,001 - $100,000",
     "tx_date": "2026-09-02", "disclosed": "2026-09-18", "asset": "Skillsoft Corp", "ticker": "SKIL",
     "link": "https://disclosures-clerk.house.gov/x"},
    {"member": "No Ticker", "chamber": "House", "trade_type": "buy", "amount": "$1,001 - $15,000",
     "tx_date": "2026-09-01", "disclosed": "2026-09-19", "asset": "A municipal bond", "ticker": "--"}]})

SEC_ATOM = """<?xml version="1.0" encoding="ISO-8859-1" ?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Latest Filings</title>
<entry><title>8-K - ACME WIDGETS INC (0000123456) (Filer)</title>
<link rel="alternate" type="text/html" href="https://www.sec.gov/Archives/edgar/data/123456/0001-index.htm"/>
<summary type="html"> &lt;b&gt;Filed:&lt;/b&gt; 2026-09-25 &lt;b&gt;AccNo:&lt;/b&gt; 0001 &lt;b&gt;Size:&lt;/b&gt; 245 KB&lt;br&gt;Item 5.02: Departure of Directors&lt;br&gt;Item 9.01: Financial Statements and Exhibits</summary>
<updated>2026-09-25T16:04:12-04:00</updated></entry>
<entry><title>8-K - Bust Co (0000999999) (Filer)</title>
<link rel="alternate" type="text/html" href="https://www.sec.gov/Archives/edgar/data/999999/0002-index.htm"/>
<summary type="html">Item 1.03: Bankruptcy or Receivership&lt;br&gt;Item 9.01: Financial Statements</summary>
<updated>2026-09-25T15:00:00-04:00</updated></entry>
<entry><title>8-K - Exhibits Only Corp (0000555555) (Filer)</title>
<link rel="alternate" type="text/html" href="https://www.sec.gov/y"/>
<summary type="html">Item 9.01: Financial Statements and Exhibits</summary>
<updated>2026-09-25T14:00:00-04:00</updated></entry>
</feed>"""

TRENDING = json.dumps({"symbols": [
    {"symbol": "SOL.X", "title": "Solana", "instrument_class": "CRYPTO", "trending_score": 40},
    {"symbol": "UPST", "title": "Upstart", "instrument_class": "Stock", "trending_score": 30,
     "watchlist_count": 90000, "sector": "Financials",
     "trends": {"summary": "Traders cheer a beat and raised guidance."}},
    {"symbol": "XLK", "title": "Tech ETF", "instrument_class": "ExchangeTradedFund", "trending_score": 20},
    {"symbol": "SKIL", "title": "Skillsoft", "instrument_class": "Stock", "trending_score": 12,
     "trends": {"summary": "Insider buying noticed."}}]})


def stream(bull, bear, neither=3):
    moods = ["Bullish"] * bull + ["Bearish"] * bear + [None] * neither
    return json.dumps({"messages": [{"entities": {"sentiment": {"basic": m} if m else None}}
                                    for m in moods]})


APEWISDOM = json.dumps({"results": [
    {"rank": 1, "ticker": "SPY", "name": "SPDR S&amp;P 500 ETF Trust", "mentions": 256,
     "mentions_24h_ago": 249, "rank_24h_ago": 2},
    {"rank": 7, "ticker": "UPST", "name": "Upstart", "mentions": 90, "mentions_24h_ago": 20,
     "rank_24h_ago": 40}]})


# --- each source, parsed -----------------------------------------------------------------

def test_insider_buys_are_read_past_the_tooltips():
    rows = trading.parse_openinsider(OPENINSIDER_BUYS)
    assert len(rows) == 1
    r = rows[0]
    assert r["ticker"] == "URG" and r["company"] == "Ur-Energy Inc"
    assert r["insider"] == "Walle Jade" and r["title"] == "VP FINANCE"
    assert r["value"] == 110071 and r["price"] == 1.14 and r["filed"] == "2026-09-25"


def test_cluster_buys_say_how_many_insiders():
    r = trading.parse_openinsider(OPENINSIDER_CLUSTERS)[0]
    assert r["ticker"] == "SKIL" and r["insiders"] == 3 and r["value"] == 2378651
    assert r["industry"] == "Prepackaged Software"


def test_a_page_without_the_table_is_nothing():
    assert trading.parse_openinsider("<html>blocked</html>") == []


def test_congress_trades_with_tickers_newest_first():
    trades = trading.parse_congress(CONGRESS)
    assert [t["ticker"] for t in trades] == ["SKIL", "IVV"]
    assert trades[0]["side"] == "buy" and trades[1]["side"] == "sell"


def test_8k_filings_the_serious_ones_first_and_only_those_that_say_something():
    filings = trading.parse_8k(SEC_ATOM, {"999999": "BUST", "123456": "ACME"})
    assert [f["ticker"] for f in filings] == ["BUST", "ACME"]
    assert filings[0]["items"][0]["label"] == "Bankruptcy"
    assert filings[1]["company"] == "Acme Widgets Inc"


def test_without_a_contact_the_sec_is_not_asked(monkeypatch):
    monkeypatch.delenv("SEC_CONTACT", raising=False)
    monkeypatch.setattr(trading, "SEC_CONTACT", "")
    monkeypatch.setattr(trading, "_download", lambda *a, **k: pytest.fail("asked the SEC"))
    assert trading.sensitive_filings() is None


def test_the_sec_is_given_your_contact_and_it_can_be_turned_off(monkeypatch):
    monkeypatch.delenv("SEC_CONTACT", raising=False)
    assert trading.sec_contact() == trading.SEC_CONTACT and "@" in trading.SEC_CONTACT
    monkeypatch.setenv("SEC_CONTACT", "off")
    assert trading.sec_contact() == ""


def test_a_company_is_known_by_its_common_stock_not_its_warrants():
    data = {"0": {"cik_str": 1, "ticker": "SLND-WT"}, "1": {"cik_str": 1, "ticker": "SLND"},
            "2": {"cik_str": 2, "ticker": "PSKY"}}
    assert trading.pick_tickers(data) == {"1": "SLND", "2": "PSKY"}


def test_trending_is_companies_not_coins_or_funds():
    names = trading.parse_trending(TRENDING)
    assert [n["symbol"] for n in names] == ["UPST", "SKIL"]
    assert names[0]["summary"].startswith("Traders cheer")


def test_sentiment_counts_only_messages_that_say_which():
    assert trading.parse_stream(stream(7, 3)) == {"bull": 7, "bear": 3}


def test_reddit_mentions_and_how_fast_they_rise():
    rows = trading.parse_apewisdom(APEWISDOM)
    assert rows[0]["name"] == "SPDR S&P 500 ETF Trust"
    assert rows[1]["rise"] == pytest.approx(4.5)


# --- the read --------------------------------------------------------------------------------

def test_the_picks_are_where_the_signals_agree():
    trending = trading.parse_trending(TRENDING)
    trending[0]["bull"], trending[1]["bull"] = 0.8, 0.9
    picks = trading.conclude(trending, trading.parse_apewisdom(APEWISDOM),
                             trading.parse_openinsider(OPENINSIDER_CLUSTERS),
                             trading.parse_openinsider(OPENINSIDER_BUYS),
                             trading.parse_congress(CONGRESS))
    tickers = [p["ticker"] for p in picks]
    # SKIL: trending, bullish, insiders clustering in and a member of Congress buying.
    assert tickers[0] == "SKIL"
    assert "UPST" in tickers
    lead = picks[0]
    assert any("insiders bought" in r for r in lead["reasons"])
    assert any("House" in r for r in lead["reasons"])
    assert lead["bull"] == 0.9


def test_a_crowd_that_is_bearish_counts_against_a_name():
    hot = [{"symbol": "AAA", "name": "A", "summary": "", "bull": 0.1},
           {"symbol": "BBB", "name": "B", "summary": "", "bull": 0.9}]
    picks = trading.conclude(hot)
    assert [p["ticker"] for p in picks][0] == "BBB"


def test_several_filings_by_one_member_are_one_signal_and_size_matters():
    small = [{"member": "A B", "chamber": "House", "side": "buy", "amount": "$1,001 - $15,000",
              "ticker": "AVGO", "asset": "Broadcom", "disclosed": "2026-09-20"}] * 2
    big = [{"member": "C D", "chamber": "Senate", "side": "buy", "amount": "$500,001 - $1,000,000",
            "ticker": "LMT", "asset": "Lockheed", "disclosed": "2026-09-20"}]
    picks = trading.conclude(congress=small + big)
    assert [p["ticker"] for p in picks] == ["LMT", "AVGO"]
    assert picks[1]["reasons"] == ["A B (House) bought $1,001 - $15,000 (2 filings)"]
    assert picks[1]["signals"] == ["congress"]


def test_the_verdict_names_the_leaders():
    picks = [{"ticker": "SKIL", "reasons": ["3 insiders bought $2.4M"]},
             {"ticker": "UPST", "reasons": []}]
    line = trading.verdict(picks)
    assert "SKIL" in line and "UPST" in line and "3 insiders" in line
    assert "quiet" in trading.verdict([])


# --- X: only with a token and the traders to follow, and within the day's reads ------------

X_BODY = json.dumps({"data": [{"author_id": "1", "text": "Loading $NVDA and $upst here"},
                              {"author_id": "2", "text": "$NVDA breakout"}],
                     "includes": {"users": [{"id": "1", "username": "trader1"},
                                            {"id": "2", "username": "trader2"}]}})


def test_x_is_off_without_a_token(monkeypatch):
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
    monkeypatch.setattr(trading, "_download", lambda *a, **k: pytest.fail("asked X"))
    assert trading.x_traders() is None


def test_x_counts_the_tickers_the_traders_name():
    got = trading.parse_x(X_BODY)
    assert got["tickers"] == {"NVDA": 2, "UPST": 1}
    assert got["posts"][0]["who"] == "trader1"


def test_x_stays_inside_the_day_s_reads(monkeypatch, tmp_path):
    monkeypatch.setenv("X_BEARER_TOKEN", "t")
    monkeypatch.setenv("X_TRADERS", "trader1,trader2")
    monkeypatch.setenv("X_DAILY_READS", "60")
    monkeypatch.setattr(trading, "X_STATE", str(tmp_path / "x.json"))
    trading._cache.clear()
    calls = []
    monkeypatch.setattr(trading, "_download", lambda url, headers=None: calls.append(url) or X_BODY)
    assert trading.x_traders()["tickers"]["NVDA"] == 2          # the first read
    trading._cache.clear()                                       # as if it had expired
    capped = trading.x_traders()                                 # 58 left, 50 wanted: fine
    assert len(calls) == 2
    trading._cache.clear()
    monkeypatch.setenv("X_DAILY_READS", "3")
    assert trading.x_traders().get("capped") is True             # over the cap: not asked
    assert len(calls) == 2
    assert capped["tickers"]


# --- the board --------------------------------------------------------------------------------

def test_one_source_down_does_not_take_the_board_down(monkeypatch):
    def fake(url, headers=None):
        if "openinsider" in url:
            raise OSError("down")
        if "stocktwits" in url and "trending" in url:
            return TRENDING.encode()
        if "stocktwits" in url:
            return stream(8, 2).encode()
        if "apewisdom" in url:
            return APEWISDOM.encode()
        if "railway" in url:
            return CONGRESS.encode()
        if "finnhub" in url:
            return b"[]"
        raise OSError("unexpected " + url)
    trading._cache.clear()
    monkeypatch.setattr(trading, "_download", fake)
    monkeypatch.setenv("SEC_CONTACT", "off")
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
    monkeypatch.setattr(trading.feeds, "search", lambda *a, **k: [])
    b = trading.board()
    assert b["buys"] == [] and b["clusters"] == []
    assert b["sources"]["filings"] == "off" and b["sources"]["x"] == "off"
    assert b["trending"][0]["symbol"] == "UPST" and b["trending"][0]["bull"] == 0.8
    assert b["picks"] and b["verdict"]


# --- one ticker, for LYLA -------------------------------------------------------------------

def test_what_traders_say_about_one_ticker(monkeypatch):
    body = json.dumps({"messages": [
        {"body": "UPST   to the moon", "entities": {"sentiment": {"basic": "Bullish"}},
         "user": {"username": "trader1"}},
        {"body": "", "entities": {}},
        {"body": "fading this", "entities": {"sentiment": {"basic": "Bearish"}}}]
        + [{"body": "long", "entities": {"sentiment": {"basic": "Bullish"}}}] * 4})
    trading._cache.clear()
    monkeypatch.setattr(trading, "_download", lambda url, headers=None: body.encode())
    said = trading.chatter("upst")
    assert said["bull"] == 5 and said["bear"] == 1 and said["bullish"] == 0.83
    assert said["messages"][0] == {"text": "UPST to the moon", "mood": "bullish", "who": "trader1"}


def test_everywhere_one_ticker_turns_up_on_the_board():
    board = {"picks": [{"ticker": "UPST", "reasons": ["#1 trending"], "summary": "beat"}],
             "trending": [{"symbol": "SKIL"}, {"symbol": "UPST", "bull": 0.8, "summary": "beat"}],
             "reddit": [{"ticker": "UPST", "mentions": 90, "before": 20}],
             "clusters": [{"ticker": "SKIL"}], "buys": [{"ticker": "UPST", "value": 1}],
             "congress": [{"ticker": "UPST", "member": "A"}],
             "filings": [{"ticker": "UPST", "company": "Upstart", "filed": "2026-09-25",
                          "items": [{"label": "Results"}]}],
             "news": [{"title": "Upstart (UPST) jumps"}, {"title": "UPSTATE bank falls"}]}
    found = trading.on_the_desk("upst", board)
    assert found["pick"]["rank"] == 1 and found["trending"]["rank"] == 2
    assert found["reddit"] == {"mentions": 90, "yesterday": 20}
    assert found["insider_clusters"] == [] and len(found["insider_buys"]) == 1
    assert found["filings"][0]["what"] == ["Results"]
    assert found["headlines"] == ["Upstart (UPST) jumps"]


# --- by voice, and on the display's clock ----------------------------------------------------

def test_the_trading_read_by_voice(monkeypatch):
    import tools
    board = {"verdict": "Traders are leaning into SKIL.", "picks": [
        {"ticker": "SKIL", "name": "Skillsoft", "reasons": ["3 insiders bought $2.4M"], "bull": 0.9}],
        "clusters": [{"ticker": "SKIL", "insiders": 3, "value": 2378651.0}],
        "congress": [{"ticker": "SKIL", "member": "Jane Roe", "amount": "$50,001 - $100,000", "side": "buy"}],
        "filings": [], "news": [{"title": "Skillsoft jumps"}]}
    monkeypatch.setattr(trading, "board", lambda: board)
    result = tools.run("trading_read", {}, tools.Context())
    assert result["ok"] is True and result["picks"][0]["bullish"] == 90
    assert result["congress_buys"][0]["member"] == "Jane Roe"
    description = tools.REGISTRY["trading_read"].description
    assert "not advice" in description and any("؀" <= ch <= "ۿ" for ch in description)


def test_the_board_is_read_only_while_trading_mode_wants_it(monkeypatch):
    import dataservice
    service = dataservice.DataService()
    read = []
    monkeypatch.setattr(trading, "board", lambda: read.append(1) or {"picks": [1]})
    assert service._read_trading() is False and read == []           # nobody asked
    service.want_trading()
    assert service._read_trading() is True and read == [1]
    assert service.snapshot["trading"] == {"picks": [1]}


def test_the_page_asks_for_it_through_the_bridge():
    import apollo

    class App:
        wanted = 0
        def want_trading(self):
            self.wanted += 1
    app = App()
    assert apollo.Api(lambda: None, app=app).trading() is True and app.wanted == 1
    assert apollo.Api(lambda: None).trading() is False


# --- the final stocks: what the desk comes to, in plain Arabic --------------------------------

def signalled_picks():
    trending = trading.parse_trending(TRENDING)
    trending[0]["bull"], trending[1]["bull"] = 0.8, 0.9
    return trading.conclude(trending, trading.parse_apewisdom(APEWISDOM),
                            trading.parse_openinsider(OPENINSIDER_CLUSTERS),
                            trading.parse_openinsider(OPENINSIDER_BUYS),
                            trading.parse_congress(CONGRESS))


def test_every_pick_says_why_in_arabic_too():
    lead = signalled_picks()[0]
    assert lead["why"] and len(lead["why"]) == len(lead["reasons"])
    assert any("كبار موظفي الشركة" in w for w in lead["why"])
    assert any("الكونجرس" in w for w in lead["why"])


def test_the_final_stocks_are_only_where_several_signals_agree():
    out = trading.final(signalled_picks())
    assert out["none"] is None
    tickers = [p["ticker"] for p in out["picks"]]
    assert tickers[0] == "SKIL"
    assert len(tickers) <= trading.FINAL
    for pick in out["picks"]:
        assert len(pick["signals"]) >= 2
        assert pick["why"]


def test_one_signal_alone_is_not_a_final_stock():
    lone = trading.conclude(congress=[{"member": "C D", "chamber": "Senate", "side": "buy",
                                       "amount": "$500,001 - $1,000,000", "ticker": "LMT",
                                       "asset": "Lockheed", "disclosed": "2026-09-20"}])
    out = trading.final(lone)
    assert out["picks"] == []
    assert "ما في" in out["none"] and "تشتري" in out["none"]


def test_a_bearish_crowd_keeps_a_name_off_the_final_list():
    picks = [{"ticker": "AAA", "name": "A", "score": 9, "bull": 0.3, "signals": ["crowd", "insiders"],
              "reasons": ["x"], "why": ["س"]}]
    assert trading.final(picks)["picks"] == []


def test_nothing_at_all_says_so():
    out = trading.final([])
    assert out["picks"] == [] and out["none"]
