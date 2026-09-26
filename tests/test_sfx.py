"""The display's sounds (ui/full/sfx.js), run under node against a stand-in
for Web Audio that writes down what it was asked to do. Nothing is played
from a file: every sound is made on the spot from a few oscillators and a
little noise, each shaped by its own envelope - so each one has to start
from silence and end in it (or it clicks), stay short and quiet (they are
the interface's, not the music's), and let go of what it made. There is
no switching them off: they are always on. And every sound the page and LYLA ask for by name is
one there is a recipe for."""
import json
import pathlib
import re
import shutil
import subprocess

import pytest

FULL = pathlib.Path(__file__).resolve().parent.parent / "ui" / "full"
SFX = FULL / "sfx.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# A Web Audio context that records instead of playing.
FAKE = r"""
class Param {
  constructor(value) { this.value = value; this.events = []; this.inputs = 0; }
  setValueAtTime(v, t) { this.events.push(['set', v, t]); this.value = v; }
  linearRampToValueAtTime(v, t) { this.events.push(['lin', v, t]); }
  exponentialRampToValueAtTime(v, t) {
    if (v <= 0) throw new Error('exponential ramp to ' + v);
    this.events.push(['exp', v, t]);
  }
}
class Node {
  constructor(ctx, kind) { this.ctx = ctx; this.kind = kind; this.outs = []; ctx.nodes.push(this); }
  connect(to) { this.outs.push(to); if (to instanceof Param) to.inputs += 1; return to; }
  disconnect() {}
}
class Source extends Node {
  start(t) { this.started = t ?? 0; }
  stop(t) { this.stopped = t ?? 0; }
}
export class Fake {
  constructor(state = 'running') {
    this.nodes = []; this.currentTime = 10; this.sampleRate = 48000;
    this.state = state; this.resumed = 0; this.destination = new Node(this, 'destination');
  }
  resume() { this.resumed += 1; this.state = 'running'; return Promise.resolve(); }
  createGain() { const n = new Node(this, 'gain'); n.gain = new Param(1); return n; }
  createOscillator() {
    const n = new Source(this, 'osc'); n.type = 'sine';
    n.frequency = new Param(440); n.detune = new Param(0); return n;
  }
  createBiquadFilter() {
    const n = new Node(this, 'filter'); n.type = 'lowpass';
    n.frequency = new Param(350); n.Q = new Param(1); return n;
  }
  createBuffer(channels, length, rate) {
    const data = new Float32Array(length);
    return { length, sampleRate: rate, duration: length / rate, getChannelData: () => data };
  }
  createBufferSource() { const n = new Source(this, 'noise'); n.buffer = null; return n; }
}
"""


def run(tmp_path, body):
    (tmp_path / "sfx.mjs").write_text(SFX.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "fake.mjs").write_text(FAKE, encoding="utf-8")
    script = tmp_path / "run.mjs"
    script.write_text("import * as S from './sfx.mjs';\nimport { Fake } from './fake.mjs';\n"
                      f"const out = (() => {{ {body} }})();\n"
                      "console.log(JSON.stringify(out));\n", encoding="utf-8")
    result = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


# What one sound made: each source with its envelope and its pitch.
PLAYED = """
const played = (name) => {
  const ctx = new Fake();
  const out = ctx.createGain();
  const sources = S.schedule(ctx, out, name, ctx.currentTime);
  return sources.map((src) => {
    // The envelope: the gain the source feeds first.
    const env = src.outs[0].gain ? src.outs[0] : src.outs[0].outs[0];
    return { kind: src.kind, started: src.started, stopped: src.stopped,
             env: env.gain.events, freq: src.frequency ? src.frequency.events : [],
             filters: ctx.nodes.filter((n) => n.kind === 'filter').map((f) => f.frequency.events) };
  });
};
"""


def test_every_sound_has_a_recipe_of_its_own(tmp_path):
    names = run(tmp_path, "return Object.keys(S.SOUNDS);")
    assert len(names) >= 12
    for name in names:
        assert run(tmp_path, PLAYED + f"return played({json.dumps(name)}).length;") >= 1


def test_each_starts_from_silence_and_ends_in_it(tmp_path):
    every = run(tmp_path, PLAYED + "return Object.keys(S.SOUNDS).map((n) => [n, played(n)]);")
    for name, sources in every:
        for src in sources:
            env = src["env"]
            assert env[0][0] == "set" and env[0][1] == 0, (name, env)          # no click in
            assert env[-1][1] <= 0.001, (name, env)                             # nor out
            assert src["stopped"] >= env[-1][2], name                           # let go after


def test_they_are_short_and_quiet(tmp_path):
    every = run(tmp_path, PLAYED + "return Object.keys(S.SOUNDS).map((n) => [n, played(n)]);")
    for name, sources in every:
        start = min(s["started"] for s in sources)
        assert max(s["stopped"] for s in sources) - start <= 1.2, name
        peaks = [max(v for _, v, _ in s["env"]) for s in sources]
        assert 0 < max(peaks) and sum(peaks) <= 0.3, (name, peaks)


def test_their_pitches_are_ones_you_can_hear(tmp_path):
    every = run(tmp_path, PLAYED + "return Object.keys(S.SOUNDS).map((n) => [n, played(n)]);")
    for name, sources in every:
        for src in sources:
            for _, hz, _ in src["freq"] + [e for f in src["filters"] for e in f]:
                assert 30 <= hz <= 14000, (name, hz)


def test_a_sound_goes_through_the_output_it_was_given(tmp_path):
    reached = run(tmp_path, """
        const ctx = new Fake(); const out = ctx.createGain();
        const reaches = (node) => node === out || node.outs.some(reaches);
        return S.schedule(ctx, out, 'press', ctx.currentTime).every(reaches);""")
    assert reached is True


def test_the_player_makes_its_context_only_when_first_asked(tmp_path):
    made, played = run(tmp_path, """
        let made = 0;
        const sfx = new S.Sfx({ make: () => { made += 1; return new Fake(); } });
        const before = made;
        const played = sfx.play('press');
        sfx.play('tick');
        return [[before, made], played];""")
    assert made == [0, 1] and played is True


def test_a_context_still_waiting_for_a_gesture_is_woken(tmp_path):
    assert run(tmp_path, """
        const ctx = new Fake('suspended');
        const sfx = new S.Sfx({ make: () => ctx });
        sfx.play('press');
        return ctx.resumed;""") == 1


def test_the_same_sound_twice_at_once_is_played_once(tmp_path):
    first, again, later, other = run(tmp_path, """
        const ctx = new Fake();
        const sfx = new S.Sfx({ make: () => ctx });
        const first = sfx.play('tick'), again = sfx.play('tick');
        const other = sfx.play('press');
        ctx.currentTime += 0.2;
        return [first, again, sfx.play('tick'), other];""")
    assert (first, again, later, other) == (True, False, True, True)


def test_a_name_there_is_no_recipe_for_is_ignored(tmp_path):
    assert run(tmp_path, "return new S.Sfx({ make: () => new Fake() }).play('kazoo');") is False


def test_no_web_audio_no_sound_and_no_error(tmp_path):
    assert run(tmp_path, """
        const sfx = new S.Sfx({ make: () => { throw new Error('no audio'); } });
        return [sfx.play('press'), sfx.play('hud')];""") == [False, False]


def test_every_sound_the_page_and_lyla_ask_for_exists(tmp_path):
    known = set(run(tmp_path, "return Object.keys(S.SOUNDS);"))
    asked = set()
    for script in ("app.js", "lyla.js", "lylaagent.js", "index.html"):
        text = (FULL / script).read_text(encoding="utf-8")
        # Every name quoted inside a call - `sound(Math.random() < 0.5 ? 'ly1' : 'ly2')`
        # asks for two - and every data-sfx on a button.
        for call in re.findall(r"(?:sfx\.play|\.sound)\(([^()]*(?:\([^()]*\)[^()]*)*)\)", text):
            asked |= set(re.findall(r"'([a-z0-9]+)'", call))
        asked |= set(re.findall(r'data-sfx="([a-z0-9]+)"', text))
    asked.discard("none")
    assert {"ly1", "ly2", "hud"} <= asked                  # LYLA's own, from the old page
    assert asked <= known, asked - known


# The granular family: every change on the display has a sound of its own,
# made of grains - many tiny blips, scattered in time and pitch - rather than
# the one click every button used to share.
GRANULAR = ["expand", "collapse", "show", "hide", "swap", "grain", "channel", "open", "close",
            "check", "fault", "ready", "scan", "clean", "alert", "drop"]


def test_the_granular_family_is_all_there(tmp_path):
    known = set(run(tmp_path, "return Object.keys(S.SOUNDS);"))
    assert set(GRANULAR) <= known, set(GRANULAR) - known


def test_a_granular_sound_is_made_of_grains(tmp_path):
    for name in ("expand", "collapse", "channel", "scan", "ready"):
        sources = run(tmp_path, PLAYED + f"return played({json.dumps(name)});")
        grains = [s for s in sources if s["stopped"] - s["started"] <= 0.08]
        assert len(grains) >= 6, (name, len(grains))


def test_the_grains_fall_the_same_way_every_time(tmp_path):
    first, again = run(tmp_path, PLAYED + "return [played('expand'), played('expand')];")
    assert first == again
