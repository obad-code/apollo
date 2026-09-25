/* LYLA as an agent - a pre-design, before she is one. The card her HP block
 * opens over the feed: a pipeline drawn as it will run once she is real -
 * your query coming in, a search for what matters to it, LYLA working, and
 * three things going out - with dots running along the wires, a line of
 * what she is doing that changes every few seconds, and a count of
 * workflows ticking up. Nothing on it is live yet, and it says PREVIEW.
 *
 * Ported from a React component (ai-agent-pipeline, framer-motion) to this
 * page's own JS, SVG and CSS, so the display still needs no build step: the
 * dots run on SVG's own animateMotion, the pulses are CSS (app.css,
 * #lyla-agent), and what framer-motion's AnimatePresence did for the line -
 * out, then the next one in - is two classes and a timer here. Set in the
 * display's own face rather than the component's system font.
 * tests/test_lyla_agent.py runs it under node. */

export const MESSAGES = [
  'Received: "Summarize Q3 performance for stakeholder report..."',
  'Chunking input → 847 tokens → 6 embeddings generated',
  'Vector search complete: 5 chunks, avg cosine sim 0.89',
  'Injecting context into prompt template (1,204 tokens)',
  'LLM inference: 3 tool calls dispatched in parallel',
  'Tool: send_email → draft created, 312 words, pending approval',
  'Tool: update_crm → record Q3_2024 flagged as reviewed',
  'Tool: generate_report → PDF queued for 17:00 dispatch',
  'Workflow complete. 3 actions dispatched in 342ms.',
  'Idle. Listening for next trigger event...',
];

export const MESSAGE_EVERY = 2700;     // ms between lines
export const WORKFLOW_EVERY = 7200;    // ms between workflows
export const FIRST_WORKFLOWS = 1247;
const LEAVE_FOR = 250;                 // ms a line takes to go before the next comes

// The wires: query to search, search to LYLA, and LYLA out to each of three.
export const PATHS = {
  p1: 'M116,88 L158,88',
  p2: 'M268,88 L306,88',
  p3: 'M411,88 C425,88 435,50 448,50',
  p4: 'M411,88 L448,88',
  p5: 'M411,88 C425,88 435,126 448,126',
};

// The dots on the wires: which wire, seconds round, seconds late, size, how lit.
const DOTS = [
  ['p1', 1.05, 0, 2.5, 1], ['p1', 1.05, 0.35, 1.8, 0.65], ['p1', 1.05, 0.7, 1.3, 0.35],
  ['p2', 0.88, 0.18, 2.5, 1], ['p2', 0.88, 0.62, 1.8, 0.65],
  ['p3', 1.3, 0.08, 2.2, 0.9], ['p3', 1.3, 0.65, 1.5, 0.55],
  ['p4', 1.15, 0.28, 2.2, 0.9], ['p4', 1.15, 0.85, 1.5, 0.55],
  ['p5', 1.4, 0.45, 2.2, 0.9], ['p5', 1.4, 1.0, 1.5, 0.55],
];

const count = (n) => n.toLocaleString('en-US');

const wire = (d, strong, arrow) =>
  `<path d="${d}" fill="none" stroke="rgba(0,82,255,${strong ? 0.22 : 0.15})" stroke-width="1.5"`
  + ` stroke-dasharray="3 5"${arrow ? ' marker-end="url(#lyla-arrow)"' : ''}/>`;

const dot = ([p, dur, delay, r, opacity]) =>
  `<circle r="${r}" fill="#0052FF" opacity="${opacity}">`
  + `<animateMotion dur="${dur}s" repeatCount="indefinite" begin="${delay}s" path="${PATHS[p]}"/></circle>`;

// A box on the pipeline: its kind over its name, and a tag under it.
const node = (x, w, kind, name, tag, nameSize = 12) => `
    <rect x="${x}" y="66" width="${w}" height="44" rx="8" fill="#141414" stroke="rgba(255,255,255,0.09)" stroke-width="0.5"/>
    <text x="${x + w / 2}" y="83" text-anchor="middle" font-size="9.5" fill="rgba(255,255,255,0.28)" letter-spacing=".07em">${kind}</text>
    <text x="${x + w / 2}" y="100" text-anchor="middle" font-size="${nameSize}" fill="rgba(255,255,255,0.82)">${name}</text>
    <text x="${x + w / 2}" y="122" text-anchor="middle" font-size="8.5" fill="rgba(255,255,255,0.18)">${tag}</text>`;

// One of the three things going out, with its light: steady when done,
// pulsing while it is still going.
const output = (y, name, colour, pulse = '') => `
    <rect x="448" y="${y}" width="116" height="30" rx="7" fill="#111" stroke="rgba(255,255,255,0.07)" stroke-width="0.5"/>
    <text x="490" y="${y + 18.5}" text-anchor="middle" font-size="11" fill="rgba(255,255,255,0.62)">${name}</text>
    <circle cx="550" cy="${y + 8}" r="3" fill="${colour}" ${pulse ? `class="agent-status" style="${pulse}"` : 'opacity="0.95"'}/>`;

/* The card, whole. */
export function markup() {
  return `
  <div class="agent-head">
    <span class="agent-live"><i></i>LYLA · AGENT PIPELINE · PREVIEW</span>
    <span class="agent-meta">3 agents · 0 errors</span>
  </div>
  <svg class="agent-map" width="100%" viewBox="0 0 580 172" aria-hidden="true">
    <defs>
      <marker id="lyla-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto">
        <path d="M2 1.5L7.5 5L2 8.5" fill="none" stroke="rgba(0,82,255,0.45)" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
      </marker>
    </defs>
    ${wire(PATHS.p1, true, true)}${wire(PATHS.p2, true, true)}
    ${wire(PATHS.p3)}${wire(PATHS.p4)}${wire(PATHS.p5)}
    ${DOTS.map(dot).join('')}
    ${node(16, 100, 'TRIGGER', 'User Query', 'node-01')}
    ${node(158, 110, 'VECTOR DB', 'Semantic Search', 'pinecone', 11)}
    <rect x="306" y="53" width="105" height="70" rx="10" fill="#050D1C" stroke="#0052FF" stroke-width="1"/>
    <rect x="318" y="53.5" width="80" height="1" rx="0.5" fill="rgba(51,117,255,0.5)"/>
    <text x="358" y="78" text-anchor="middle" font-size="9.5" fill="rgba(51,117,255,0.65)" letter-spacing=".07em">LYLA</text>
    <text x="358" y="97" text-anchor="middle" font-size="13" fill="#fff" font-weight="500">Processing</text>
    <circle class="agent-think" cx="346" cy="113" r="2.8" fill="#0052FF"/>
    <circle class="agent-think" cx="358" cy="113" r="2.8" fill="#0052FF" style="animation-delay:.4s"/>
    <circle class="agent-think" cx="370" cy="113" r="2.8" fill="#0052FF" style="animation-delay:.8s"/>
    <text x="358" y="139" text-anchor="middle" font-size="8.5" fill="rgba(0,82,255,0.4)">claude</text>
    ${output(35, 'Email Draft', '#22c55e')}
    ${output(73, 'CRM Update', '#f59e0b', 'animation-duration:1.9s')}
    ${output(111, 'Report Gen', '#f59e0b', 'animation-duration:2.2s;animation-delay:.35s')}
  </svg>
  <div class="agent-say">
    <span class="agent-prompt">›</span>
    <div class="agent-line"></div>
  </div>
  <div class="agent-stats">
    <div><small>WORKFLOWS</small><b class="agent-count"></b></div>
    <div><small>TOKENS</small><b>4.2M</b></div>
    <div><small>AVG LATENCY</small><b>342ms</b></div>
    <div class="agent-stack"><small>STACK</small><em>Claude · Pinecone</em></div>
  </div>`;
}

/* The card on the page: shut until asked, and nothing running while it is. */
export class LylaAgent {
  constructor(root, { sound = () => {}, timers = globalThis } = {}) {
    this.root = root;
    this.sound = sound;
    this.timers = timers;
    this.message = 0;
    this.workflows = FIRST_WORKFLOWS;
    this.jobs = [];
    this.leaving = null;
    root.innerHTML = markup();
    root.setAttribute('aria-hidden', 'true');
    this.line = root.querySelector('.agent-line');
    this.count = root.querySelector('.agent-count');
    this.line.textContent = MESSAGES[this.message];
    this.count.textContent = count(this.workflows);
  }

  get open() { return this.root.classList.contains('open'); }

  toggle() { if (this.open) this.hide(); else this.show(); }

  show() {
    if (this.open) return;
    this.root.classList.add('open');
    this.root.setAttribute('aria-hidden', 'false');
    this.sound('hud');
    this.jobs = [
      this.timers.setInterval(() => this.nextLine(), MESSAGE_EVERY),
      this.timers.setInterval(() => this.nextWorkflow(), WORKFLOW_EVERY),
    ];
  }

  hide() {
    if (!this.open) return;
    this.root.classList.remove('open');
    this.root.setAttribute('aria-hidden', 'true');
    this.sound('down');
    for (const job of this.jobs) this.timers.clearInterval(job);
    this.jobs = [];
    if (this.leaving !== null) this.timers.clearTimeout(this.leaving);
    this.leaving = null;
    this.line.classList.remove('leaving', 'arriving');
  }

  /* The line goes up and out, then the next comes up from under it. */
  nextLine() {
    const line = this.line;
    line.classList.add('leaving');
    this.leaving = this.timers.setTimeout(() => {
      this.leaving = null;
      this.message = (this.message + 1) % MESSAGES.length;
      line.textContent = MESSAGES[this.message];
      line.classList.remove('leaving');
      line.classList.add('arriving');
      void line.offsetWidth;               // placed below, then eased up
      line.classList.remove('arriving');
    }, LEAVE_FOR);
  }

  /* One more workflow, and the count gives a little pop. */
  nextWorkflow() {
    this.workflows += 1;
    this.count.textContent = count(this.workflows);
    this.count.classList.remove('pop');
    void this.count.offsetWidth;
    this.count.classList.add('pop');
  }
}
