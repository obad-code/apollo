"""LYLA's desk (lyla.py): research Apollo hands her, done in the background.

You ask Apollo for a stock analysis; he hands it to LYLA and is free at
once. She works on her own thread - her card told each step - and when she
is done Apollo passes on what she found, after any turn in progress. She
reads and writes, and never takes the screen."""
import threading
import time

import pytest

import lyla
import tools


def wait_for(check, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if check():
            return True
        time.sleep(0.01)
    return False


def desk(tmp_path, **kw):
    kw.setdefault("resolve", lambda stock: "NVDA")
    kw.setdefault("facts", lambda job, step: (step("Reading NVDA: the desk"), {"sources": {"desk": "ok"}})[1])
    kw.setdefault("think", lambda prompt: ("SUMMARY: NVDA is bid. Traders are bullish.\n\n## Price\nUp 4%.", "Gemini"))
    return lyla.Desk(path=str(tmp_path / "reports.json"), **kw)


def test_a_job_is_taken_at_once_while_she_is_still_thinking(tmp_path):
    release, told, reported = threading.Event(), [], []

    def slow(prompt):
        release.wait(5)
        return "SUMMARY: Done.\n\nReport.", "Gemini"
    d = desk(tmp_path, think=slow, tell=told.append, report=reported.append)
    started = time.monotonic()
    taken = d.take("analyse nvidia for me", "nvidia")
    assert time.monotonic() - started < 0.5          # Apollo is free again at once
    assert taken == {"job": 1, "ahead": 0}
    assert wait_for(lambda: any(e["stage"] == "asking" for e in told))
    assert reported == []                             # still thinking
    release.set()
    assert wait_for(lambda: reported)
    assert reported[0]["ok"] and reported[0]["summary"] == "Done."


def test_her_card_is_told_each_step_in_order(tmp_path):
    told, reported = [], []
    d = desk(tmp_path, tell=told.append, report=reported.append)
    d.take("analyse nvidia", "nvidia")
    assert wait_for(lambda: reported)
    stages = [e["stage"] for e in told]
    assert stages[0] == "received" and stages[-1] == "done"
    assert "step" in stages and "asking" in stages
    assert told[0]["by"] == "Apollo" and told[0]["agent"] == "LYLA"
    done = told[-1]
    assert done["text"] == "NVDA is bid. Traders are bullish."
    assert done["report"] == "## Price\nUp 4%." and done["brain"] == "Gemini"
    assert done["symbol"] == "NVDA" and isinstance(done["ms"], int)


def test_the_report_waits_for_the_turn_in_progress(tmp_path):
    gate, reported = threading.Lock(), []
    d = desk(tmp_path, report=reported.append, gate=gate)
    with gate:                                        # a turn is going on
        d.take("analyse nvidia", "nvidia")
        time.sleep(0.3)
        assert reported == []
    assert wait_for(lambda: reported)


def test_jobs_wait_their_turn(tmp_path):
    release, reported = threading.Event(), []

    def slow(prompt):
        release.wait(5)
        return "SUMMARY: ok.", "Gemini"
    d = desk(tmp_path, think=slow, report=reported.append)
    d.take("one", "a")
    assert wait_for(lambda: d.current is not None)
    assert d.take("two", "b")["ahead"] == 1
    release.set()
    assert wait_for(lambda: len(reported) == 2)
    assert [r["task"] for r in reported] == ["one", "two"]


def test_a_failed_job_is_reported_as_failed(tmp_path):
    told, reported = [], []

    def broken(prompt):
        raise RuntimeError("quota gone")
    d = desk(tmp_path, think=broken, tell=told.append, report=reported.append)
    d.take("analyse nvidia", "nvidia")
    assert wait_for(lambda: reported)
    assert reported[0]["ok"] is False and "quota gone" in reported[0]["error"]
    assert told[-1]["stage"] == "error"
    assert d.reports == []


def test_her_reports_are_kept_newest_first(tmp_path):
    reported = []
    d = desk(tmp_path, report=reported.append)
    d.take("first", "a")
    assert wait_for(lambda: len(reported) == 1)
    d.take("second", "b")
    assert wait_for(lambda: len(reported) == 2)
    assert [r["task"] for r in d.reports] == ["second", "first"]
    again = lyla.Desk(path=str(tmp_path / "reports.json"))
    assert [r["task"] for r in again.reports] == ["second", "first"]


def test_a_job_that_is_not_a_stock_skips_the_ticker(tmp_path):
    asked, reported = [], []
    d = desk(tmp_path, resolve=lambda s: asked.append(s) or "X", report=reported.append)
    d.take("find the best budget GPUs")
    assert wait_for(lambda: reported)
    assert asked == [] and reported[0]["symbol"] == ""


@pytest.mark.parametrize("answer, said, report", [
    ("SUMMARY: Up. Bid.\n\nThe report.", "Up. Bid.", "The report."),
    ("**SUMMARY:** Up.\nThe report.", "Up.", "The report."),
    ("Up a lot. Traders like it. More here.", "Up a lot. Traders like it.", "Up a lot. Traders like it. More here."),
])
def test_her_answer_splits_into_what_is_said_and_the_report(answer, said, report):
    assert lyla.split(answer) == (said, report)


def test_hermes_is_used_when_it_is_set_up(monkeypatch):
    monkeypatch.setenv("HERMES_URL", "http://127.0.0.1:8642/")
    monkeypatch.setenv("HERMES_KEY", "k")
    sent = []

    def post(url, payload, key, timeout):
        sent.append((url, payload["messages"][-1]["content"], key))
        return {"choices": [{"message": {"content": "SUMMARY: from Hermes."}}]}
    monkeypatch.setattr(lyla, "_post", post)
    monkeypatch.setattr(lyla, "_generate", lambda *a: pytest.fail("Gemini asked"))
    assert lyla.think("the job") == ("SUMMARY: from Hermes.", "Hermes")
    assert sent == [("http://127.0.0.1:8642/v1/chat/completions", "the job", "k")]


def test_gemini_answers_when_hermes_does_not(monkeypatch):
    monkeypatch.setenv("HERMES_URL", "http://127.0.0.1:8642")
    monkeypatch.setenv("HERMES_KEY", "k")
    monkeypatch.setenv("GEMINI_API_KEY", "g")

    def down(*a):
        raise OSError("refused")
    monkeypatch.setattr(lyla, "_post", down)
    monkeypatch.setattr(lyla, "_generate", lambda model, prompt, search: "SUMMARY: from Gemini.")
    assert lyla.think("the job") == ("SUMMARY: from Gemini.", "Gemini")


def test_gemini_falls_back_through_models_then_without_search(monkeypatch):
    monkeypatch.delenv("HERMES_URL", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setattr(lyla, "MODELS", ("a", "b"))
    tried = []

    def generate(model, prompt, search):
        tried.append((model, search))
        if search:
            raise RuntimeError("404")
        return "SUMMARY: ok."
    monkeypatch.setattr(lyla, "_generate", generate)
    assert lyla.think("job") == ("SUMMARY: ok.", "Gemini")
    assert tried == [("a", True), ("b", True), ("a", False)]


def test_without_a_key_she_says_so():
    import os
    saved = os.environ.pop("GEMINI_API_KEY", None)
    try:
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
            lyla.ask_gemini("job")
    finally:
        if saved is not None:
            os.environ["GEMINI_API_KEY"] = saved


# -- Apollo's side: the tools ---------------------------------------------------------

class Ctx(tools.Context):
    def __init__(self):
        super().__init__()
        self.asked = []
        self.display = self.asked.append


def test_ask_lyla_hands_the_job_over_and_returns(monkeypatch, tmp_path):
    taken = []
    d = desk(tmp_path)
    monkeypatch.setattr(d, "take", lambda task, stock="": taken.append((task, stock)) or {"job": 7, "ahead": 0})
    monkeypatch.setattr(lyla, "DESK", d)
    ctx = Ctx()
    out = tools.run("ask_lyla", {"task": "حلل لي سهم انفيديا", "stock": "Nvidia"}, ctx)
    assert out["ok"] and out["job"] == 7 and "LYLA" in out["result"]
    assert taken == [("حلل لي سهم انفيديا", "Nvidia")]
    assert ctx.asked == []                            # she never takes the screen


def test_lyla_findings_reads_back_her_latest(monkeypatch, tmp_path):
    d = desk(tmp_path)
    d.reports = [{"task": "analyse nvidia", "symbol": "NVDA", "summary": "Bid.", "report": "Full."}]
    monkeypatch.setattr(lyla, "DESK", d)
    out = tools.run("lyla_findings", {}, Ctx())
    assert out["reports"][0]["summary"] == "Bid." and out["report"] == "Full."
    assert out["working_on"] is None


def test_lylas_tools_are_declared_for_gemini():
    assert {"ask_lyla", "lyla_findings"} <= set(tools.REGISTRY)
