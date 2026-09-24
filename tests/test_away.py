"""Away mode: when you have left the house the PC stays up with Claude open,
so you can reach it from your phone; when you are home it may rest.

You leave when you say so, or when your phone has been off the home Wi-Fi a
while and nobody is at the keyboard. You are back when you touch the PC, or
when the phone comes home after it was gone."""
import away
import phone
import tools
from tools import Context


def test_saying_you_are_going_out_is_away_at_once():
    a = away.Away()
    assert a.leaving(now=100.0) is True
    assert a.away


def test_what_you_did_to_say_it_does_not_bring_you_back():
    a = away.Away()
    a.leaving(now=100.0)
    assert a.update(now=105.0, idle=6.0) is False       # the chord, at 99
    assert a.away


def test_touching_the_pc_is_being_back():
    a = away.Away()
    a.leaving(now=100.0)
    assert a.update(now=400.0, idle=1.0) is True
    assert not a.away


def test_the_phone_gone_a_while_and_nobody_at_the_keyboard_is_away():
    a = away.Away(gone_after=900, quiet_after=600)
    a.update(now=0.0, idle=0.0, phone=True)
    assert not a.update(now=800.0, idle=800.0, phone=False)     # not long enough
    assert a.update(now=1000.0, idle=1000.0, phone=False)
    assert a.away


def test_the_phone_gone_but_someone_typing_is_not_away():
    """A phone that dropped off the Wi-Fi is not you leaving, if you are here."""
    a = away.Away(gone_after=900, quiet_after=600)
    a.update(now=0.0, idle=0.0, phone=True)
    assert not a.update(now=2000.0, idle=5.0, phone=False)
    assert not a.away


def test_the_phone_coming_home_is_being_back():
    a = away.Away(gone_after=900, quiet_after=600)
    a.update(now=0.0, idle=0.0, phone=True)
    a.update(now=1000.0, idle=1000.0, phone=False)
    assert a.update(now=5000.0, idle=5000.0, phone=True)
    assert not a.away


def test_a_phone_still_home_after_you_said_you_are_going_does_not_undo_it():
    """You say it on the way out; the phone is still on the Wi-Fi for a minute."""
    a = away.Away(gone_after=900, quiet_after=600)
    a.update(now=0.0, idle=0.0, phone=True)
    a.leaving(now=10.0)
    assert not a.update(now=60.0, idle=60.0, phone=True)
    assert a.away


def test_away_keeps_the_pc_up_and_opens_claude_and_back_lets_it_rest():
    states, launched = [], []
    keeper = away.Keeper(set_state=states.append, running=lambda: False,
                         launch=lambda: launched.append(1))
    keeper.apply(True)
    assert states[-1] & away.ES_SYSTEM_REQUIRED and states[-1] & away.ES_CONTINUOUS
    assert launched == [1]
    keeper.apply(False)
    assert states[-1] == away.ES_CONTINUOUS                 # back to the power plan


def test_claude_already_open_is_left_as_it_is():
    launched = []
    keeper = away.Keeper(set_state=lambda s: None, running=lambda: True,
                         launch=lambda: launched.append(1))
    keeper.apply(True)
    assert launched == []


# -- the phone ------------------------------------------------------------------------

ARP = """
Interface: 192.168.1.10 --- 0x9
  Internet Address      Physical Address      Type
  192.168.1.1           a0-b1-c2-d3-e4-f5     dynamic
  192.168.1.23          3a-4b-5c-6d-7e-8f     dynamic
  192.168.1.255         ff-ff-ff-ff-ff-ff     static
"""


def test_the_arp_table_is_read():
    table = phone.parse_arp(ARP)
    assert table["192.168.1.23"] == "3a-4b-5c-6d-7e-8f"


def test_a_phone_is_found_by_its_wifi_address_whatever_the_separators():
    p = phone.Phone("3A:4B:5C:6D:7E:8F", ping=lambda ip: False, arp=lambda: ARP)
    assert p.seen() is True


def test_a_phone_that_answers_a_ping_is_home():
    p = phone.Phone("192.168.1.50", ping=lambda ip: ip == "192.168.1.50", arp=lambda: "")
    assert p.seen() is True


def test_a_phone_nowhere_is_not_home():
    swept = []
    p = phone.Phone("3a-4b-5c-6d-7e-00", ping=lambda ip: False, arp=lambda: ARP,
                    sweep=lambda: swept.append(1))
    assert p.seen() is False
    assert swept == [1]                  # looked for it across the network first


def test_saying_you_are_going_out_by_voice():
    asked = []
    result = tools.run("going_out", {}, Context(away_hook=lambda: asked.append(1)))
    assert result["ok"] is True and asked == [1]
    assert "طالع" in tools.REGISTRY["going_out"].description


def test_the_watcher_does_it_and_lets_it_go_when_you_are_back(monkeypatch):
    import apollo
    from test_sleep import make

    app, log = make(monkeypatch)
    applied = []
    app.away = away.Away()
    app.keeper = type("Keeper", (), {"apply": lambda self, on: applied.append(on)})()
    app.phone_watch = None
    clock = [1000.0]
    monkeypatch.setattr(apollo.time, "monotonic", lambda: clock[0])
    app.request_away()
    app.check_presence(5.0)
    assert applied == [True]
    clock[0] = 1300.0
    app.check_presence(0.5)                  # a key, at the PC
    assert applied == [True, False]
