"""LYLA as an agent, before she is one (ui/full/lylaagent.js): the pipeline
card her HP block opens over the feed - a query coming in, a search, LYLA
working, three things going out - with dots running along the wires, a
line of what she is doing that changes every few seconds, and a count of
workflows that ticks up. A pre-design: nothing on it is live yet, and it
says so. Ported from a React component to this page's own JS, so it
needs no build step. Run under node against a stand-in for the DOM."""
import json
import pathlib
import shutil
import subprocess

import pytest

FULL = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full"
AGENT = FULL / "lylaagent.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# Just enough of the DOM, and a clock that only moves when told to.
FAKE = r"""
class ClassList {
  constructor() { this.names = new Set(); }
  add(...n) { n.forEach((x) => this.names.add(x)); }
  remove(...n) { n.forEach((x) => this.names.delete(x)); }
  toggle(n, on) { if (on === undefined) on = !this.names.has(n); on ? this.add(n) : this.remove(n); return on; }
  contains(n) { return this.names.has(n); }
}
export class El {
  constructor() { this.classList = new ClassList(); this.attrs = {}; this.parts = {}; this.textContent = ''; this._html = ''; this.offsetWidth = 1; }
  set innerHTML(html) { this._html = html; this.parts = {}; }
  get innerHTML() { return this._html; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return this.attrs[k]; }
  querySelector(sel) { return this.parts[sel] || (this.parts[sel] = new El()); }
  querySelectorAll() { return []; }
  addEventListener() {}
}
export class Clock {
  constructor() { this.now = 0; this.next = 1; this.jobs = new Map(); }
  setInterval(fn, ms) { const id = this.next++; this.jobs.set(id, { fn, ms, at: this.now + ms, every: true }); return id; }
  setTimeout(fn, ms) { const id = this.next++; this.jobs.set(id, { fn, ms, at: this.now + ms, every: false }); return id; }
  clearInterval(id) { this.jobs.delete(id); }
  clearTimeout(id) { this.jobs.delete(id); }
  advance(ms) {
    const end = this.now + ms;
    for (;;) {
      let first = null;
      for (const [id, job] of this.jobs) if (job.at <= end && (!first || job.at < first[1].at)) first = [id, job];
      if (!first) break;
      const [id, job] = first;
      this.now = job.at;
      if (job.every) job.at += job.ms; else this.jobs.delete(id);
      job.fn();
    }
    this.now = end;
  }
}
"""


def run(tmp_path, body):
    (tmp_path / "lylaagent.mjs").write_text(AGENT.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "fake.mjs").write_text(FAKE, encoding="utf-8")
    script = tmp_path / "run.mjs"
    script.write_text("import * as A from './lylaagent.mjs';\nimport { El, Clock } from './fake.mjs';\n"
                      f"const out = (() => {{ {body} }})();\n"
                      "console.log(JSON.stringify(out));\n", encoding="utf-8")
    result = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


MADE = """
const root = new El(), clock = new Clock(), heard = [];
const agent = new A.LylaAgent(root, { sound: (n) => heard.push(n), timers: clock });
const line = () => root.querySelector('.agent-line').textContent;
const count = () => root.querySelector('.agent-count').textContent;
"""


def test_the_card_draws_the_whole_pipeline(tmp_path):
    html = run(tmp_path, "return A.markup();")
    for label in ("TRIGGER", "User Query", "VECTOR DB", "Semantic Search", "LYLA", "Processing",
                  "Email Draft", "CRM Update", "Report Gen", "WORKFLOWS", "TOKENS", "AVG LATENCY",
                  "STACK"):
        assert label in html, label
    assert html.count("<animateMotion") == 11                    # the dots on the wires
    assert html.count('stroke-dasharray="3 5"') == 5            # the five wires
    assert 'id="lyla-arrow"' in html and "url(#lyla-arrow)" in html


def test_it_says_it_is_a_preview_not_live(tmp_path):
    import re
    html = run(tmp_path, "return A.markup();")
    shown = re.sub(r'data-live="[^"]*"', "", html)       # what it says until it is live
    assert "PREVIEW" in shown and "LIVE" not in shown


def test_it_is_set_in_the_display_s_own_face(tmp_path):
    html = run(tmp_path, "return A.markup();")
    assert "system-ui" not in html and 'font-family="monospace"' not in html


def test_it_starts_on_the_first_line_and_the_first_count(tmp_path):
    first, shown, number = run(tmp_path, MADE + "return [A.MESSAGES[0], line(), count()];")
    assert shown == first and number == "1,247"


def test_it_is_shut_until_asked_and_nothing_runs_while_it_is(tmp_path):
    opened, jobs, text = run(tmp_path, MADE + """
        const opened = agent.open;
        clock.advance(20000);
        return [opened, clock.jobs.size, line()];""")
    assert opened is False and jobs == 0 and text == run(tmp_path, "return A.MESSAGES[0];")


def test_opened_the_line_changes_every_few_seconds_and_goes_round(tmp_path):
    lines = run(tmp_path, MADE + """
        agent.show();
        const seen = [line()];
        clock.advance(300);                 // each look a little after a change
        for (let i = 0; i < 10; i++) { clock.advance(A.MESSAGE_EVERY); seen.push(line()); }
        return seen;""")
    messages = run(tmp_path, "return A.MESSAGES;")
    assert len(messages) == 10
    assert lines[:10] == messages
    assert lines[10] == messages[0]                               # round again


def test_the_line_fades_out_before_the_next_one_comes_in(tmp_path):
    leaving, text_then, text_after, still_leaving = run(tmp_path, MADE + """
        agent.show();
        clock.advance(A.MESSAGE_EVERY);
        const el = root.querySelector('.agent-line');
        const leaving = el.classList.contains('leaving'), then = el.textContent;
        clock.advance(300);
        return [leaving, then, el.textContent, el.classList.contains('leaving')];""")
    messages = run(tmp_path, "return A.MESSAGES;")
    assert leaving is True and text_then == messages[0]
    assert text_after == messages[1] and still_leaving is False


def test_the_workflows_tick_up(tmp_path):
    counts = run(tmp_path, MADE + """
        agent.show();
        clock.advance(A.WORKFLOW_EVERY * 3);
        return count();""")
    assert counts == "1,250"


def test_opening_and_shutting_it_is_heard_and_marked(tmp_path):
    heard, opened, shut, expanded = run(tmp_path, MADE + """
        agent.toggle();
        const opened = [agent.open, root.classList.contains('open')];
        agent.toggle();
        const shut = [agent.open, root.classList.contains('open'), clock.jobs.size];
        return [heard, opened, shut, root.getAttribute('aria-hidden')];""")
    assert heard == ["hud", "down"]
    assert opened == [True, True] and shut == [False, False, 0]
    assert expanded == "true"


def test_shown_twice_it_runs_once(tmp_path):
    jobs, heard = run(tmp_path, MADE + "agent.show(); agent.show(); return [clock.jobs.size, heard];")
    assert jobs == 2 and heard == ["hud"]



# --- live: when you command her ------------------------------------------------------
# The same card, running for real: what you said, where it went, how long it
# took. No more demo lines once it is live.

LIVE = MADE + """
const runs = () => root.querySelector('.agent-count').textContent;
const latency = () => root.querySelector('.agent-latency').textContent;
"""


def test_a_command_takes_the_card_live(tmp_path):
    live, jobs, text, counted = run(tmp_path, LIVE + """
        agent.show();
        agent.live({ stage: 'received', text: 'hey lyla sort my notes' });
        clock.advance(300);
        return [root.classList.contains('live'), clock.jobs.size, line(), runs()];""")
    assert live is True and jobs == 0                     # the demo has stopped
    assert text == 'Received: "hey lyla sort my notes"' and counted == "1"


def test_it_says_where_it_went_and_how_long_it_took(tmp_path):
    lines = run(tmp_path, LIVE + """
        agent.live({ stage: 'received', text: 'hey lyla' });
        clock.advance(300);
        agent.live({ stage: 'asking' });
        clock.advance(300);
        const asking = line();
        agent.live({ stage: 'done', text: 'Your notes are sorted.', ms: 1840 });
        clock.advance(300);
        return [asking, line(), latency()];""")
    assert "Claude" in lines[0]
    assert "1840 ms" in lines[1] and "Your notes are sorted." in lines[1]
    assert lines[2] == "1840 ms"


def test_the_latency_is_the_average_of_the_runs(tmp_path):
    assert run(tmp_path, LIVE + """
        for (const ms of [1000, 3000]) {
          agent.live({ stage: 'received', text: 'x' });
          agent.live({ stage: 'done', text: 'y', ms });
        }
        clock.advance(300);
        return [runs(), latency()];""") == ["2", "2000 ms"]


def test_an_error_says_so(tmp_path):
    text = run(tmp_path, LIVE + """
        agent.live({ stage: 'received', text: 'x' });
        agent.live({ stage: 'error', text: 'could not reach the API' });
        clock.advance(300);
        return line();""")
    assert text.startswith("Error:") and "API" in text


def test_a_long_command_is_cut_to_a_line(tmp_path):
    text = run(tmp_path, LIVE + """
        agent.live({ stage: 'received', text: 'word '.repeat(60) });
        clock.advance(300);
        return line();""")
    assert len(text) < 100 and text.endswith('…"')


def test_live_it_reopens_without_the_demo(tmp_path):
    jobs = run(tmp_path, LIVE + """
        agent.live({ stage: 'received', text: 'x' });
        clock.advance(300);
        agent.hide(); agent.show();
        return clock.jobs.size;""")
    assert jobs == 0
