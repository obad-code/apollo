"""What the display's side panel can show besides the stocks: your recent
talks with Apollo, your projects - Claude Code sessions, the git folders on
this PC, your GitHub repos - and your ideas for new ones."""
import datetime
import json
import os
import subprocess

import pytest

import dataservice
import ideas
import journal
import projects
import talks
import tools
from tools import Context


# -- talks ------------------------------------------------------------------------

def test_talks_pair_what_you_said_with_what_apollo_answered_newest_first():
    journal.said("how is nvidia")
    journal.write("tool", name="stock_quote", args={"symbols": ["NVDA"]})
    journal.answered("Up 2% today.")
    journal.said("open story three")
    journal.answered("Opening it.")
    got = talks.recent()
    assert [(t["you"], t["apollo"]) for t in got] == [
        ("open story three", "Opening it."), ("how is nvidia", "Up 2% today.")]
    assert got[1]["tools"] == ["stock_quote"]
    assert got[0]["time"]


def test_an_agent_answer_is_labelled_with_who_gave_it():
    journal.said("hey atlas, research gpus")
    journal.answered("Here's what I found.", who="ATLAS")
    assert talks.recent()[0]["who"] == "ATLAS"


# -- projects: Claude Code sessions ---------------------------------------------------

def session(root, folder, name, title, cwd, prompt="do the thing", key="customTitle"):
    path = root / folder
    path.mkdir(parents=True, exist_ok=True)
    kind = "custom-title" if key == "customTitle" else "ai-title"
    lines = [{"type": "user", "cwd": cwd, "message": {"content": prompt}},
             {"type": "last-prompt", "lastPrompt": prompt},
             {"type": kind, key: title}]
    (path / f"{name}.jsonl").write_text("\n".join(json.dumps(l) for l in lines), encoding="utf-8")
    return path / f"{name}.jsonl"


def test_claude_code_sessions_are_listed_with_their_titles_newest_first(tmp_path):
    older = session(tmp_path, "C--proj-a", "s1", "Fix the login", r"C:\proj\a")
    newer = session(tmp_path, "C--proj-b", "s2", "Apollo redesign", r"C:\proj\b", key="aiTitle")
    os.utime(older, (1_000_000, 1_000_000))
    session(tmp_path, "C--Users-Admin--claude-mem-observer-sessions", "s3", "noise", r"C:\x")
    got = projects.claude_sessions(root=str(tmp_path))
    assert [s["title"] for s in got] == ["Apollo redesign", "Fix the login"]
    assert got[0]["project"] == "b" and got[0]["prompt"] == "do the thing"


def test_a_session_with_no_title_goes_by_its_last_prompt(tmp_path):
    path = tmp_path / "C--p"
    path.mkdir()
    (path / "s.jsonl").write_text(json.dumps({"type": "last-prompt", "lastPrompt": "add dark mode"}),
                                  encoding="utf-8")
    assert projects.claude_sessions(root=str(tmp_path))[0]["title"] == "add dark mode"


# -- projects: folders on this PC ---------------------------------------------------

def git(path, *args):
    subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True,
                   env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                            GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t"))


def test_git_folders_are_listed_with_their_last_commit(tmp_path):
    repo = tmp_path / "Desktop" / "my-game"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    (repo / "a.txt").write_text("x")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "First level done")
    (tmp_path / "Desktop" / "not-a-repo").mkdir()
    got = projects.folders(roots=[str(tmp_path / "Desktop")])
    assert [f["name"] for f in got] == ["my-game"]
    assert got[0]["branch"] == "main" and got[0]["last"] == "First level done"
    assert got[0]["when"] > 0


# -- projects: GitHub -------------------------------------------------------------

def test_github_repos_are_read_newest_first(monkeypatch):
    asked = []

    def fetch(url, token=None):
        asked.append((url, token))
        return [{"name": "apollo", "full_name": "obad-code/apollo", "private": True,
                 "html_url": "https://github.com/obad-code/apollo",
                 "pushed_at": "2026-09-24T21:00:00Z", "description": "voice assistant"}]

    got = projects.github_repos("obad-code", token=None, fetch=fetch)
    assert got[0]["name"] == "apollo" and got[0]["link"].startswith("https://github.com/")
    assert "users/obad-code/repos" in asked[0][0]
    projects.github_repos("obad-code", token="t0k", fetch=fetch)
    assert "/user/repos" in asked[1][0] and asked[1][1] == "t0k"


def test_a_github_that_does_not_answer_is_an_empty_list():
    def fetch(url, token=None):
        raise OSError("offline")
    assert projects.github_repos("obad-code", fetch=fetch) == []


# -- ideas ------------------------------------------------------------------------------

@pytest.fixture
def own_ideas(tmp_path, monkeypatch):
    monkeypatch.setattr(ideas, "PATH", str(tmp_path / "ideas.json"))


def test_an_idea_is_kept_and_listed_newest_first(own_ideas):
    ideas.add("a Discord bot for the clan")
    ideas.add("an app that tracks gym sets")
    assert [i["text"] for i in ideas.all()] == ["an app that tracks gym sets",
                                               "a Discord bot for the clan"]


def test_an_idea_can_be_dropped(own_ideas):
    first = ideas.add("one")
    ideas.add("two")
    ideas.remove(first["id"])
    assert [i["text"] for i in ideas.all()] == ["two"]


def test_ideas_by_voice(own_ideas):
    assert tools.run("save_idea", {"text": "a CRT shader pack"}, Context())["ok"] is True
    listed = tools.run("list_ideas", {}, Context())
    assert listed["ideas"][0] == {"number": 1, "text": "a CRT shader pack",
                                  "age": listed["ideas"][0]["age"]}
    assert tools.run("drop_idea", {"number": 1}, Context())["ok"] is True
    assert ideas.all() == []
    assert "فكرة" in tools.REGISTRY["save_idea"].description


# -- the display --------------------------------------------------------------------

def test_the_display_is_given_all_three(monkeypatch, own_ideas):
    monkeypatch.setattr(projects, "snapshot", lambda: {"sessions": [{"title": "x"}],
                                                       "folders": [], "repos": []})
    journal.said("hi")
    journal.answered("Hello.")
    ideas.add("a thing")
    service = dataservice.DataService()
    assert service._read_talks() and service._read_projects() and service._read_ideas()
    snap = service.snapshot
    assert snap["talks"][0]["you"] == "hi"
    assert snap["projects"]["sessions"][0]["title"] == "x"
    assert snap["ideas"]["ideas"][0]["text"] == "a thing"
    assert "reminders" in snap["ideas"]


def test_a_tab_can_be_asked_for_by_voice():
    asked = []
    result = tools.run("panel_tab", {"tab": "projects"}, Context(tab_hook=asked.append))
    assert result["ok"] is True and asked == ["projects"]


def test_the_display_opens_only_folders_it_listed(monkeypatch):
    import apollo

    opened = []
    monkeypatch.setattr(projects, "_last_folders", [r"C:\Users\Admin\Desktop\my-game"])
    monkeypatch.setattr(projects, "open_folder_with", lambda path: opened.append(path))
    api = apollo.Api(lambda: None)
    assert api.open_folder(r"C:\Users\Admin\Desktop\my-game") is True
    assert api.open_folder(r"C:\Windows\System32") is False
    assert opened == [r"C:\Users\Admin\Desktop\my-game"]


def test_the_display_drops_an_idea(own_ideas):
    import apollo

    idea = ideas.add("one")
    poked = []
    api = apollo.Api(lambda: None, poke=lambda *keys: poked.append(keys))
    assert api.drop_idea(idea["id"]) is True
    assert ideas.all() == [] and poked == [("ideas",)]
