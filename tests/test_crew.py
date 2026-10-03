"""The crew: THEIA, MONEYPENNY, Q and LYLA's downloads."""
import urllib.error

import pytest

import agents
import crew
import github_requests
import lyla
import youtube


def desk_with(think, facts=None, name="THEIA", tmp=None):
    return crew.CrewDesk(think=think, facts=facts or (lambda job, step: {"sources": {}}),
                         name=name, path=str(tmp / f"{name}.json"))


def test_a_deep_job_is_marked_for_the_deep_brain(tmp_path):
    prompts = []
    desk = desk_with(lambda p: (prompts.append(p), ("SUMMARY: Done.\n\nReport.", "x"))[1], tmp=tmp_path)
    desk.run({"id": 1, "task": "is my plan good", "stock": "", "symbol": "", "deep": True,
              "agent": "THEIA", "asked": 0})
    assert prompts[0].startswith(crew.DEEP_MARK)
    assert desk.reports[0]["summary"] == "Done."


def test_the_fast_brain_never_sees_the_mark(monkeypatch):
    seen = {}

    def fake_think(prompt, system=None, models=None):
        seen.update(prompt=prompt, system=system, models=models)
        return "SUMMARY: ok", "Gemini"
    monkeypatch.setattr(lyla, "think", fake_think)
    crew.thinker(crew.THEIA_SYSTEM, deep_capable=True)("plain job")
    assert seen["prompt"] == "plain job" and seen["models"] == crew.FAST_MODELS
    assert "CRITIQUE" in seen["system"]


def test_deep_without_a_claude_key_uses_gemini_pro(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    seen = {}
    monkeypatch.setattr(lyla, "ask_gemini",
                        lambda p, s, m: seen.update(p=p, m=m) or "SUMMARY: deep")
    text, brain = crew.thinker(crew.THEIA_SYSTEM, True)(crew.DEEP_MARK + "job")
    assert brain == "Gemini Pro" and seen["p"] == "job" and seen["m"] == crew.DEEP_GEMINI


def test_reports_say_whose_they_are(tmp_path):
    told = []
    desk = desk_with(lambda p: ("SUMMARY: Hold.\n\nWhy.", "x"), name="MONEYPENNY", tmp=tmp_path)
    desk.configure(report=told.append)
    desk.run(dict(desk_job := {"id": 1, "task": "nvda", "stock": "", "symbol": "",
                               "agent": "MONEYPENNY", "asked": 0}))
    assert told[0]["agent"] == "MONEYPENNY" and told[0]["ok"]


def test_moneypenny_reads_every_stock_on_the_watchlist(monkeypatch):
    read = []
    monkeypatch.setattr(lyla, "stock_facts",
                        lambda s, step: read.append(s) or {"symbol": s, "sources": {"price": "ok"}})
    facts = crew.moneypenny_facts({"task": "review", "symbol": "", "symbols": ["NVDA", "AMD"]},
                                  lambda t: None)
    assert read == ["NVDA", "AMD"] and set(facts["stocks"]) == {"NVDA", "AMD"}
    assert facts["sources"] == {"NVDA:price": "ok", "AMD:price": "ok"}


def test_q_files_the_ticket_and_says_its_number(monkeypatch):
    monkeypatch.setattr(lyla, "think", lambda p, s=None, m=None: (
        "SUMMARY: Q filed it.\nTITLE: Add a clock widget\n\nThe user wants a clock.", "Gemini"))
    filed = {}
    monkeypatch.setattr(github_requests, "file_issue",
                        lambda title, body: filed.update(title=title, body=body)
                        or {"number": 7, "url": "https://github.com/o/r/issues/7"})
    text, _ = crew.q_think("prompt")
    assert filed == {"title": "Add a clock widget", "body": "The user wants a clock."}
    assert text.startswith("SUMMARY: Q filed it. Ticket #7 is filed for Claude.")
    assert text.endswith("https://github.com/o/r/issues/7")


def test_an_issue_needs_a_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="GITHUB_TOKEN"):
        github_requests.file_issue("t", "b")


def test_an_issue_mentions_claude_and_falls_back_without_the_label(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    sent = []

    def post(url, payload, token):
        sent.append(payload)
        if "labels" in payload:
            raise urllib.error.HTTPError(url, 422, "label", {}, None)
        return {"number": 3, "html_url": "u"}
    monkeypatch.setattr(github_requests, "_post", post)
    assert github_requests.file_issue("Title", "Body") == {"number": 3, "url": "u"}
    assert "@claude" in sent[-1]["body"] and "labels" not in sent[-1]


@pytest.mark.parametrize("said, name", [
    ("THEIA حللي هالفكرة", "THEIA"), ("يا ثيا وش رايك", "THEIA"),
    ("Moneypenny how is Nvidia", "MONEYPENNY"), ("ميني بيني حلل انفيديا", "MONEYPENNY"),
    ("Q, add a button", "Q"), ("hey lyla download it", "LYLA"),
    ("the queue is long", None), ("I have a quick question", None)])
def test_names_are_made_out_in_both_languages(said, name):
    assert agents.detect(said) == name


def test_youtube_links_pass_and_anything_else_is_searched():
    assert youtube.target_for("https://youtu.be/abc") == "https://youtu.be/abc"
    assert youtube.target_for("gta 6 trailer") == "ytsearch1:gta 6 trailer"
    with pytest.raises(ValueError):
        youtube.target_for("https://evil.example/video")
    with pytest.raises(ValueError):
        youtube.target_for("  ")


def test_sound_only_becomes_mp3_with_ffmpeg():
    opts = youtube.options(True, True, "out")
    assert opts["postprocessors"][0]["preferredcodec"] == "mp3"
    assert youtube.options(False, False, "out")["format"] == "b[ext=mp4]/b"


def test_a_download_is_reported_once_done(tmp_path, monkeypatch):
    monkeypatch.setattr(youtube, "folder", lambda audio=False: str(tmp_path))
    told = []
    downloads = youtube.Downloads(run=lambda target, opts: {"title": "Trailer", "path": "p.mp4"},
                                  report=told.append)
    job = downloads.do({"what": "trailer", "target": "ytsearch1:trailer", "audio": False})
    assert job["ok"] and told[0]["title"] == "Trailer"


def test_every_agent_has_a_desk_and_a_role():
    assert set(crew.DESKS) == set(crew.NAMES) == set(agents.NAMES)
    assert all(crew.ROLES[n] for n in crew.NAMES)


def test_the_board_counts_todays_jobs_by_agent_and_hour(tmp_path):
    import datetime as dt
    now = dt.datetime(2026, 10, 3, 15, 0)
    desk = crew.DESKS["THEIA"]
    kept = desk.reports
    desk.reports = [{"task": "plan", "summary": "ok", "done": dt.datetime(2026, 10, 3, 9, 30).timestamp()},
                    {"task": "old", "summary": "x", "done": dt.datetime(2026, 10, 1, 9, 0).timestamp()}]
    try:
        got = crew.board(now, journal_day=[{"kind": "tool", "name": "ask_theia"},
                                           {"kind": "tool", "name": "ask_theia"},
                                           {"kind": "you", "text": "hi"}],
                         spend={"cost": 0.4}, problems=[{"title": "MIC", "level": "fail"}],
                         alerts_state={"watching": True, "sent_hour": 1})
    finally:
        desk.reports = kept
    assert got["agents"]["THEIA"]["done_today"] == 1 and got["hours"]["THEIA"][9] == 1
    assert got["jobs"][0]["task"] == "plan" and got["tools"] == [("ask_theia", 2)]
    assert got["issues"] == {"count": 1, "failing": 1, "top": ["MIC"]}
