/* The full display.
 *
 * Everything on this page comes from apollo.py through `window.apollo.*`:
 * `data` for the world (dataservice.DataService), `status` and `turn` for the
 * conversation, `visual` for a chart an answer brought with it. Nothing here
 * invents a number - a reader that failed shows its last value with an age on
 * it, or a dash.
 *
 * The one exception is SAMPLE below, which lets the page be opened and
 * screenshotted on its own while it is being worked on.
 */

import { Shader } from './shader.js';
import { Lyla } from './lyla.js';
import { DotFlow, FRAMES } from './dotflow.js';
import { LedWord } from './ledword.js';
import { HEADER, checkLine, detailLine, lastLines, readyLine, schedule, typed, typedAt } from './boot.js';
import * as Tiles from './tiles.js';
import * as Globe from './globe.js';
import { Sfx } from './sfx.js';
import { LylaAgent, LOOKS, emblem } from './lylaagent.js';
import * as Feed from './feed.js';
import * as Modes from './modes.js';
import * as Hud from './hud.js';
import * as Lights from './consolelights.js';
import * as Explain from './explain.js';

const Motion = window.Motion || {};
// Motion is vendored beside this page. If it ever fails to load, the page must
// still be readable - so the fallback puts every element in its RESTING state
// rather than trying to apply keyframe arrays as styles, which silently leaves
// opacity at 0 and the display blank.
const animate = Motion.animate || ((el, props) => {
  for (const [name, value] of Object.entries(props)) {
    el.style[name] = Array.isArray(value) ? value[value.length - 1] : value;
  }
  return { finished: Promise.resolve() };
});

const $ = (id) => document.getElementById(id);

/* Headlines come from Bing and Google News, posts from Truth Social. Neither is
 * Apollo's to trust: a title carrying `<img src=x onerror=...>` written into
 * innerHTML would run as script in the window that holds your watchlist, your
 * usage and a bridge back into the app. The old page was React, which escaped
 * everything it rendered; this one builds its own markup, so every value that
 * Apollo did not write itself goes through here first.
 * tests/test_page_escapes_feeds.py fails if one ever does not. */
const esc = (value) => String(value ?? '').replace(/[&<>"']/g,
  (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
const RISE = { opacity: [0, 1], transform: ['translateY(16px)', 'translateY(0px)'] };
const SPRING = { type: 'spring', stiffness: 220, damping: 26 };

// The last is Private Eye's own: its finds, and nothing else.
const TOPICS = ['all', 'gaming', 'marvel', 'movies', 'markets', 'private eye'];

// dataservice.INTERVALS x 3. Past this a panel is showing something it could
// not refresh, and it has to say so - a price from an hour ago that looks
// current is worse than no price at all.
const STALE_AFTER = { market: 180, news: 1800, posts: 900, weather: 2700, system: 15 };

const NOW = Date.now() / 1000;

const SAMPLE = {
  market: {
    status: 'NYSE opens in 37h 37m',
    indices: [
      { symbol: '^GSPC', name: 'S&P 500', price: 7650.5, change_pct: 0.17, spark: [] },
      { symbol: '^IXIC', name: 'Nasdaq', price: 26522.54, change_pct: 0.39, spark: [] },
    ],
    watchlist: [
      { symbol: 'AAPL', name: 'Apple Inc.', price: 336.13, change_pct: -0.26, logo: 'logos/AAPL.png',
        target: 328.22, upside: -2.35, pe: 38.59,
        spark: [330, 332, 331, 335, 338, 336, 334, 337, 336, 334, 336] },
      { symbol: 'MSFT', name: 'Microsoft Corporation', price: 493.78, change_pct: -0.8, logo: 'logos/MSFT.png',
        target: 560.4, upside: 13.5, pe: 31.2,
        spark: [498, 496, 495, 492, 490, 494, 493, 491, 494, 492, 494] },
      { symbol: 'NVDA', name: 'NVIDIA Corporation', price: 222.27, change_pct: 1.34, logo: 'logos/NVDA.png',
        target: 327.7, upside: 47.43, pe: 28.1, earnings: '2026-09-28',
        spark: [206, 210, 214, 212, 218, 224, 229, 232, 226, 220, 222] },
      { symbol: 'TSLA', name: 'Tesla, Inc.', price: 364.27, change_pct: -0.53, logo: 'logos/TSLA.png',
        target: 396.94, upside: 8.97, pe: 334.19,
        spark: [372, 368, 366, 370, 367, 364, 361, 365, 363, 366, 364] },
      { symbol: 'AMZN', name: 'Amazon.com, Inc.', price: 253.71, change_pct: 1.0, logo: 'logos/AMZN.png',
        target: 288.1, upside: 13.6, pe: 34.8,
        spark: [246, 249, 248, 251, 250, 252, 255, 253, 252, 254, 254] },
      { symbol: 'GOOGL', name: 'Alphabet Inc.', price: 201.35, change_pct: -0.3, logo: 'logos/GOOGL.png',
        target: 224.6, upside: 11.5, pe: 26.4,
        spark: [205, 203, 204, 202, 203, 201, 200, 202, 201, 202, 201] },
      { symbol: 'META', name: 'Meta Platforms, Inc.', price: 665.75, change_pct: -2.43, logo: 'logos/META.png',
        target: 790.2, upside: 18.7, pe: 24.9,
        spark: [692, 686, 682, 679, 674, 670, 673, 668, 666, 669, 666] },
    ],
  },
  news: {
    gaming: [{ title: "Marvel's Wolverine sold very well on PlayStation 5", source: 'levelup', age: '1h ago', when: NOW - 3600,
               summary: 'Early figures put the launch among the fastest-selling first-party games on the console, ahead of the studio\'s last release.' },
             { title: 'Maono G3 mixer launches with dual-PC streaming', source: 'Notebookcheck', age: '1h ago', when: NOW - 4200,
               summary: 'The mixer routes a game PC and a streaming PC through one box, with separate levels for chat and game audio.' }],
    marvel: [{ title: "Marvel's Wolverine compared to Uncharted 4", source: 'GameGPU', age: '56m ago', when: NOW - 3360, summary: '' }],
    movies: [{ title: "'Resident Evil' obliterates franchise box office records", source: "Murphy's Multiverse", age: '14m ago', when: NOW - 840,
               summary: 'A $108M worldwide opening, the best start the franchise has had, with the international markets carrying most of it.' }],
    markets: [{ title: "2026's top stock flashes buy signal", source: "Investor's Business Daily", age: '2h ago', when: NOW - 7200, summary: '' }],
  },
  posts: [{ text: 'Over the years, there have been many Hoaxes, but the greatest of them all is the one being perpetrated right now.', age: '25m ago', market: true, when: NOW - 1500 },
          { text: 'Many people think that the words "Artificial Intelligence" are inaccurate...', age: '8h ago', market: false, when: NOW - 28800 }],
  weather: { temp: 32, high: 42, low: 30, text: 'clear' },
  prayer: { name: 'Asr', at: NOW + 5400 },
  system: { cpu: 16, ram: 83, gpu: 3, gpu_name: 'NVIDIA GeForce RTX 4060 Ti', vram: 2.1 },
  usage: { tokens: 839, cost: 0.02, estimated: true, turns: 1 },
  clips: { saved_today: 0, seconds: 60 },
  updated: Date.now() / 1000,
  stamps: { market: Date.now() / 1000, news: Date.now() / 1000, posts: Date.now() / 1000,
            weather: Date.now() / 1000, system: Date.now() / 1000 },
};

// The day's range, as dataservice works it out from the day's curve.
for (const quote of SAMPLE.market.watchlist) {
  quote.high = Math.max(...quote.spark);
  quote.low = Math.min(...quote.spark);
}

const state = {
  snapshot: null,
  prices: new Map(),
  phase: 'idle',
  entered: false,
  topic: 0,
  settleTimer: null,
  cardsTimer: null,
  level: 0,
  levelSmooth: 0,
  mode: 'full',           // what apollo.py last said the window is
  feed: [],               // the stories on screen, in the order they are numbered
  feedKey: '',            // ...and what they were, so an unchanged feed is left alone
  lit: -1,                // the row under the pointer
  open: null,             // the story opened out of its row: { index, item }
  rowLit: null,           // the stock row under the pointer
  stock: null,            // the stock opened out of its card, or the add picker
  pending: new Map(),     // stocks asked for whose cards have not come yet
  marketKey: '',          // what the cards were last drawn from
  tab: 'stocks',          // which of the side panel's tabs is showing
  projects: null,         // the projects last drawn, for their clicks
  liveTimer: null,        // takes LIVE off the panel when the trades stop
  panels: {},             // which panels apollo.py last said are shown
  osiris: false,          // OSIRIS laid into the normal display, and Apollo in its colours
  view: 'normal',         // which view of the display: normal, clear, trading or agents
  lylaReports: [],        // what LYLA found, newest first (apollo.py keeps them)
  feedSeen: null,         // the stories the feed last drew, so a new one can arrive
  reportOpen: -1,         // the report of hers opened out, if any
  agentOpen: null,        // the agent whose process agents mode is showing, if any
  hud: Hud.emptyHud(),    // the normal display as arranged by hand (hud.js), kept by apollo.py
  hudEdit: false,         // the HUD editor is up
  hudSnap: true,          // edges pull onto the grid and each other while it is
  away: false,            // away mode, as apollo.py last said
  listening: false,       // hands-free, as apollo.py last said
  modeTicket: 0,          // the mode last asked for, so an older one stops half way
  osirisReturn: false,    // ...and taken into ultra mode, to go back when it ends
  osirisTicket: 0,        // the last placing of the map asked for; older ones stand down
  osirisTimer: null,      // ...places the map once the stage has its new shape
  channelTimer: null,     // ends the channel change that covers a change of shape
  roomTimer: null,        // stops LYLA once her room has faded
  layout: Tiles.defaultLayout(),  // ultra mode's displays, as apollo.py keeps them
  drag: null,             // the display being moved by its top edge
  resizing: null,         // ...or resized by its corner
  dragMoved: false,       // swallows the click that ends a drag
  configFor: null,        // the display whose settings are open
  saveTimer: null,        // hands the layout to apollo.py once the changes stop
  powerTimer: null,       // ends the displays' power-on
};

// Whether the display is the idle screen. Up here because the clock, which
// starts ticking before the rest of the page is built, asks it.
const asleep = { on: false, timer: null, last: '' };

/* --- the shader, the ring and LYLA --------------------------------------- */

const shader = new Shader($('shader'));
shader.start();

/* The name in lit cells, in its two places: on the idle screen, and in the
 * intro as Apollo comes up. (Under the ring it is a neon sign, all markup
 * and CSS.) Upright, in Orbitron at its
 * heaviest drawn at four fifths of its width - a little taller than it
 * comes - with room between the letters, and arriving scrambled. */
const NAME = { font: '"Orbitron", "Segoe UI", sans-serif', weight: 900, stretch: 0.8,
               tracking: 0.3 };
const sleepWord = new LedWord($('sleep-word'), { ...NAME, rows: 16, fill: 0.7 });
// In the intro the name is lit in the boot screen's own green phosphor.
const introWord = new LedWord($('intro-word'), { ...NAME, rows: 22, glow: 1.15,
                                                 colour: [168, 255, 192] });

window.addEventListener('resize', () => {
  shader.resize();
  for (const word of [sleepWord, introWord]) word.resize();
});

/* The boot screen is a real loading screen: apollo.py's checks and the
 * parts of Apollo coming up (window.apollo.boot) are its lines, each typed
 * as it lands with a sound for how it went, and it goes once they are all
 * in (window.apollo.bootDone) - a moment to read the last line, and off. */
const READY_AT = 1.7;            // s: never before the name has settled
const READY_RATE = 60;           // letters a second, the last line
const READY_HOLD = 800;          // ms it is read before the tube goes off
const OFF_FOR = 800;             // ms the tube takes to go off
const REVEAL_FOR = 1100;         // ms the display takes to come into focus
const INTRO_MOST = 11500;        // ms: done or not, the display comes then
const LOG_ROWS = 12;             // lines the glass holds before it scrolls
const LINE_GAP = 0.09;           // s between two lines that came at once
const LINE_RATE = 300;           // letters a second, a check
const boot = { steps: [], arrivals: [], done: null, total: 16 };

// How many of the steps so far went wrong - the summary when apollo.py never
// says it is done and the screen has to go anyway.
const bootSoFar = () => ({ issues: boot.steps.filter((s) => s.status !== 'ok').length,
                           fails: boot.steps.filter((s) => s.status === 'fail').length });

const pad = (n) => String(n).padStart(2, '0');
const stamp = (d) => `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}  `
                   + `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;

function playIntro() {
  const box = $('intro');
  clearTimeout(box._off);
  clearTimeout(box._gone);
  clearTimeout(box._revealed);
  clearTimeout(box._cap);
  document.body.classList.remove('revealing');
  cancelAnimationFrame(box._typing);
  box.classList.remove('off');
  box.classList.add('on');
  introWord.resize();              // it had no size while it was not shown
  introWord.scramble(1.0, 0.5);
  sfx.play('boot');

  // The checks type themselves out as they land, each with a sound for how
  // it went, the log scrolling when the glass is full; then the prompt
  // under the name.
  const log = $('intro-log'), ready = $('intro-ready'), bar = $('intro-bar');
  $('intro-foot').textContent = `APOLLO/OS   ${stamp(new Date())}`;
  const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const began = performance.now();
  let sounded = 0;
  let readyAt = null;

  const finish = (summary) => {
    sfx.play(summary.fails ? 'alert' : 'ready');
    const line = readyLine(summary);
    const read = (line.length / READY_RATE) * 1000 + READY_HOLD;
    box._off = setTimeout(() => {
      box.classList.add('off');
      document.body.classList.add('revealing');
    }, read);
    box._gone = setTimeout(() => {
      box.classList.remove('on', 'off');
      introWord.stop();
      scheduleOsiris(200);           // a map kept back while the tube warmed up
    }, read + OFF_FOR);
    box._revealed = setTimeout(() => document.body.classList.remove('revealing'),
                               read + REVEAL_FOR);
  };

  const type = (now) => {
    const t = still ? 600 : (now - began) / 1000;
    const entries = HEADER.map((text) => ({ text, arrived: 0, sound: null }));
    boot.steps.forEach((step, i) => {
      const arrived = Math.max(0, (boot.arrivals[i] - began) / 1000);
      entries.push({ text: checkLine(step), arrived, sound: step.status === 'ok' ? 'check' : 'fault' });
      if (step.status !== 'ok' && step.detail) entries.push({ text: detailLine(step), arrived, sound: null });
    });
    const lines = schedule(entries, LINE_GAP);
    log.querySelector('.text').textContent = lastLines(typedAt(lines, t, LINE_RATE), LOG_ROWS);
    while (sounded < lines.length && lines[sounded].at <= t) {
      if (lines[sounded].sound && !still) sfx.play(lines[sounded].sound);
      sounded += 1;
    }
    const last = lines[lines.length - 1];
    const typedOut = t >= last.at + last.text.length / LINE_RATE;
    bar.style.transform = `scaleX(${boot.done ? 1 : Math.min(0.96, boot.steps.length / boot.total)})`;
    if (readyAt === null && boot.done && typedOut && t >= READY_AT) {
      readyAt = t;
      finish(boot.done);
    }
    ready.querySelector('.text').textContent =
      readyAt === null ? '' : typed([readyLine(boot.done)], t, { start: readyAt, rate: READY_RATE });
    ready.classList.toggle('shown', readyAt !== null);
    log.querySelector('.cursor').classList.toggle('gone', readyAt !== null);
    if (box.classList.contains('on')) box._typing = requestAnimationFrame(type);
  };
  box._typing = requestAnimationFrame(type);
  // A start that never says it is done does not keep the display from you.
  box._cap = setTimeout(() => { if (!boot.done) boot.done = bootSoFar(); }, INTRO_MOST);
}

/* --- the issues: what Apollo found wrong with itself ---------------------------
 *
 * Its checks at startup, and what went wrong while it ran (issues.py), on the
 * System panel until fixed or dismissed: a few in the status block, all of
 * them in ultra mode's System display. Check again runs every check now. */

function renderIssues(items) {
  if (Array.isArray(items)) state.issues = items;
  const all = state.issues || [];
  const most = ultraOn() ? 8 : 3;
  const fails = all.filter((issue) => issue.level === 'fail').length;
  const rows = all.slice(0, most).map((issue) => `
    <li class="issue ${issue.level === 'fail' ? 'fail' : 'warn'}">
      <i class="led"></i><b>${esc(issue.title)}</b><span>${esc(issue.detail)}</span>
      <button type="button" class="issue-x" data-dismiss="${esc(issue.key)}" data-sfx="none"
              title="Dismiss: fixed, or not worth fixing">✕</button>
    </li>`).join('');
  const head = all.length ? `${all.length} to fix` : 'All clear';
  $('issues').innerHTML = `
    <div class="issues-head"><b>${head}</b>
      <button type="button" id="recheck" data-sfx="none" ${state.rechecking ? 'disabled' : ''}
              title="Run Apollo's checks again">${state.rechecking ? 'Checking…' : 'Check again'}</button></div>
    ${all.length ? `<ul>${rows}</ul>` : ''}
    ${all.length > most ? `<p class="issues-more">${all.length - most} more in Expanded</p>` : ''}`;
  $('issues').classList.toggle('bad', fails > 0);
  $('issues').classList.toggle('clear', !all.length);
}

$('issues').addEventListener('click', (event) => {
  const dismiss = event.target.closest('[data-dismiss]');
  const api = bridge();
  if (dismiss) {
    sfx.play('hide');
    if (api && api.dismiss_issue) api.dismiss_issue(dismiss.dataset.dismiss);
    return;
  }
  if (event.target.closest('#recheck') && !state.rechecking) {
    sfx.play('scan');
    state.rechecking = true;
    renderIssues();
    if (api && api.run_checks) api.run_checks();
    // Done or not, the button comes back.
    setTimeout(() => { if (state.rechecking) { state.rechecking = false; renderIssues(); } }, 15000);
  }
});
renderIssues([]);

/* What she is doing, under her bar. Her name is over the bar already, so the
 * "LYLA // " lyla.js starts every line with is taken off on the way in. */
const lylaDoing = {
  said: '',
  job: '',
  get textContent() { return $('lyla-label').textContent; },
  set textContent(text) { this.said = String(text).replace(/^LYLA\s*\/\/\s*/, ''); this.show(); },
  /* On a job Apollo handed her, that is what she is doing, whatever her
   * room says. */
  show() {
    $('lyla-label').textContent = this.job || this.said;
    $('lyla-block').classList.toggle('on-job', Boolean(this.job));
  },
};

/* The display's sounds, made on the spot (sfx.js): a tick as the pointer
 * comes onto a button and a click as it is pressed - or the button's own
 * sound (data-sfx, or played where it does its work) - and a sound for each
 * change worth hearing: Apollo listening, your words heard, the answer
 * coming, the display up and away, asleep and awake. LYLA has her own two.
 * Always on. */
const sfx = new Sfx();
const PRESSABLE = 'button, .tab, .chip, [data-sfx]';
let hovered = null;
document.addEventListener('pointerover', (event) => {
  const target = event.target.closest(PRESSABLE);
  if (target === hovered) return;
  hovered = target;
  if (target && event.pointerType === 'mouse') sfx.play('tick');
});
document.addEventListener('click', (event) => {
  const target = event.target.closest(PRESSABLE);
  if (!target || target.dataset.sfx === 'none') return;
  sfx.play(target.dataset.sfx || 'press');
}, true);

const lyla = new Lyla($('lyla'), {
  label: lylaDoing, icon: $('lyla-icon'),
  bar: $('lyla-bar'), pct: $('lyla-pct'), ring: $('ring'),
  sound: (name) => sfx.play(name),
});
lyla.start();

/* LYLA as an agent, before she is one (lylaagent.js): her block - or AGENT
 * on it - opens the pipeline card over the feed, and shuts it; so does
 * Escape. Out of sight with her block, in ultra mode and under the map. */
const agent = new LylaAgent($('lyla-agent'), { sound: (name) => sfx.play(name) });
// ...and the same card in agents mode, which has its own sound for arriving.
const agentsCard = new LylaAgent($('agent-lyla'));

/* Agents mode: each agent by its mark down the left - LYLA, THEIA,
 * MONEYPENNY and Q, Apollo's crew (crew.py) - and a click on one opens its
 * process (its pipeline card) beside the marks; a click on it again puts it
 * away. LYLA's reports go with hers. */
const AGENTS = ['LYLA', 'THEIA', 'MONEYPENNY', 'Q'];
const crewDoing = {};          // agent -> what it is on, while it is
const agentCards = {
  LYLA: agentsCard,
  ...Object.fromEntries(AGENTS.slice(1).map((key) =>
    [key, new LylaAgent($(`agent-${key.toLowerCase()}`), { look: LOOKS[key] })])),
};
function agentState(key) {
  if (key !== 'LYLA') {
    if (crewDoing[key]) return ['ON A JOB', 'working'];
    return agentCards[key].isLive ? ['LIVE', 'live'] : ['READY', 'ready'];
  }
  if (lylaDoing.job) return ['ON A JOB', 'working'];
  return agentsCard.isLive ? ['LIVE', 'live'] : ['READY', 'ready'];
}
function renderMarks() {
  $('agent-marks').innerHTML = AGENTS.map((key) => {
    const look = LOOKS[key];
    const [said, kind] = agentState(key);
    const picked = state.agentOpen === key;
    return `<button type="button" class="agent-mark${picked ? ' chosen' : ''}" data-agent="${key}"
        data-sfx="none" aria-pressed="${picked ? 'true' : 'false'}" style="--agent-rgb:${look.rgb};--agent-mark:${look.mark || look.hex}">
      <span class="mark-emblem">${emblem(key, 40)}</span>
      <span class="mark-name"><b>${key}</b><small>${look.role}</small></span>
      <em class="mark-state ${kind}">${said}</em>
    </button>`;
  }).join('');
}
function openAgent(key) {
  const was = state.agentOpen;
  state.agentOpen = was === key ? null : key;
  for (const name of AGENTS) {
    if (name !== state.agentOpen) agentCards[name].hide();
  }
  if (state.agentOpen) agentCards[state.agentOpen].show();
  sfx.play(state.agentOpen ? 'hud' : 'down');
  showAgentStage();
}
function showAgentStage() {
  const open = state.agentOpen;
  $('agent-pick').hidden = Boolean(open);
  $('lyla-reports').hidden = open !== 'LYLA';
  renderMarks();
}
$('agent-marks').addEventListener('click', (event) => {
  const mark = event.target.closest('[data-agent]');
  if (mark) openAgent(mark.dataset.agent);
});
function toggleAgent() {
  agent.toggle();
  $('lyla-agent-toggle').setAttribute('aria-expanded', agent.open ? 'true' : 'false');
}
$('lyla-block').addEventListener('click', toggleAgent);

// Click the display and LYLA comes after the pointer for a while (lyla.js).
document.addEventListener('pointerdown', (event) => { if (!state.hudEdit) lyla.follow(event.clientX, event.clientY); });
document.addEventListener('pointermove', (event) => lyla.pointer(event.clientX, event.clientY));

/* Apollo's shape: a globe, the way a wireframe icon draws one, with a star
 * of light at its heart (globe.js has the lines). In warm white, over a
 * warm glow: a wide outline, meridians pole to pole that widen and narrow
 * as the globe turns about its upright axis - their near halves bright,
 * their far halves faint behind - parallels straight across, and in the
 * middle a four-pointed star breathing with your voice. While Apollo is
 * busy the globe brightens and turns faster and a wave goes out from the
 * star over and over; while it is listening the lines take a gradient,
 * cyan in the middle to amber and orange at the edge; and while it speaks
 * the star grows and a white bloom lifts off it. */
const ring = $('ring').getContext('2d');
const LINE = [255, 244, 222];
const LISTEN = [[90, 215, 255], [127, 227, 255], [255, 227, 168], [255, 122, 46]];
const core = { env: 0, talk: 0, listen: 0, spin: 1, turn: 0 };
let lastFrame = performance.now();
let ringFrame = null;

function drawRing(now) {
  const dt = Math.min(0.05, (now - lastFrame) / 1000);
  lastFrame = now;
  const phase = state.phase;
  // Eased, not followed: the raw level jumps every packet, and a globe that
  // jumps with it reads as a fault rather than as breathing.
  state.levelSmooth += (state.level - state.levelSmooth)
                     * (1 - Math.exp(-dt / (state.level > state.levelSmooth ? 0.05 : 0.28)));
  core.env = Globe.ease(core.env, phase === 'idle' ? 0 : 1, dt, 0.35);
  core.talk = Globe.ease(core.talk, phase === 'speaking' ? 1 : 0, dt, 0.2);
  core.listen = Globe.ease(core.listen, phase === 'listening' ? 1 : 0, dt, 0.3);
  core.spin = Globe.ease(core.spin, phase === 'thinking' ? 3.2 : 1 + 1.2 * core.env + 3.4 * core.talk, dt, 0.4);
  // Turned by its pace, accumulated rather than multiplied, so a change of
  // pace never makes it jump.
  core.turn += dt * 0.22 * core.spin;
  const env = core.env, w = core.talk, t = now;

  // Drawn at the canvas's own size on the screen, in the screen's pixels, so
  // a line of one is a line of one; `px` is one CSS pixel.
  const canvas = $('ring');
  const px = Math.min(2, window.devicePixelRatio || 1);
  const wide = Math.max(1, Math.round(canvas.clientWidth * px));
  const tall = Math.max(1, Math.round(canvas.clientHeight * px));
  if (canvas.width !== wide || canvas.height !== tall) { canvas.width = wide; canvas.height = tall; }
  const cx = wide / 2, cy = tall / 2;
  // The globe's half-width and half-height: most of the canvas, breathing a
  // little with your voice.
  const A = Math.min(wide * 0.45, (tall * 0.4) / Globe.ASPECT) * (1 + 0.04 * state.levelSmooth);
  const B = A * Globe.ASPECT;
  // Towards white while it speaks.
  const rgb = LINE.map((v) => Math.round(v + (255 - v) * w)).join(',');
  ring.clearRect(0, 0, wide, tall);
  ring.globalCompositeOperation = 'lighter';

  // The white bloom while Apollo speaks - kept inside the canvas.
  if (w > 0.004) {
    const reach = Math.min(A * 0.9, tall / 2);
    const flick = 0.82 + 0.18 * Math.sin(t * 0.026);
    const bloom = ring.createRadialGradient(cx, cy, A * 0.05, cx, cy, reach);
    bloom.addColorStop(0, `rgba(255,255,255,${(0.3 * w * flick).toFixed(3)})`);
    bloom.addColorStop(0.42, `rgba(255,248,232,${(0.13 * w * flick).toFixed(3)})`);
    bloom.addColorStop(1, 'rgba(255,255,255,0)');
    ring.fillStyle = bloom;
    ring.beginPath();
    ring.arc(cx, cy, reach, 0, Math.PI * 2);
    ring.fill();
  }

  // The lines. Listening, they take the gradient, cross-faded in so they
  // never drop out.
  const pulse = 0.82 + 0.18 * Math.sin(t * 0.0016) + 0.12 * env * Math.sin(t * 0.0052)
              + 0.25 * w + 0.2 * state.levelSmooth;
  let tint = null;
  if (core.listen > 0.02) {
    tint = ring.createRadialGradient(cx, cy, A * 0.05, cx, cy, A);
    LISTEN.forEach((c, i) => tint.addColorStop([0, 0.38, 0.62, 1][i], `rgb(${c.join(',')})`));
  }
  const mix = Math.min(1, core.listen * 1.4);
  const stroke = (alpha, draw) => {
    for (const [style, share] of [[`rgb(${rgb})`, tint ? 1 - mix : 1], [tint, tint ? mix : 0]]) {
      const a = alpha * share;
      if (a <= 0.004) continue;
      ring.globalAlpha = Math.min(1, a);
      ring.strokeStyle = style;
      draw();
    }
    ring.globalAlpha = 1;
  };
  const lineA = (0.66 + 0.25 * env + 0.2 * w) * pulse;
  const thick = (1.1 + 0.9 * env + 0.8 * w) * px;
  ring.lineCap = 'round';
  ring.shadowBlur = (6 + 10 * env + 18 * w) * px;
  ring.shadowColor = `rgba(${rgb},0.55)`;

  // The meridians, far halves first and faint, near ones bright over them.
  const halves = Globe.meridians(core.turn).sort((p, q) => p.near - q.near);
  const depthOf = (near) => 0.3 + 0.35 * (near + 1);           // 0.3 far .. 1 near
  const drawHalf = (h) => {
    ring.lineWidth = thick * (0.8 + 0.2 * depthOf(h.near));
    stroke(lineA * depthOf(h.near), () => {
      ring.beginPath();
      ring.ellipse(cx, cy, Math.max(0.01, Math.abs(h.w) * A), B, 0, -Math.PI / 2, Math.PI / 2, h.w < 0);
      ring.stroke();
    });
  };
  halves.filter((h) => h.near < 0).forEach(drawHalf);
  // Straight across: each parallel a circle seen edge on, near and far at once.
  ring.lineWidth = thick * 0.9;
  for (const across of Globe.parallels()) {
    stroke(lineA * 0.8, () => {
      ring.beginPath();
      ring.moveTo(cx - across.half * A, cy + across.y * A);
      ring.lineTo(cx + across.half * A, cy + across.y * A);
      ring.stroke();
    });
  }
  halves.filter((h) => h.near >= 0).forEach(drawHalf);
  // The outline over it all.
  ring.lineWidth = thick * 1.15;
  stroke(lineA, () => {
    ring.beginPath();
    ring.ellipse(cx, cy, A, B, 0, 0, Math.PI * 2);
    ring.stroke();
  });

  // The star at its heart: a halo, then four thin points of white, growing
  // with your voice and while Apollo speaks, twinkling as it turns.
  const sr = A * (0.2 + 0.06 * state.levelSmooth + 0.03 * env + 0.08 * w)
           * (1 + 0.06 * Math.sin(t * 0.0021 * core.spin));
  const halo = ring.createRadialGradient(cx, cy, 0, cx, cy, sr * 2.2);
  halo.addColorStop(0, `rgba(255,255,255,${(0.45 + 0.3 * w).toFixed(3)})`);
  halo.addColorStop(0.3, `rgba(255,240,210,${(0.18 + 0.12 * env).toFixed(3)})`);
  halo.addColorStop(1, 'rgba(255,200,120,0)');
  ring.shadowBlur = 0;
  ring.fillStyle = halo;
  ring.beginPath();
  ring.arc(cx, cy, sr * 2.2, 0, Math.PI * 2);
  ring.fill();
  const arms = Globe.star(sr);
  ring.shadowBlur = (16 + 20 * env + 30 * w) * px;
  ring.shadowColor = 'rgba(255,248,230,0.9)';
  ring.fillStyle = '#ffffff';
  ring.beginPath();
  ring.moveTo(cx + arms[0].tip[0], cy + arms[0].tip[1]);
  arms.forEach((arm, i) => {
    const next = arms[(i + 1) % arms.length].tip;
    ring.quadraticCurveTo(cx + arm.pinch[0], cy + arm.pinch[1], cx + next[0], cy + next[1]);
  });
  ring.fill();
  ring.shadowBlur = 0;

  // While Apollo works, a wave going out from the star, over and over, the
  // globe's own shape.
  if (env > 0.004) {
    const period = env > 0.5 ? 1100 : 3400;
    const wave = (t % period) / period;
    const rx = A * (0.2 + wave * 0.95);
    ring.lineWidth = 1.4 * px;
    ring.strokeStyle = `rgba(255,176,0,${(0.3 * env * (1 - wave) ** 2).toFixed(3)})`;
    ring.shadowBlur = 18 * px;
    ring.shadowColor = `rgba(${rgb},0.7)`;
    ring.beginPath();
    ring.ellipse(cx, cy, rx, Math.min(rx * Globe.ASPECT, tall / 2 - 2 * px), 0, 0, Math.PI * 2);
    ring.stroke();
    ring.shadowBlur = 0;
  }
  ring.globalCompositeOperation = 'source-over';
  ringFrame = requestAnimationFrame(drawRing);
}

/* The ring stops with the shader and with LYLA. Apollo's window is hidden by
 * Win32, not by the browser, so nothing throttles it on our behalf: left
 * running it would keep compositing a blurred canvas behind a window nobody
 * can see, for as long as Apollo is up. */
function ringStart() {
  if (ringFrame === null) {
    lastFrame = performance.now();
    ringFrame = requestAnimationFrame(drawRing);
  }
}

function ringStop() {
  if (ringFrame !== null) cancelAnimationFrame(ringFrame);
  ringFrame = null;
}

ringStart();

/* --- the clock ------------------------------------------------------------ */

function tickClock() {
  tickSleep();
  const now = new Date();
  // Read from the clock rather than counting frames, so it can neither drift
  // nor stall while the display is open.
  $('hhmm').textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  $('seconds').textContent = ':' + String(now.getSeconds()).padStart(2, '0');
  $('date').textContent = now.toLocaleDateString('en-GB',
    { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  // The map's time, beside the map.
  if (state.osiris) {
    $('world-utc').textContent = `${String(now.getUTCHours()).padStart(2, '0')}:`
      + `${String(now.getUTCMinutes()).padStart(2, '0')} UTC`;
  }
}
setInterval(tickClock, 250);
tickClock();

/* --- rendering the world -------------------------------------------------- */

function money(value) {
  return value >= 1000 ? value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                       : value.toFixed(2);
}

function moveClass(pct) { return pct >= 0 ? 'up' : 'down'; }
function moveText(pct) { return `${pct >= 0 ? '▲' : '▼'}${Math.abs(pct).toFixed(2)}%`; }

function words(seconds) {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

/* A panel whose reader last succeeded longer ago than its interval allows
 * carries its age in the heading. Everything else says nothing, because a
 * timestamp on fresh data is noise. */
function stale(key) {
  const stamps = (state.snapshot && state.snapshot.stamps) || {};
  if (!stamps[key]) return '';
  const age = Date.now() / 1000 - stamps[key];
  return age > (STALE_AFTER[key] || Infinity) ? ` <b class="age">${words(age)} old</b>` : '';
}

/* Numbers arrive at their value instead of appearing at it, once, on the
 * first paint. Later snapshots just set the text - a price counting up from
 * zero every minute would be theatre, not information. */
function countUp(el, value, format) {
  const from = 0;
  const started = performance.now();
  const step = (now) => {
    const at = Math.min(1, (now - started) / 600);
    const eased = 1 - Math.pow(1 - at, 3);
    el.textContent = format(from + (value - from) * eased);
    if (at < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

/* A Catmull-Rom spline through the closes, written out as cubic Béziers.
 * Straight segments between daily closes read as a saw; the design's line is
 * one smooth curve. */
function smooth(points) {
  let d = `M${points[0][0].toFixed(1)},${points[0][1].toFixed(1)}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i - 1] || points[i], p1 = points[i];
    const p2 = points[i + 1], p3 = points[i + 2] || p2;
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
    const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    d += `C${c1[0].toFixed(1)},${c1[1].toFixed(1)} ${c2[0].toFixed(1)},${c2[1].toFixed(1)} `
       + `${p2[0].toFixed(1)},${p2[1].toFixed(1)}`;
  }
  return d;
}

const SPARK_W = 300, SPARK_H = 62, SPARK_PAD = 7;

function sparkline(points, rising) {
  if (!points || points.length < 2) return '<div class="chart empty"></div>';
  const low = Math.min(...points), high = Math.max(...points);
  const span = high - low || 1;
  const laid = points.map((value, i) => [
    (i / (points.length - 1)) * SPARK_W,
    SPARK_PAD + (1 - (value - low) / span) * (SPARK_H - SPARK_PAD * 2),
  ]);
  const up = rising === undefined ? points[points.length - 1] >= points[0] : rising;
  const line = smooth(laid);
  // pathLength="1" normalises the dash units, so one CSS rule draws every
  // curve on first paint whatever shape it happens to be.
  return `<svg class="chart" viewBox="0 0 ${SPARK_W} ${SPARK_H}" preserveAspectRatio="none">
    <path class="wash" d="${line}L${SPARK_W},${SPARK_H}L0,${SPARK_H}Z"
          fill="url(#${up ? 'washUp' : 'washDown'})"/>
    <path class="line" d="${line}" fill="none" pathLength="1"
          stroke="${up ? 'var(--up)' : 'var(--down)'}" stroke-width="2.2"
          stroke-linejoin="round" stroke-linecap="round"/>
  </svg>`;
}

/* How many days until a stock next reports, or null when nobody knows yet.
 * Counted between noons, so a report tomorrow is 1 whatever the hour. */
function earningsIn(quote) {
  if (!quote || !/^\d{4}-\d{2}-\d{2}$/.test(String(quote.earnings || ''))) return null;
  const day = new Date(`${quote.earnings}T12:00:00`);
  const today = new Date();
  today.setHours(12, 0, 0, 0);
  return Math.round((day - today) / 86400000);
}

const earningsWords = (days) =>
  (days === 0 ? 'today' : days === 1 ? 'tomorrow' : `in ${days} days`);

/* One stock, as a row of the list: its mark and ticker, its name, the day's
 * curve drawn small, what it costs and what it did - the interactive-list
 * component's row, the way the feed has it. Its chart opens beside the panel
 * while the pointer is on it (quoteShot), and a click opens the stock. */
const MINI_W = 84, MINI_H = 22;

function mini(points, rising) {
  if (!points || points.length < 2) return '<i class="mini empty"></i>';
  const low = Math.min(...points), high = Math.max(...points);
  const span = high - low || 1;
  const laid = points.map((value, i) => [
    (i / (points.length - 1)) * MINI_W,
    2 + (1 - (value - low) / span) * (MINI_H - 4),
  ]);
  return `<svg class="mini" viewBox="0 0 ${MINI_W} ${MINI_H}" width="${MINI_W}" height="${MINI_H}">
    <path class="line" d="${smooth(laid)}" fill="none" pathLength="1"
          stroke="${rising ? 'var(--up)' : 'var(--down)'}" stroke-width="1.6"
          stroke-linejoin="round" stroke-linecap="round"/>
  </svg>`;
}

/* The words a stock has earned this week: earnings within seven days, and
 * someone who runs the company buying in the last month - rare, and worth it. */
function stockNotes(quote) {
  const notes = [];
  const days = earningsIn(quote);
  if (days !== null && days >= 0 && days <= 7) notes.push(`<b class="soon">Earnings ${earningsWords(days)}</b>`);
  const inside = ((state.snapshot || {}).insiders || {})[quote.symbol];
  if (inside && inside.recent_buy) notes.push('<b class="buying">Insider buying</b>');
  return notes;
}

function markOf(quote) {
  return quote.logo
    ? `<img class="mark" src="${esc(quote.logo)}" alt="">`
    : `<span class="mark none">${esc((quote.symbol || '?')[0])}</span>`;
}

/* Where the price sits in the day's range, as a lit point on a short line -
 * low on the left, high on the right - or an empty line when the day has
 * no range yet. */
function rangeMark(quote) {
  const low = Number(quote.low), high = Number(quote.high), price = Number(quote.price);
  if (!Number.isFinite(low) || !Number.isFinite(high) || !(high > low)) return '<i class="range empty"></i>';
  const at = Math.max(0, Math.min(1, (price - low) / (high - low)));
  return `<i class="range"><s style="left:${(at * 100).toFixed(1)}%"></s></i>`;
}

/* What it earns and what the analysts think it is worth: a line each. */
function stockFacts(quote) {
  const pe = Number(quote.pe) > 0 ? Number(quote.pe).toFixed(1) : '—';
  const upside = Number(quote.upside);
  const target = quote.target && Number.isFinite(upside)
    ? `<em class="${moveClass(upside)}">${upside >= 0 ? '+' : ''}${upside.toFixed(1)}%</em>` : '—';
  return `<small><i>P/E</i> ${pe}</small><small><i>TGT</i> ${target}</small>`;
}

const flagOf = (quote) => (stockNotes(quote).length ? '<i class="flag"></i>' : '');

/* A row in full: the mark, the ticker with the name under it, the day's
 * curve with where the price sits in the day's range under it, what it
 * earns and what it is thought worth, and the price with the day's move. */
function stockRow(quote) {
  return `
    <div class="stock-row" data-symbol="${esc(quote.symbol)}">
      <span class="sym">${markOf(quote)}<span class="id"><b>${esc(quote.symbol)}</b>${flagOf(quote)}<small class="name">${esc(quote.name || '')}</small></span></span>
      <span class="day">${mini(quote.spark, quote.change_pct >= 0)}${rangeMark(quote)}</span>
      <span class="facts">${stockFacts(quote)}</span>
      <span class="now"><span class="price">${money(quote.price)}</span><span class="move ${moveClass(quote.change_pct)}">${moveText(quote.change_pct)}</span></span>
    </div>`;
}

/* ...and folded: the ticker, the curve and the move - nothing more. */
function compactRow(quote) {
  return `
    <div class="stock-row compact" data-symbol="${esc(quote.symbol)}">
      <span class="sym">${markOf(quote)}<b>${esc(quote.symbol)}</b>${flagOf(quote)}</span>
      ${mini(quote.spark, quote.change_pct >= 0)}
      <span class="move ${moveClass(quote.change_pct)}">${moveText(quote.change_pct)}</span>
    </div>`;
}

/* The row under a folded list: how many are folded away, and the way back. */
const moreRow = (hidden) => `
    <button class="stock-row rest" type="button">
      <span class="sym"><span class="mark none">+${Number(hidden) || 0}</span><b>Show all</b></span>
    </button>`;

/* The picture a row opens beside the panel - the component's image, as the
 * stock's own card: the price large, the day's curve, and what the analysts
 * make of it. The same card the overlay draws, so the two halves of Apollo
 * say the same thing the same way. */
function quoteShot(quote) {
  const upside = quote.target && quote.upside != null
    ? ` <i class="${moveClass(quote.upside)}">${quote.upside >= 0 ? '+' : ''}${quote.upside.toFixed(1)}%</i>` : '';
  const facts = [
    `Target <b>${quote.target ? money(quote.target) : '—'}</b>${upside}`,
    `P/E <b>${quote.pe ? quote.pe.toFixed(1) : '—'}</b>`,
    ...stockNotes(quote),
  ];
  return `
    <div class="quote-shot">
      <div class="qs-head">${markOf(quote)}
        <div class="who"><b>${esc(quote.symbol)}</b><span>${esc(quote.name || '')}</span></div>
        <div class="now"><span class="price">${money(quote.price)}</span>
          <span class="move ${moveClass(quote.change_pct)}">${moveText(quote.change_pct)} today</span></div>
      </div>
      ${sparkline(quote.spark, quote.change_pct >= 0)}
      <div class="qs-foot">${facts.join('<i class="dot">·</i>')}</div>
    </div>`;
}

function renderMarkets(market) {
  $('market-clock').textContent = market.status || '';
  $('markets-head').innerHTML = 'Markets' + stale('market');
  $('indices').innerHTML = (market.indices || []).map((quote) => `
    <div class="index">
      <div class="name">${esc(quote.name || quote.symbol)}</div>
      <div class="value"><span class="figure">${money(quote.price)}</span><span class="move ${moveClass(quote.change_pct)}">${moveText(quote.change_pct)}</span></div>
    </div>`).join('');

  if (!state.entered) {
    const figures = $('indices').querySelectorAll('.figure');
    (market.indices || []).forEach((quote, i) => {
      if (figures[i]) countUp(figures[i], quote.price, money);
    });
  }

  const list = $('watchlist');
  list.classList.toggle('drawing', !state.entered);
  // Which stocks were here a moment ago, so a card that has just been asked
  // for can arrive rather than appear, and one that has been dropped can
  // leave rather than vanish. Folded, only the first few are here at all.
  const watched = market.watchlist || [];
  const folded = Boolean(state.layout.folded);
  const shown = Tiles.foldedStocks(watched, folded);
  for (const [symbol, asked] of [...state.pending]) {
    if (watched.some((quote) => quote.symbol === symbol) || Date.now() - asked.since > PENDING_FOR) {
      state.pending.delete(symbol);
    }
  }
  const before = [...list.children].map((row) => row.dataset.symbol).filter(Boolean);
  const after = shown.map((quote) => quote.symbol).concat(folded ? [] : [...state.pending.keys()]);
  const leaving = before.filter((symbol) => !after.includes(symbol));

  if (state.entered && leaving.length) {
    // Let them go first, then draw the rest - otherwise the row under a
    // removed one jumps up while it is still fading.
    for (const symbol of leaving) {
      const row = [...list.children].find((r) => r.dataset.symbol === symbol);
      if (row) animate(row, { opacity: [1, 0], transform: ['translateX(0px)', 'translateX(-14px)'] },
                       { duration: 0.26, ease: 'easeOut' });
    }
    clearTimeout(state.cardsTimer);
    state.cardsTimer = setTimeout(() => {
      for (const row of [...list.children]) {
        if (leaving.includes(row.dataset.symbol)) row.remove();
      }
      renderMarkets(market);
    }, 280);
    return;
  }

  // A snapshot comes every few seconds for the machine's numbers; the rows
  // are rebuilt only when something on them changed, or the bar under the
  // pointer would drop off its row every five seconds.
  const key = JSON.stringify([after, shown.map((quote) =>
    [quote.price, quote.change_pct, quote.target, quote.pe, quote.logo, quote.spark, quote.name,
     quote.high, quote.low]), state.entered, folded, watched.length]);
  if (key === state.marketKey) return;
  state.marketKey = key;
  const lit = state.rowLit ? (state.rowLit.dataset.symbol || 'add') : null;
  unlightRow();
  list.innerHTML = folded
    ? shown.map((quote) => compactRow(quote)).join('')
      + (watched.length > shown.length ? moreRow(watched.length - shown.length) : '')
    : shown.map((quote) => stockRow(quote)).join('')
      + [...state.pending].map(([symbol, asked]) => pendingRow(symbol, asked.name)).join('')
      + (watched.length + state.pending.size < WATCH_MAX ? ADD_ROW : '');
  // Each stock's chart, stacked beside the panel in the same order as the rows.
  $('chart-peek').innerHTML = shown.map((quote) => `<div class="shot">${quoteShot(quote)}</div>`).join('');
  if (lit) lightRow(lit === 'add' ? list.querySelector('.add') : rowFor(lit));

  if (state.entered) {
    const arriving = after.filter((symbol) => !before.includes(symbol));
    for (const symbol of arriving) {
      const row = [...list.children].find((r) => r.dataset.symbol === symbol);
      if (row) animate(row, {
        opacity: [0, 1], transform: ['translateX(-14px)', 'translateX(0px)'],
      }, { ...SPRING, delay: 0.04 });
    }
  }

  // A price that moved since the last snapshot flashes its row; one that did
  // not stays still, or the whole column would blink every minute. Rows are
  // found by position rather than by a selector built from a ticker, which
  // would be one more piece of feed data steering the page.
  shown.forEach((quote, i) => {
    const previous = state.prices.get(quote.symbol);
    const row = list.children[i];
    if (previous !== undefined && previous !== quote.price && row) {
      row.classList.add(quote.price > previous ? 'flash-up' : 'flash-down');
      setTimeout(() => row.classList.remove('flash-up', 'flash-down'), 700);
    }
    state.prices.set(quote.symbol, quote.price);
  });
}

/* One feed, newest first. Trump's posts used to have a panel to themselves,
 * which gave one man his own column on your screen regardless of whether he
 * had said anything worth it. They are one source among several now, marked
 * as such, and they sort by when they happened like everything else. */
function feedItems(snapshot) {
  const chosen = TOPICS[state.topic];
  const items = [];
  for (const [topic, stories] of Object.entries(snapshot.news || {})) {
    if (chosen !== 'all' && chosen !== topic) continue;
    for (const story of stories || []) {
      items.push({ title: story.title, source: story.source, age: story.age,
                   summary: story.summary || '', image: story.image || '',
                   link: story.link || '', when: story.when || 0, topic });
    }
  }
  // Posts belong to the markets tab as well as to "all": a market-moving post
  // is a market story whoever wrote it.
  if (chosen === 'all' || chosen === 'markets') {
    for (const post of snapshot.posts || []) {
      items.push({ title: post.text, source: 'Truth Social', age: post.age,
                   summary: post.text, image: '', link: post.link || '',
                   when: post.when || 0, topic: 'posts', moving: post.market });
    }
  }
  // What Private Eye found (private_eye.py): in "all" among the rest, marked,
  // and alone under its own chip.
  if (chosen === 'all' || chosen === 'private eye') {
    for (const find of snapshot.finds || []) {
      items.push({ title: find.title, source: find.source, age: find.age,
                   summary: find.summary || '', image: find.image || '',
                   link: find.link || '', when: find.when || 0, topic: 'private eye',
                   eye: true, id: String(find.id || ''), interest: find.interest || '' });
    }
  }
  items.sort((a, b) => (b.when || 0) - (a.when || 0));
  return items;
}

/* Only pictures served over https, and only as pictures: the address comes
 * from a feed. It arrives already sized (feeds.parse_bing): asked for bigger
 * than its original, Bing pads a picture out with white. */
const safeImage = (url) => (/^https:\/\//.test(String(url || '')) ? String(url) : '');
const numbered = (index) => String(index + 1).padStart(2, '0');

/* Each topic's class - its colour, down the row's edge, on its tag and its
 * chip (app.css) - and its mark, drawn on a story's tile where it came
 * without a picture: a pad, a star, a strip of film, a rising line, a
 * speaker, an eye. */
const topicClass = (kind) => `t-${esc(String(kind || 'news').toLowerCase().replace(/[^a-z0-9]+/g, '-'))}`;
const GLYPHS = {
  gaming: '<path d="M7 9h10a4 4 0 0 1 3.9 4.8l-.7 3.2a2 2 0 0 1-3.4.9L14.5 16h-5l-2.3 1.9a2 2 0 0 1-3.4-.9l-.7-3.2A4 4 0 0 1 7 9z"/><path d="M8 12v2M7 13h2M15.5 12.5h.01M17 14h.01"/>',
  marvel: '<path d="M12 3l2.6 5.6 6.1.7-4.5 4.2 1.2 6L12 16.6 6.6 19.5l1.2-6-4.5-4.2 6.1-.7z"/>',
  movies: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 5v14M17 5v14M3 9h4M3 15h4M17 9h4M17 15h4"/>',
  markets: '<path d="M3 17l5-5 4 3 7-8"/><path d="M15 7h4v4"/>',
  posts: '<path d="M4 10v4h3l6 4V6L7 10z"/><path d="M16.5 9a4 4 0 0 1 0 6"/>',
  'private eye': '<path d="M2 12s3.6-6 10-6 10 6 10 6-3.6 6-10 6S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
};
const glyph = (kind) => `<svg class="glyph" viewBox="0 0 24 24" aria-hidden="true">${GLYPHS[kind] || GLYPHS.markets}</svg>`;

function renderChips() {
  $('topics').innerHTML = TOPICS.map((name, i) =>
    `<span class="chip ${topicClass(name)} ${i === state.topic ? 'on' : ''}" data-topic="${i}" data-sfx="tab">${esc(name)}</span>`).join('');
}

function renderFeed(snapshot) {
  const items = feedItems(snapshot).slice(0, 11);
  // Over the list: how much is in it, from how many places, how new.
  const line = Feed.summaryLine(items);
  $('headlines-head').innerHTML = 'Feed' + stale('news')
    + (line ? `<span class="feed-sum">${esc(line)}</span>` : '');
  renderChips();
  // Folded, only the newest few are drawn; they keep their numbers, and the
  // rest are still there to be asked for by number.
  const folded = Boolean(state.layout.feedFolded);
  const drawn = Tiles.foldedStories(items, folded);
  // A snapshot arrives every few seconds for the machine's numbers. The feed
  // is rebuilt only when the feed changed, or the row under the pointer would
  // lose its bar every five seconds.
  const key = state.topic + '#' + folded + '#' + items.map((item) => [item.title, item.age].join('|')).join('\n');
  if (key === state.feedKey) return;
  state.feedKey = key;
  state.feed = items;
  unlight();
  // What a story says, where it says more than its title - a post's text is
  // its title already.
  const gistOf = (item) => (item.summary && item.summary !== item.title ? String(item.summary) : '');
  // Beside each, its picture - or its topic's mark on a tile in its colour,
  // which is also what shows if the picture will not load.
  const thumb = (item) => `<span class="thumb ${topicClass(item.topic)}">${glyph(item.topic)}${safeImage(item.image)
      ? `<img src="${esc(safeImage(item.image))}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.remove()">`
      : ''}</span>`;
  const chosen = TOPICS[state.topic];
  // The newest story leads, large, with its picture across the panel; the
  // rest are a line each, like the stocks. Folded, every one is a line.
  const lead = !folded && drawn.length > 1;
  // What came in since the feed was last drawn slides in; anything under
  // half an hour old says NEW.
  const seen = state.feedSeen || new Set();
  const first = seen.size === 0;
  const now = Date.now() / 1000;
  $('stories').innerHTML = drawn.map((item, i) => {
    const tag = Feed.topicTag(item.topic, chosen);
    const arriving = !first && !seen.has(item.title);
    const young = item.when && now - item.when < 1800;
    const hero = lead && i === 0;
    return `
    <div class="story ${topicClass(item.topic)}${hero ? ' hero' : ''}${item.moving ? ' moving' : ''}${arriving ? ' arriving' : ''}" data-i="${i}">
      <span class="num">${numbered(i)}</span>
      <span class="what">${esc(String(item.title).slice(0, 150))}</span>
      ${hero && gistOf(item) ? `<span class="gist">${esc(gistOf(item).slice(0, 260))}</span>` : ''}
      <span class="who"><b>${esc(item.source)}</b> · ${esc(item.age)}${tag ? ` · <em>${esc(tag)}</em>` : ''}${
        young ? ' · <i class="new">new</i>' : ''}${
        item.moving ? ' · <i class="moving">market-moving</i>' : ''}${
        item.eye ? ' · <i class="eye">Private Eye</i>' : ''}</span>
      ${thumb(item)}
    </div>`;
  }).join('')
    || '<div class="story empty"><span class="num">—</span><span class="what">Nothing has come in yet</span>'
     + '<span class="who">the feeds are quiet</span></div>';
  state.feedSeen = new Set(items.map((item) => item.title));
  if (items.length > drawn.length) {
    $('stories').insertAdjacentHTML('beforeend',
      `<div class="story rest"><b><i>+${items.length - drawn.length}</i>Show all</b></div>`);
  }
  markReading();
  $('peek').innerHTML = drawn.map((item) => `<div class="shot">${shot(item)}</div>`).join('');
}

/* The reading head: every few seconds the next story is the one Apollo is
 * on - brighter, with a line in its colour running along under it for as
 * long as it stays - down the list and round again. It waits while the
 * pointer is over the feed, and there is nothing to do while the display
 * is away or asleep. */
const READ_EVERY = 7000;
state.reading = 0;
function markReading() {
  const rows = [...document.querySelectorAll('#stories .story[data-i]')];
  if (!rows.length) return;
  state.reading %= rows.length;
  rows.forEach((row, i) => row.classList.toggle('reading', i === state.reading));
}
setInterval(() => {
  const body = document.body.classList;
  if (body.contains('offscreen') || body.contains('asleep') || $('feed').matches(':hover')) return;
  state.reading += 1;
  markReading();
}, READ_EVERY);

/* A story's picture, or its source set large where it has none. */
function shot(item) {
  if (safeImage(item.image)) {
    return `<img src="${esc(safeImage(item.image))}" alt="">`;
  }
  return `<div class="tile"><b>${esc(item.source || 'Apollo')}</b><span>${esc(item.topic)}</span></div>`;
}

/* --- the list, after the interactive-list component ---------------------------
 *
 * The component's three moving parts, without GSAP or React: the bar that
 * slides to the row under the pointer (a CSS transition on its transform and
 * height), the row's text going dark as the bar arrives (a class, with its
 * own transition), and the picture that opens out of its centre beside the
 * list and follows the pointer a little behind it (a lerp, on frames only
 * while there is something to follow). */

const PEEK_LERP = 0.18;          // the component's `lerp`
const PEEK_WANDER = 20;          // ...and its IMAGE_OFFSET_MULTIPLIER

/* The picture beside a list: every row's picture stacked in `el`, and the one
 * under the pointer opening out of its own centre on top of the last,
 * following the pointer a little behind it - on the side of `panel` that has
 * the room, level with the pointer, drifting with it by up to PEEK_WANDER. */
function makePeek(el, panel, side) {
  const at = { x: 0, y: 0, tx: 0, ty: 0, frame: null, placed: false, lit: -1, top: 10 };
  const target = () => {
    const box = panel.getBoundingClientRect();
    const width = el.offsetWidth, height = el.offsetHeight;
    const across = (at.tx - box.left) / Math.max(1, box.width) - 0.5;
    // The side it was given, unless there is no room there - in ultra mode a
    // panel can be anywhere on the screen - and inside the panel's own edge
    // when there is room on neither side.
    const left = box.left - width - 30, right = box.right + 30;
    const fitsLeft = left >= 12, fitsRight = right + width <= window.innerWidth - 12;
    let x = box.right - width - 24;
    if (fitsLeft || fitsRight) {
      const onLeft = side === 'left' ? fitsLeft : !fitsRight;
      x = (onLeft ? left : right) + across * PEEK_WANDER * 2;
    }
    const y = Math.max(24, Math.min(window.innerHeight - height - 24, at.ty - height / 2));
    return [x, y];
  };
  const follow = () => {
    if (at.frame !== null) return;
    const step = () => {
      const [x, y] = target();
      if (!at.placed) { at.x = x; at.y = y; at.placed = true; }
      at.x += (x - at.x) * PEEK_LERP;
      at.y += (y - at.y) * PEEK_LERP;
      el.style.transform = `translate3d(${at.x.toFixed(1)}px, ${at.y.toFixed(1)}px, 0)`;
      const settled = Math.abs(x - at.x) < 0.3 && Math.abs(y - at.y) < 0.3;
      // Frames only while there is somewhere to go.
      at.frame = at.lit >= 0 || !settled ? requestAnimationFrame(step) : null;
    };
    at.frame = requestAnimationFrame(step);
  };
  const close = (index) => {
    const frame = el.children[index];
    if (!frame || !frame.classList.contains('open')) return;
    frame.classList.remove('open');
    frame.classList.add('gone');
    frame._closing = setTimeout(() => frame.classList.remove('gone'), 640);
  };
  return {
    open(index) {
      if (at.lit >= 0 && at.lit !== index) close(at.lit);
      at.lit = index;
      const frame = el.children[index];
      if (!frame) { el.classList.remove('on'); return; }
      clearTimeout(frame._closing);
      frame.classList.remove('gone', 'open');
      at.top += 1;
      frame.style.zIndex = String(at.top);
      void frame.offsetWidth;                  // from closed, every time
      frame.classList.add('open');
      el.classList.add('on');
      follow();
    },
    hide() {
      if (at.lit >= 0) close(at.lit);
      at.lit = -1;
      el.classList.remove('on');
    },
    point(x, y) { at.tx = x; at.ty = y; },
    leave() { this.hide(); at.placed = false; },
  };
}

const feedPeek = makePeek($('peek'), $('headlines'), 'left');
const chartPeek = makePeek($('chart-peek'), $('markets'), 'right');

const rowAt = (index) => $('stories').children[index] || null;

function light(index) {
  if (state.open || index === state.lit) return;
  const row = rowAt(index);
  if (!row || row.classList.contains('empty')) return;
  if (state.lit >= 0) {
    const before = rowAt(state.lit);
    if (before) before.classList.remove('lit');
  }
  state.lit = index;
  row.classList.add('lit');
  const bar = $('feed-bar');
  bar.style.transform = `translateY(${row.offsetTop}px) scaleY(${row.offsetHeight / 100})`;
  bar.style.opacity = '1';
  feedPeek.open(index);
}

function unlight() {
  if (state.lit >= 0) {
    const row = rowAt(state.lit);
    if (row) row.classList.remove('lit');
  }
  state.lit = -1;
  $('feed-bar').style.opacity = '0';
  feedPeek.hide();
}

$('stories').addEventListener('pointerover', (event) => {
  const row = event.target.closest('.story');
  if (row && row.dataset.i !== undefined) light(Number(row.dataset.i));
});
$('feed').addEventListener('pointermove', (event) => feedPeek.point(event.clientX, event.clientY));
$('feed').addEventListener('pointerleave', () => {
  unlight();
  feedPeek.leave();
});
$('stories').addEventListener('error', (event) => {
  if (event.target.tagName === 'IMG') event.target.remove();
}, true);
$('stories').addEventListener('click', (event) => {
  const row = event.target.closest('.story');
  if (row && row.classList.contains('rest')) setFeedFolded(false);
  else if (row && row.dataset.i !== undefined) openStory(Number(row.dataset.i));
});
$('topics').addEventListener('click', (event) => {
  const chip = event.target.closest('.chip');
  if (!chip || state.snapshot === null) return;
  state.topic = Number(chip.dataset.topic) || 0;
  closeStory();
  renderFeed(state.snapshot);
});

/* --- one story, opened out of its row ------------------------------------- */

function clipTo(row, across = $('headlines')) {
  const panel = across.getBoundingClientRect();
  if (!row) return 'inset(45% 0px 45% 0px round 22px)';
  const r = row.getBoundingClientRect();
  return `inset(${(r.top - panel.top).toFixed(0)}px ${(panel.right - r.right).toFixed(0)}px `
       + `${(panel.bottom - r.bottom).toFixed(0)}px ${(r.left - panel.left).toFixed(0)}px round 10px)`;
}

function storyMarkup(item, index) {
  const read = item.link ? '<button class="read" data-act="read">Read the story ↗</button>' : '';
  // A find says whether it was worth finding: that is what Private Eye learns from.
  const rate = item.eye
    ? '<button class="useful" data-act="useful">Useful</button>'
      + '<button class="useless" data-act="useless">Not for me</button>'
    : '';
  return `
    <div class="media">${shot(item)}</div>
    <div class="body">
      <div class="meta"><span class="num">${numbered(index)}</span><b>${esc(item.source)}</b> · ${esc(item.age)}</div>
      <h3></h3>
      <p class="text"></p>
      <div class="actions">${read}${rate}<button class="back" data-act="back">Back to the feed</button></div>
    </div>`;
}

/* What Apollo is told about a story it opened, so it can talk about it. */
const told = (item, index) => ({ number: index + 1, title: String(item.title || ''),
                                 source: String(item.source || ''),
                                 summary: String(item.summary || '') });

/* Into Apollo's record (journal.py): what you open says what you care about. */
function noted(what, title, source) {
  const api = window.pywebview && window.pywebview.api;
  if (api && api.noted) api.noted(what, String(title || ''), String(source || ''));
}

function openStory(index) {
  const item = state.feed[index];
  if (!item) return null;
  // A story opens across the whole feed: folded, the feed opens out first.
  if (state.layout.feedFolded) setFeedFolded(false);
  noted('story', item.title, item.source);
  sfx.play('rev');
  const card = $('story');
  unlight();
  state.open = { index, item };
  card.innerHTML = storyMarkup(item, index);
  card.classList.add('on');
  card.setAttribute('aria-hidden', 'false');
  // Clipped to its own row first, then to the whole panel: the row opens.
  card.style.transition = 'none';
  card.style.clipPath = clipTo(rowAt(index));
  void card.offsetWidth;
  card.style.transition = '';
  card.style.clipPath = 'inset(0px 0px 0px 0px round 22px)';
  card.classList.toggle('shown', document.hidden);
  reveal(card.querySelector('h3'), String(item.title || ''));
  const text = card.querySelector('.text');
  if (item.summary && item.summary !== item.title) {
    reveal(text, String(item.summary));
  } else {
    text.textContent = item.link ? 'No summary came with this one. Read the story for all of it.'
                                 : 'That is all there is of this one.';
    text.classList.add('none');
  }
  return told(item, index);
}

function closeStory() {
  const open = state.open;
  if (!open) return;
  sfx.play('close');
  state.open = null;
  const card = $('story');
  card.setAttribute('aria-hidden', 'true');
  card.style.clipPath = clipTo(rowAt(open.index));
  setTimeout(() => {
    if (state.open) return;               // another was opened meanwhile
    card.classList.remove('on');
    card.innerHTML = '';
  }, 560);
}

$('story').addEventListener('click', (event) => {
  const button = event.target.closest('[data-act]');
  if (!button) return;
  if (button.dataset.act === 'back') closeStory();
  if (button.dataset.act === 'read' && state.open) {
    const api = window.pywebview && window.pywebview.api;
    if (api && api.open_link) api.open_link(String(state.open.item.link || ''));
  }
  if ((button.dataset.act === 'useful' || button.dataset.act === 'useless') && state.open) {
    const useful = button.dataset.act === 'useful';
    const api = window.pywebview && window.pywebview.api;
    if (api && api.rate_find) api.rate_find(state.open.item.id, useful);
    // Not for you: it goes. Useful: it stays, and says it was heard.
    if (!useful) { closeStory(); return; }
    button.textContent = 'Noted - more like this';
    button.disabled = true;
  }
});
document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') return;
  if (agent.open) toggleAgent();
  closeStory();
  closeStock();
  if (state.configFor) closeConfig();
  else if (ultraOn() && state.layout.focus) focusDisplay(null);
  else if (state.view !== 'normal' && !ultraOn() && !state.osiris) setMode('normal');
});

/* --- the stocks, picked the way the feed is -----------------------------------
 *
 * The paper bar slides to the row under the pointer and the stock's chart
 * opens beside the panel; a click opens the stock out of its row across the
 * whole panel: its chart over a day, a week, a month, six months or a year,
 * with a line you can run along it; what it did; what the analysts think it
 * is worth; and a button that takes it off the list. The row after the last
 * puts one on. Voice does the same through apollo.py: "open Nvidia", "add
 * Palantir", "take off Tesla". */

const SPANS = [['1d', '1D'], ['5d', '5D'], ['1mo', '1M'], ['6mo', '6M'], ['1y', '1Y']];
const WATCH_MAX = 12;             // watchlist.MAX
const PENDING_FOR = 45000;        // a card asked for and never delivered goes
const BIG_W = 600, BIG_H = 200, BIG_PAD = 14;

const bridge = () => (window.pywebview && window.pywebview.api) || null;
const rowFor = (symbol) =>
  [...$('watchlist').children].find((row) => row.dataset.symbol === symbol) || null;

function pendingRow(symbol, name) {
  return `
    <div class="stock-row pending" data-symbol="${esc(symbol)}">
      <span class="sym"><span class="mark none">${esc(String(symbol)[0])}</span><span class="id"><b>${esc(symbol)}</b><small class="name">Fetching ${esc(name)}…</small></span></span>
      <span class="day"><i class="mini empty"></i></span><span class="facts"></span><span class="now"><span class="price">…</span></span>
    </div>`;
}

const ADD_ROW = `
    <button class="stock-row add" type="button">
      <span class="sym"><span class="mark none">+</span><span class="id"><b>Add a stock</b><small class="name">or say “add Palantir”</small></span></span>
    </button>`;

function lightRow(row) {
  if (state.stock || !row || row === state.rowLit || row.classList.contains('pending')) return;
  if (state.rowLit) state.rowLit.classList.remove('lit');
  state.rowLit = row;
  row.classList.add('lit');
  // A fixed 100px bar, moved and stretched to the row by transform alone.
  const bar = $('watch-bar');
  bar.style.transform = `translateY(${row.offsetTop}px) scaleY(${row.offsetHeight / 100})`;
  bar.style.opacity = '1';
  // The add row, and the one under a folded list, have no chart to show.
  const chartless = row.classList.contains('add') || row.classList.contains('rest');
  chartPeek.open(chartless ? -1 : [...$('watchlist').children].indexOf(row));
}

function unlightRow() {
  if (state.rowLit) state.rowLit.classList.remove('lit');
  state.rowLit = null;
  $('watch-bar').style.opacity = '0';
  chartPeek.hide();
}

/* What Apollo is told about a stock it opened, so it can talk about it. */
const toldStock = (quote) => ({
  symbol: String(quote.symbol || ''), name: String(quote.name || ''),
  price: quote.price, change_pct: quote.change_pct, target: quote.target ?? null,
  upside: quote.upside ?? null, pe: quote.pe ?? null });

/* A dollar amount the way a headline says it. */
function big(value) {
  const v = Number(value) || 0;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  return `$${Math.round(v / 1e3)}K`;
}

/* What the company's own people did with its shares (insiders.py): open-
 * market buys and sells from their Form 4 filings, the last 90 days. */
function insidersMarkup(quote) {
  const s = ((state.snapshot || {}).insiders || {})[quote.symbol];
  if (!s) return '';
  const bought = s.buys.count ? big(s.buys.value) : 'nothing';
  const sold = s.sells.count ? big(s.sells.value) : 'nothing';
  const rows = (s.latest || []).slice(0, 3).map((trade) => `
    <div class="trade ${trade.side === 'buy' ? 'buy' : 'sell'}">
      <b>${esc(trade.name)}</b>
      <span>${trade.side === 'buy' ? 'bought' : 'sold'} ${big(trade.value)}</span>
      <i>${esc(trade.date)}</i>
    </div>`).join('');
  return `<div class="insiders"><h4>Insiders · ${Number(s.days) || 90} days: bought ${bought}, sold ${sold}</h4>${rows}</div>`;
}

function nextEarnings(quote) {
  const days = earningsIn(quote);
  if (days === null || days < 0) return '<b>—</b>';
  const day = new Date(`${quote.earnings}T12:00:00`).toLocaleDateString('en-GB',
    { weekday: 'short', day: 'numeric', month: 'short' });
  const guess = quote.earnings_estimate ? ' (est.)' : '';
  return `<b>${esc(day)}</b><i>${esc(earningsWords(days) + guess)}</i>`;
}

function stockMarkup(quote) {
  const mark = quote.logo
    ? `<img class="mark" src="${esc(quote.logo)}" alt="">`
    : `<span class="mark none">${esc((quote.symbol || '?')[0])}</span>`;
  const upside = quote.target && quote.upside != null
    ? ` <i class="${moveClass(quote.upside)}">${quote.upside >= 0 ? '+' : ''}${quote.upside.toFixed(1)}%</i>` : '';
  return `
    <div class="stock-head">
      ${mark}
      <div class="who"><b>${esc(quote.symbol)}</b><span>${esc(quote.name || '')}</span></div>
      <div class="now">
        <span class="price">${money(quote.price)}</span>
        <span class="move ${moveClass(quote.change_pct)}">${moveText(quote.change_pct)} today</span>
      </div>
    </div>
    <div class="spans">
      ${SPANS.map(([span, label]) =>
        `<span class="chip${span === '1d' ? ' on' : ''}" data-span="${span}" data-sfx="tab">${label}</span>`).join('')}
      <span class="live-badge">Live</span>
      <span class="span-move"></span>
    </div>
    <div class="big">
      <div class="plot"></div>
      <i class="pulse"></i>
      <span class="hi"></span><span class="lo"></span>
      <div class="scrub"><i></i><b></b></div>
    </div>
    <div class="facts">
      <div><span>Day high</span><b>${quote.high != null ? money(quote.high) : '—'}</b></div>
      <div><span>Day low</span><b>${quote.low != null ? money(quote.low) : '—'}</b></div>
      <div><span>Target</span><b>${quote.target ? money(quote.target) : '—'}</b>${upside}</div>
      <div><span>P/E</span><b>${quote.pe ? quote.pe.toFixed(1) : '—'}</b></div>
      <div><span>Next earnings</span>${nextEarnings(quote)}</div>
    </div>
    ${insidersMarkup(quote)}
    <div class="actions">
      <button class="drop" data-act="drop">Remove from watchlist</button>
      <button class="back" data-act="back">Back to the list</button>
    </div>`;
}

/* The chart across the open stock, drawn in again for every span - and, while
 * trades stream, redrawn still (no sweep) as its last point moves. */
function drawBig(points, rising, { still = false } = {}) {
  const view = $('stock');
  const plot = view.querySelector('.plot');
  if (!plot) return;
  if (!points || points.length < 2) {
    plot.innerHTML = '';
    view.querySelector('.hi').textContent = '';
    view.querySelector('.lo').textContent = '';
    return;
  }
  const low = Math.min(...points), high = Math.max(...points);
  const span = high - low || 1;
  const laid = points.map((value, i) => [
    (i / (points.length - 1)) * BIG_W,
    BIG_PAD + (1 - (value - low) / span) * (BIG_H - BIG_PAD * 2),
  ]);
  const line = smooth(laid);
  const start = laid[0][1].toFixed(1);
  plot.innerHTML = `<svg class="${still ? 'still' : ''}" viewBox="0 0 ${BIG_W} ${BIG_H}" preserveAspectRatio="none">
      <path class="base" d="M0,${start}L${BIG_W},${start}" vector-effect="non-scaling-stroke"/>
      <path class="wash" d="${line}L${BIG_W},${BIG_H}L0,${BIG_H}Z"
            fill="url(#${rising ? 'washUp' : 'washDown'})"/>
      <path class="line" d="${line}" fill="none" vector-effect="non-scaling-stroke"
            stroke="${rising ? 'var(--up)' : 'var(--down)'}" stroke-width="2.6"
            stroke-linejoin="round" stroke-linecap="round"/>
    </svg>`;
  view.querySelector('.hi').textContent = money(high);
  view.querySelector('.lo').textContent = money(low);
  // The dot sits on the last point: moved, not laid out again.
  const pulse = view.querySelector('.pulse');
  if (pulse) {
    const height = view.querySelector('.big').clientHeight;
    pulse.style.transform = `translateY(${((laid[laid.length - 1][1] / BIG_H) * height).toFixed(1)}px)`;
  }
}

function spanWhen(stamp, span) {
  if (!stamp) return '';
  const at = new Date(stamp * 1000);
  if (span === '1d') return at.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  if (span === '5d') return at.toLocaleString('en-GB', { weekday: 'short', hour: '2-digit', minute: '2-digit', hour12: false });
  return at.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: span === '1y' ? 'numeric' : undefined });
}

function spanMove(pct, span) {
  const words = { '1d': 'today', '5d': 'over 5 days', '1mo': 'over a month',
                  '6mo': 'over 6 months', '1y': 'over a year' };
  const move = $('stock').querySelector('.span-move');
  if (!move) return;
  // The day's move is in the heading already; the span's own is for the rest.
  if (span === '1d') { move.textContent = ''; return; }
  move.className = `span-move ${moveClass(pct)}`;
  move.textContent = `${moveText(pct)} ${words[span]}`;
}

async function loadSpan(span) {
  const open = state.stock;
  if (!open || open.picker) return;
  open.span = span;
  const view = $('stock');
  view.querySelectorAll('.spans .chip').forEach((chip) =>
    chip.classList.toggle('on', chip.dataset.span === span));
  const api = bridge();
  if (!api || !api.chart) {
    // On its own, as a sample, there is only today's line.
    if (span === '1d') spanMove(open.quote.change_pct, span);
    return;
  }
  view.classList.add('loading');
  let result = null;
  try { result = await api.chart(open.symbol, span); } catch (error) { result = null; }
  if (state.stock !== open || open.span !== span) return;     // moved on meanwhile
  view.classList.remove('loading');
  if (!result || !result.ok || !result.points || result.points.length < 2) {
    const move = view.querySelector('.span-move');
    move.className = 'span-move';
    move.textContent = (result && result.error) || 'No chart came back for that span';
    return;
  }
  open.points = result.points;
  open.times = result.times || [];
  const pct = Number(result.change_pct) || 0;
  drawBig(open.points, pct >= 0);
  spanMove(pct, span);
}

function openStock(symbol) {
  const market = (state.snapshot && state.snapshot.market) || {};
  const quote = (market.watchlist || []).find((q) => q.symbol === symbol);
  if (!quote) return null;
  noted('stock', quote.symbol, quote.name);
  sfx.play('rev');
  unlightRow();
  const view = $('stock');
  state.stock = { symbol, quote, span: '1d', points: quote.spark || [], times: [] };
  view.innerHTML = stockMarkup(quote);
  openOver(view, $('markets'), rowFor(symbol));
  drawBig(state.stock.points, quote.change_pct >= 0);
  spanMove(quote.change_pct, '1d');
  loadSpan('1d');
  return toldStock(quote);
}

/* Opened out of `from`: clipped to it first, then to the whole panel. */
function openOver(view, panel, from) {
  view.classList.add('on');
  view.setAttribute('aria-hidden', 'false');
  view.style.transition = 'none';
  view.style.clipPath = clipTo(from, panel);
  void view.offsetWidth;
  view.style.transition = '';
  view.style.clipPath = 'inset(0px 0px 0px 0px round 22px)';
}

function closeStock() {
  const open = state.stock;
  if (!open) return;
  sfx.play('close');
  state.stock = null;
  const view = $('stock');
  view.setAttribute('aria-hidden', 'true');
  view.style.clipPath = clipTo(open.picker ? $('watchlist').querySelector('.add') : rowFor(open.symbol),
                               $('markets'));
  setTimeout(() => {
    if (state.stock) return;               // another was opened meanwhile
    view.classList.remove('on', 'loading');
    view.innerHTML = '';
  }, 560);
}

/* Two clicks, the first one saying what the second will do: there is no
 * dialog to ask with, and a list you built should not lose a stock to a
 * stray click. */
function dropStock(button) {
  const open = state.stock;
  if (!open || open.picker) return;
  if (!button.classList.contains('sure')) {
    button.classList.add('sure');
    button.textContent = `Click again to remove ${open.symbol}`;
    clearTimeout(button._undo);
    button._undo = setTimeout(() => {
      button.classList.remove('sure');
      button.textContent = 'Remove from watchlist';
    }, 3500);
    return;
  }
  const api = bridge();
  if (api && api.unwatch) api.unwatch(open.symbol);
  closeStock();
  // Off the list at once, not when the next snapshot comes round.
  const market = state.snapshot && state.snapshot.market;
  if (market) {
    market.watchlist = (market.watchlist || []).filter((q) => q.symbol !== open.symbol);
    renderMarkets(market);
  }
}

async function openPicker() {
  unlightRow();
  const view = $('stock');
  const open = { picker: true };
  state.stock = open;
  view.innerHTML = `
    <div class="stock-head">
      <span class="mark none">+</span>
      <div class="who"><b>Add a stock</b><span>Pick one - or say “add” and any company</span></div>
    </div>
    <div class="picks"></div>
    <p class="said"></p>
    <div class="actions"><button class="back" data-act="back">Back to the list</button></div>`;
  openOver(view, $('markets'), $('watchlist').querySelector('.add'));
  const api = bridge();
  let picks = [];
  try { picks = api && api.suggestions ? await api.suggestions() : SAMPLE_PICKS; } catch (error) { picks = []; }
  if (state.stock !== open) return;
  view.querySelector('.picks').innerHTML = (picks || []).map((pick) => `
    <button class="pick" data-pick="${esc(pick.symbol)}"><b>${esc(pick.symbol)}</b><span>${esc(pick.name)}</span></button>`).join('')
    || '<p class="said">Everything suggested is on your list already.</p>';
}

const SAMPLE_PICKS = [{ symbol: 'PLTR', name: 'Palantir' }, { symbol: 'AMD', name: 'AMD' },
                      { symbol: '2222.SR', name: 'Aramco' }];

async function addPick(button) {
  const symbol = button.dataset.pick;
  const name = button.querySelector('span').textContent;
  button.disabled = true;
  button.classList.add('busy');
  const api = bridge();
  let result = { ok: true, symbol };
  try { if (api && api.watch) result = await api.watch(symbol); } catch (error) { result = null; }
  if (!result || !result.ok) {
    button.disabled = false;
    button.classList.remove('busy');
    $('stock').querySelector('.said').textContent = (result && result.error) || 'That one would not go on.';
    return;
  }
  if (!result.already) state.pending.set(result.symbol || symbol, { name, since: Date.now() });
  closeStock();
  if (state.snapshot) renderMarkets(state.snapshot.market || {});
}

$('watch-area').addEventListener('pointerover', (event) => {
  lightRow(event.target.closest('.stock-row'));
});
$('watch-area').addEventListener('pointermove', (event) => chartPeek.point(event.clientX, event.clientY));
$('watch-area').addEventListener('pointerleave', () => {
  unlightRow();
  chartPeek.leave();
});
$('watchlist').addEventListener('click', (event) => {
  const row = event.target.closest('.stock-row');
  if (!row) return;
  if (row.classList.contains('add')) openPicker();
  else if (row.classList.contains('rest')) setFolded(false);
  else if (row.dataset.symbol && !row.classList.contains('pending')) openStock(row.dataset.symbol);
});
$('stock').addEventListener('click', (event) => {
  const span = event.target.closest('[data-span]');
  if (span) { loadSpan(span.dataset.span); return; }
  const pick = event.target.closest('[data-pick]');
  if (pick) { addPick(pick); return; }
  const button = event.target.closest('[data-act]');
  if (!button) return;
  if (button.dataset.act === 'back') closeStock();
  if (button.dataset.act === 'drop') dropStock(button);
});

/* Run the pointer along the chart: the close under it, and when. */
$('stock').addEventListener('pointermove', (event) => {
  const open = state.stock;
  const big = event.target.closest('.big');
  const view = $('stock');
  if (!open || open.picker || !big || !open.points || open.points.length < 2) {
    view.classList.remove('scrubbing');
    return;
  }
  const box = big.getBoundingClientRect();
  const at = Math.max(0, Math.min(1, (event.clientX - box.left) / box.width));
  const i = Math.round(at * (open.points.length - 1));
  const x = (i / (open.points.length - 1)) * box.width;
  const scrub = big.querySelector('.scrub');
  scrub.style.transform = `translateX(${x.toFixed(1)}px)`;
  scrub.querySelector('b').textContent =
    [money(open.points[i]), spanWhen(open.times[i], open.span)].filter(Boolean).join(' · ');
  scrub.classList.toggle('left', at > 0.72);
  view.classList.add('scrubbing');
});
$('stock').addEventListener('pointerleave', () => $('stock').classList.remove('scrubbing'));

/* --- prices as they trade ------------------------------------------------------
 *
 * With a Finnhub key, apollo.py hands on the stream's trades about once a
 * second. A card's price and move change in place, the price flickers the
 * way it went, and the end of its curve follows; an opened stock's day
 * chart grows at its right edge, with a dot pulsing at the price. The panel
 * says LIVE while trades are coming and stops saying it when they stop -
 * the market shut, the stream down - rather than claiming a pulse it has
 * not got. */

const LIVE_QUIET = 15000;        // this long without a trade, and it is not live
const BAR_SECONDS = 300;         // Yahoo's day comes in five-minute closes

function markLive() {
  const panel = $('markets');
  panel.classList.add('streaming');
  clearTimeout(state.liveTimer);
  state.liveTimer = setTimeout(() => panel.classList.remove('streaming'), LIVE_QUIET);
}

function flicker(element, up) {
  if (!element) return;
  element.classList.remove('tick-up', 'tick-down');
  void element.offsetWidth;                  // from the start, every trade
  element.classList.add(up ? 'tick-up' : 'tick-down');
}

function tickRow(quote, before) {
  // The next full redraw compares against this, so it has nothing to flash.
  state.prices.set(quote.symbol, quote.price);
  const row = rowFor(quote.symbol);
  if (!row || row.classList.contains('pending')) return;
  const price = row.querySelector('.price');
  const move = row.querySelector('.move');
  if (price) price.textContent = money(quote.price);
  if (move) {
    move.className = `move ${moveClass(quote.change_pct)}`;
    move.textContent = moveText(quote.change_pct);
  }
  if (price && quote.price !== before) flicker(price, quote.price > before);
  const day = row.querySelector('.range');
  if (day) day.outerHTML = rangeMark(quote);
  const chart = row.querySelector('.mini');
  if (chart && quote.spark && quote.spark.length > 1) {
    chart.outerHTML = mini(quote.spark, quote.change_pct >= 0);
  }
  // ...and its chart beside the panel, which may be the one showing.
  const shot = $('chart-peek').children[[...$('watchlist').children].indexOf(row)];
  if (shot) shot.innerHTML = quoteShot(quote);
}

function tickStock(quote, tick, before) {
  const open = state.stock;
  const view = $('stock');
  const price = view.querySelector('.stock-head .price');
  const move = view.querySelector('.stock-head .move');
  if (price) price.textContent = money(quote.price);
  if (move) {
    move.className = `move ${moveClass(quote.change_pct)}`;
    move.textContent = `${moveText(quote.change_pct)} today`;
  }
  if (quote.price !== before) flicker(price, quote.price > before);
  view.classList.add('live');
  clearTimeout(open.liveTimer);
  open.liveTimer = setTimeout(() => view.classList.remove('live'), LIVE_QUIET);
  if (open.span !== '1d' || !open.points || open.points.length < 2) return;
  // A trade inside the last bar moves it; a trade past it starts the next.
  const last = open.times.length ? open.times[open.times.length - 1] : 0;
  if (last && Number(tick.time) - last >= BAR_SECONDS) {
    open.points.push(quote.price);
    open.times.push(Number(tick.time));
  } else {
    open.points[open.points.length - 1] = quote.price;
  }
  drawBig(open.points, quote.change_pct >= 0, { still: true });
}

function applyLive(batch) {
  const market = state.snapshot && state.snapshot.market;
  if (!market || !batch) return;
  let traded = false;
  for (const quote of market.watchlist || []) {
    const tick = batch[quote.symbol];
    const price = tick ? Number(tick.price) : NaN;
    if (!(price > 0)) continue;
    traded = true;
    const before = quote.price;
    quote.price = price;
    if (quote.previous) quote.change_pct = ((price - quote.previous) / quote.previous) * 100;
    if (quote.spark && quote.spark.length) quote.spark[quote.spark.length - 1] = price;
    tickRow(quote, before);
    const open = state.stock;
    if (open && !open.picker && open.symbol === quote.symbol) tickStock(quote, tick, before);
  }
  if (traded) markLive();
}

/* --- the side panel's other tabs ---------------------------------------------
 *
 * Talks: what you said to Apollo and what came back, newest first (talks.py,
 * from the record). Projects: the Claude Code sessions you have been in, the
 * git folders on this PC - a click opens one - and your GitHub repos - a click
 * opens it in the browser (projects.py). Ideas: the ideas you told Apollo to
 * keep, and your reminders (ideas.py). */

const TABS = ['stocks', 'talks', 'projects', 'ideas'];

function showTab(name) {
  if (!TABS.includes(name)) return;
  // In ultra mode every tab is a display of its own: asked for, it is
  // brought forward instead.
  if (ultraOn()) {
    revealDisplay(name === 'stocks' ? 'markets' : name);
    return;
  }
  state.tab = name;
  document.querySelectorAll('#panel-tabs .tab').forEach((tab) =>
    tab.classList.toggle('on', tab.dataset.tab === name));
  for (const tab of TABS) $(`pane-${tab}`).hidden = tab !== name;
  if (name !== 'stocks') closeStock();
}

$('panel-tabs').addEventListener('click', (event) => {
  const tab = event.target.closest('.tab');
  if (tab) showTab(tab.dataset.tab);
});

const ago = (when) => (when ? `${words(Math.max(0, Date.now() / 1000 - when))} ago` : '');

function renderTalks(list) {
  $('pane-talks').innerHTML = (list || []).map((talk) => `
    <div class="talk">
      <span class="when">${esc(talk.day === 'today' ? talk.time : 'yday ' + talk.time)}</span>
      <div class="lines">
        <p class="you">${esc(talk.you)}</p>
        <p class="said"><b>${esc(talk.who)}</b> ${esc(talk.apollo || '…')}</p>
        ${(talk.tools || []).length ? `<p class="used">${(talk.tools || []).map((name) =>
          `<i>${esc(name)}</i>`).join('')}</p>` : ''}
      </div>
    </div>`).join('')
    || '<p class="quiet">Nothing said yet today. Hold Ctrl+Alt and ask him something.</p>';
}

function renderProjects(p) {
  const group = (title, rows, empty) => `<h3>${title}</h3>${rows || `<p class="quiet">${empty}</p>`}`;
  const sessions = (p.sessions || []).map((session) => `
    <div class="work">
      <b>${esc(session.title)}</b>
      <span>${esc(session.project)} · ${esc(ago(session.when))}</span>
      ${session.prompt && session.prompt !== session.title ? `<i>${esc(session.prompt)}</i>` : ''}
    </div>`).join('');
  const folders = (p.folders || []).map((folder, n) => `
    <div class="work link" data-folder="${n}">
      <b>${esc(folder.name)}</b>
      <span>${esc(folder.branch)} · ${esc(ago(folder.when))}</span>
      ${folder.last ? `<i>${esc(folder.last)}</i>` : ''}
    </div>`).join('');
  const repos = (p.repos || []).map((repo, n) => `
    <div class="work link" data-repo="${n}">
      <b>${esc(repo.name)}${repo.private ? ' <em>private</em>' : ''}</b>
      <span>${esc(ago(repo.when))}</span>
      ${repo.about ? `<i>${esc(repo.about)}</i>` : ''}
    </div>`).join('');
  state.projects = p;
  $('pane-projects').innerHTML =
    group('Claude Code', sessions, 'No sessions found.')
    + group('On this PC', folders, 'No git folders on the Desktop or in Documents.')
    + group('GitHub', repos, 'Nothing public to show. Save a GitHub token as '
            + 'GITHUB_TOKEN to see private repos too.');
}

$('pane-projects').addEventListener('click', (event) => {
  const row = event.target.closest('.link');
  const p = state.projects || {};
  const api = window.pywebview && window.pywebview.api;
  if (!row || !api) return;
  if (row.dataset.folder !== undefined && api.open_folder) {
    const folder = (p.folders || [])[Number(row.dataset.folder)];
    if (folder) api.open_folder(folder.path);
  }
  if (row.dataset.repo !== undefined && api.open_link) {
    const repo = (p.repos || [])[Number(row.dataset.repo)];
    if (repo && repo.link) api.open_link(repo.link);
  }
});

function renderIdeas(data) {
  const list = (data.ideas || []).map((idea) => `
    <div class="idea">
      <p>${esc(idea.text)}</p>
      <span>${esc(idea.age)}</span>
      <button data-idea="${esc(idea.id)}" title="Remove">×</button>
    </div>`).join('');
  const due = (data.reminders || []).map((reminder) => `
    <div class="idea due"><p>${esc(reminder.text)}</p><span>${esc(reminder.due)}</span></div>`).join('');
  $('pane-ideas').innerHTML = `<h3>Ideas</h3>${list
    || '<p class="quiet">No ideas kept yet. Say “فكرة” or “idea:” and what it is.</p>'}`
    + `<h3>Reminders</h3>${due || '<p class="quiet">No reminders set.</p>'}`;
}

/* Two clicks to take an idea off: the first asks, the second does it. */
$('pane-ideas').addEventListener('click', (event) => {
  const button = event.target.closest('[data-idea]');
  if (!button) return;
  if (!button.classList.contains('sure')) {
    button.classList.add('sure');
    button.textContent = 'Remove?';
    setTimeout(() => { button.classList.remove('sure'); button.textContent = '×'; }, 3000);
    return;
  }
  const api = window.pywebview && window.pywebview.api;
  if (api && api.drop_idea) api.drop_idea(button.dataset.idea);
  button.closest('.idea').remove();
});

/* The gauges in the corner: the machine as rows of lit segments, and under
 * them the day's talking, the clips, and how fresh all of it is. */
const SEGMENTS = 16;

function gaugeBar(bar, pct) {
  if (bar.children.length !== SEGMENTS) {
    bar.innerHTML = '<s></s>'.repeat(SEGMENTS);
    [...bar.children].forEach((segment, i) => {
      if (i >= SEGMENTS - 3) segment.classList.add('hot');
      else if (i >= SEGMENTS - 6) segment.classList.add('warm');
    });
  }
  const lit = pct === null ? 0 : Math.round((Math.max(0, Math.min(100, pct)) / 100) * SEGMENTS);
  [...bar.children].forEach((segment, i) => segment.classList.toggle('on', i < lit));
}

function renderGauges(snapshot) {
  const system = snapshot.system || {};
  const old = STALE_AFTER.system && snapshot.stamps && snapshot.stamps.system
    && Date.now() / 1000 - snapshot.stamps.system > STALE_AFTER.system;
  for (const gauge of document.querySelectorAll('.gauge')) {
    const value = Number(system[gauge.dataset.gauge]);
    const known = Number.isFinite(value) && !old;
    gaugeBar(gauge.querySelector('.bar'), known ? value : null);
    gauge.querySelector('b').textContent = known ? `${Math.round(value)}%` : '—';
  }
  const usage = snapshot.usage || {};
  const clips = snapshot.clips || {};
  const said = [];
  said.push(usage.tokens ? `${usage.tokens.toLocaleString()} tokens · $${(usage.cost || 0).toFixed(2)}`
                         : '0 tokens');
  if (clips.saved_today !== undefined) said.push(`${clips.saved_today} clip${clips.saved_today === 1 ? '' : 's'}`);
  const age = snapshot.updated ? Math.max(0, Date.now() / 1000 - snapshot.updated) : null;
  const fresh = age === null ? '' : age < 60 ? 'live' : `${Math.floor(age / 60)}m ago`;
  $('gauge-foot').innerHTML = said.join(' · ')
    + (fresh ? ` · <span class="fresh${age >= 180 ? ' old' : ''}">● ${fresh}</span>` : '');

  // Under the meters: the card, what it holds, and each model's share of the
  // day's talking.
  const line = [];
  if (system.gpu_name) line.push(esc(String(system.gpu_name).replace(/^NVIDIA\s+(GeForce\s+)?/i, '')));
  if (system.vram !== null && system.vram !== undefined && Number.isFinite(Number(system.vram))) {
    line.push(`VRAM ${Number(system.vram).toFixed(1)} GB`);
  }
  const turns = Number(usage.turns) || 0;
  line.push(`${turns} turn${turns === 1 ? '' : 's'}`);
  for (const [name, key] of [['Gemini', 'gemini'], ['Claude', 'claude']]) {
    const used = usage[key] || {};
    if (used.prompt || used.response) line.push(`${name} ${shortCount(used.prompt)}/${shortCount(used.response)}`);
  }
  $('system-line').innerHTML = line.join(' · ');
}

function renderWeather(weather) {
  const now = new Date();
  const start = new Date(now.getFullYear(), 0, 0);
  const day = Math.floor((now - start) / 86400000);
  const week = Math.ceil(((now - start) / 86400000 + start.getDay() + 1) / 7);
  const hijri = new Intl.DateTimeFormat('en-TN-u-ca-islamic-umalqura',
    { day: 'numeric', month: 'long', year: 'numeric' }).format(now);
  $('date-extra').textContent = `Day ${day} · Week ${week} · ${hijri}`;
  // The day's range only when the reader had one: a missing high is not
  // "undefined°".
  const ranged = weather && Number.isFinite(Number(weather.high)) && weather.high !== null
    && Number.isFinite(Number(weather.low)) && weather.low !== null;
  const range = ranged ? ` · high ${Number(weather.high)}° low ${Number(weather.low)}°` : '';
  $('weather').innerHTML = weather && weather.temp !== undefined
    ? `Riyadh ${weather.temp}° · ${esc(weather.text)}${range}${stale('weather')}`
    : 'Riyadh · weather unavailable';
}

/* Ultra mode's Today, in full: the next prayer, the market's hours, who on
 * your list reports or has an insider buying this week, and what is due. */
function renderToday(snapshot) {
  const rows = [];
  const next = snapshot.prayer || {};
  if (next.name && next.at * 1000 > Date.now()) {
    const minutes = Math.round((next.at * 1000 - Date.now()) / 60000);
    const wait = minutes >= 60 ? `${Math.floor(minutes / 60)}h ${minutes % 60}m` : `${minutes}m`;
    rows.push(`<div class="row"><span>Next prayer</span><b>${esc(next.name)} · ${clock(new Date(next.at * 1000))}</b><i>in ${wait}</i></div>`);
  }
  const market = snapshot.market || {};
  if (market.status) rows.push(`<div class="row"><span>Market</span><b>${esc(market.status)}</b></div>`);
  const watched = market.watchlist || [];
  const reporting = watched.map((quote) => [quote, earningsIn(quote)])
    .filter(([, days]) => days !== null && days >= 0 && days <= 7)
    .sort((a, b) => a[1] - b[1])
    .map(([quote, days]) => `<div class="row"><span>${esc(quote.symbol)}</span><b>Earnings ${esc(earningsWords(days))}</b></div>`)
    .join('');
  const insiders = snapshot.insiders || {};
  const buying = watched.filter((quote) => (insiders[quote.symbol] || {}).recent_buy)
    .map((quote) => `<div class="row"><span>${esc(quote.symbol)}</span><b>Insider buying</b></div>`)
    .join('');
  const due = ((snapshot.ideas || {}).reminders || []).map((reminder) =>
    `<div class="row"><span>Due</span><b>${esc(reminder.text)}</b><i>${esc(reminder.due)}</i></div>`).join('');
  // On the normal display, the same in one line under the weather.
  const line = [];
  if (next.name && next.at * 1000 > Date.now()) {
    const minutes = Math.round((next.at * 1000 - Date.now()) / 60000);
    const wait = minutes >= 60 ? `${Math.floor(minutes / 60)}h ${minutes % 60}m` : `${minutes}m`;
    line.push(`<b>${esc(next.name)}</b> at ${clock(new Date(next.at * 1000))} · in ${wait}`);
  }
  const soonest = watched.map((quote) => [quote, earningsIn(quote)])
    .filter(([, days]) => days !== null && days >= 0 && days <= 7)
    .sort((a, b) => a[1] - b[1])[0];
  if (soonest) line.push(`<b>${esc(soonest[0].symbol)}</b> reports ${esc(earningsWords(soonest[1]))}`);
  $('today-line').innerHTML = line.join(' · ');
  $('today-more').innerHTML = rows.join('')
    + `<h4>This week on your list</h4>${reporting + buying || '<p class="quiet">Nobody on your list reports this week.</p>'}`
    + `<h4>Reminders</h4>${due || '<p class="quiet">Nothing due.</p>'}`;
}

const shortCount = (n) => {
  const v = Number(n) || 0;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return String(Math.round(v));
};

/* Ultra mode's System, in full: what each model took today, the day's turns
 * and cost, the machine's card, the clips, and how fresh every reading is. */
function renderSystem(snapshot) {
  const usage = snapshot.usage || {};
  const model = (name, key, voice) => {
    const used = usage[key] || {};
    const minutes = voice && used.seconds ? ` · ${Math.max(1, Math.round(used.seconds / 60))}m of voice` : '';
    return `<div class="row"><span>${name}</span><b>${shortCount(used.prompt)} in · ${shortCount(used.response)} out${minutes}</b></div>`;
  };
  const system = snapshot.system || {};
  const clips = snapshot.clips || {};
  const vram = Number.isFinite(Number(system.vram)) && system.vram !== null ? `${Number(system.vram).toFixed(1)} GB in use` : '';
  const card = system.gpu_name
    ? `<div class="row"><span>Card</span><b>${esc(system.gpu_name)}</b><i>${vram}</i></div>` : '';
  const stamps = snapshot.stamps || {};
  const readings = ['market', 'news', 'posts', 'weather', 'system'].map((key) => {
    const age = stamps[key] ? Math.max(0, Date.now() / 1000 - stamps[key]) : null;
    const old = age !== null && age > (STALE_AFTER[key] || Infinity);
    const said = age === null ? 'Not yet' : age < 60 ? 'Live' : `${words(age)} ago`;
    return `<div class="row"><span>${key}</span><b class="${old ? 'down' : ''}">${said}</b></div>`;
  }).join('');
  $('system-more').innerHTML = `<h4>Models today</h4>${model('Gemini', 'gemini', true)}${model('Claude', 'claude', false)}`
    + `<div class="row"><span>Turns</span><b>${Number(usage.turns) || 0}</b><i>$${(Number(usage.cost) || 0).toFixed(2)}${usage.estimated ? ' estimated' : ''}</i></div>`
    + `<h4>Machine</h4>${card}<div class="row"><span>Clips</span><b>${Number(clips.saved_today) || 0} saved today</b><i>${Number(clips.seconds) || 60}s kept</i></div>`
    + `<h4>Readings</h4>${readings}`;
}

function render(snapshot) {
  state.snapshot = snapshot;
  renderMarkets(snapshot.market || {});
  renderTalks(snapshot.talks);
  renderProjects(snapshot.projects || {});
  renderIdeas(snapshot.ideas || {});
  renderFeed(snapshot);
  renderGauges(snapshot);
  renderWeather(snapshot.weather);
  renderToday(snapshot);
  renderSystem(snapshot);
  renderSummaries();
  renderTrading(snapshot.trading);
  renderWorld(snapshot.world);
  enter();
}

/* --- the scanner ----------------------------------------------------------------------
 * A file dropped anywhere on the display goes to apollo.py - its path comes
 * with pywebview's drop event - and is scanned there (scanner.py). This page
 * shows the file coming, the steps, and the report: under the feed, as a
 * display of its own in ultra mode, or floating over a view that has no room
 * for it (clear, trading, agents, OSIRIS). */

const VERDICTS = { clean: 'Clean', caution: 'Careful', danger: 'Danger', error: 'Could not scan' };
const sizeOf = (n) => (n >= 2 ** 30 ? `${(n / 2 ** 30).toFixed(1)} GB` : n >= 2 ** 20
  ? `${(n / 2 ** 20).toFixed(1)} MB` : n >= 1024 ? `${Math.round(n / 1024)} KB` : `${n} bytes`);

let dragDepth = 0;
const carriesFiles = (event) => Boolean(event.dataTransfer)
  && [...(event.dataTransfer.types || [])].includes('Files');
document.addEventListener('dragenter', (event) => {
  if (!carriesFiles(event)) return;
  event.preventDefault();
  dragDepth += 1;
  if (dragDepth === 1) { document.body.classList.add('dropping'); sfx.play('show'); }
});
document.addEventListener('dragover', (event) => {
  if (!carriesFiles(event)) return;
  event.preventDefault();
  event.dataTransfer.dropEffect = 'copy';
});
document.addEventListener('dragleave', (event) => {
  if (!carriesFiles(event)) return;
  dragDepth = Math.max(0, dragDepth - 1);
  if (!dragDepth) { document.body.classList.remove('dropping'); sfx.play('hide'); }
});
document.addEventListener('drop', (event) => {
  event.preventDefault();            // a file is never opened in place of the page
  const had = dragDepth > 0 || carriesFiles(event);
  dragDepth = 0;
  document.body.classList.remove('dropping');
  if (had) sfx.play('drop');
});

function openScan() {
  if (state.hudEdit) exitHudEdit();
  document.body.classList.add('scan-open');
  if (ultraOn()) {
    document.body.classList.remove('scan-float');
    revealDisplay('scan');
  } else {
    document.body.classList.toggle('scan-float', state.view !== 'normal' || Boolean(state.osiris));
  }
}

function closeScan() {
  if (!document.body.classList.contains('scan-open')) return;
  sfx.play('close');
  document.body.classList.remove('scan-open', 'scan-float');
}
$('scan-close').addEventListener('click', closeScan);

/* The display fills the screen, so there is nothing to drag a file from:
 * Choose file opens File Explorer's own open dialog over it instead
 * (apollo.py), and what you pick is scanned like a drop. Apollo opens it
 * too when asked to scan a file. */
async function pickFile() {
  const api = bridge();
  if (!api || !api.pick_file) return false;
  sfx.play('open');
  $('scan-block').classList.add('picking');
  try {
    return Boolean(await api.pick_file());
  } catch (e) {
    return false;
  } finally {
    $('scan-block').classList.remove('picking');
  }
}
$('scan-pick').addEventListener('click', pickFile);

function onScan(event) {
  if (!event) return;
  if (event.state === 'scanning') {
    state.scan = { state: 'scanning', name: String(event.name || ''), steps: [] };
    sfx.play('scan');
    openScan();
  } else if (event.state === 'step') {
    if (state.scan && state.scan.state === 'scanning') state.scan.steps.push(String(event.text || ''));
  } else if (event.state === 'done') {
    state.scan = { state: 'done', name: String(event.name || ''), report: event.report || {} };
    sfx.play(state.scan.report.verdict === 'clean' ? 'clean' : 'alert');
  } else if (event.state === 'error') {
    state.scan = { state: 'done', name: String(event.name || ''),
                   report: { verdict: 'error', headline: String(event.text || ''), findings: [] } };
    sfx.play('fault');
    openScan();
  }
  renderScan();
  renderSummaries();
}

function renderScan() {
  const scan = state.scan;
  const body = $('scan-body');
  $('scan-block').dataset.verdict = !scan ? '' : scan.state === 'done' ? (scan.report.verdict || '') : 'scanning';
  if (!scan) { body.innerHTML = ''; return; }
  if (scan.state === 'scanning') {
    body.innerHTML = `
      <p class="scan-file">${esc(scan.name)}</p>
      <div class="scan-sweep"><i></i></div>
      <ul class="scan-steps">${scan.steps.map((text) => `<li>${esc(text)}…</li>`).join('')}</ul>`;
    return;
  }
  const report = scan.report || {};
  const findings = report.findings || [];
  const defender = report.defender || {};
  const facts = [];
  if (report.verdict !== 'error') {
    facts.push(['Defender', defender.ran ? (defender.clean ? 'No threats found' : esc(defender.threat))
                                        : esc(defender.why || 'Did not run')]);
  }
  if (report.origin) facts.push(['From', esc(report.origin)]);
  if (report.pe) {
    facts.push(['Program', `${Number(report.pe.bits) || ''}-bit · ${Number(report.pe.imports) || 0} imports`
                         + ` · ${(report.pe.sections || []).length} sections`]);
  }
  if ((report.urls || []).length) facts.push(['Links in it', report.urls.slice(0, 4).map((url) => esc(url)).join('<br>')]);
  if (report.sha256) facts.push(['SHA-256', `<span class="hash">${esc(report.sha256)}</span>`]);
  body.innerHTML = `
    <div class="scan-verdict"><b>${esc(VERDICTS[report.verdict] || 'Scanned')}</b><span>${esc(report.headline)}</span></div>
    <p class="scan-file">${esc(report.name || scan.name)}<em>${esc(report.kind || '')}${
      report.size ? ` · ${esc(sizeOf(Number(report.size)))}` : ''}</em></p>
    ${findings.length ? `<ul class="scan-findings">${findings.map((finding) =>
      `<li class="${esc(finding.level)}"><i></i>${esc(finding.text)}</li>`).join('')}</ul>` : ''}
    ${facts.length ? `<dl class="scan-facts">${facts.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>` : ''}
    ${report.lookup ? `<button type="button" class="scan-lookup" data-link="${esc(report.lookup)}" data-sfx="none">Look it up on VirusTotal</button>` : ''}
    <p class="scan-again">Choose or drop another file to scan it.</p>`;
}

$('scan-body').addEventListener('click', (event) => {
  const button = event.target.closest('[data-link]');
  const api = bridge();
  if (button && api && api.open_link) {
    sfx.play('open');
    api.open_link(button.dataset.link);
  }
});

/* --- the world, beside OSIRIS -------------------------------------------------------
 * OSIRIS mode shows only what belongs with a map (world.py): the day's
 * strongest earthquakes, the world's headlines, and the map's own layers. */

// The map's layers in words (the settings' own names come later, in LAYER_NAMES,
// which this runs before).
const WORLD_LAYERS = { cctv_previews: 'CCTV previews', live_news: 'live news', day_night: 'day and night',
                      global_incidents: 'incidents', sdk_sea: 'sea traffic', sdk_air: 'air traffic',
                      sdk_naval: 'naval', cctv: 'CCTV' };

function renderWorld(world) {
  if (!world) return;
  const quakes = world.quakes || [];
  const news = world.news || [];
  $('world-quakes').innerHTML = quakes.map((quake) => `
    <li class="world-row${quake.link ? ' link' : ''}" data-link="${esc(quake.link)}">
      <b class="mag${Number(quake.mag) >= 6 ? ' quake-strong' : ''}">M${esc((Number(quake.mag) || 0).toFixed(1))}</b>
      <span class="grow">${esc(quake.place)}</span><em>${esc(ago(quake.when))}</em></li>`).join('')
    || '<li class="world-empty">No strong earthquakes today.</li>';
  $('world-news').innerHTML = news.map((story) => `
    <li class="world-row${story.link ? ' link' : ''}" data-link="${esc(story.link)}">
      <span class="grow">${esc(story.title)}</span><em>${esc(story.source)}</em></li>`).join('')
    || '<li class="world-empty">The world\'s news is not in yet.</li>';
  renderWorldLayers();
}

function renderWorldLayers() {
  const layers = (state.layout && state.layout.layers) || [];
  $('world-layers').textContent = layers.length
    ? layers.map((layer) => WORLD_LAYERS[layer] || layer.replace(/_/g, ' ')).join(' · ')
    : 'No layers on';
}

$('world').addEventListener('click', (event) => {
  const row = event.target.closest('[data-link]');
  const api = bridge();
  if (row && row.dataset.link && api && api.open_link) {
    sfx.play('open');
    api.open_link(row.dataset.link);
  }
});

/* --- trading mode ------------------------------------------------------------------
 *
 * The desk (trading.py reads it): the read of the next picks where the
 * signals agree, what traders are on, the filings and headlines that move a
 * price, insiders buying their own stock, Congress's disclosed trades, and
 * the traders you follow on X - or, until X is set up, where your own
 * stocks turn up on the desk. Everything off a source goes through esc(). */

// What the display asks apollo.py for while the desk is up: read it now,
// and again every quarter of an hour it stays up.
/* LYLA's reports, newest first: the job, the stock it was about, her two
 * lines, and the whole report folded under them - a click opens it. The
 * list comes from apollo.py when agents mode comes up, and each new one as
 * she finishes. */
const REPORTS_SHOWN = 6;
function renderReports() {
  const list = $('lyla-reports');
  if (!list) return;
  const reports = state.lylaReports.slice(0, REPORTS_SHOWN);
  list.innerHTML = reports.length ? reports.map((report, i) => `
    <li class="report${state.reportOpen === i ? ' open' : ''}" data-report="${i}">
      <header>${report.symbol ? `<b>${esc(report.symbol)}</b>` : ''}<span class="report-task">${esc(report.task)}</span>
        <em>${esc(report.brain)}${report.done ? ` · ${esc(ago(report.done))}` : ''}</em></header>
      <p class="report-sum">${esc(report.summary)}</p>
      <div class="report-full">${esc(report.report)}</div>
    </li>`).join('') : '<li class="report-none">No reports yet. Ask Apollo to have LYLA look into something - a stock, say.</li>';
}
async function loadReports() {
  const api = bridge();
  if (!api || !api.lyla_reports) return renderReports();
  try {
    const got = await api.lyla_reports();
    state.lylaReports = Array.isArray(got && got.reports) ? got.reports : [];
    const working = got && got.working;
    lylaDoing.job = working ? `ON A JOB${working.symbol ? ` · ${working.symbol}` : ''}` : '';
    lylaDoing.show();
  } catch (e) { /* the list stays as it was */ }
  renderReports();
  if (state.view === 'agents') renderMarks();
}
$('lyla-reports')?.addEventListener('click', (event) => {
  const item = event.target.closest('[data-report]');
  if (!item) return;
  const i = Number(item.dataset.report);
  state.reportOpen = state.reportOpen === i ? -1 : i;
  sfx.play(state.reportOpen === -1 ? 'down' : 'hud');
  renderReports();
});

function wantTrading() {
  const api = bridge();
  if (api && api.trading) api.trading();
}
setInterval(() => { if (state.view === 'trading' && state.mode === 'full') wantTrading(); }, 15 * 60 * 1000);

const cash = (value) => {
  const n = Number(value) || 0;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `$${Math.round(n / 1e3)}k`;
  return `$${Math.round(n)}`;
};
const pct = (share) => `${Math.round((Number(share) || 0) * 100)}%`;
const bullBar = (share) => (share === null || share === undefined ? '<span class="bull none">no votes</span>'
  : `<span class="bull"><i style="width:${Math.round(Number(share) * 100)}%"></i></span><span class="bull-n">${pct(share)}</span>`);

// The signals, as the final stocks name them.
const SIGNAL_AR = { crowd: 'المتداولين', reddit: 'Reddit', insiders: 'كبار موظفي الشركة',
                    congress: 'الكونجرس', x: 'X' };

function renderTrading(board) {
  if (!board || !board.updated) return;
  const key = String(board.updated);
  if (key === state.deskKey) return;
  state.deskKey = key;
  $('desk-verdict').textContent = String(board.verdict || '');
  $('desk-age').textContent = `updated ${words(Date.now() / 1000 - board.updated)} ago`;
  const body = (id) => $(id).querySelector('.desk-body');
  const empty = (text) => `<p class="desk-empty">${esc(text)}</p>`;

  // What it comes to, in the middle: the final stocks and why, or that
  // nothing is worth it this period (trading.final).
  const final = board.final || { picks: [], none: '' };
  body('desk-final').innerHTML = (final.picks || []).length ? final.picks.map((pick, i) => `
    <div class="final-pick">
      <span class="final-n">${i + 1}</span>
      <div class="final-id"><b>${esc(pick.ticker)}</b><span class="final-name">${esc(pick.name)}</span></div>
      ${pick.bull === null || pick.bull === undefined ? '' : `<span class="final-bull">${pct(pick.bull)} متفائلين</span>`}
      <p class="final-why"><em>السبب:</em> ${esc(pick.why)}</p>
      <div class="final-sig">${(pick.signals || []).map((signal) => `<i>${esc(SIGNAL_AR[signal] || signal)}</i>`).join('')}</div>
    </div>`).join('') : `
    <div class="final-none"><b>ما في شي يستاهل هالفترة</b><p>${esc(final.none)}</p></div>`;

  const picks = board.picks || [];
  const top = Math.max(1, ...picks.map((pick) => Number(pick.score) || 0));
  body('desk-read').innerHTML = picks.map((pick, i) => `
    <div class="pick">
      <span class="pick-n">${i + 1}</span>
      <div class="pick-main">
        <div class="pick-line"><b>${esc(pick.ticker)}</b><span class="pick-name">${esc(pick.name)}</span>${bullBar(pick.bull)}</div>
        <span class="score"><i style="width:${Math.round((Number(pick.score) || 0) / top * 100)}%"></i></span>
        <ul>${(pick.reasons || []).map((reason) => `<li>${esc(reason)}</li>`).join('')}</ul>
        ${pick.summary ? `<p class="pick-why">${esc(pick.summary)}</p>` : ''}
      </div>
    </div>`).join('') || empty('Nothing stands out yet.');

  const hot = (board.trending || []).slice(0, 10);
  const movers = (board.reddit || []).slice(0, 6);
  body('desk-traders').innerHTML = `
    <h4>Trending on StockTwits</h4>
    ${hot.map((name, i) => `
      <div class="desk-row"><span class="rank">${i + 1}</span><b>${esc(name.symbol)}</b>
        <span class="grow">${esc(name.name)}</span>${bullBar(name.bull)}</div>`).join('') || empty('StockTwits is quiet or unreachable.')}
    <h4>Most mentioned on Reddit</h4>
    ${movers.map((mover) => `
      <div class="desk-row"><b>${esc(mover.ticker)}</b><span class="grow">${esc(mover.name)}</span>
        <span class="num">${Number(mover.mentions) || 0}</span>
        <span class="desk-rise ${Number(mover.rise) >= 1.5 ? 'up' : ''}">${(Number(mover.rise) || 0).toFixed(1)}x</span></div>`).join('') || empty('Reddit is quiet or unreachable.')}`;

  const filings = board.filings || [];
  const news = (board.news || []).slice(0, 8);
  body('desk-sensitive').innerHTML = `
    <h4>SEC filings - material events</h4>
    ${board.sec_contact ? (filings.map((filing) => `
      <div class="desk-row link w${Number(filing.weight) || 1}" data-link="${esc(filing.link)}">
        <i class="dot"></i><b>${esc(filing.ticker || '—')}</b>
        <span class="grow">${esc(filing.company)}<small>${(filing.items || []).map((item) => esc(item.label)).join(' · ')}</small></span>
        <span class="when">${esc(String(filing.filed).slice(11))}</span></div>`).join('') || empty('No serious 8-K filings in the latest batch.'))
      : empty('Off - the SEC answers only requests that name a contact. Set SEC_CONTACT to your email to turn it on.')}
    <h4>Market-moving headlines</h4>
    ${news.map((headline) => `
      <div class="desk-row link${headline.moving ? ' moving' : ''}" data-link="${esc(headline.link)}">
        <span class="grow">${esc(headline.title)}<small>${esc(headline.source)} · ${esc(headline.age)}</small></span></div>`).join('') || empty('No headlines right now.')}`;

  const clusters = (board.clusters || []).slice(0, 6);
  const buys = (board.buys || []).slice(0, 8);
  body('desk-insiders').innerHTML = `
    <h4>Cluster buys - several insiders at once</h4>
    ${clusters.map((buy) => `
      <div class="desk-row"><b>${esc(buy.ticker)}</b><span class="grow">${esc(buy.company)}<small>${esc(buy.industry)}</small></span>
        <span class="tag up">${Number(buy.insiders) || 0} insiders</span><span class="num">${cash(buy.value)}</span></div>`).join('') || empty('None in the latest filings.')}
    <h4>Biggest purchases</h4>
    ${buys.map((buy) => `
      <div class="desk-row"><b>${esc(buy.ticker)}</b><span class="grow">${esc(buy.insider)}<small>${esc(buy.title)} · ${esc(buy.traded)}</small></span>
        <span class="num">${cash(buy.value)}</span></div>`).join('') || empty('None in the latest filings.')}`;

  const deals = (board.congress || []).slice(0, 12);
  body('desk-congress').innerHTML = deals.map((deal) => `
    <div class="desk-row link" data-link="${esc(deal.link)}"><span class="tag ${deal.side === 'buy' ? 'up' : 'down'}">${deal.side === 'buy' ? 'BUY' : 'SELL'}</span>
      <b>${esc(deal.ticker)}</b><span class="grow">${esc(deal.member)}<small>${esc(deal.chamber)} · ${esc(deal.amount)} · disclosed ${esc(deal.disclosed)}</small></span></div>`).join('')
    || empty('No disclosed trades in the last month, or the source is down.');

  const x = board.x;
  if (x && (x.posts || []).length) {
    $('desk-x').querySelector('h3').innerHTML = 'On X<em>the traders you follow</em>';
    body('desk-x').innerHTML = `
      <div class="x-tags">${Object.entries(x.tickers || {}).sort((a, b) => b[1] - a[1]).slice(0, 8)
        .map(([ticker, n]) => `<span class="tag">${esc(ticker)} ${Number(n) || 0}</span>`).join('')}</div>
      ${(x.posts || []).slice(0, 8).map((post) => `
        <div class="desk-row"><span class="grow"><b>@${esc(post.who)}</b> ${esc(post.text)}</span></div>`).join('')}`;
  } else {
    // Until X is set up: where your own stocks turn up on the desk.
    const mine = ((state.snapshot && state.snapshot.market && state.snapshot.market.watchlist) || []).map((q) => q.symbol);
    const seen = (ticker) => [
      (board.trending || []).some((t) => t.symbol === ticker) && 'trending',
      (board.reddit || []).some((t) => t.ticker === ticker) && 'Reddit',
      [...(board.clusters || []), ...(board.buys || [])].some((t) => t.ticker === ticker) && 'insiders buying',
      (board.congress || []).some((t) => t.ticker === ticker) && 'Congress',
      picks.some((t) => t.ticker === ticker) && 'a pick',
    ].filter(Boolean);
    $('desk-x').querySelector('h3').innerHTML = 'Your stocks<em>where they turn up on the desk</em>';
    body('desk-x').innerHTML = mine.map((ticker) => {
      const where = seen(ticker);
      return `<div class="desk-row"><b>${esc(ticker)}</b><span class="grow">${where.length ? esc(where.join(' · ')) : '<small>not on the desk</small>'}</span></div>`;
    }).join('') + `<p class="desk-empty">${board.sources && board.sources.x === 'off'
      ? 'To follow traders on X, give Apollo an X API bearer token (X_BEARER_TOKEN) and the accounts (X_TRADERS). X charges about half a cent a post; Apollo reads at most X_DAILY_READS a day.'
      : 'X is set up, but nothing came back this time.'}</p>`;
  }
}

// A filing, a headline or a disclosure opens in your browser.
$('trading').addEventListener('click', (event) => {
  const row = event.target.closest('[data-link]');
  const api = bridge();
  if (row && row.dataset.link && api && api.open_link) api.open_link(row.dataset.link);
});

/* --- asleep ------------------------------------------------------------------
 *
 * Ten quiet minutes and the display is just the name, one or two things worth
 * knowing, and how to wake it. The things change every little while, picked
 * at random from what the snapshot already knows; none of them is invented. */

const FACT_EVERY = 16000;

function clock(date) {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
}

/* Sentences, not markup: they only ever reach the page through `reveal`,
 * which sets text. So feed values are joined as text here, not placed in
 * templates - the templates on this page are the markup ones. */
function facts(snapshot) {
  const out = [];
  const now = new Date();
  const hijri = new Intl.DateTimeFormat('en-TN-u-ca-islamic-umalqura',
    { day: 'numeric', month: 'long' }).format(now);
  out.push(`It's ${now.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })}, ${hijri}.`);

  const weather = snapshot.weather || {};
  if (weather.temp !== undefined) {
    out.push('Riyadh is ' + weather.temp + '° and ' + (weather.text || 'quiet')
      + (weather.high !== undefined ? ', with a high of ' + weather.high + '°.' : '.'));
  }
  const next = snapshot.prayer || {};
  if (next.name && next.at * 1000 > Date.now()) {
    const minutes = Math.round((next.at * 1000 - Date.now()) / 60000);
    const wait = minutes >= 60 ? `${Math.floor(minutes / 60)}h ${minutes % 60}m` : `${minutes} minutes`;
    out.push(`${next.name} is at ${clock(new Date(next.at * 1000))}, in ${wait}.`);
  }
  const market = snapshot.market || {};
  for (const index of market.indices || []) {
    const flat = Math.abs(index.change_pct) < 0.005;
    out.push(`The ${index.name || index.symbol} is `
      + (flat ? 'flat' : `${index.change_pct >= 0 ? 'up' : 'down'} ${Math.abs(index.change_pct).toFixed(2)}%`)
      + `, at ${money(index.price)}.`);
  }
  const movers = [...(market.watchlist || [])].sort(
    (a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct));
  if (movers.length) {
    const mover = movers[0];
    out.push(`${mover.symbol} has moved the most on your watchlist today: `
      + `${mover.change_pct >= 0 ? 'up' : 'down'} ${Math.abs(mover.change_pct).toFixed(2)}% to ${money(mover.price)}.`);
  }
  if (market.status) out.push(market.status + '.');
  const headlines = feedItems({ news: snapshot.news || {}, posts: [] });
  if (headlines.length) {
    const pick = headlines[Math.floor(Math.random() * Math.min(6, headlines.length))];
    out.push(pick.title + ' (' + pick.source + ').');
  }
  const usage = snapshot.usage || {};
  if (usage.turns) out.push(`You've talked to Apollo ${usage.turns} time${usage.turns === 1 ? '' : 's'} today.`);
  return out;
}

function nextFact() {
  const all = facts(state.snapshot || {});
  if (!all.length) return;
  // Two at a time, never the same pair twice running.
  let pair = '';
  for (let tries = 0; tries < 6; tries++) {
    const first = all[Math.floor(Math.random() * all.length)];
    const rest = all.filter((fact) => fact !== first);
    const second = rest.length ? rest[Math.floor(Math.random() * rest.length)] : '';
    pair = second && (first + second).length < 190 ? `${first} ${second}` : first;
    if (pair !== asleep.last) break;
  }
  asleep.last = pair;
  const element = $('sleep-fact');
  const swap = () => {
    element.style.opacity = '';
    element.classList.toggle('shown', document.hidden);
    reveal(element, pair);
  };
  // The old words fade before the new ones arrive - but only if there are
  // old words. Faded with nothing in it, the line finished the fade after
  // the first fact had been written, and sat at opacity 0 with it inside.
  if (!element.textContent) { swap(); return; }
  const done = animate(element, { opacity: [1, 0] }, { duration: 0.4, ease: 'easeIn' });
  if (done && done.finished && done.finished.then) done.finished.then(swap, swap);
  else swap();
}

function tickSleep() {
  if (!asleep.on) return;
  const now = new Date();
  $('sleep-tag').textContent = `${clock(now)} · ${now.toLocaleDateString('en-GB', { weekday: 'short' })}`;
}

function setSleep(on) {
  on = Boolean(on);
  if (on === asleep.on) return;
  asleep.on = on;
  if (state.mode === 'full') sfx.play(on ? 'sleep' : 'wake');
  document.body.classList.toggle('asleep', on);
  $('sleep').setAttribute('aria-hidden', on ? 'false' : 'true');
  shader.sleep(on);
  clearInterval(asleep.timer);
  if (on) {
    unlight();
    closeStory();
    closeConfig();
    // Under the idle screen only the dots are seen; nothing else earns frames.
    lyla.stop();
    ringStop();
    sleepWord.resize();
    sleepWord.scramble(0.9, 0.5);  // as the idle screen fades in
    tickSleep();
    nextFact();
    asleep.timer = setInterval(nextFact, FACT_EVERY);
  } else {
    sleepWord.stop();
  }
  if (!on && state.mode === 'full') {
    ringStart();
    if (roomShown()) lyla.start();
  }
}

/* Which panels are on the display. Apollo can take one off by voice, so they
 * leave rather than disappear: the grid would otherwise reflow in one frame
 * and everything else on the screen would jump. */
const PANEL_OF = {
  markets: 'markets', feed: 'headlines', clock: 'clock-block',
  status: 'status-block', strip: 'gauges', lyla: 'lyla-block', core: 'core',
};

function setPanels(wanted) {
  // What is asked for on top of what was last said: the button changes one
  // panel, and must not bring back the others that were put away.
  wanted = state.panels = { ...state.panels, ...wanted };
  for (const [panel, id] of Object.entries(PANEL_OF)) {
    const element = $(id);
    if (!element) continue;
    const show = wanted[panel] !== false;
    const already = element.dataset.hidden !== 'true';
    if (show === already) continue;
    element.dataset.hidden = show ? 'false' : 'true';
    if (show) {
      element.classList.remove('away');
      animate(element, { opacity: [0, 1], transform: ['scale(.97)', 'scale(1)'] },
              { ...SPRING });
    } else {
      const done = animate(element, { opacity: [1, 0], transform: ['scale(1)', 'scale(.97)'] },
                           { duration: 0.24, ease: 'easeOut' });
      // A class, not an inline style: ultra mode shows its displays by its own list.
      const hide = () => { if (element.dataset.hidden === 'true') element.classList.add('away'); };
      // The grid reflows only once the panel has finished leaving.
      if (done && done.finished && done.finished.then) done.finished.then(hide, hide);
      else setTimeout(hide, 260);
    }
  }
  applyRoom();
}

/* LYLA's room is out while OSIRIS is up or ultra mode is, and back the way
 * it was after. */
function applyRoom(options) {
  setRoom(!state.osiris && !ultraOn() && state.view === 'normal' && state.panels.lyla !== false, options);
}

/* LYLA's room, in or out - the button along the bottom, or "hide Lyla". Her
 * room is a full-window canvas, not a grid cell: it fades, she stops, and
 * the stage gives the space to the panels and the ring. */
function roomShown() { return !document.body.classList.contains('roomless'); }

function setRoom(shown, { quiet = false } = {}) {
  const button = $('room-toggle');
  button.setAttribute('aria-pressed', shown ? 'true' : 'false');
  button.querySelector('em').textContent = shown ? 'ROOM ON' : 'ROOM OFF';
  if (shown === roomShown()) return;
  if (!quiet) sfx.play(shown ? 'hud' : 'down');
  clearTimeout(state.roomTimer);
  const swap = () => {
    document.body.classList.toggle('roomless', !shown);
    if (shown) {
      if (state.mode === 'full' && !asleep.on) lyla.start();
    } else {
      state.roomTimer = setTimeout(() => { if (!roomShown()) lyla.stop(); }, 460);
    }
  };
  if (quiet) swap();
  else channelChange(swap);
}

/* A change of shape on an old set: a flash and a jolt, and the new picture
 * underneath it. The stage changes in one frame, at the dark moment - never
 * stretched frame by frame, which would lay the whole page out again on
 * every one of them. */
function channelChange(swap) {
  sfx.play('channel');
  document.body.classList.remove('switching');
  void document.body.offsetWidth;          // from the start, every time
  document.body.classList.add('switching');
  clearTimeout(state.channelTimer);
  setTimeout(swap, 150);
  state.channelTimer = setTimeout(() => document.body.classList.remove('switching'), 520);
}

/* --- OSIRIS --------------------------------------------------------------------
 *
 * The open-source intelligence map, laid into the display where the ring
 * and the feed were, with all of Apollo in OSIRIS's colours while it is up.
 * The map is a window of its own (osiris.py): this page lays out the frame
 * and says where it is, and apollo.py puts the window exactly over it. */

function setOsiris(on) {
  on = Boolean(on);
  if (ultraOn()) {
    // In ultra mode the map is one of the displays: opened, it is the one
    // expanded, in its own colours; closed, it is taken off.
    if (on) focusDisplay('osiris');
    else showDisplay('osiris', false);
    return on;
  }
  if (on === state.osiris) return on;
  state.osiris = on;
  sfx.play(on ? 'ping' : 'down');
  closeStory();
  closeStock();
  unlight();
  unlightRow();
  renderModes();
  // The switch is a channel change: Apollo goes into OSIRIS's colours, and
  // LYLA's room out, at its dark moment.
  if (!on) syncOsiris();                  // gone at once
  channelChange(() => {
    document.body.classList.toggle('osiris-map', on);
    $('osiris').setAttribute('aria-hidden', on ? 'false' : 'true');
    applySkin();
    applyRoom({ quiet: true });
    // Laid over the frame once the stage has its new shape.
    if (on) scheduleOsiris(200);
  });
  return on;
}

$('osiris-close').addEventListener('click', () => setOsiris(false));
window.addEventListener('resize', () => scheduleOsiris(300));

/* --- the modes -----------------------------------------------------------------
 *
 * One at a time, on the bar along the bottom (modes.js): normal, clear,
 * trading, agents, expanded and OSIRIS - clicked there, or asked for by
 * voice. Expanded is ultra mode and OSIRIS the map, switches the page
 * already had; the other four are views of the display: the display itself,
 * clear (nothing on the screen but Apollo and the sign to press Ctrl+Alt),
 * the trading desk, and the agents. A mode asked for throws the switches it
 * needs in order, leaving before arriving, each after the last one's
 * channel change has settled. */

function modeFlags() {
  return { ultra: ultraOn(), osiris: state.osiris, view: state.view };
}

function renderModes() {
  const mode = Modes.current(modeFlags());
  document.querySelectorAll('[data-mode]').forEach((button) =>
    button.setAttribute('aria-pressed', button.dataset.mode === mode ? 'true' : 'false'));
}

/* A view of the display: normal, or one that puts the panels, the clock,
 * LYLA and her room away for something else - Apollo alone with his sign
 * (clear), the trading desk, or the agents. */
function setView(view) {
  view = Modes.VIEWS.includes(view) ? view : 'normal';
  if (view === state.view) return;
  const was = state.view;
  if (state.hudEdit) exitHudEdit();
  state.view = view;
  const back = view === 'normal';
  sfx.play(back ? 'down' : 'hud');
  closeStory();
  closeStock();
  unlight();
  unlightRow();
  if (agent.open) toggleAgent();
  if (view === 'trading') wantTrading();
  if (was === 'agents') for (const key of AGENTS) agentCards[key].hide();
  renderModes();
  channelChange(() => {
    for (const name of ['clear', 'trading', 'agents']) document.body.classList.toggle(name, view === name);
    document.body.classList.toggle('viewing', view !== 'normal');
    if (view === 'agents') {
      if (state.agentOpen) agentCards[state.agentOpen].show();
      showAgentStage();
      loadReports();
    }
    applyRoom({ quiet: true });
    applySkin();
    applyHud();
  });
}

async function setMode(mode) {
  const ticket = ++state.modeTicket;
  const steps = Modes.plan(modeFlags(), mode);
  for (let i = 0; i < steps.length; i++) {
    if (ticket !== state.modeTicket) return;      // another mode was asked for meanwhile
    const [what, on] = steps[i];
    if (what === 'ultra') {
      // Straight to the mode asked for: the map ultra mode held stays there
      // rather than coming back into the normal display on the way out.
      if (!on) state.osirisReturn = false;
      setUltra(on);
    } else if (what === 'osiris') {
      setOsiris(on);
    } else {
      setView(on);
    }
    if (i < steps.length - 1) await new Promise((done) => setTimeout(done, 560));
  }
  renderModes();
}

document.addEventListener('click', (event) => {
  const button = event.target.closest('[data-mode]');
  if (button) setMode(button.dataset.mode);
});

/* Apollo's own modes, beside the display's: the idle screen now, away mode
 * and hands-free listening. apollo.py does them - they are the machine's,
 * not the page's - and says when away or hands-free changes, so they light
 * while they are on. Idle needs no light: the idle screen is all there is
 * while it is on. */
function renderOwnModes() {
  document.querySelectorAll('[data-act="away"]').forEach((b) =>
    b.setAttribute('aria-pressed', state.away ? 'true' : 'false'));
  document.querySelectorAll('[data-act="listen"]').forEach((b) =>
    b.setAttribute('aria-pressed', state.listening ? 'true' : 'false'));
}

document.addEventListener('click', (event) => {
  const button = event.target.closest('[data-act]');
  const api = bridge();
  if (!button || !api) return;
  const act = button.dataset.act;
  if (act === 'idle' && api.idle) api.idle();
  if (act === 'away' && api.away) api.away();
  if (act === 'listen' && api.listen) api.listen(!state.listening);
});

$('room-toggle').addEventListener('click', () => {
  const shown = !roomShown();
  setPanels({ lyla: shown });
  const api = window.pywebview && window.pywebview.api;
  if (api && api.set_panel) api.set_panel('lyla', shown);
});

/* --- ultra mode -------------------------------------------------------------------
 *
 * Every display on the screen at once, ready for work: the markets, the feed,
 * OSIRIS, projects, ideas, talks, the system, today and Apollo himself, each a
 * tile on a grid of twelve columns and twelve rows. A tile is moved by its top
 * edge - dropped on another, the two trade places - resized by its bottom
 * corner, and has its controls in its top corner: minimize it to its name and
 * one line, expand it with the rest minimized down the side, its settings, and
 * hide. The bar along the bottom switches displays on and off. By voice:
 * "ultra mode", "put the projects on my screen", "hide the ideas".
 *
 * tiles.js has the rules; apollo.py keeps the layout (displays.py), so the
 * screen you set up is the one you get tomorrow. */

const TILE_OF = Object.fromEntries(
  [...document.querySelectorAll('[data-display]')].map((tile) => [tile.dataset.display, tile]));
// The side panel's other tabs are displays of their own in ultra mode: their
// lists move into their tiles, and back into the side panel after.
const PANE_TILE = { projects: 'd-projects', ideas: 'd-ideas', talks: 'd-talks' };
const LAYER_NAMES = {
  maritime: 'Ships', cctv: 'CCTV', cctv_previews: 'CCTV previews', live_news: 'Live news',
  earthquakes: 'Earthquakes', global_incidents: 'Incidents', day_night: 'Day and night',
  cables: 'Undersea cables', sdk_sea: 'Sea traffic', sdk_air: 'Air traffic', sdk_naval: 'Naval',
};
const ICON = {
  grip: '<svg viewBox="0 0 12 16" aria-hidden="true"><circle cx="3.5" cy="3" r="1.4"/><circle cx="8.5" cy="3" r="1.4"/>'
      + '<circle cx="3.5" cy="8" r="1.4"/><circle cx="8.5" cy="8" r="1.4"/><circle cx="3.5" cy="13" r="1.4"/>'
      + '<circle cx="8.5" cy="13" r="1.4"/></svg>',
  min: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 11.5h10"/></svg>',
  focus: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M9.5 2.5h4v4M6.5 13.5h-4v-4M13.5 2.5 9 7M2.5 13.5 7 9"/></svg>',
  config: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 4.5h11M2.5 11.5h11"/>'
        + '<circle cx="6" cy="4.5" r="1.9" fill="currentColor"/><circle cx="10.5" cy="11.5" r="1.9" fill="currentColor"/></svg>',
  hide: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8"/></svg>',
};
const EASE = 'cubic-bezier(.32, .72, 0, 1)';

// Declarations, not arrows: the normal display asks them too, from code
// that is written above this and may run before it.
function ultraOn() { return document.body.classList.contains('ultra'); }
function still() { return matchMedia('(prefers-reduced-motion: reduce)').matches; }

// Each display's handle, controls, minimized line and corner - there, but
// only shown in ultra mode.
for (const [id, tile] of Object.entries(TILE_OF)) {
  const handle = document.createElement('div');
  handle.className = 'tile-handle';
  handle.title = 'Drag to move it · double-click to expand it';
  const line = document.createElement('div');
  line.className = 'tile-min';
  line.innerHTML = `<b>${Tiles.NAMES[id]}</b><span class="tile-sum"></span>`;
  const controls = document.createElement('div');
  controls.className = 'tile-ctl';
  controls.innerHTML = `<span class="tile-grip">${ICON.grip}</span>`
    + `<button type="button" data-tile="min" data-sfx="none" title="Minimize">${ICON.min}</button>`
    + `<button type="button" data-tile="focus" data-sfx="none" title="Expand">${ICON.focus}</button>`
    + `<button type="button" data-tile="config" data-sfx="none" title="Settings">${ICON.config}</button>`
    + `<button type="button" data-tile="hide" data-sfx="none" title="Hide">${ICON.hide}</button>`;
  const corner = document.createElement('i');
  corner.className = 'tile-resize';
  corner.title = 'Drag to resize';
  tile.append(handle, line, controls, corner);
}

/* The layout onto the page: which displays are shown, where, how big, which
 * one is expanded and which are minimized. Placed inline, since the normal
 * display's own grid places the same blocks by id. */
function applyLayout() {
  const layout = state.layout;
  renderWorldLayers();                   // the map's layers, beside it
  const ultra = ultraOn();
  const focusing = ultra && Boolean(layout.focus);
  document.body.classList.toggle('focusing', focusing);
  const railed = focusing ? Tiles.visible(layout).filter((id) => id !== layout.focus) : [];
  $('stage').style.gridTemplateRows = focusing ? `repeat(${railed.length}, auto) minmax(0, 1fr)` : '';
  for (const id of Tiles.DISPLAYS) {
    const tile = TILE_OF[id];
    if (!tile) continue;
    const item = layout.items[id];
    const lead = focusing && id === layout.focus;
    const side = focusing && item.shown && !lead;
    tile.classList.toggle('tile-off', ultra && !item.shown);
    tile.classList.toggle('focused', lead);
    tile.classList.toggle('railed', side);
    tile.classList.toggle('is-min', ultra && item.shown && (side || (!focusing && item.min)));
    tile.querySelector('[data-tile="focus"]').title = lead ? 'Back to the grid' : 'Expand';
    tile.querySelector('[data-tile="min"]').title = item.min ? 'Restore' : 'Minimize';
    if (!ultra) {
      for (const name of ['grid-column', 'grid-row', 'order']) tile.style.removeProperty(name);
      continue;
    }
    tile.style.order = String(layout.order.indexOf(id));
    if (lead) {
      tile.style.gridColumn = '1';
      tile.style.gridRow = `1 / span ${railed.length + 1}`;
    } else if (side) {
      tile.style.gridColumn = '2';
      tile.style.gridRow = 'auto';
    } else {
      tile.style.gridColumn = `span ${item.w}`;
      tile.style.gridRow = `span ${item.min ? 1 : item.h}`;
    }
  }
  const folded = Boolean(layout.folded);
  $('markets').classList.toggle('folded', folded);
  const fold = $('stocks-fold');
  fold.setAttribute('aria-pressed', folded ? 'true' : 'false');
  fold.title = folded ? 'All the stocks back' : 'Fold the stocks away to a few';
  fold.querySelector('span').textContent = folded ? 'ALL' : 'FOLD';
  const feedFolded = Boolean(layout.feedFolded);
  $('headlines').classList.toggle('folded', feedFolded);
  const feedFold = $('feed-fold');
  feedFold.setAttribute('aria-pressed', feedFolded ? 'true' : 'false');
  feedFold.title = feedFolded ? 'The whole feed back' : 'Fold the feed away to a few stories';
  feedFold.querySelector('span').textContent = feedFolded ? 'ALL' : 'FOLD';
  // Redrawn only if a fold changed: each list knows what it last drew.
  if (state.snapshot) {
    renderMarkets(state.snapshot.market || {});
    renderFeed(state.snapshot);
  }
  renderDisplayChips();
  renderSummaries();
  renderModes();
  applySkin();
  if (state.fitConsoles) requestAnimationFrame(state.fitConsoles);
}

/* Apollo in OSIRIS's colours: while the map is laid into the normal display,
 * and in ultra mode while it is the display expanded. In the market's while
 * the trading desk is what is on the screen. */
function applySkin() {
  const skin = state.osiris || (ultraOn() && state.layout.focus === 'osiris');
  document.body.classList.toggle('osiris', skin);
  shader.theme(skin);
  shader.market(state.view === 'trading' && !skin && !ultraOn());
}

/* A change of layout that moves displays: each one slides from where it was
 * to where it is now, drawn by transform alone - the grid itself changes in
 * one frame (the FLIP technique). */
function flip(change, { skip = null } = {}) {
  const tiles = Object.values(TILE_OF).filter((tile) => tile !== skip);
  const before = new Map(tiles.map((tile) => [tile, tile.getBoundingClientRect()]));
  change();
  if (still()) return;
  for (const tile of tiles) {
    const was = before.get(tile);
    const now = tile.getBoundingClientRect();
    if (!now.width) continue;
    if (!was.width) {                               // just switched on: it arrives
      tile.animate([{ opacity: 0, transform: 'scale(.96)' }, { opacity: 1, transform: 'none' }],
                   { duration: 360, easing: EASE });
      continue;
    }
    const dx = was.left - now.left, dy = was.top - now.top;
    const sx = was.width / now.width, sy = was.height / now.height;
    if (Math.abs(dx) < 1 && Math.abs(dy) < 1 && Math.abs(sx - 1) < 0.01 && Math.abs(sy - 1) < 0.01) continue;
    tile.animate([
      { transformOrigin: '0 0', transform: `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})` },
      { transformOrigin: '0 0', transform: 'none' },
    ], { duration: 460, easing: EASE });
  }
}

function changeLayout(next, { animate: moving = true, save = true, quiet = false } = {}) {
  // What the change was, heard: expanded, put back, minimized, hidden,
  // shown, swapped, resized, a list folded (tiles.soundFor, sfx.js).
  const heard = quiet ? null : Tiles.soundFor(state.layout, next);
  if (heard) sfx.play(heard);
  const run = () => { state.layout = next; applyLayout(); };
  if (moving && ultraOn() && next.ultra) flip(run);
  else run();
  if (save) saveLayout();
  if (state.configFor) renderConfig();
  scheduleOsiris();
}

/* The feed folded away to its newest few, a line each, or all of it back -
 * kept with the layout like the stocks'. */
function setFeedFolded(on) {
  if (Boolean(on) === Boolean(state.layout.feedFolded)) return;
  closeStory();
  unlight();
  changeLayout(Tiles.setFeedFolded(state.layout, on), { animate: false });
}
$('feed-fold').addEventListener('click', () => setFeedFolded(!state.layout.feedFolded));

/* The stocks folded away to a few, small, or all of them back - kept with
 * the layout, so it is the same tomorrow. */
function setFolded(on) {
  if (Boolean(on) === Boolean(state.layout.folded)) return;
  closeStock();
  unlightRow();
  changeLayout(Tiles.setFolded(state.layout, on), { animate: false });
}
$('stocks-fold').addEventListener('click', () => setFolded(!state.layout.folded));

/* Into apollo.py's keeping once the changes stop. */
function saveLayout() {
  clearTimeout(state.saveTimer);
  state.saveTimer = setTimeout(() => {
    const api = bridge();
    if (api && api.save_layout) api.save_layout(state.layout);
  }, 400);
}

/* Ultra mode on or off: a channel change, and at its dark moment the stage
 * becomes the grid of displays - or the normal display again. */
function setUltra(on, { quiet = false, layout = null } = {}) {
  on = Boolean(on);
  const next = layout || Tiles.setUltra(state.layout, on);
  if (on === ultraOn()) { changeLayout(next); return on; }
  if (on && state.hudEdit) exitHudEdit();
  if (!quiet) sfx.play(on ? 'swipe' : 'down');
  closeStory();
  closeStock();
  unlight();
  unlightRow();
  closeConfig();
  if (on && state.osiris) {
    // The map laid into the normal display becomes one of ultra mode's -
    // and goes back into the normal display after, if it is still up.
    state.osiris = false;
    state.osirisReturn = true;
  } else if (on) {
    state.osirisReturn = false;
  }
  const back = !on && state.osirisReturn && next.items.osiris.shown;
  if (!on) state.osirisReturn = false;
  state.layout = next;
  // Off the screen while the picture changes, and laid over wherever its
  // frame is once it has: told before the change, it went where the frame
  // had been, and stayed there over the display that replaced it.
  const api = bridge();
  if (api && api.osiris_park) api.osiris_park();
  const swap = () => {
    if (back) state.osiris = true;
    document.body.classList.toggle('osiris-map', back);
    document.body.classList.toggle('ultra', on);
    $('osiris').setAttribute('aria-hidden', on || back ? 'false' : 'true');
    movePanes(on);
    if (on) settleTiles();
    applyLayout();
    applyRoom({ quiet: true });
    if (on) powerOn();
    scheduleOsiris(on ? 600 : 320);
  };
  if (quiet) swap();
  else channelChange(swap);
  saveLayout();
  return on;
}

function movePanes(on) {
  for (const [tab, tile] of Object.entries(PANE_TILE)) {
    const pane = $(`pane-${tab}`);
    if (on) {
      $(tile).appendChild(pane);
      pane.hidden = false;
    } else {
      $('markets').insertBefore(pane, $('stock'));
    }
  }
  if (on) {
    $('pane-stocks').hidden = false;
    document.querySelectorAll('#panel-tabs .tab').forEach((tab) =>
      tab.classList.toggle('on', tab.dataset.tab === 'stocks'));
  } else {
    showTab(state.tab);
  }
}

/* What the entrance animations and a panel taken off by voice leave inline
 * would outrank the tiles' own look. */
function settleTiles() {
  for (const element of [...Object.values(TILE_OF), $('gauges')]) {
    element.style.removeProperty('opacity');
    element.style.removeProperty('transform');
  }
}

/* Coming up for work: the displays power on one after another, under a line
 * of light running down the glass. */
function powerOn() {
  if (still()) return;
  const shown = Tiles.visible(state.layout);
  shown.forEach((id, i) => {
    const tile = TILE_OF[id];
    tile.style.setProperty('--i', String(i));
    tile.classList.remove('powering');
    void tile.offsetWidth;                          // from the start, every time
    tile.classList.add('powering');
  });
  document.body.classList.remove('sweeping');
  void document.body.offsetWidth;
  document.body.classList.add('sweeping');
  clearTimeout(state.powerTimer);
  state.powerTimer = setTimeout(() => {
    for (const tile of Object.values(TILE_OF)) tile.classList.remove('powering');
    document.body.classList.remove('sweeping');
  }, 900 + shown.length * 70);
}

/* "Put it on my screen": ultra mode if it is not, that display expanded,
 * the rest minimized beside it. null puts the grid back. */
function focusDisplay(id) {
  const next = Tiles.focus(state.layout, id || null);
  if (!ultraOn()) {
    if (id) setUltra(true, { layout: next });
    return;
  }
  changeLayout(next);
}

function showDisplay(id, shown) {
  if (!Tiles.NAMES[id]) return;
  let next = Tiles.setShown(state.layout, id, shown);
  if (shown) next = Tiles.setMin(next, id, false);
  if (!ultraOn()) {
    if (shown) setUltra(true, { layout: Tiles.setUltra(next, true) });
    else changeLayout(next, { animate: false });
    return;
  }
  changeLayout(next);
  if (shown) pulse(id);
}

/* A display asked for that is already there: brought forward - out of the
 * rail, or out of being minimized - and lit up for a moment. */
function revealDisplay(id) {
  const item = state.layout.items[id];
  if (!item) return;
  if (state.layout.focus && state.layout.focus !== id) focusDisplay(id);
  else if (!item.shown || item.min) changeLayout(Tiles.setMin(Tiles.setShown(state.layout, id, true), id, false));
  pulse(id);
}

function pulse(id) {
  const tile = TILE_OF[id];
  if (!tile) return;
  tile.classList.remove('pulse-tile');
  void tile.offsetWidth;
  tile.classList.add('pulse-tile');
}

/* The layout apollo.py kept, as the display opens: taken as it is. */
function adoptLayout(raw) {
  const next = Tiles.sanitize(raw);
  if (next.ultra !== ultraOn()) { setUltra(next.ultra, { quiet: true, layout: next }); return; }
  changeLayout(next, { animate: false, save: false, quiet: true });
}

/* --- the map among the displays -----------------------------------------------
 * The map is a window laid over its frame (osiris.py), and a window can only
 * lie over the page, never under it: whatever the page drew where the map is
 * would be hidden. So it is parked - off the screen, still loaded - while
 * anything is moving, while its settings or another display's are open,
 * while it is minimized or another display is expanded, and while Apollo
 * answers; and put back over its frame once things have settled. */

function osirisSpot() {
  // Never over the intro: the map waits for the tube to have warmed up.
  if ($('intro').classList.contains('on')) {
    return (ultraOn() ? state.layout.items.osiris.shown : state.osiris) ? 'park' : 'close';
  }
  if (!ultraOn()) return state.osiris ? 'open' : 'close';
  const layout = state.layout;
  const item = layout.items.osiris;
  if (!item.shown) return 'close';
  if (item.min || (layout.focus && layout.focus !== 'osiris')) return 'park';
  if (state.drag || state.resizing || state.configFor) return 'park';
  if (state.phase === 'thinking' || state.phase === 'speaking') return 'park';
  return 'open';
}

function syncOsiris() {
  const api = bridge();
  const spot = osirisSpot();
  if (spot === 'open') {
    const view = $('osiris-view');
    const box = view.getBoundingClientRect();
    // Too small a frame for the map to be any use: it says so instead.
    const small = box.width < 200 || box.height < 200;
    view.classList.toggle('small', small);
    if (small) {
      if (api && api.osiris_park) api.osiris_park();
      return;
    }
    const ratio = window.devicePixelRatio || 1;
    if (api && api.osiris_open) {
      api.osiris_open({ x: Math.round(box.left * ratio), y: Math.round(box.top * ratio),
                        w: Math.round(box.width * ratio), h: Math.round(box.height * ratio) });
    }
  } else if (spot === 'park') {
    if (api && api.osiris_park) api.osiris_park();
  } else if (api && api.osiris_close) {
    api.osiris_close();
  }
}

/* Everything on the stage that is moving and will stop - a display sliding
 * to its new place, powering on, a channel change - come to rest. The sign's
 * pulse and the like go on for ever and are not waited for. */
function whenSettled() {
  const stage = $('stage');
  const moving = document.getAnimations().filter((motion) => {
    const effect = motion.effect;
    if (!effect || !effect.target || !stage.contains(effect.target)) return false;
    if (motion.playState === 'finished') return false;
    return Number.isFinite(effect.getComputedTiming().endTime);
  });
  return Promise.all(moving.map((motion) => motion.finished.catch(() => null)));
}

/* Off the screen at once if the page is about to move, and back over its
 * frame once the move has settled - after `delay`, and then only once
 * nothing on the stage is still on its way: a frame measured mid-slide is
 * where the display was going, not where it went, and the map would stay
 * there. Only the last one asked for places it. */
function scheduleOsiris(delay = 480) {
  clearTimeout(state.osirisTimer);
  const ticket = state.osirisTicket = (state.osirisTicket || 0) + 1;
  const api = bridge();
  if (osirisSpot() !== 'open') { syncOsiris(); return; }
  if (ultraOn() && api && api.osiris_park) api.osiris_park();
  state.osirisTimer = setTimeout(() => {
    whenSettled().then(() => { if (ticket === state.osirisTicket) syncOsiris(); });
  }, delay);
}

/* --- the bar along the bottom ---------------------------------------------------- */

function renderDisplayChips() {
  const layout = state.layout;
  $('ultra-chips').innerHTML = Tiles.DISPLAYS.map((id) => {
    const shown = layout.items[id].shown;
    return `<button type="button" class="dchip${shown ? ' on' : ''}${layout.focus === id ? ' lead' : ''}"
              data-chip="${id}" data-sfx="none" aria-pressed="${shown ? 'true' : 'false'}"
              title="${shown ? 'Hide' : 'Show'} ${Tiles.NAMES[id]}"><i class="led"></i>${Tiles.NAMES[id]}</button>`;
  }).join('');
}

function renderSummaries() {
  if (!ultraOn()) return;
  const extra = { clock: $('hhmm').textContent, phase: state.phase,
                  layers: state.layout.layers.length, feed: state.feed, scan: state.scan };
  for (const [id, tile] of Object.entries(TILE_OF)) {
    const line = tile.querySelector('.tile-sum');
    if (line) line.textContent = Tiles.summary(id, state.snapshot || {}, extra);
  }
}

/* --- expanded mode's consoles ---------------------------------------------------
 * Either side of its bar, the way a facility's desk has them: switches that
 * flip, lights that blink, armed buttons that fire, a dial that turns and
 * readouts that tick. For the look of the place; they do nothing else. */
(function consoles() {
  // Eighteen lights, each something true (consolelights.js) - lit below.
  document.querySelector('.console-leds').innerHTML = Array.from({ length: 18 }, () => '<i></i>').join('');
  document.querySelectorAll('.console').forEach((panel) => panel.addEventListener('click', (event) => {
    const flip = event.target.closest('.flip');
    if (flip) flip.classList.toggle('on');
    const arm = event.target.closest('.arm');
    if (arm) {
      arm.classList.remove('fired');
      void arm.offsetWidth;                  // fired again from the start
      arm.classList.add('fired');
    }
    const knob = event.target.closest('.knob');
    if (knob) {
      knob.dataset.turn = String((Number(knob.dataset.turn || 0) + 45) % 360);
      knob.style.setProperty('--turn', `${knob.dataset.turn}deg`);
    }
  }));
  // Beside the bar, never over it: a desk that would touch it steps away.
  const fit = () => {
    const bar = $('ultra-bar').getBoundingClientRect();
    document.querySelectorAll('.console').forEach((desk) => {
      desk.classList.remove('squeezed');
      if (!ultraOn()) return;
      const box = desk.getBoundingClientRect();
      if (box.width && box.right + 8 > bar.left && box.left - 8 < bar.right) desk.classList.add('squeezed');
    });
  };
  window.addEventListener('resize', fit);
  state.fitConsoles = fit;
  // The readouts and the lights, once a second while a console is on the
  // screen: how long Apollo has been up (the display opens as he starts),
  // how quickly the internet answers, the load, the card's heat.
  const began = Date.now();
  const history = [];
  let heard = 0;
  const read = (name, text) => {
    const element = document.querySelector(`[data-read="${name}"]`);
    if (element) element.textContent = text;
  };
  setInterval(() => {
    const body = document.body.classList;
    if (state.mode !== 'full' || body.contains('asleep') || (!ultraOn() && state.view !== 'normal')) return;
    const snapshot = state.snapshot || {};
    const system = snapshot.system || {};
    const stamps = snapshot.stamps || {};
    // A new reading of the machine is one more bar.
    if (stamps.system && stamps.system !== heard) {
      heard = stamps.system;
      history.push(Number(system.cpu));
      if (history.length > 12) history.shift();
    }
    read('clock', Lights.uptime((Date.now() - began) / 1000));
    read('link', Lights.linkText(system.link_ms === null ? NaN : Number(system.link_ms)));
    read('core', Lights.cpuText(Number(system.cpu)));
    read('temp', Lights.tempText(system.gpu_temp === null ? NaN : Number(system.gpu_temp)));
    document.querySelectorAll('[data-read="link"]').forEach((el) =>
      el.classList.toggle('down', !Number.isFinite(Number(system.link_ms)) || system.link_ms === null));
    const heights = Lights.bars(history);
    document.querySelectorAll('.console-bars i').forEach((bar, i) => { bar.style.height = `${heights[i]}px`; });
    const lit = Lights.lights({ stamps, now: Date.now() / 1000, phase: state.phase, listening: state.listening,
                                away: state.away, lyla: Boolean(lylaDoing.job), cpu: Number(system.cpu) });
    document.querySelectorAll('.console-leds i').forEach((led, i) => {
      const it = lit[i];
      if (!it) return;
      led.className = `${it.colour}${it.on ? ' on' : ''}${it.blink ? ' blink' : ''}`;
      led.title = it.title;
    });
  }, 1000);
})();

/* --- the HUD: the normal display arranged by hand -----------------------------------
 * F2, HUD on the console, or "customize the HUD": every panel of the normal
 * display in a frame. Drag one and it follows the hand on a spring, leaning
 * into the way it is going, and lets go onto the grid or the nearest edge of
 * another - with the guide it lined up on; a corner resizes it (Apollo and
 * the consoles keep their shape); the wheel or +/- scales what is inside;
 * the eye hides it. Reset all flies every panel home. The result is kept
 * (hud.py) and laid out whenever the normal display is up; every other view
 * lays itself out as ever. hud.js has the numbers. */

const panelOf = (id) => $(Hud.ELEMENT[id]);
const hudFree = () => state.hud.free;
function stageBox() {
  const r = $('stage').getBoundingClientRect();
  return { x: r.left, y: r.top, w: r.width, h: r.height };
}
function seenRect(id, stage = stageBox()) {
  const r = panelOf(id).getBoundingClientRect();
  return { x: r.left - stage.x, y: r.top - stage.y, w: r.width, h: r.height };
}

/* One panel laid out to cover `rect` (px on the stage) with its insides
 * scaled by `s`. The consoles live outside the stage, fixed to the window. */
function placePanel(id, rect, s, stage = stageBox()) {
  const panel = panelOf(id);
  const b = Hud.box(rect, s);
  const outside = panel.classList.contains('console');
  panel.style.setProperty('--hl', `${b.left + (outside ? stage.x : 0)}px`);
  panel.style.setProperty('--ht', `${b.top + (outside ? stage.y : 0)}px`);
  panel.style.setProperty('--hw', `${b.width}px`);
  panel.style.setProperty('--hh', `${b.height}px`);
  panel.style.setProperty('--hs', String(s));
}

/* The answer sits under Apollo wherever he is, LYLA's card under her bar,
 * and the scanner's report grows out of its line. */
function hudFollowers(stage = stageBox()) {
  const { core, lyla, scan } = state.hud.items;
  if (core) {
    const r = Hud.toPixels(core, stage);
    const half = Math.min(450, window.innerWidth * 0.31);
    $('answer').style.setProperty('--al', `${Math.min(Math.max(r.x + r.w / 2, half + 16), stage.w - half - 16)}px`);
    $('answer').style.setProperty('--at', `${r.y + r.h * 0.795}px`);
  }
  if (lyla) {
    const r = Hud.toPixels(lyla, stage);
    $('lyla-agent').style.setProperty('--ll', `${r.x}px`);
    $('lyla-agent').style.setProperty('--lt', `${r.y + r.h + 6}px`);
    $('lyla-agent').style.setProperty('--lw', `${Math.max(r.w, 420)}px`);
  }
  const block = $('scan-block');
  block.classList.toggle('hud-grow', Boolean(scan) && !state.hudEdit);
  block.classList.toggle('up', Boolean(scan) && (scan.y + scan.h / 2) > 0.5);
}

function applyHud() {
  const stage = stageBox();
  document.body.classList.toggle('hud-free', hudFree());
  for (const id of Hud.PANELS) {
    const panel = panelOf(id);
    if (!panel) continue;
    panel.classList.add('hud-panel');
    panel.classList.toggle('hud-whole', Hud.WHOLE.has(id));
    const item = state.hud.items[id];
    panel.classList.toggle('hud-hidden', Boolean(hudFree() && item && item.hidden));
    if (!hudFree() || !item) {
      for (const name of ['--hl', '--ht', '--hw', '--hh', '--hs']) panel.style.removeProperty(name);
      continue;
    }
    placePanel(id, Hud.toPixels(item, stage), item.s, stage);
  }
  if (hudFree()) hudFollowers(stage);
  if (state.hudEdit) drawFrames();
}
window.addEventListener('resize', () => applyHud());

let hudSaving = null;
function saveHud() {
  clearTimeout(hudSaving);
  hudSaving = setTimeout(() => {
    const api = bridge();
    if (api && api.save_hud) api.save_hud(state.hud);
  }, 350);
}

/* The first arrangement: every panel taken from where the grid put it. One
 * not on the screen right now starts small in the middle, hidden. */
function captureHud() {
  const stage = stageBox();
  const items = {};
  for (const id of Hud.PANELS) {
    const rect = seenRect(id, stage);
    const seen = rect.w > 2 && rect.h > 2;
    items[id] = Hud.toItem(seen ? rect : { x: stage.w * 0.4, y: stage.h * 0.4, w: stage.w * 0.2, h: stage.h * 0.1 },
                           stage, 1, !seen);
  }
  state.hud = Hud.sanitize({ free: true, items });
}

/* A change that is not a drag - a scale step, a panel hidden, a nudge -
 * eases into place. */
function easeHud(ids, change) {
  for (const id of ids) panelOf(id).classList.add('hud-easing');
  change();
  applyHud();
  setTimeout(() => ids.forEach((id) => panelOf(id).classList.remove('hud-easing')), 320);
}

// -- the editor -------------------------------------------------------------------------

const EYE = '<svg viewBox="0 0 16 16"><path d="M1.5 8s2.4-4.5 6.5-4.5S14.5 8 14.5 8 12.1 12.5 8 12.5 1.5 8 1.5 8z"/><circle cx="8" cy="8" r="2"/></svg>';
const EYE_SHUT = '<svg viewBox="0 0 16 16"><path d="M2 2l12 12M6.2 3.8C6.8 3.6 7.4 3.5 8 3.5c4.1 0 6.5 4.5 6.5 4.5a11 11 0 0 1-2 2.6M9.8 12.2c-.6.2-1.2.3-1.8.3-4.1 0-6.5-4.5-6.5-4.5a11 11 0 0 1 2-2.6"/></svg>';

function frameStyle(rect, stage) {
  return `left:${stage.x + rect.x}px;top:${stage.y + rect.y}px;width:${rect.w}px;height:${rect.h}px`;
}

/* The frames: drawn afresh - flying in one after another - as the editor
 * opens, and after that only moved and relabelled, so the one in your hand
 * is never taken from under it. */
function drawFrames() {
  const stage = stageBox();
  const frames = $('hud-frames');
  if (frames.children.length) {
    for (const id of Hud.PANELS) {
      const item = state.hud.items[id];
      const frame = frames.querySelector(`.hud-frame[data-hud="${id}"]`);
      if (!item || !frame) continue;
      moveFrame(id, Hud.toPixels(item, stage), stage);
      frame.classList.toggle('is-hidden', item.hidden);
      frame.querySelector('.hud-tag em').textContent = `${Math.round(item.s * 100)}%`;
      const eye = frame.querySelector('[data-hud-act="hide"]');
      eye.innerHTML = item.hidden ? EYE_SHUT : EYE;
      eye.title = item.hidden ? 'Show it' : 'Hide it';
    }
    return;
  }
  frames.innerHTML = Hud.PANELS.map((id, i) => {
    const item = state.hud.items[id];
    if (!item) return '';
    const rect = Hud.toPixels(item, stage);
    // Its tag sits over the frame, unless the frame is at the top of the screen.
    const inside = stage.y + rect.y < 40;
    return `<div class="hud-frame${item.hidden ? ' is-hidden' : ''}${Hud.WHOLE.has(id) ? ' whole' : ''}${state.hudPick === id ? ' picked' : ''}${inside ? ' tag-in' : ''}"
        data-hud="${id}" style="${frameStyle(rect, stage)};--i:${i}">
      <div class="hud-tag"><b>${Hud.NAMES[id]}</b><em>${Math.round(item.s * 100)}%</em>
        <button type="button" data-hud-act="smaller" data-sfx="none" title="Smaller inside">−</button>
        <button type="button" data-hud-act="bigger" data-sfx="none" title="Bigger inside">+</button>
        <button type="button" data-hud-act="hide" data-sfx="none" title="${item.hidden ? 'Show it' : 'Hide it'}">${item.hidden ? EYE_SHUT : EYE}</button>
      </div>
      <i class="hud-handle" data-corner="nw"></i><i class="hud-handle" data-corner="ne"></i>
      <i class="hud-handle" data-corner="sw"></i><i class="hud-handle" data-corner="se"></i>
    </div>`;
  }).join('');
}

function moveFrame(id, rect, stage = stageBox()) {
  const frame = document.querySelector(`.hud-frame[data-hud="${id}"]`);
  if (!frame) return;
  frame.setAttribute('style', `${frameStyle(rect, stage)};--i:0;opacity:1;animation:none`);
  frame.classList.toggle('tag-in', stage.y + rect.y < 40);
}
function clearFrames() {
  $('hud-frames').innerHTML = '';
}

function showGuides(lines, stage = stageBox()) {
  $('hud-guides').innerHTML = lines.map((line) => (line.axis === 'x'
    ? `<i class="hud-guide x" style="left:${stage.x + line.at}px"></i>`
    : `<i class="hud-guide y" style="top:${stage.y + line.at}px"></i>`)).join('');
}

function othersThan(id, stage) {
  return Hud.PANELS.filter((other) => other !== id && state.hud.items[other] && !state.hud.items[other].hidden)
    .map((other) => Hud.toPixels(state.hud.items[other], stage));
}

function enterHudEdit() {
  if (state.hudEdit) return;
  if (state.view !== 'normal' || ultraOn() || state.osiris) {
    // Arranged in the normal display, so that is where it goes first.
    setMode('normal');
    setTimeout(enterHudEdit, 1300);
    return;
  }
  closeScan();
  closeStory();
  closeStock();
  if (agent.open) toggleAgent();
  if (!hudFree()) captureHud();
  state.hudEdit = true;
  document.body.classList.add('hud-editing');
  $('hud-edit').setAttribute('aria-hidden', 'false');
  sfx.play('expand');
  clearFrames();
  applyHud();
}

function exitHudEdit() {
  if (!state.hudEdit) return;
  state.hudEdit = false;
  state.hudPick = null;
  document.body.classList.remove('hud-editing');
  $('hud-edit').setAttribute('aria-hidden', 'true');
  clearFrames();
  $('hud-guides').innerHTML = '';
  sfx.play('collapse');
  applyHud();
  saveHud();
}

/* Every panel home, flown there: where each is now is measured, the grid
 * lays them out, and each starts from where it was and eases to where it
 * belongs - a little after the one before. */
function resetHud() {
  const firsts = Object.fromEntries(Hud.PANELS.map((id) => [id, panelOf(id).getBoundingClientRect()]));
  state.hud = Hud.emptyHud();
  applyHud();
  if (state.hudEdit) { captureHud(); applyHud(); }
  sfx.play('swap');
  Hud.PANELS.forEach((id, i) => {
    const panel = panelOf(id);
    const first = firsts[id];
    const last = panel.getBoundingClientRect();
    if (!first.width || !last.width) return;
    const dx = (first.left + first.width / 2) - (last.left + last.width / 2);
    const dy = (first.top + first.height / 2) - (last.top + last.height / 2);
    panel.classList.remove('hud-flip');
    panel.style.translate = `${dx}px ${dy}px`;
    panel.style.scale = String(first.width / last.width);
    void panel.offsetWidth;
    panel.style.setProperty('--flip-delay', `${i * 0.035}s`);
    panel.classList.add('hud-flip');
    panel.style.translate = '';
    panel.style.scale = '';
    setTimeout(() => panel.classList.remove('hud-flip'), 700 + i * 35);
  });
  saveHud();
}

// -- the hands --------------------------------------------------------------------------

let hudHand = null;

function handLoop(now) {
  const hand = hudHand;
  if (!hand || hand.kind !== 'move') return;
  const stage = stageBox();
  // The spring is stepped once per sixtieth of a second, however often the
  // screen is drawn, so it feels the same on a slow frame.
  const steps = Math.min(4, Math.max(1, Math.round((now - (hand.at || now - 16.7)) / 16.7)));
  hand.at = now;
  for (let i = 0; i < steps; i++) {
    [hand.pos.x, hand.vel.x] = Hud.spring(hand.pos.x, hand.vel.x, hand.target.x);
    [hand.pos.y, hand.vel.y] = Hud.spring(hand.pos.y, hand.vel.y, hand.target.y);
    // It leans into the way it is going, and straightens as it slows.
    const lean = Math.max(-6, Math.min(6, hand.vel.x * 0.45));
    [hand.tilt, hand.tiltV] = Hud.spring(hand.tilt, hand.tiltV, hand.let ? 0 : lean, { stiffness: 0.18, damping: 0.7 });
  }
  const rect = { x: hand.pos.x, y: hand.pos.y, w: hand.start.w, h: hand.start.h };
  placePanel(hand.id, rect, hand.s, stage);
  panelOf(hand.id).style.rotate = `${hand.tilt.toFixed(2)}deg`;
  moveFrame(hand.id, rect, stage);
  const still = Math.abs(hand.vel.x) + Math.abs(hand.vel.y) < 0.08
    && Math.abs(hand.target.x - hand.pos.x) + Math.abs(hand.target.y - hand.pos.y) < 0.4
    && Math.abs(hand.tilt) < 0.05;
  if (hand.let && still) {
    settleHand(hand, { x: hand.target.x, y: hand.target.y, w: hand.start.w, h: hand.start.h });
    return;
  }
  requestAnimationFrame(handLoop);
}

function settleHand(hand, rect) {
  const stage = stageBox();
  const was = state.hud.items[hand.id];
  state.hud.items[hand.id] = Hud.toItem(rect, stage, hand.s, was.hidden);
  const panel = panelOf(hand.id);
  panel.style.rotate = '';
  panel.classList.remove('hud-lifted');
  hudHand = null;
  showGuides([]);
  applyHud();
  saveHud();
}

$('hud-frames').addEventListener('pointerdown', (event) => {
  const frame = event.target.closest('.hud-frame');
  if (!frame || event.button !== 0 || event.target.closest('.hud-tag button')) return;
  if (event.target.closest('.hud-tag') && !event.target.closest('.hud-tag b')) return;
  event.preventDefault();
  // One still settling from the last drag is put where it was going first.
  if (hudHand) {
    const was = hudHand;
    settleHand(was, was.kind === 'move' ? { ...was.start, x: was.target.x, y: was.target.y } : was.rect);
  }
  const id = frame.dataset.hud;
  const stage = stageBox();
  const item = state.hud.items[id];
  const start = Hud.toPixels(item, stage);
  const corner = event.target.closest('.hud-handle')?.dataset.corner || null;
  state.hudPick = id;
  document.querySelectorAll('.hud-frame.picked').forEach((f) => f.classList.remove('picked'));
  frame.classList.add('picked', 'active');
  frame.setPointerCapture(event.pointerId);
  hudHand = {
    id, kind: corner ? 'size' : 'move', corner, start, s: item.s, s0: item.s,
    px: event.clientX, py: event.clientY, pos: { x: start.x, y: start.y }, vel: { x: 0, y: 0 },
    target: { x: start.x, y: start.y }, tilt: 0, tiltV: 0, let: false, rect: start,
  };
  panelOf(id).classList.add('hud-lifted');
  sfx.play('grain');
  if (!corner) requestAnimationFrame(handLoop);
});

$('hud-frames').addEventListener('pointermove', (event) => {
  const hand = hudHand;
  if (!hand || hand.let) return;
  const stage = stageBox();
  const dx = event.clientX - hand.px;
  const dy = event.clientY - hand.py;
  const others = othersThan(hand.id, stage);
  if (hand.kind === 'move') {
    const raw = { x: hand.start.x + dx, y: hand.start.y + dy, w: hand.start.w, h: hand.start.h };
    const snapped = state.hudSnap ? Hud.snap(raw, others, stage) : { rect: Hud.clampInto(raw, stage), lines: [] };
    hand.target = { x: snapped.rect.x, y: snapped.rect.y };
    showGuides(snapped.lines, stage);
    return;
  }
  const whole = Hud.WHOLE.has(hand.id);
  const sized = Hud.resize(hand.start, hand.corner, dx, dy, stage,
                           { others, whole, pull: state.hudSnap ? Hud.PULL : 0, grid: state.hudSnap ? Hud.GRID : 1 });
  let rect = sized.rect;
  if (whole) {
    // A whole panel is its scale: the corner makes all of it larger.
    hand.s = Math.min(Hud.SCALE_MAX, Math.max(Hud.SCALE_MIN, hand.s0 * sized.k));
    const k = hand.s / hand.s0;
    const w = hand.start.w * k;
    const h = hand.start.h * k;
    rect = Hud.clampInto({ x: hand.corner.includes('w') ? hand.start.x + hand.start.w - w : hand.start.x,
                           y: hand.corner.includes('n') ? hand.start.y + hand.start.h - h : hand.start.y, w, h }, stage);
  }
  hand.rect = rect;
  placePanel(hand.id, rect, hand.s, stage);
  moveFrame(hand.id, rect, stage);
  showGuides(sized.lines, stage);
});

function letGo(event) {
  const hand = hudHand;
  if (!hand || hand.let) return;
  const frame = event.target.closest('.hud-frame');
  if (frame) frame.classList.remove('active');
  hand.let = true;
  sfx.play('swap');
  if (hand.kind === 'size') settleHand(hand, hand.rect);
}
$('hud-frames').addEventListener('pointerup', letGo);
$('hud-frames').addEventListener('pointercancel', letGo);

/* What is inside a panel, a step larger or smaller - a whole panel grows
 * about its middle. */
function scaleHud(id, steps) {
  const item = state.hud.items[id];
  if (!item) return;
  const s = Hud.scaled(item.s, steps);
  if (s === item.s) return;
  sfx.play(steps > 0 ? 'show' : 'hide');
  easeHud([id], () => {
    const stage = stageBox();
    if (Hud.WHOLE.has(id)) {
      const r = Hud.toPixels(item, stage);
      const k = s / item.s;
      const rect = Hud.clampInto({ x: r.x + (r.w - r.w * k) / 2, y: r.y + (r.h - r.h * k) / 2, w: r.w * k, h: r.h * k }, stage);
      state.hud.items[id] = Hud.toItem(rect, stage, s, item.hidden);
    } else {
      state.hud.items[id] = { ...item, s };
    }
  });
  saveHud();
}

$('hud-frames').addEventListener('click', (event) => {
  const button = event.target.closest('[data-hud-act]');
  if (!button) return;
  const id = button.closest('.hud-frame').dataset.hud;
  const act = button.dataset.hudAct;
  if (act === 'bigger') scaleHud(id, 1);
  if (act === 'smaller') scaleHud(id, -1);
  if (act === 'hide') {
    const item = state.hud.items[id];
    sfx.play(item.hidden ? 'show' : 'hide');
    easeHud([id], () => { state.hud.items[id] = { ...item, hidden: !item.hidden }; });
    saveHud();
  }
});

$('hud-frames').addEventListener('dblclick', (event) => {
  const frame = event.target.closest('.hud-frame');
  if (!frame || event.target.closest('.hud-tag button')) return;
  const item = state.hud.items[frame.dataset.hud];
  if (item && item.s !== 1) scaleHud(frame.dataset.hud, Math.round((1 - item.s) / Hud.SCALE_STEP));
});

$('hud-frames').addEventListener('wheel', (event) => {
  const frame = event.target.closest('.hud-frame');
  if (!frame) return;
  event.preventDefault();
  scaleHud(frame.dataset.hud, event.deltaY < 0 ? 1 : -1);
}, { passive: false });

$('hud-done').addEventListener('click', exitHudEdit);
$('hud-reset').addEventListener('click', resetHud);
$('hud-snap').addEventListener('click', () => {
  state.hudSnap = !state.hudSnap;
  $('hud-snap').setAttribute('aria-pressed', state.hudSnap ? 'true' : 'false');
  sfx.play(state.hudSnap ? 'check' : 'tick');
});

// F2 opens and closes it; Escape or Enter closes it; the arrows nudge the
// panel last touched - a grid step, or a pixel with Shift.
document.addEventListener('keydown', (event) => {
  if (event.key === 'F2') {
    event.preventDefault();
    if (state.hudEdit) exitHudEdit(); else enterHudEdit();
    return;
  }
  if (!state.hudEdit) return;
  if (event.key === 'Escape' || event.key === 'Enter') {
    event.preventDefault();
    event.stopImmediatePropagation();
    exitHudEdit();
    return;
  }
  const step = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[event.key];
  const id = state.hudPick;
  if (!step || !id || !state.hud.items[id]) return;
  event.preventDefault();
  const stage = stageBox();
  const by = event.shiftKey ? 1 : Hud.GRID;
  const r = Hud.toPixels(state.hud.items[id], stage);
  const rect = Hud.clampInto({ ...r, x: r.x + step[0] * by, y: r.y + step[1] * by }, stage);
  easeHud([id], () => { state.hud.items[id] = Hud.toItem(rect, stage, state.hud.items[id].s, state.hud.items[id].hidden); });
  saveHud();
}, true);

// The console's two live buttons: SCAN chooses a file, HUD arranges.
document.querySelector('[data-console="scan"]').addEventListener('click', () => pickFile());
document.querySelector('[data-console="hud"]').addEventListener('click', () => enterHudEdit());

$('ultra-grid').addEventListener('click', () => focusDisplay(null));
$('ultra-chips').addEventListener('click', (event) => {
  const chip = event.target.closest('[data-chip]');
  if (chip) showDisplay(chip.dataset.chip, !state.layout.items[chip.dataset.chip].shown);
});
// Two clicks, the first saying what the second does: a layout you built
// should not go to a stray click.
$('ultra-reset').addEventListener('click', (event) => {
  const button = event.currentTarget;
  const label = button.querySelector('span');
  clearTimeout(button._undo);
  if (!button.classList.contains('sure')) {
    button.classList.add('sure');
    label.textContent = 'RESET ALL?';
    button._undo = setTimeout(() => { button.classList.remove('sure'); label.textContent = 'RESET'; }, 3000);
    return;
  }
  button.classList.remove('sure');
  label.textContent = 'RESET';
  changeLayout(Tiles.setLayers(Tiles.setUltra(Tiles.defaultLayout(), true), state.layout.layers));
  powerOn();
});

/* --- a display's controls ----------------------------------------------------------- */

$('stage').addEventListener('click', (event) => {
  if (!ultraOn() || state.dragMoved) return;
  const tile = event.target.closest('[data-display]');
  if (!tile) return;
  const id = tile.dataset.display;
  if (tile.classList.contains('railed')) { focusDisplay(id); return; }
  const button = event.target.closest('[data-tile]');
  if (!button) {
    if (event.target.closest('.tile-min')) changeLayout(Tiles.setMin(state.layout, id, false));
    return;
  }
  const item = state.layout.items[id];
  if (button.dataset.tile === 'min') changeLayout(Tiles.setMin(state.layout, id, !item.min));
  if (button.dataset.tile === 'focus') focusDisplay(state.layout.focus === id ? null : id);
  if (button.dataset.tile === 'hide') changeLayout(Tiles.setShown(state.layout, id, false));
  if (button.dataset.tile === 'config') {
    if (state.configFor === id) closeConfig();
    else openConfig(id, button);
  }
});

$('stage').addEventListener('dblclick', (event) => {
  const handle = ultraOn() && event.target.closest('.tile-handle');
  if (!handle) return;
  const id = handle.closest('[data-display]').dataset.display;
  focusDisplay(state.layout.focus === id ? null : id);
});

/* Moved by the top edge, or by a minimized display's line; resized by the
 * corner. Only in the grid - an expanded display and its rail are laid out
 * for you. */
$('stage').addEventListener('pointerdown', (event) => {
  if (!ultraOn() || event.button !== 0 || state.layout.focus) return;
  const tile = event.target.closest('[data-display]');
  if (!tile) return;
  if (event.target.closest('.tile-resize')) startResize(tile, event);
  else if (event.target.closest('.tile-handle, .tile-min')) armDrag(tile, event);
});

/* Follow the pointer from `target` until it lets go. */
function track(target, event, move, done) {
  // Captured, so the pointer can leave the handle and still be followed. A
  // pointer that has already gone cannot be captured, and need not be.
  try { target.setPointerCapture(event.pointerId); } catch (error) { /* followed as it is */ }
  const up = () => {
    target.removeEventListener('pointermove', move);
    target.removeEventListener('pointerup', up);
    target.removeEventListener('pointercancel', up);
    done();
    // The click that ends a drag is not a click on anything.
    setTimeout(() => { state.dragMoved = false; }, 0);
  };
  target.addEventListener('pointermove', move);
  target.addEventListener('pointerup', up);
  target.addEventListener('pointercancel', up);
}

function armDrag(tile, event) {
  const start = { x: event.clientX, y: event.clientY };
  track(event.target, event, (e) => {
    if (!state.drag) {
      if (Math.hypot(e.clientX - start.x, e.clientY - start.y) < 6) return;
      beginDrag(tile, start);
    }
    dragTo(e.clientX, e.clientY);
  }, () => { if (state.drag) endDrag(); });
}

function beginDrag(tile, start) {
  const box = tile.getBoundingClientRect();
  state.drag = { tile, id: tile.dataset.display, grabX: start.x - box.left,
                 grabY: start.y - box.top, over: null };
  state.dragMoved = true;
  tile.classList.add('dragging');
  document.body.classList.add('arranging');
  closeConfig();
  scheduleOsiris();
}

/* Where a display's own place in the grid is on the screen, whatever
 * transform it is wearing. */
function gridPlace(tile) {
  const stage = $('stage').getBoundingClientRect();
  return { x: stage.left + tile.offsetLeft, y: stage.top + tile.offsetTop };
}

/* The display follows the pointer, and the one under the pointer is marked:
 * that is the one it trades places with when it is let go. Nothing else
 * moves while it is carried - swapping with every display it passed over
 * on the way would shuffle the whole screen. */
function dragTo(x, y) {
  const drag = state.drag;
  const place = gridPlace(drag.tile);
  drag.tile.style.transform = `translate(${(x - drag.grabX - place.x).toFixed(1)}px, `
                            + `${(y - drag.grabY - place.y).toFixed(1)}px)`;
  const under = document.elementsFromPoint(x, y)
    .map((element) => element.closest('[data-display]'))
    .find((tile) => tile && tile !== drag.tile && !tile.classList.contains('tile-off'));
  if (under === drag.over) return;
  if (drag.over) drag.over.classList.remove('drop-target');
  drag.over = under || null;
  if (drag.over) drag.over.classList.add('drop-target');
}

function endDrag() {
  const drag = state.drag;
  state.drag = null;
  drag.tile.classList.remove('dragging');
  document.body.classList.remove('arranging');
  if (drag.over) drag.over.classList.remove('drop-target');
  // Both go to their new places from where they are, the carried one from
  // under the pointer; let go over nothing, it goes back to its own.
  flip(() => {
    drag.tile.style.removeProperty('transform');
    if (drag.over) {
      sfx.play('swap');
      state.layout = Tiles.swap(state.layout, drag.id, drag.over.dataset.display);
      applyLayout();
    }
  });
  saveLayout();
  scheduleOsiris(480);
}

/* The grid's cells, measured off the page: its columns and gap from the
 * stage, its rows from the rows it has now. */
function gridMetrics() {
  const stage = $('stage');
  const style = getComputedStyle(stage);
  const gap = parseFloat(style.columnGap) || 12;
  const width = stage.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
  const height = stage.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom);
  const rows = Math.max(1, style.gridTemplateRows.split(' ').filter(Boolean).length);
  return { colW: (width - gap * (Tiles.COLUMNS - 1)) / Tiles.COLUMNS,
           rowH: (height - gap * (rows - 1)) / rows, gap };
}

function startResize(tile, event) {
  const id = tile.dataset.display;
  const item = state.layout.items[id];
  const from = { x: event.clientX, y: event.clientY, w: item.w, h: item.h, grid: gridMetrics() };
  state.resizing = { id, tile };
  state.dragMoved = true;
  tile.classList.add('resizing');
  document.body.classList.add('arranging');
  closeConfig();
  scheduleOsiris();
  track(event.target, event, (e) => {
    const spans = Tiles.spansFor({ w: from.w, h: from.h, dx: e.clientX - from.x,
                                   dy: e.clientY - from.y, ...from.grid });
    const now = state.layout.items[id];
    if (spans.w === now.w && spans.h === now.h) return;
    sfx.play('grain');
    flip(() => {
      state.layout = Tiles.resize(state.layout, id, spans.w, spans.h);
      applyLayout();
    });
  }, () => {
    state.resizing = null;
    tile.classList.remove('resizing');
    document.body.classList.remove('arranging');
    saveLayout();
    scheduleOsiris(420);
  });
}

/* --- a display's settings ------------------------------------------------------------ */

function openConfig(id, anchor) {
  sfx.play('open');
  state.configFor = id;
  const pop = $('tile-config');
  renderConfig();
  pop.classList.add('on');
  pop.setAttribute('aria-hidden', 'false');
  // Under the button that opened it, and on the screen.
  const box = anchor.getBoundingClientRect();
  const width = pop.offsetWidth, height = pop.offsetHeight;
  const x = Math.max(16, Math.min(window.innerWidth - width - 16, box.right - width));
  let y = box.bottom + 10;
  if (y + height > window.innerHeight - 16) y = Math.max(16, box.top - height - 10);
  pop.style.transform = `translate(${x}px, ${y}px)`;
  scheduleOsiris();                            // the map steps out from under it
}

function closeConfig() {
  if (!state.configFor) return;
  sfx.play('close');
  state.configFor = null;
  $('tile-config').classList.remove('on');
  $('tile-config').setAttribute('aria-hidden', 'true');
  scheduleOsiris(200);
}

function renderConfig() {
  const id = state.configFor;
  if (!id) return;
  const item = state.layout.items[id];
  const button = (label, act, extra = '', on = false) =>
    `<button type="button" class="cfg-btn${on ? ' on' : ''}" data-cfg="${act}" ${extra}>${label}</button>`;
  const sizes = Object.entries(Tiles.SIZES).map(([name, [w, h]]) =>
    button(name, 'size', `data-size="${name}"`, item.w === w && item.h === h)).join('');
  let own = '';
  if (id === 'feed') {
    own = `<div class="cfg-row"><span>Topic</span>${TOPICS.map((topic, i) =>
      button(esc(topic), 'topic', `data-topic="${i}"`, i === state.topic)).join('')}</div>`;
  }
  if (id === 'osiris') {
    own = `<div class="cfg-row"><span>Layers</span></div><div class="cfg-layers">${Tiles.LAYERS.map((layer) =>
      button(LAYER_NAMES[layer], 'layer', `data-layer="${layer}"`, state.layout.layers.includes(layer))).join('')}</div>
      <p class="cfg-note">The map loads again with the layers you pick.</p>`;
  }
  $('tile-config').innerHTML = `
    <header><b>${Tiles.NAMES[id]}</b><span>Settings</span>${button(ICON.hide, 'close', 'title="Close"')}</header>
    <div class="cfg-row"><span>Size</span>${sizes}</div>
    <div class="cfg-row"><span>Width</span>${button('−', 'w', 'data-by="-1"')}<b>${item.w} columns</b>${button('+', 'w', 'data-by="1"')}</div>
    <div class="cfg-row"><span>Height</span>${button('−', 'h', 'data-by="-1"')}<b>${item.h} rows</b>${button('+', 'h', 'data-by="1"')}</div>
    ${own}
    <div class="cfg-row"><span>Show</span>${button(item.min ? 'Restore' : 'Minimize', 'min')}${
      button(state.layout.focus === id ? 'Grid' : 'Expand', 'focus')}${button('Hide', 'hide')}</div>`;
}

$('tile-config').addEventListener('click', (event) => {
  const button = event.target.closest('[data-cfg]');
  const id = state.configFor;
  if (!button || !id) return;
  const item = state.layout.items[id];
  const act = button.dataset.cfg;
  if (act === 'close') closeConfig();
  if (act === 'size') {
    const [w, h] = Tiles.SIZES[button.dataset.size];
    changeLayout(Tiles.resize(state.layout, id, w, h));
  }
  if (act === 'w') changeLayout(Tiles.resize(state.layout, id, item.w + Number(button.dataset.by), item.h));
  if (act === 'h') changeLayout(Tiles.resize(state.layout, id, item.w, item.h + Number(button.dataset.by)));
  if (act === 'topic') {
    state.topic = Number(button.dataset.topic) || 0;
    closeStory();
    if (state.snapshot) renderFeed(state.snapshot);
    renderConfig();
  }
  if (act === 'layer') {
    const layer = button.dataset.layer;
    const layers = state.layout.layers.includes(layer)
      ? state.layout.layers.filter((kept) => kept !== layer) : [...state.layout.layers, layer];
    changeLayout(Tiles.setLayers(state.layout, layers), { animate: false });
    const api = bridge();
    if (api && api.osiris_layers) api.osiris_layers(state.layout.layers);
  }
  if (act === 'min') changeLayout(Tiles.setMin(state.layout, id, !item.min));
  if (act === 'focus') { closeConfig(); focusDisplay(state.layout.focus === id ? null : id); }
  if (act === 'hide') { closeConfig(); changeLayout(Tiles.setShown(state.layout, id, false)); }
});

// Anywhere else, and the settings close.
document.addEventListener('pointerdown', (event) => {
  if (state.configFor && !event.target.closest('#tile-config, [data-tile="config"]')) closeConfig();
}, true);

/* --- the choreography ------------------------------------------------------ */

/* The panels rise in once, the first time anyone can actually see them.
 *
 * A hidden page gets no animation frames at all, so an entrance started while
 * Apollo is still an orb would never move: every panel would sit at the
 * opacity: 0 it starts from, and the display would open empty. So it waits
 * for the page to be shown - which is also when the count-up and the
 * sparkline draw are worth spending. */
/* Put the panels in their resting state and hand opacity back to the
 * stylesheet. The inline styles Motion writes while it animates would
 * otherwise outrank every rule that comes later - including the dim that
 * clears the room while Apollo is answering. */
function settle() {
  document.querySelectorAll('.rise').forEach((panel) => {
    panel.style.removeProperty('opacity');
    panel.style.removeProperty('transform');
    panel.classList.add('assembled');
  });
}

function enter() {
  if (state.entered) return;
  // Hidden: no frames, so assemble the page outright. If it is shown later
  // the entrance plays then; if it is never shown, nothing was wasted.
  if (document.hidden) { settle(); return; }
  state.entered = true;
  [...document.querySelectorAll('.rise')].forEach((panel, i) => {
    animate(panel, RISE, { ...SPRING, delay: i * 0.04 });
  });
  // Timers still run where animation frames do not. If the entrance has not
  // landed by now - frames throttled, Motion missing, anything - the panels
  // go to their resting state anyway. A display that opens blank is a worse
  // failure than one that opens without its flourish.
  clearTimeout(state.settleTimer);
  state.settleTimer = setTimeout(settle, 1200);
  // The first paint's flourishes are spent; re-render so they are not
  // repeated and the rows settle into their resting form.
  if (state.snapshot) render(state.snapshot);
}

document.addEventListener('visibilitychange', () => enter());

/* What the display says it is doing. Each state has to be visible on its own
 * and has to lead to the next: holding the chord used to change nothing here
 * at all, so the display simply went quiet and you could not tell whether it
 * had heard you. */
/* What the matrix plays while Apollo is working. `activity` swaps the words
 * for whatever he is actually doing - fetching NVDA, searching the web - and
 * the sequence goes on underneath it. */
const THINKING = [
  { title: 'Thinking', frames: FRAMES.importing, duration: 170 },
  { title: 'Working', frames: FRAMES.syncing, duration: 110, repeatCount: 2 },
  { title: 'Looking', frames: FRAMES.searching, duration: 140, repeatCount: 2 },
];

const dots = new DotFlow($('thinking'), { dotSize: 8, gap: 4 });

const SAYS = {
  idle: 'Hold Ctrl+Alt to talk',
  listening: 'Listening',
  thinking: 'Thinking',
  speaking: '',
};

function setPhase(phase) {
  if (phase === state.phase) return;
  state.phase = phase;
  lyla.setPhase(phase);
  // Heard as the old page had it: a sound as Apollo starts listening and
  // one as its answer comes - none on thinking, which starts before there
  // is anything to have heard (a cough, a chord pressed by accident); your
  // words get theirs when they arrive (turn).
  if (phase === 'listening') sfx.play('listen');
  if (phase === 'speaking') sfx.play('rev');

  const answering = phase === 'thinking' || phase === 'speaking';
  const attending = phase !== 'idle';
  // Apollo goes small into the corner while he answers (explain.js), and
  // the box stays up a while after he stops, so it can still be read.
  if (answering) placeMini();
  linger(!answering && phase === 'idle' && Boolean($('reply').textContent || $('visual').innerHTML));
  $('ex-state').textContent = { listening: 'Listening', thinking: 'Thinking', speaking: 'Speaking' }[phase] || 'Done';
  document.body.classList.toggle('listening', phase === 'listening');
  document.body.classList.toggle('thinking', phase === 'thinking');
  document.body.classList.toggle('answering', answering);
  $('answer').classList.toggle('show', answering || document.body.classList.contains('lingering'));
  // The room steps back as far as the state warrants: a little while it is
  // listening to you, all the way once it is answering.
  shader.speed(phase === 'thinking' ? 2.2 : attending ? 1.5 : 1);

  const hint = $('hint');
  // The matrix carries the word while it is working, so the hint stands down
  // rather than saying "Thinking" a second time just above it.
  hint.textContent = phase === 'thinking' ? '' : (SAYS[phase] || '');
  hint.classList.toggle('busy', attending && phase !== 'thinking');

  // The matrix replaces the word "Thinking" entirely while it is working.
  $('thinking').classList.toggle('on', phase === 'thinking');
  if (phase === 'thinking') dots.play(THINKING);
  else dots.stop();

  // In ultra mode the map steps aside while there is an answer on screen.
  if (ultraOn()) {
    scheduleOsiris(400);
    renderSummaries();
  }

  if (phase === 'listening') {
    $('you').textContent = '';
    $('reply').textContent = '';
    $('visual').innerHTML = '';
  }
}

/* Where Apollo goes while he answers: the corner, measured from where he is
 * laid out (not where his transform has him), every time he goes there. */
function placeMini() {
  const shift = Explain.cornerShift($('core'));
  if (!shift) return;
  const root = document.body.style;
  root.setProperty('--mini-dx', `${shift.dx}px`);
  root.setProperty('--mini-dy', `${shift.dy}px`);
  root.setProperty('--mini-s', String(shift.scale));
}

/* The answer stays on screen for a while after he has finished - long
 * enough to read it - unless you start talking again. */
const LINGER_MS = 12000;
let lingerTimer = null;
function linger(on) {
  clearTimeout(lingerTimer);
  document.body.classList.toggle('lingering', on);
  $('answer').classList.toggle('show', on || document.body.classList.contains('answering'));
  if (on) {
    lingerTimer = setTimeout(() => {
      document.body.classList.remove('lingering');
      $('answer').classList.remove('show');
    }, LINGER_MS);
  }
}

/* Your voice, as the ring's breath. The overlay has always reacted to this;
 * the display ignored it, which is half of why holding the chord looked like
 * nothing happening. */
function setLevel(value) {
  state.level = Math.max(0, Math.min(1, Number(value) || 0));
}

/* The reply arrives a word at a time - low, blurred, and on a stagger - the
 * same reveal the overlay's card does, from the same brief. It used to cross-
 * fade as one block, which is what "not smooth" meant: forty words appearing
 * together is a cut, not an animation. */
const WORD_STAGGER = 0.045;

function reveal(element, text) {
  const words = String(text || '').trim().split(/\s+/).filter(Boolean);
  element.setAttribute('dir', /[֐-ࣿ]/.test(text) ? 'rtl' : 'ltr');
  element.textContent = '';
  if (!words.length) return;
  const fragment = document.createDocumentFragment();
  for (const word of words) {
    const span = document.createElement('span');
    span.textContent = word;
    fragment.appendChild(span);
  }
  element.appendChild(fragment);
  // Hidden pages get no frames, so the words would sit at opacity 0 for as
  // long as the display stayed closed. There is nothing to reveal to nobody.
  if (document.hidden) {
    element.classList.add('shown');
    return;
  }
  element.classList.remove('shown');
  [...element.children].forEach((span, i) => {
    animate(span, {
      opacity: [0, 1],
      transform: ['translateY(14px)', 'translateY(0px)'],
      filter: ['blur(7px)', 'blur(0px)'],
    }, { duration: 0.55, delay: i * WORD_STAGGER, ease: [0.215, 0.61, 0.355, 1] });
  });
}

function chart(visual) {
  const chartData = visual && visual.chart;
  if (!chartData || !chartData.points || chartData.points.length < 2) return '';
  const points = chartData.points;
  const low = Math.min(...points), high = Math.max(...points);
  const span = high - low || 1;
  const step = 880 / (points.length - 1);
  const line = points.map((value, i) =>
    `${i ? 'L' : 'M'}${(i * step).toFixed(1)},${(150 - ((value - low) / span) * 130).toFixed(1)}`).join('');
  return `<svg viewBox="0 0 880 170" preserveAspectRatio="none">
    <defs>
      <linearGradient id="stroke" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="#a77be0"/><stop offset=".6" stop-color="#5fd0dc"/>
        <stop offset="1" stop-color="#f0c060"/>
      </linearGradient>
      <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#5fd0dc" stop-opacity=".28"/>
        <stop offset="1" stop-color="#a77be0" stop-opacity="0"/>
      </linearGradient>
    </defs>
    <path d="${line}L880,170L0,170Z" fill="url(#fill)"/>
    <path d="${line}" fill="none" stroke="url(#stroke)" stroke-width="2.6"
          stroke-linejoin="round" stroke-linecap="round"/>
  </svg>`;
}

/* --- what apollo.py calls --------------------------------------------------- */

window.apollo = {
  status(phase) {
    const map = { Waking: 'idle', Idle: 'idle', Listening: 'listening',
                  Thinking: 'thinking', Speaking: 'speaking' };
    setPhase(map[phase] || 'idle');
    $('dots').innerHTML = `
      <span><i class="${phase === 'Error' ? 'off' : 'ok'}">●</i>GEMINI LIVE</span>
      <span><i class="ok">●</i>CLAUDE READY</span>
      <span><i class="${phase === 'Listening' ? 'ok' : ''}" style="color:var(--accent)">●</i>MIC</span>`;
  },
  turn(who, text) {
    if (who === 'You') {
      sfx.play('heard');
      $('you').textContent = text;
      return;
    }
    reveal($('reply'), text);
  },
  // A chart or figures a tool drew for this turn, in the box.
  visual(payload) { $('visual').innerHTML = Explain.markup(payload, chart); },
  // A picture, steps or text Apollo wants to show you (the explain tools).
  explain(payload) {
    $('visual').innerHTML = Explain.markup(payload, chart);
    if (!document.body.classList.contains('answering')) linger(true);
    $('answer').classList.add('show');
    return true;
  },
  data(snapshot) { render(snapshot); },
  // "Show my projects": one tab of the side panel.
  tab(name) { showTab(String(name || '')); },
  // Trades from the stream, {symbol: {price, time}}, about once a second.
  live(batch) { applyLive(batch); },
  activity(text) {
    if (state.phase === 'thinking' && text) dots.say(text);
  },
  note(text) {
    const note = $('note');
    note.textContent = text || '';
    note.classList.toggle('show', Boolean(text));
    clearTimeout(note._timer);
    note._timer = setTimeout(() => note.classList.remove('show'), 6000);
  },
  fatal(text) { window.apollo.note(text); },
  mode(name) {
    const was = state.mode;
    state.mode = name;
    // The display up, or away again - not while the intro has the screen,
    // which has its own.
    const up = name === 'full';
    if (was !== name && !$('intro').classList.contains('on')) sfx.play(up ? 'hud' : 'down');
    // The overlay has the screen while Apollo is at rest; a shader drawing to
    // a window nobody can see is a GPU burning for nothing.
    // Nothing on the sign moves while nobody can see it.
    document.body.classList.toggle('offscreen', name !== 'full');
    // ...and the SVGs' own animations (LYLA's agent map), which no
    // stylesheet reaches.
    document.querySelectorAll('svg').forEach((svg) => {
      if (up) svg.unpauseAnimations(); else svg.pauseAnimations();
    });
    if (name === 'full') {
      shader.start();
      if (!asleep.on) { if (roomShown()) lyla.start(); ringStart(); }
      else sleepWord.start();
      enter();
    } else {
      shader.stop(); lyla.stop(); ringStop();
      sleepWord.stop();
      unlight();
      unlightRow();
    }
  },
  level(value) { setLevel(value); },
  panels(state) { setPanels(state); },
  briefing(payload) { if (payload) render(payload); },
  sleep(on) { setSleep(on); },
  // A step of an agent's run, as it happens. The crew's go to their own
  // cards; LYLA's to both of hers.
  agent(event) {
    const step = event || {};
    if (step.agent && step.agent !== 'LYLA') {
      const card = agentCards[step.agent];
      if (!card) return;
      card.live(step);
      crewDoing[step.agent] = step.stage !== 'done' && step.stage !== 'error';
      if (state.view === 'agents') renderMarks();
      return;
    }
    agent.live(step);
    agentsCard.live(step);
    // A job Apollo handed her shows under her bar while she is on it, and
    // what she found joins her reports.
    if (step.job) {
      const on = step.stage !== 'done' && step.stage !== 'error';
      lylaDoing.job = on ? `ON A JOB${step.symbol ? ` · ${step.symbol}` : ''}` : '';
      lylaDoing.show();
    }
    if (state.view === 'agents') renderMarks();
    if (step.stage === 'done' && step.report) {
      state.lylaReports.unshift({ task: step.task, symbol: step.symbol, summary: step.text,
                                  report: step.report, brain: step.brain, done: Date.now() / 1000 });
      state.lylaReports.length = Math.min(state.lylaReports.length, 20);
      state.reportOpen = -1;
      renderReports();
    }
  },
  // Which of Apollo's own modes are on - away, hands-free - for the bar.
  states(states) {
    const given = states || {};
    if ('away' in given) state.away = Boolean(given.away);
    if ('listening' in given) state.listening = Boolean(given.listening);
    renderOwnModes();
  },
  // As Apollo comes up: the name, once, blurring away into the display.
  intro() { playIntro(); },
  // A line of the boot screen, and the boot done (apollo.py).
  boot(step) {
    if (!step) return;
    boot.steps.push(step);
    boot.arrivals.push(performance.now());
    if (Number.isFinite(step.total)) boot.total = step.total;
  },
  bootDone(summary) { if (!boot.done) boot.done = summary || bootSoFar(); },
  // What is wrong, for the System panel; and the checks run again, done.
  issues(items) { renderIssues(items); },
  // The scanner: a file scanning, each step, and the report (apollo.py).
  scan(event) { onScan(event); },
  checked(summary) {
    state.rechecking = false;
    sfx.play(summary && summary.issues ? 'alert' : 'clean');
    renderIssues();
  },
  // OSIRIS in the display, or not - by voice, or its window closed itself.
  osiris(on) { return setOsiris(on); },
  // Ultra mode's displays: on or off, one expanded, one shown or hidden - or
  // the layout apollo.py kept, as the display opens.
  display(request) {
    const asked = request || {};
    if (asked.action === 'layout') adoptLayout(asked.layout);
    if (asked.action === 'ultra') setUltra(Boolean(asked.on));
    if (asked.action === 'focus') focusDisplay(asked.id || null);
    if (asked.action === 'show' || asked.action === 'hide') showDisplay(asked.id, asked.action === 'show');
    if (asked.action === 'mode') setMode(String(asked.mode || ''));
    if (asked.action === 'scan') pickFile();
    // The layout as the display opens carries the normal display's HUD too.
    if (asked.action === 'layout' && 'hud' in asked) { state.hud = Hud.sanitize(asked.hud); applyHud(); }
    if (asked.action === 'hud_edit') {
      if (asked.do === 'edit') enterHudEdit();
      if (asked.do === 'done') exitHudEdit();
      if (asked.do === 'reset') resetHud();
    }
    return { ultra: state.layout.ultra, focus: state.layout.focus, mode: Modes.current(modeFlags()) };
  },
  // "Open story three": opens it and says what it is. 0 closes it.
  story(number) {
    number = Number(number) || 0;
    if (!number) { closeStory(); return { closed: true }; }
    return openStory(number - 1);
  },
  // "Open Nvidia": opens it out of its card and says what it shows. An empty
  // symbol closes it.
  stock(symbol) {
    symbol = String(symbol || '');
    if (!symbol) { closeStock(); return { closed: true }; }
    return openStock(symbol);
  },
};

render(SAMPLE);
