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
 * one; ATLAS, NOVA and ECHO are previews of agents not built yet, to see
 * how they will look - they never go live. Each has a mark of its own too
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
  ATLAS: {
    key: 'ATLAS', role: 'Planner', rgb: '255,122,26', hex: '#FF7A1A', light: '255,164,96', deep: '#1A0B02',
    preview: true,
    trigger: 'Your goal', read: ['MAPPING', 'Calendar · projects', 'atlas.py'], brain: 'route planner',
    outputs: [['The plan', '#22c55e'], ['Reminders', '#f59e0b'], ['Calendar', '#f59e0b']],
    stack: 'Planner · calendar', meta: 'not built yet', workflows: 318,
    messages: [
      'Goal received: "Ship the Apollo update by Friday"',
      'Mapping the week: 14 free hours across 4 days',
      'Breaking the goal down → 6 steps, 2 depend on others',
      'Route found: critical path is 3 steps, 9h of work',
      'Placing steps round prayer times and your usual breaks',
      'Reminder set: "Start the trading tests" - Wed 16:00',
      'Calendar: 3 blocks added, 1 moved to make room',
      'Plan ready: on track for Thursday night, a day spare',
      'Idle. Waiting for the next goal...',
    ],
  },
  NOVA: {
    key: 'NOVA', role: 'Creator', rgb: '232,62,255', hex: '#E83EFF', light: '240,140,255', deep: '#15041A',
    preview: true,
    trigger: 'An idea', read: ['MOODBOARD', 'Your ideas · refs', 'nova.py'], brain: 'drafting',
    outputs: [['Draft', '#22c55e'], ['Visuals', '#f59e0b'], ['Post', '#f59e0b']],
    stack: 'Writer · image model', meta: 'not built yet', workflows: 96,
    messages: [
      'Idea received: "A teaser for Apollo\'s trading desk"',
      'Pulling your saved ideas → 3 match, tone: bold, short',
      'Moodboard: green on ink, terminal type, a live dot',
      'Drafting 3 hooks, keeping the best under 12 words',
      'Visual: 1600×900 frame of the desk, verdict in the head',
      'Draft ready: 58 words, 2 variants for you to pick',
      'Post queued as a draft - nothing goes out without you',
      'Idle. Waiting for the next spark...',
    ],
  },
  ECHO: {
    key: 'ECHO', role: 'Memory', rgb: '24,224,194', hex: '#18E0C2', light: '110,240,222', deep: '#021614',
    preview: true,
    trigger: 'A question', read: ['RECALL', 'Journal · talks', 'echo.py'], brain: 'remembering',
    outputs: [['The answer', '#22c55e'], ['Notes', '#f59e0b'], ['Journal', '#f59e0b']],
    stack: 'Journal · embeddings', meta: 'not built yet', workflows: 2041,
    messages: [
      'Asked: "What did I decide about the X token last week?"',
      'Searching 6 days of the journal → 41 moments',
      'Recall: 3 talks mention X, the latest on Tuesday',
      'Found it: "keep X off until the desk proves itself"',
      'Linking: the trading desk went live the same day',
      'Answer ready, with the two talks it came from',
      'Note filed under Trading → decisions',
      'Idle. Listening, remembering...',
    ],
  },
};

/* Two ways of saying a label: [preview, live] or the same for both. */
const both = (label) => (Array.isArray(label) ? label : [label, label]);

/* Each agent's mark, the shape agents mode lists it by: LYLA's lens, ATLAS's
 * compass, NOVA's burst and ECHO's waves, each in its own colour. */
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
    // A compass: a ring, its four ticks, the needle - north filled.
    ATLAS: `<circle cx="32" cy="32" r="25" fill="none" stroke="${soft}" stroke-width="2"/>
      <path d="M32 3v8M32 53v8M3 32h8M53 32h8" stroke="${c}" stroke-width="2.4" stroke-linecap="round"/>
      <path d="M32 12L39 32H25Z" fill="${c}"/>
      <path d="M32 52L39 32H25Z" fill="none" stroke="${c}" stroke-width="2" stroke-linejoin="round"/>`,
    // A burst of eight points: something new.
    NOVA: `<path d="${[...Array(16)].map((_, i) => {
      const a = -Math.PI / 2 + i * Math.PI / 8, r = i % 2 ? 9 : (i % 4 ? 20 : 28);
      return `${i ? 'L' : 'M'}${(32 + r * Math.cos(a)).toFixed(1)},${(32 + r * Math.sin(a)).toFixed(1)}`;
    }).join('')}Z" fill="${soft}" stroke="${c}" stroke-width="2" stroke-linejoin="round"/>
      <circle cx="32" cy="32" r="4.5" fill="${c}"/>`,
    // Waves going out from a point, and coming back.
    ECHO: `<circle cx="32" cy="32" r="4.5" fill="${c}"/>
      <path d="M22 22a14 14 0 0 0 0 20M42 22a14 14 0 0 1 0 20" fill="none" stroke="${c}" stroke-width="2.6" stroke-linecap="round"/>
      <path d="M15 15a24 24 0 0 0 0 34M49 15a24 24 0 0 1 0 34" fill="none" stroke="${c}" stroke-width="2.2" stroke-linecap="round" opacity=".6"/>
      <path d="M8 9a33 33 0 0 0 0 46M56 9a33 33 0 0 1 0 46" fill="none" stroke="${soft}" stroke-width="2" stroke-linecap="round"/>`,
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
      this.say(text ? `${short(text, 60)}…` : 'Routed to LYLA - called by name. Asking Claude…');
    } else if (stage === 'done') {
      if (brain) {
        this.stack.textContent = `${brain} · lyla.py`;
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
