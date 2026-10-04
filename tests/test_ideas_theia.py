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
