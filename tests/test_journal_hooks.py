"""Where the record is written from: the end of every turn, every tool, and
whatever you open on the display."""
import datetime

import apollo
import assistant
import journal
import stockdesk
import tools
import watchlist
from test_ptt_turn import UI, Live, NoWhisper, Voice


def kinds():
    return [(e["kind"], e.get("text") or e.get("name") or e.get("title"))
            for e in journal.day(datetime.date.today())]


def test_a_push_to_talk_turn_is_recorded_once_each_way():
    assistant.push_to_talk_turn(UI(), NoWhisper(), Voice(Live("open chrome")))
    assert kinds() == [("you", "open chrome"), ("apollo", "Opening Chrome.")]


def test_an_always_listening_turn_is_recorded():
    class Heard:
        def next_turn(self, timeout=0):
            return ("what time is it", "It's nine.")

        def wait_until_quiet(self):
            pass

    class V:
        live = Heard()

    assistant.always_listening_turn(UI(), V())
    assert kinds() == [("you", "what time is it"), ("apollo", "It's nine.")]


def test_a_tool_call_is_recorded_with_its_arguments():
    tools.run("open_story", {"number": 3}, tools.Context(story_hook=lambda n: None))
    (entry,) = journal.day(datetime.date.today())
    assert entry["kind"] == "tool" and entry["name"] == "open_story"
    assert entry["args"] == {"number": 3}


def test_what_you_open_on_the_display_is_recorded():
    api = apollo.Api(lambda: None)
    api.noted("story", "Marvel's new trailer", "Collider")
    (entry,) = journal.day(datetime.date.today())
    assert (entry["kind"], entry["what"], entry["title"], entry["source"]) == (
        "opened", "story", "Marvel's new trailer", "Collider")


def test_a_stock_put_on_by_hand_is_recorded(monkeypatch, tmp_path):
    monkeypatch.setattr(watchlist, "PATH", str(tmp_path / "watchlist.json"))
    watchlist._memo = None
    monkeypatch.setattr(watchlist.market, "resolve", lambda text: text.upper())
    stockdesk.StockDesk().watch("PLTR")
    assert ("watch", "PLTR") in [(e["kind"], e.get("symbol")) for e in journal.day(datetime.date.today())]
