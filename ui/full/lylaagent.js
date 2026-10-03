/* LYLA as an agent. The card her HP block opens over the feed, and the one
 * agents mode shows: a pipeline - your command coming in, where it is sent,
 * LYLA working, and what goes out - with dots running along the wires, a
 * line of what is happening, and the runs counted.
 *
 * Until you first command her it is a preview, and says PREVIEW: a demo
 * run on a loop. The moment you do (apollo.py calls `live`), it goes LIVE
 * and shows the real thing - the job (yours, called by name, or one Apollo
 * handed her), each step of it, what she is thinking with, and the answer
 * with how long it took (or the error) - and the demo stops for good.
 *
 * Ported from a React component (ai-agent-pipeline, framer-motion) to this
 * page's own JS, SVG and CSS, so the display still needs no build step: the
 * dots run on SVG's own animateMotion, the pulses are CSS (app.css,
 * #lyla-agent), and what framer-motion's AnimatePresence did for the line -
 * out, then the next one in - is two classes and a timer here. Set in the
 * display's own face rather than the component's system font.
 * tests/test_lyla_agent.py runs it under node.
 *
 * The same card serves every agent, each in its own look (LOOKS): its
 * colour, what goes in and what comes out, its lines. LYLA's is the real
 * one, and THEIA, MONEYPENNY and Q go live the same way the first time
 * Apollo hands one of them a job (crew.py). Each has a mark of its own too
 * (`emblem`), the shape agents mode lists them by. */

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

/* Each agent's look. `rgb` is its colour, for the wires, its box and its
 * mark; `deep` the inside of its box. `trigger`, `read`, `brain` and
 * `outputs` are what its pipeline says, `messages` its demo's lines. LYLA's
 * labels change to what they say live (data-live); the rest are previews. */
export const LOOKS = {
  LYLA: {
    key: 'LYLA', role: 'Research', rgb: '0,82,255', hex: '#0052FF', light: '51,117,255', deep: '#050D1C',
    mark: '#5B8CFF',   // her blue, lifted: the brand blue is too deep to read small on black
    trigger: [['TRIGGER', 'TRIGGER'], ['User Query', 'A job'], ['node-01', 'Apollo · you']],
    read: [['VECTOR DB', 'READING'], ['Semantic Search', 'Desk · news · web'], ['pinecone', 'lyla.py']],
    brain: ['claude', 'gemini · hermes'],
    outputs: [[['Email Draft', 'Voice reply'], '#22c55e'], [['CRM Update', 'On screen'], '#f59e0b'],
              [['Report Gen', 'Journal'], '#f59e0b']],
    stack: ['Claude · Pinecone', 'Gemini · lyla.py'],
    meta: '3 agents · 0 errors', workflows: FIRST_WORKFLOWS, messages: MESSAGES,
  },
  THEIA: {
    key: 'THEIA', role: 'Professor', rgb: '168,85,247', hex: '#A855F7', light: '205,160,255', deep: '#12061C',
    mark: '#C084FC', file: 'crew.py',
    trigger: [['TRIGGER', 'TRIGGER'], ['An idea', 'A job'], ['node-theia', 'Apollo · you']],
    read: [['THINKING', 'THINKING'], ['Analyse · critique', 'Analyse · critique'], ['3 passes', 'crew.py']],
    brain: ['gemini', 'gemini · claude'],
    outputs: [[['Analysis', 'Analysis'], '#22c55e'], [['Critique', 'Critique'], '#f59e0b'],
              [['Best way', 'Best way'], '#f59e0b']],
    stack: ['Gemini · Claude', 'Gemini · crew.py'], meta: 'professor · ready', workflows: 0,
    messages: [
      'Idea received: "Should Apollo get a phone app?"',
      'Pass 1 - analysis: what it needs, what it costs, who it serves',
      'Pass 2 - critique: battery, a second login, a store review',
      'Pass 3 - the best way: a web page first, the app after',
      'Verdict: worth it, staged - confidence medium',
      'Idle. Waiting for the next idea...',
    ],
  },
  MONEYPENNY: {
    key: 'MONEYPENNY', role: 'Markets', rgb: '58,196,170', hex: '#3AC4AA', light: '140,226,210', deep: '#03140F',
    mark: '#6FD8C4', file: 'crew.py',
    trigger: [['TRIGGER', 'TRIGGER'], ['A stock', 'A job'], ['node-moneypenny', 'Apollo · you']],
    read: [['READING', 'READING'], ['Price · desk · insiders', 'Price · desk · insiders'], ['market.py', 'crew.py']],
    brain: ['gemini', 'gemini'],
    outputs: [[['Verdict', 'Verdict'], '#22c55e'], [['Red flags', 'Red flags'], '#f59e0b'],
              [['Ranking', 'Ranking'], '#f59e0b']],
    stack: ['Gemini · market data', 'Gemini · crew.py'], meta: 'markets desk · ready', workflows: 0,
    messages: [
      'Job: "Review my watchlist - what should I sell?"',
      'Reading NVDA: price, valuation, the desk, insiders',
      'Reading TSLA: 3 insiders sold this month',
      'Verdicts: NVDA buy · AMD hold · TSLA trim',
      'Red flag on TSLA: margins down 4 quarters running',
      'Ranking ready: pull from TSLA first',
      'Idle. Watching the tape...',
    ],
  },
  Q: {
    key: 'Q', role: 'Quartermaster', rgb: '255,122,26', hex: '#FF7A1A', light: '255,164,96', deep: '#1A0B02',
    mark: '#FF9A4D', file: 'crew.py',
    trigger: [['TRIGGER', 'TRIGGER'], ['A request', 'A request'], ['node-q', 'Apollo · you']],
    read: [['WRITING', 'WRITING'], ['The ticket', 'The ticket'], ['github', 'github']],
    brain: ['gemini', 'gemini'],
    outputs: [[['Issue', 'Issue'], '#22c55e'], [['@claude', '@claude'], '#f59e0b'],
              [['Journal', 'Journal'], '#f59e0b']],
    stack: ['Gemini · GitHub', 'Gemini · GitHub'], meta: 'quartermaster · ready', workflows: 0,
    messages: [
      'Request: "Tell Claude to add a clock to the HUD"',
      'Writing the ticket: what, why, how to tell it works',
      'Filed: issue #42 on obad-code/apollo, @claude asked',
      'Idle. Waiting for the next request...',
    ],
  },
};

/* Two ways of saying a label: [preview, live] or the same for both. */
const both = (label) => (Array.isArray(label) ? label : [label, label]);

/* Each agent's mark, the shape agents mode lists it by: LYLA's lens,
 * THEIA's eye, MONEYPENNY's candles and Q's gear, each in its own colour. */
export function emblem(key, size = 44) {
  const look = LOOKS[key] || LOOKS.LYLA;
  const c = look.mark || look.hex, soft = `rgba(${look.rgb},0.35)`;
  const shapes = {
    // A hexagon with a lens in it: she looks into things.
    LYLA: `<path d="${[...Array(6)].map((_, i) => {
      const a = Math.PI / 6 + i * Math.PI / 3;
      return `${i ? 'L' : 'M'}${(32 + 26 * Math.cos(a)).toFixed(1)},${(32 + 26 * Math.sin(a)).toFixed(1)}`;
    }).join('')}Z" fill="none" stroke="${c}" stroke-width="2.4"/>
      <circle cx="32" cy="32" r="11" fill="none" stroke="${c}" stroke-width="2.4"/>
      <circle cx="32" cy="32" r="4" fill="${c}"/>`,
    // An eye inside a laurel of arcs: she sees through things.
    THEIA: `<path d="M8 32C16 19 24 14 32 14s16 5 24 18c-8 13-16 18-24 18S16 45 8 32Z" fill="none" stroke="${c}" stroke-width="2.4" stroke-linejoin="round"/>
      <circle cx="32" cy="32" r="8" fill="${soft}" stroke="${c}" stroke-width="2.2"/>
      <circle cx="32" cy="32" r="3.2" fill="${c}"/>
      <path d="M32 4v5M32 55v5M10 10l4 4M50 50l4 4M54 10l-4 4M14 50l-4 4" stroke="${soft}" stroke-width="2" stroke-linecap="round"/>`,
    // Three candles climbing: the markets.
    MONEYPENNY: `<path d="M16 22v26M32 14v30M48 8v26" stroke="${soft}" stroke-width="2" stroke-linecap="round"/>
      <rect x="11" y="28" width="10" height="14" rx="2" fill="${soft}" stroke="${c}" stroke-width="2"/>
      <rect x="27" y="20" width="10" height="16" rx="2" fill="${soft}" stroke="${c}" stroke-width="2"/>
      <rect x="43" y="12" width="10" height="16" rx="2" fill="${c}"/>
      <path d="M8 56h48" stroke="${c}" stroke-width="2.2" stroke-linecap="round"/>`,
    // A gear with a Q's tail: the workshop.
    Q: `<path d="${[...Array(16)].map((_, i) => {
      const a = i * Math.PI / 8, r = i % 2 ? 22 : 27;
      return `${i ? 'L' : 'M'}${(32 + r * Math.cos(a)).toFixed(1)},${(32 + r * Math.sin(a)).toFixed(1)}`;
    }).join('')}Z" fill="none" stroke="${c}" stroke-width="2.2" stroke-linejoin="round"/>
      <circle cx="32" cy="32" r="10" fill="${soft}" stroke="${c}" stroke-width="2.4"/>
      <path d="M37 37l9 9" stroke="${c}" stroke-width="3" stroke-linecap="round"/>`,
  };
  return `<svg class="emblem emblem-${look.key.toLowerCase()}" width="${size}" height="${size}" viewBox="0 0 64 64" aria-hidden="true">${shapes[look.key]}</svg>`;
}

const count = (n) => n.toLocaleString('en-US');
const short = (text, most = 64) => {
  const said = String(text || '').replace(/\s+/g, ' ').trim();
  return said.length > most ? `${said.slice(0, most - 1).trimEnd()}…` : said;
};

const wire = (look, d, strong, arrow) =>
  `<path d="${d}" fill="none" stroke="rgba(${look.rgb},${strong ? 0.22 : 0.15})" stroke-width="1.5"`
  + ` stroke-dasharray="3 5"${arrow ? ` marker-end="url(#${look.key.toLowerCase()}-arrow)"` : ''}/>`;

const dot = (look) => ([p, dur, delay, r, opacity]) =>
  `<circle r="${r}" fill="${look.hex}" opacity="${opacity}">`
  + `<animateMotion dur="${dur}s" repeatCount="indefinite" begin="${delay}s" path="${PATHS[p]}"/></circle>`;

// A box on the pipeline: its kind over its name, and a tag under it.
// Each label carries what it says once the card is live (data-live).
const node = (x, w, kindLabel, nameLabel, tagLabel, nameSize = 12) => {
  const [[kind, liveKind], [name, liveName], [tag, liveTag]] = [kindLabel, nameLabel, tagLabel].map(both);
  return `
    <rect x="${x}" y="66" width="${w}" height="44" rx="8" fill="#141414" stroke="rgba(255,255,255,0.09)" stroke-width="0.5"/>
    <text x="${x + w / 2}" y="83" text-anchor="middle" font-size="9.5" fill="rgba(255,255,255,0.28)" letter-spacing=".07em" data-live="${liveKind}">${kind}</text>
    <text x="${x + w / 2}" y="100" text-anchor="middle" font-size="${nameSize}" fill="rgba(255,255,255,0.82)" data-live="${liveName}">${name}</text>
    <text x="${x + w / 2}" y="122" text-anchor="middle" font-size="8.5" fill="rgba(255,255,255,0.18)" data-live="${liveTag}">${tag}</text>`;
};

// One of the three things going out, with its light: steady when done,
// pulsing while it is still going.
const output = (y, label, colour, pulse = '') => {
  const [name, liveName] = both(label);
  return `
    <rect x="448" y="${y}" width="116" height="30" rx="7" fill="#111" stroke="rgba(255,255,255,0.07)" stroke-width="0.5"/>
    <text x="490" y="${y + 18.5}" text-anchor="middle" font-size="11" fill="rgba(255,255,255,0.62)" data-live="${liveName}">${name}</text>
    <circle class="agent-out${pulse ? ' agent-status' : ''}" cx="550" cy="${y + 8}" r="3" fill="${colour}" ${pulse ? `style="${pulse}"` : 'opacity="0.95"'}/>`;
};

/* The card, whole, in one agent's look - LYLA's unless told. */
export function markup(look = LOOKS.LYLA) {
  const name = look.key;
  const [brain, liveBrain] = both(look.brain);
  const [stack, liveStack] = both(look.stack);
  const [out1, out2, out3] = look.outputs;
  // A preview names only what comes in; the kind and tag are the card's own.
  const trigger = look.preview ? ['TRIGGER', look.trigger, `node-${name.toLowerCase()}`] : look.trigger;
  return `
  <div class="agent-head">
    <span class="agent-live"><i></i><span data-live="${name} · AGENT PIPELINE · LIVE">${name} · AGENT PIPELINE · PREVIEW</span></span>
    <span class="agent-meta">${look.meta}</span>
  </div>
  <svg class="agent-map" width="100%" viewBox="0 0 580 172" aria-hidden="true">
    <defs>
      <marker id="${name.toLowerCase()}-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto">
        <path d="M2 1.5L7.5 5L2 8.5" fill="none" stroke="rgba(${look.rgb},0.45)" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
      </marker>
    </defs>
    ${wire(look, PATHS.p1, true, true)}${wire(look, PATHS.p2, true, true)}
    ${wire(look, PATHS.p3)}${wire(look, PATHS.p4)}${wire(look, PATHS.p5)}
    ${DOTS.map(dot(look)).join('')}
    ${node(16, 100, ...trigger)}
    ${node(158, 110, look.read[0], look.read[1], look.read[2], 11)}
    <rect x="306" y="53" width="105" height="70" rx="10" fill="${look.deep}" stroke="${look.hex}" stroke-width="1"/>
    <rect x="318" y="53.5" width="80" height="1" rx="0.5" fill="rgba(${look.light},0.5)"/>
    <text x="358" y="78" text-anchor="middle" font-size="9.5" fill="rgba(${look.light},0.65)" letter-spacing=".07em">${name}</text>
    <text x="358" y="97" text-anchor="middle" font-size="13" fill="#fff" font-weight="500">Processing</text>
    <circle class="agent-think" cx="346" cy="113" r="2.8" fill="${look.hex}"/>
    <circle class="agent-think" cx="358" cy="113" r="2.8" fill="${look.hex}" style="animation-delay:.4s"/>
    <circle class="agent-think" cx="370" cy="113" r="2.8" fill="${look.hex}" style="animation-delay:.8s"/>
    <text x="358" y="139" text-anchor="middle" font-size="8.5" fill="rgba(${look.rgb},0.4)" class="agent-brain" data-live="${liveBrain}">${brain}</text>
    ${output(35, out1[0], out1[1])}
    ${output(73, out2[0], out2[1], 'animation-duration:1.9s')}
    ${output(111, out3[0], out3[1], 'animation-duration:2.2s;animation-delay:.35s')}
  </svg>
  <div class="agent-say">
    <span class="agent-prompt">›</span>
    <div class="agent-line"></div>
  </div>
  <div class="agent-stats">
    <div><small data-live="RUNS">WORKFLOWS</small><b class="agent-count"></b></div>
    <div><small data-live="LAST">TOKENS</small><b class="agent-last">4.2M</b></div>
    <div><small>AVG LATENCY</small><b class="agent-latency">342ms</b></div>
    <div class="agent-stack"><small>STACK</small><em data-live="${liveStack}">${stack}</em></div>
  </div>`;
}

/* The card on the page: shut until asked, and nothing running while it is.
 * LYLA's unless given another agent's `look`. */
export class LylaAgent {
  constructor(root, { sound = () => {}, timers = globalThis, look = LOOKS.LYLA } = {}) {
    this.root = root;
    this.sound = sound;
    this.timers = timers;
    this.look = look;
    this.messages = look.messages;
    this.message = 0;
    this.workflows = look.workflows;
    this.jobs = [];
    this.leaving = null;
    this.isLive = false;
    this.runs = 0;
    this.errors = 0;
    this.times = [];
    root.innerHTML = markup(look);
    root.setAttribute('aria-hidden', 'true');
    root.setAttribute('data-agent', look.key);
    if (root.style && root.style.setProperty) root.style.setProperty('--agent-rgb', look.rgb);
    this.line = root.querySelector('.agent-line');
    this.count = root.querySelector('.agent-count');
    this.last = root.querySelector('.agent-last');
    this.latency = root.querySelector('.agent-latency');
    this.meta = root.querySelector('.agent-meta');
    this.stack = root.querySelector('.agent-stack em');
    this.brain = root.querySelector('.agent-brain');
    this.line.textContent = this.messages[this.message];
    this.count.textContent = count(this.workflows);
  }

  /* An agent that is only a preview never goes live. */
  get preview() { return Boolean(this.look.preview); }

  get open() { return this.root.classList.contains('open'); }

  toggle() { if (this.open) this.hide(); else this.show(); }

  show() {
    if (this.open) return;
    this.root.classList.add('open');
    this.root.setAttribute('aria-hidden', 'false');
    this.sound('hud');
    if (!this.isLive) this.demo();
  }

  /* The preview's loop: the demo's lines, and its workflows ticking up. */
  demo() {
    this.jobs = [
      this.timers.setInterval(() => this.nextLine(), MESSAGE_EVERY),
      this.timers.setInterval(() => this.nextWorkflow(), WORKFLOW_EVERY),
    ];
  }

  stopDemo() {
    for (const job of this.jobs) this.timers.clearInterval(job);
    this.jobs = [];
  }

  /* A run of hers, as it happens: `stage` is received (with the job, and
   * `by` Apollo when he handed it to her), step (what she is reading),
   * asking (she is thinking it through), done (with the answer, how many ms
   * it took and the `brain` that gave it) or error (with what went wrong). */
  live(event) {
    if (this.preview) return;
    const { stage, text = '', ms = 0, by = '', brain = '' } = event || {};
    if (!this.isLive) this.goLive();
    if (stage === 'received') {
      this.runs += 1;
      this.count.textContent = count(this.runs);
      this.outputs('wait');
      this.say(by ? `From ${by}: "${short(text, 56)}"` : `Received: "${short(text, 60)}"`);
    } else if (stage === 'step') {
      this.say(`${short(text, 70)}…`);
    } else if (stage === 'asking') {
      this.say(text ? `${short(text, 60)}…` : `${this.look.key} is thinking it through…`);
    } else if (stage === 'done') {
      if (brain) {
        this.stack.textContent = `${brain} · ${this.look.file || 'lyla.py'}`;
        this.brain.textContent = brain.toLowerCase();
      }
      const took = Math.round(Number(ms) || 0);
      this.times.push(took);
      const average = this.times.reduce((a, b) => a + b, 0) / this.times.length;
      this.last.textContent = `${took} ms`;
      this.latency.textContent = `${Math.round(average)} ms`;
      this.outputs('ok');
      this.say(`Done in ${took} ms: ${short(text, 44)}`);
    } else if (stage === 'error') {
      this.errors += 1;
      this.meta.textContent = `1 agent · ${this.errors} error${this.errors === 1 ? '' : 's'}`;
      this.outputs('err');
      this.say(`Error: ${short(text, 70)}`);
    }
  }

  /* From the preview to the real thing: every label to what it says live,
   * the demo's numbers cleared, and the demo stopped. */
  goLive() {
    this.isLive = true;
    this.stopDemo();
    this.root.classList.add('live');
    this.root.querySelectorAll('[data-live]').forEach((el) => { el.textContent = el.dataset.live; });
    this.meta.textContent = '1 agent · 0 errors';
    this.count.textContent = '0';
    this.last.textContent = '—';
    this.latency.textContent = '—';
  }

  /* The three things going out: waiting on her, done, or failed. */
  outputs(state) {
    this.root.querySelectorAll('.agent-out').forEach((dot) => {
      dot.classList.remove('wait', 'ok', 'err', 'agent-status');
      dot.classList.add(state);
    });
  }

  /* A line of its own, out with the old one and in from below. */
  say(text) {
    if (this.leaving !== null) this.timers.clearTimeout(this.leaving);
    const line = this.line;
    line.classList.add('leaving');
    this.leaving = this.timers.setTimeout(() => {
      this.leaving = null;
      line.textContent = text;
      line.classList.remove('leaving');
      line.classList.add('arriving');
      void line.offsetWidth;
      line.classList.remove('arriving');
    }, LEAVE_FOR);
  }

  hide() {
    if (!this.open) return;
    this.root.classList.remove('open');
    this.root.setAttribute('aria-hidden', 'true');
    this.sound('down');
    this.stopDemo();
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
      this.message = (this.message + 1) % this.messages.length;
      line.textContent = this.messages[this.message];
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

/* The same card for any agent, by name. */
export const AgentCard = LylaAgent;
