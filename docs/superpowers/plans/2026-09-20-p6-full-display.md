# P6 The Full Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The display you approved: your shader rippling behind everything, a big clock and both dates, Riyadh's weather, your watchlist with sparklines, headlines on what you follow, Trump's posts, what Apollo has cost today, the machine's load — and LYLA still in her room.

**Architecture:** A new hand-written page under `ui/full/` replaces the generated one. `shader.js` runs the ring shader in plain WebGL at half resolution; `app.js` owns the panels, the bridge (`window.apollo.*`) and the motion; `lyla.js` is her canvas engine lifted out of the old page; `app.css` holds the CRT skin. The old page stays as `ui/legacy/` so nothing is lost.

**Tech Stack:** Plain ES modules in a WebView2 page (no React, no build step), WebGL, Motion (vendored at `ui/vendor/motion.js`), driven from `apollo.py` through `window.apollo.*`.

**Spec:** `docs/superpowers/specs/2026-09-19-apollo-jarvis-design.md` (§4 P6) and the approved part-3 mockup.

## Global Constraints

- The page is data-driven: everything on it comes from `window.apollo.data(snapshot)` (`dataservice.DataService`), `status`, `turn`, `visual` and `briefing`. Nothing on this page invents a number — where a reader failed, the panel shows its last value with an age, or a dash.
- Colours are the overlay's palette (`overlay_paint.PALETTE`), written once as CSS variables.
- The shader is the one from the brief, tinted violet/amber/teal and dimmed, rendered at half resolution and paused whenever the display is not on screen.
- 2560×1440 is the target; the layout is a grid that holds at 1920×1080 too.
- Tests: `.venv/Scripts/python.exe -m pytest -q` for the Python side; the page is checked in the browser pane and by screenshot.
- Commit per task with the `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` trailer.

## Review Focus

1. A stale or missing feed must show its age, not a zero — Task 3 (`test_panel_shows_age_when_data_is_old`).
2. The display must not burn the GPU when it is hidden — Task 1 (the shader pauses on `mode('orb')`).
3. A price that has not changed must not flash — Task 3.
4. The clock must not drift or stall while the display is open — Task 3 (it ticks from `Date`, not from a counter).
5. LYLA must survive the move: same sprite, same room, same label — Task 2 (side-by-side screenshot).

---

### Task 1: the page, the shader, the skin

**Files:**
- Create: `ui/full/index.html`, `ui/full/app.css`, `ui/full/shader.js`, `ui/full/app.js` (skeleton + sample snapshot)
- Move: the generated page to `ui/legacy/index.html` (kept, not deleted)

**Interfaces:**
- Produces: `window.apollo = {status, turn, note, fatal, mode, data, visual, level, briefing}`; `Shader(canvas)` with `.start()`, `.stop()`, `.speed(multiplier)`; `ui/full/index.html` loads `app.js` as a module.

The layout, as the approved mockup has it (a 12-column grid, 40px gutters):

| Area | Content |
|---|---|
| top left | clock `HH:MM` + seconds, the date, then `Day 263 · Week 38 · 7 Rabi II 1448`, then Riyadh's weather |
| top right | status dots (Gemini, Claude, mic), and the NYSE countdown |
| left column | `MARKETS`: the two indices large, then the seven stocks, each a row of ticker, sparkline, price, change |
| right column | `HEADLINES` with topic chips (gaming, marvel, movies, markets) and four stories; below it `TRUMP · TRUTH SOCIAL` with three posts, market-moving ones flagged |
| bottom strip | `TOKENS TODAY`, `SYSTEM` (CPU/GPU/RAM), `CLIPS` |
| centre | Apollo's ring, the wordmark, and the hint |
| bottom centre | LYLA's room (Task 2) |

- [ ] **Step 1: The shader**, ported from the brief's Three.js component to plain WebGL:

```js
// FILE: ui/full/shader.js
// The ring shader from the brief, in plain WebGL: three.js would be 600 KB to
// draw two triangles. Tinted to Apollo's palette and dimmed - it sits behind
// text that has to stay readable - and rendered at half resolution, which is
// both cheaper and softer, the way a CRT is.

const VERTEX = `
attribute vec2 position;
void main() { gl_Position = vec4(position, 0.0, 1.0); }
`;

const FRAGMENT = `
precision highp float;
uniform vec2 resolution;
uniform float time;

void main() {
  vec2 uv = (gl_FragCoord.xy * 2.0 - resolution.xy) / min(resolution.x, resolution.y);
  float t = time * 0.05;
  float lineWidth = 0.002;

  vec3 colour = vec3(0.0);
  for (int j = 0; j < 3; j++) {
    for (int i = 0; i < 5; i++) {
      colour[j] += lineWidth * float(i * i) /
        abs(fract(t - 0.01 * float(j) + float(i) * 0.01) * 5.0
            - length(uv) + mod(uv.x + uv.y, 0.2));
    }
  }

  // The three channels become Apollo's three lights rather than red, green
  // and blue, and the whole thing is dimmed to sit under the panels.
  vec3 tinted = colour.r * vec3(0.55, 0.35, 0.85)
              + colour.g * vec3(0.95, 0.70, 0.30)
              + colour.b * vec3(0.25, 0.75, 0.80);
  gl_FragColor = vec4(tinted * 0.34 + vec3(0.016, 0.018, 0.036), 1.0);
}
`;

export class Shader {
  constructor(canvas, { scale = 0.5 } = {}) {
    this.canvas = canvas;
    this.scale = scale;
    this.gl = canvas.getContext('webgl', { antialias: false, depth: false });
    this.time = 1.0;
    this.rate = 1.0;
    this.frame = null;
    if (this.gl) this._build();
  }

  _build() {
    const gl = this.gl;
    const compile = (type, source) => {
      const shader = gl.createShader(type);
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      return shader;
    };
    const program = gl.createProgram();
    gl.attachShader(program, compile(gl.VERTEX_SHADER, VERTEX));
    gl.attachShader(program, compile(gl.FRAGMENT_SHADER, FRAGMENT));
    gl.linkProgram(program);
    gl.useProgram(program);
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    const position = gl.getAttribLocation(program, 'position');
    gl.enableVertexAttribArray(position);
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
    this.resolution = gl.getUniformLocation(program, 'resolution');
    this.clock = gl.getUniformLocation(program, 'time');
    this.resize();
  }

  resize() {
    if (!this.gl) return;
    const width = Math.max(1, Math.floor(window.innerWidth * this.scale));
    const height = Math.max(1, Math.floor(window.innerHeight * this.scale));
    this.canvas.width = width;
    this.canvas.height = height;
    this.gl.viewport(0, 0, width, height);
    this.gl.uniform2f(this.resolution, width, height);
  }

  speed(rate) { this.rate = rate; }

  start() {
    if (!this.gl || this.frame !== null) return;
    const draw = () => {
      this.time += 0.05 * this.rate;
      this.gl.uniform1f(this.clock, this.time);
      this.gl.drawArrays(this.gl.TRIANGLES, 0, 3);
      this.frame = requestAnimationFrame(draw);
    };
    this.frame = requestAnimationFrame(draw);
  }

  stop() {
    // Nothing is watching while the overlay has the screen, and a shader that
    // keeps drawing to a hidden window is a GPU burning for nobody.
    if (this.frame !== null) cancelAnimationFrame(this.frame);
    this.frame = null;
  }
}
```

- [ ] **Step 2: `index.html`** — a single page that loads `app.css`, `../vendor/motion.js` and `app.js` (type=module), with the structure above as semantic sections: `#shader`, `#clock`, `#status`, `#markets`, `#headlines`, `#posts`, `#strip`, `#core`, `#lyla`, `#answer`. No inline styles beyond the canvas.
- [ ] **Step 3: `app.css`** — the palette as CSS variables (`--amber #e8b958`, `--you #d2eef3`, `--caption rgba(200,185,240,.65)`, `--up #5fe39a`, `--down #ff6b7a`, `--panel rgba(10,14,30,.42)`), the grid, the panel skin (radius 22, no borders), the scanline and vignette overlays, and `@media (max-width: 1920px)` sizes.
- [ ] **Step 4: `app.js` skeleton** — mounts the shader, holds `state`, exposes `window.apollo`, and renders from a sample snapshot baked in as `SAMPLE` so the page can be developed and screenshotted with no backend.
- [ ] **Step 5:** Serve `ui/full/` in the browser pane at 2560×1440, screenshot, compare with the approved mockup.
- [ ] **Step 6: Commit** `git add ui/full ui/legacy && git commit -m "The full display: page, shader and skin"`

---

### Task 2: LYLA moves house

**Files:**
- Create: `ui/full/lyla.js`
- Test: by picture, against the old page

**Interfaces:**
- Produces: `class Lyla { constructor(canvas, { label, icon }); start(); stop(); setMood(mood) }`, drawing the same sprite, room and activities as the old page.

- [ ] **Step 1:** Lift her methods out of `ui/legacy/index.html` — `drawLyla`, `drawLylaPose`, `drawLylaIcon`, `drawLylaHealth`, `drawProps`, `drawEnv`, `drawSpeech`, `drawBubble`, `lylaNext`, `lylaFact`, `lylaTarget`, `feedScenes`, `currentScene` — plus the data tables they read, into a class that owns its own canvas and state rather than the old component's refs.
- [ ] **Step 2:** Mount her in `#lyla` at the bottom centre of the new display, with her label line underneath as before.
- [ ] **Step 3:** Screenshot old and new side by side; they must be the same character in the same room.
- [ ] **Step 4: Commit** `git add ui/full/lyla.js && git commit -m "Move LYLA into the new display"`

---

### Task 3: live data, and how it moves

**Files:**
- Modify: `ui/full/app.js`
- Test: `tests/test_snapshot_shape.py` (the contract between `dataservice` and the page)

**Interfaces:**
- Consumes: the snapshot from `dataservice.DataService` — `{market: {indices, watchlist, status}, news: {topic: [...]}, posts, weather, system, usage, updated}`.
- Produces: `render(snapshot)`, `sparkline(points, width, height)` (an SVG path), `countUp(el, value)`, `flash(el, direction)`, `setPhase(phase)`.

- [ ] **Step 1: The contract test** — the page and the service must agree on shape:

```python
# FILE: tests/test_snapshot_shape.py
"""The snapshot the display reads is a contract; this is the copy of it."""
import dataservice


def test_snapshot_has_every_key_the_display_reads(monkeypatch):
    monkeypatch.setattr(dataservice.market, "quote", lambda s: {
        "symbol": s, "name": s, "price": 1.0, "change": 0.0, "change_pct": 0.0,
        "currency": "USD", "exchange": "NMS", "points": [(1, 1.0)],
        "previous_close": 1.0, "time": 0})
    monkeypatch.setattr(dataservice.market, "history", lambda s, p: {
        "symbol": s, "name": s, "price": 1.0, "change_pct": 0.0, "currency": "USD",
        "exchange": "NMS", "points": [(i, 1.0) for i in range(6)],
        "previous_close": 1.0, "time": 0})
    monkeypatch.setattr(dataservice.feeds, "headlines",
                        lambda topic, limit=5: [{"title": "t", "source": "s",
                                                 "age": "1h ago", "when": 1, "link": ""}])
    monkeypatch.setattr(dataservice.feeds, "posts",
                        lambda hours=24, limit=5: [{"text": "p", "age": "2h ago",
                                                    "when": 1, "market": True}])
    monkeypatch.setattr(dataservice.weather, "now",
                        lambda: {"temp": 32, "high": 42, "low": 30, "text": "clear", "code": 0})

    service = dataservice.DataService()
    service.refresh(force=True)
    snap = service.snapshot

    assert set(snap) >= {"market", "news", "posts", "weather", "system", "usage", "updated"}
    assert set(snap["market"]) == {"indices", "watchlist", "status"}
    stock = snap["market"]["watchlist"][0]
    assert set(stock) >= {"symbol", "name", "price", "change_pct", "currency", "spark"}
    assert set(snap["system"]) >= {"cpu", "ram", "gpu", "gpu_name"}
    assert set(snap["usage"]) >= {"tokens", "cost", "estimated", "turns"}
    headline = snap["news"]["gaming"][0]
    assert set(headline) >= {"title", "source", "age"}
    assert set(snap["posts"][0]) >= {"text", "age", "market"}


def test_age_of_a_snapshot_is_readable():
    assert dataservice.age_words(0).endswith("now") or dataservice.age_words(0) == "just now"
    assert dataservice.age_words(3600) == "1h ago"
```
(`dataservice` re-exports `feeds.age_words` for this.)

- [ ] **Step 2:** Render everything from the snapshot, with these rules:
  - a value older than its interval × 3 gets its age beside it, in the caption colour;
  - a price that changed since the last snapshot flashes its row (green up, red down) for 600 ms, and one that did not does nothing;
  - the clock reads `new Date()` every 250 ms, so it can neither drift nor stall;
  - sparklines are SVG paths, drawn once per snapshot, with `stroke-dasharray` animating on first paint only.
- [ ] **Step 3: The motion**, with Motion (`ui/vendor/motion.js`):
  - opening: panels rise 16 px and fade in, staggered 40 ms, with the spring `{ stiffness: 220, damping: 26 }`;
  - numbers count up over 600 ms on first paint;
  - answering (`status('Speaking')` or `turn('Apollo', …)`): panels drop to 18% opacity, the core lifts and shrinks to 0.8, the answer and any chart fade in at the centre, and the shader speeds up ×3;
  - back to idle: the reverse, faster.
- [ ] **Step 4:** Check each in the browser pane with a fake snapshot; screenshot idle and answering.
- [ ] **Step 5: Commit** `git add ui/full/app.js tests/test_snapshot_shape.py && git commit -m "Feed the display live data, and give it its motion"`

---

### Task 4: Apollo drives it

**Files:**
- Modify: `apollo.py` (serve `ui/full/index.html`; push data on mode change), `build_ui.py` (retire, with a note)

- [ ] **Step 1:** `INDEX` points at `ui/full/index.html`. The old generated page stays at `ui/legacy/index.html`, and `build_ui.py` gains a line at the top saying it builds the legacy page and is no longer part of the run.
- [ ] **Step 2:** `Apollo.on_data` pushes to the page only while the display is up (already true); on opening the display (`apply_mode` → FULL), push the current snapshot immediately so it is never empty, and call `ui.mode("full")` as now.
- [ ] **Step 3:** The briefing opens the display (P4 already does) — check the two together: the recap speaks while the display shows the same numbers.
- [ ] **Step 4:** Smoke: run Apollo, press Ctrl+`, screenshot the real screen, quit.
- [ ] **Step 5: Commit** `git add -A && git commit -m "Apollo opens the new display"`

---

### Task 5: README and review

- [ ] **Step 1:** README: replace "The full display" with what it now shows and how it is driven; note that `ui/legacy` is the old design and `build_ui.py` only builds that.
- [ ] **Step 2:** Full suite, a last look at both displays, and the final review for the whole branch.
- [ ] **Step 3: Commit** `git add -A && git commit -m "README: the new full display"`
