import telegram_bot as tb


def run(text):
    calls = []
    out = tb.handle(text, make_short=lambda t: calls.append(("short", t)), make_batch=lambda: calls.append(("batch",)),
                    choose=lambda n: calls.append(("choose", n)) or {"result": "ok"}, status=lambda: "s")
    return out, calls


def test_commands():
    assert run("short about octopuses")[1] == [("short", "octopuses")]
    assert run("شورت عن الاخطبوط")[1] == [("short", "الاخطبوط")]
    assert run("نزل رقم ٢")[1] == [("choose", 2)]
    assert run("post 1")[1] == [("choose", 1)]
    assert run("لا تنزل شي")[1] == [("choose", 0)]
    assert run("today")[1] == [("batch",)]
    assert run("hello")[0] == tb.HELP


def test_style_notes(tmp_path, monkeypatch):
    import shorts
    monkeypatch.setattr(shorts, "style_file", lambda: str(tmp_path / "s.txt"))
    assert shorts.set_style("slow and calm") == "slow and calm"
    assert shorts.set_style("no money talk") == "slow and calm\nno money talk"
    assert shorts.set_style("", False) == ""


def test_niche_commands(monkeypatch, tmp_path):
    import json
    import niche
    import shorts
    monkeypatch.setattr(niche, "path", lambda: str(tmp_path / "n.json"))
    monkeypatch.setattr(shorts, "style_file", lambda: str(tmp_path / "s.txt"))
    rows = niche.ask(2, think=lambda p: json.dumps([{"niche": "History twists", "angle": "a", "ideas": ["x", "y"]},
                                                    {"niche": "Money habits", "angle": "b"}]))
    assert len(rows) == 2 and "History twists" in niche.render(rows)
    niche.save(rows)
    assert niche.choose(2)["ok"] and "Money habits" in shorts.style_notes()
    assert niche.choose(1)["ok"] and shorts.style_notes().count("Channel niche:") == 1
    assert not niche.choose(9)["ok"]
    calls = []
    out = tb.handle("niche 2", pick_niche=lambda n: calls.append(n) or {"result": "ok"})
    assert calls == [2] and out == "ok"
    tb.handle("نيش", find_niches=lambda: calls.append("find"))
    assert calls[-1] == "find"
