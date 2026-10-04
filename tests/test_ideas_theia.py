import ideas


def test_a_new_idea_goes_to_theia_and_her_read_waits_on_it(tmp_path, monkeypatch):
    monkeypatch.setattr(ideas, "PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setattr(ideas.journal, "write", lambda *a, **k: None)
    idea = ideas.add("a Discord bot for the clan")
    taken = []
    assert ideas.send_to_theia(idea, take=lambda task, **kw: taken.append(kw))
    assert taken == [{"idea": idea["id"], "routine": True}]           # quiet: no announcement
    assert ideas.waiting() and not ideas.unseen()
    ideas.attach(idea["id"], "Worth building", "## Analysis\\nGood.")
    assert [i["id"] for i in ideas.unseen()] == [idea["id"]] and not ideas.waiting()
    ideas.mark_seen()
    assert not ideas.unseen()


def test_talking_an_idea_through_with_theia(tmp_path, monkeypatch):
    monkeypatch.setattr(ideas, "PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setattr(ideas.journal, "write", lambda *a, **k: None)
    idea = ideas.add("a study lock app")
    got = ideas.analyse_now(idea["id"], think=lambda p: "SUMMARY: Worth an MVP.\n\n1. ANALYSIS: ...")
    assert got["theia"]["summary"] == "Worth an MVP."
    seen = []
    reply = ideas.chat(idea["id"], "what first?", think=lambda p: seen.append(p) or "Build the timer.")
    assert reply == "Build the timer." and "Worth an MVP." in seen[0]
    ideas.chat(idea["id"], "free or paid?", think=lambda p: seen.append(p) or "Free first.")
    assert "Build the timer." in seen[1]                      # she remembers the conversation
    assert [m["who"] for m in ideas.get(idea["id"])["chat"]] == ["you", "theia", "you", "theia"]
