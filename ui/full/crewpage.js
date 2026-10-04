/* The crew, on one page: you and Apollo on the left, a wire to each agent,
 * and each agent as a lane - who it is, where its job has got to (received,
 * reading, thinking, done), and what it is on or what it last turned out.
 * Click a lane for what it takes, its live steps, and every result, each
 * one opening. Under them, the day in five numbers.
 *
 * Two looks, switched at the top right: MINIMAL, flat and quiet, and
 * CONSOLE, glass and metal, whose number panels sit on a grid that glows and
 * flickers like an old lit screen. Everything shown comes from crew.board
 * (Python); nothing is made up. */

import { creature, health, IO } from './crewview.js';

let analysisHtml = () => '';
/* app.js hands in how a stock's full analysis is drawn (the trading desk's own look). */
export function setAnalysisRenderer(fn) { analysisHtml = fn; }
const chip = (r) => (r && r.verdict ? `<span class="cc-verdict t-${esc(r.tone || 'HOLD')}">${esc(r.verdict)}</span>` : '');

const KEYS = ['LYLA', 'THEIA', 'MONEYPENNY', 'Q'];
const ROLE = { LYLA: 'Research & media', THEIA: 'Professor', MONEYPENNY: 'Markets desk', Q: 'Quartermaster' };
export const STAGES = ['Received', 'Reading', 'Thinking', 'Writing', 'Done'];

const esc = (v) => String(v ?? '').replace(/[&<>"']/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const short = (t, n = 70) => { const s = String(t || '').replace(/\s+/g, ' ').trim(); return s.length > n ? `${s.slice(0, n - 1)}…` : s; };

/* Where a job has got to, from the desk's own steps: 0..3, or -1 idle. */
export function stageOf(agent = {}) {
  if (!agent.working) return -1;
  const steps = agent.steps || [];
  const last = steps.length ? steps[steps.length - 1].stage : 'received';
  return { received: 0, step: 1, asking: 2, writing: 3, done: 4 }[last] ?? 1;
}

function lane(key, a, open, now) {
  const at = stageOf(a);
  const h = health(a, now);
  const pct = at < 0 ? 0 : at / (STAGES.length - 1);
  const last = (a.results || [])[0];
  const right = a.working
    ? `<b>${esc(short(a.working, 60))}</b><span class="cp-state cp-s-${h.state}">${h.state.toUpperCase()}</span>`
    : h.state === 'failing'
      ? `<b>${esc(short((a.error || {}).task, 60))}</b><span class="cp-state cp-s-failing">FAILED · ${esc(short((a.error || {}).why, 40))}</span>`
      : last
        ? `<b>${esc(short(last.summary || last.task, 60))}</b><button type="button" class="cp-open" data-file="${esc(last.file || '')}" data-link="${esc(last.link || '')}" data-report="${esc(last.report || last.summary || '')}">${last.link ? 'Open on GitHub ›' : 'Open report ›'}</button>`
        : '<b class="cp-quiet">Nothing yet</b>';
  const steps = (a.steps || []).filter(() => a.working);
  const results = (a.results || []).slice(0, 6);
  return `<div class="cp-lane${a.working ? ' busy' : ''}${open ? ' open' : ''}" data-key="${key}">
    <div class="cp-who"><span class="cp-badge">${creature(key, 30)}</span><div><b>${key}</b><small>${ROLE[key]}</small></div></div>
    <div class="cp-track"><span class="cp-fill" style="--p:${pct}"></span>${a.working ? `<span class="cp-run" style="--p:${pct}"></span>` : ''}
      ${STAGES.map((s, j) => `<span class="cp-step ${at < 0 ? '' : j < at ? 'done' : j === at ? 'now' : ''}"><i></i><em>${s}</em></span>`).join('')}</div>
    <div class="cp-out">${right}</div>
    ${open ? `<div class="cp-detail">
      <div><h4>TAKES</h4><p>${esc(IO[key][0])}</p></div>
      <div><h4>${a.working ? 'LIVE' : 'RESULTS'}</h4>${a.working
        ? `<ul>${steps.map((s) => `<li>· ${esc(short(s.text || s.stage, 80))}</li>`).join('') || '<li>Starting…</li>'}</ul>`
        : results.length ? `<ul>${results.map((r) => `<li><button type="button" class="cp-open" data-file="${esc(r.file || '')}" data-link="${esc(r.link || '')}" data-report="${esc(r.report || r.summary || '')}">${esc(short(r.summary || r.task, 80))} ›</button></li>`).join('')}</ul>`
          : '<p>No results yet.</p>'}</div>
      <div><h4>GIVES</h4><p>${esc(IO[key][1])}</p><p class="cp-where">Saved in Documents\\Apollo\\Crew\\${key}</p></div>
    </div>` : ''}
  </div>`;
}

function totals(board) {
  const agents = board.agents || {};
  const sum = (f) => KEYS.reduce((n, k) => n + (Number((agents[k] || {})[f]) || 0), 0);
  const done = sum('done_today'), failed = sum('failed_today');
  const avg = KEYS.map((k) => (agents[k] || {}).avg_ms).filter(Boolean);
  const spend = board.spend || {};
  return {
    working: KEYS.filter((k) => (agents[k] || {}).working).length,
    runs: done + failed,
    success: done + failed ? `${Math.round((done / (done + failed)) * 100)}%` : '—',
    avg: avg.length ? `${Math.round(avg.reduce((a, b) => a + b, 0) / avg.length / 1000)}s` : '—',
    errors: failed + ((board.issues || {}).failing || 0),
    cost: `$${(Number(spend.cost) || 0).toFixed(2)}`,
    tokens: Number(spend.tokens) || 0,
  };
}

/* CARDS: Apollo above, a dotted line down to each of four cards; each card
 * the agent in its corner, what it is for, and below the fold what it is on
 * now. A corner of each lights in its colour - steady at rest, sweeping
 * while it works. Click a card for its live steps and results. */
const GLOW = { LYLA: '255,176,0', THEIA: '150,110,255', MONEYPENNY: '58,196,170', Q: '220,70,200' };
const CORNER = { LYLA: 'tl', THEIA: 'tr', MONEYPENNY: 'br', Q: 'bl' };
const ABOUT = {
  LYLA: 'Finds things out: research with sources, your connected accounts, videos.',
  THEIA: 'Thinks ideas through: what it is, a hard critique, the best way to do it.',
  MONEYPENNY: 'Reads stocks: buy more, hold or pull money out - with reasons and red flags.',
  Q: 'Turns "tell Claude to add..." into a GitHub ticket Claude builds from.',
};

/* How each one works, step by step - shown, animated, when its card opens. */
export const FLOW = {
  LYLA: [['Your question', 'a topic, a link, or a job for your accounts'], ['Searches', 'the web, the news, your connected accounts'],
         ['Writes it up', 'Gemini (or Claude) reads it all and writes it short'], ['Report', 'two lines said aloud, the rest kept in Crew\\LYLA']],
  THEIA: [['Your idea', 'a plan, a decision, anything to think through'], ['Analyses', 'what it really is and what it needs'],
          ['Critiques itself', 'turns on its own analysis, hard'], ['Plan + verdict', 'the best way to do it, and whether to']],
  MONEYPENNY: [['A stock', 'or your whole watchlist'], ['Reads the numbers', 'price, growth, margins, debt, news'],
               ['Weighs the flags', 'green flags against red'], ['The call', 'BUY MORE · HOLD · PULL MONEY OUT, emailed']],
  Q: [['"Tell Claude…"', 'a feature or a fix, in your words'], ['Writes a ticket', 'clear title, what and why'],
      ['Files it', 'an issue on GitHub, obad-code/apollo'], ['Claude builds it', 'and the change comes back to you']],
};

function flowMarkup(key, at) {
  return `<div class="cc-flow" style="--n:${FLOW[key].length}">${FLOW[key].map(([title, line], i) => `
    <div class="cf-step${at === i ? ' live' : ''}" style="--i:${i}"><i class="cf-dot"></i>
      <b>${esc(title)}</b><span>${esc(line)}</span></div>`).join('')}<i class="cf-runner"></i></div>`;
}

function card(key, a, open, now, analysis = null) {
  const at = stageOf(a);
  const h = health(a, now);
  const last = (a.results || [])[0];
  const lower = a.working
    ? `<p class="cc-now"><i class="cc-dot s-${h.state}"></i>${esc(short(a.working, 70))}</p>
       <div class="cc-steps">${STAGES.map((s, j) => `<i class="${j < at ? 'done' : j === at ? 'now' : ''}" title="${s}"></i>`).join('')}</div>
       <small>${esc(STAGES[Math.max(0, at)])} · ${esc(h.text)}</small>`
    : h.state === 'failing'
      ? `<p class="cc-now"><i class="cc-dot s-failing"></i>Last job failed</p><small>${esc(short((a.error || {}).why, 80))}</small>`
      : last
        ? `<p class="cc-now"><i class="cc-dot s-idle"></i>${chip(last)}${esc(short(last.summary || last.task, 70))}</p>
           <button type="button" class="cp-open" data-key="${key}" data-i="0">${last.video ? 'Watch the Short ›' : last.symbol ? 'Read the analysis ›' : 'Read the report ›'}</button>`
        : '<p class="cc-now"><i class="cc-dot s-idle"></i>Ready · nothing yet</p>';
  const steps = a.working ? (a.steps || []) : [];
  const results = (a.results || []).slice(0, 6);
  return `<article class="cc-card cc-${CORNER[key]}${a.working ? ' busy' : ''}${open ? ' open' : ''}" data-key="${key}" style="--g:${GLOW[key]}">
    <div class="cc-top">
      <span class="cc-badge">${creature(key, 34)}</span>
      <h3>${key}</h3><em>${ROLE[key]}</em>
      <p>${esc(ABOUT[key])}</p>
    </div>
    <div class="cc-bottom">${lower}</div>
    ${open ? `<div class="cc-more">
      ${analysis ? '' : `<h4>HOW IT WORKS</h4>${flowMarkup(key, a.working ? Math.min(stageOf(a), 3) : -1)}`}
      <h4>${a.working ? 'LIVE' : 'RESULTS'}</h4>
      ${a.working ? `<ul>${steps.map((x) => `<li>· ${esc(short(x.text || x.stage, 70))}</li>`).join('') || '<li>Starting…</li>'}</ul>`
        : results.length ? `<ul>${results.map((r, i) => `<li><button type="button" class="cp-open cp-row" data-key="${key}" data-i="${i}">${chip(r)}${r.video ? '▶ ' : ''}${esc(short(r.summary || r.task, 64))} ›</button></li>`).join('')}</ul>`
          : '<p>No results yet.</p>'}
    </div>` : ''}
  </article>`;
}

function renderCards(root, board, t, look, open, now, analysis = null) {
  const agents = board.agents || {};
  root.innerHTML = `
    <header class="cp-top">
      <h1>THE CREW</h1>
      <button type="button" class="cp-results" data-results title="Everything the crew made - reports, analyses, Shorts">RESULTS <b>${KEYS.reduce((n, k) => n + (((board.agents || {})[k] || {}).results || []).length, 0)}</b> ›</button>
      <div class="cp-meta"><span><i class="cp-led${t.working ? ' lit' : ''}"></i><b>${t.working}</b> working</span>
        <span><i class="cp-led amb"></i><b>${t.runs}</b> jobs today</span>
        <span><i class="cp-led${t.errors ? ' bad' : ''}"></i><b>${t.errors}</b> errors</span></div>
      ${looks(look)}
    </header>
    <div class="cc-hub"><canvas class="cc-apollo" width="320" height="200" aria-label="Apollo"></canvas><span class="cp-node apollo">APOLLO</span></div>
    <svg class="cc-wires" aria-hidden="true"></svg>
    <div class="cc-row">${KEYS.map((key) => card(key, agents[key] || {}, open === key, now, analysis)).join('')}</div>
    <footer class="cp-foot">
      <div class="cp-g"><b>${t.runs}</b><span>RUNS TODAY</span></div>
      <div class="cp-g"><b>${t.success}</b><span>SUCCESS</span></div>
      <div class="cp-g"><b>${t.avg}</b><span>AVG JOB</span></div>
      <div class="cp-g"><b>${t.errors}</b><span>ERRORS</span></div>
      <div class="cp-g"><b>${t.cost}</b><span>COST TODAY</span></div>
    </footer>`;
  requestAnimationFrame(() => cardWires(root, agents));
}

/* Dotted lines from Apollo down to each card, with light running on the
 * ones whose agent is at work. */
function cardWires(root, agents) {
  const svg = root.querySelector('.cc-wires');
  const hub = root.querySelector('.cc-hub .cp-node');
  if (!svg || !hub) return;
  const base = root.getBoundingClientRect();
  const top = svg.getBoundingClientRect();
  const h = hub.getBoundingClientRect();
  svg.setAttribute('viewBox', `0 0 ${top.width} ${top.height}`);
  const x0 = h.left + h.width / 2 - top.left;
  svg.innerHTML = [...root.querySelectorAll('.cc-card')].map((el) => {
    const b = el.getBoundingClientRect();
    const x = b.left + b.width / 2 - top.left;
    const busy = Boolean((agents[el.dataset.key] || {}).working);
    const y = b.top - top.top;
    const d = `M${x0},0 C${x0},${y * 0.6} ${x},${y * 0.4} ${x},${y}`;
    return `<path class="cc-wire${busy ? ' busy' : ''}" d="${d}" style="--g:${GLOW[el.dataset.key]}"/>${busy
      ? `<circle r="3" class="cc-spark" style="--g:${GLOW[el.dataset.key]}"><animateMotion dur="1.6s" repeatCount="indefinite" path="${d}"/></circle>` : ''}`;
  }).join('');
  void base;
}

export const LOOKS = ['minimal', 'console', 'y2k'];
const looks = () => '';  // one look for now; the others are kept below
const looksSwitch = (look) => `<div class="cp-looks" role="group" aria-label="Look">
  ${LOOKS.map((l) => `<button type="button" data-look="${l}" class="${look === l ? 'on' : ''}">${l.toUpperCase()}</button>`).join('')}
</div>`;

export function render(root, board = {}, { look = 'cards', open = null, analysis = null } = {}) {
  // Every look is the cards; the looks only dress them differently.
  look = 'minimal';
  {
    // Entrances play once; the 4-second refreshes redraw without replaying them.
    const settled = root.dataset.drawn === look + ':' + (open || '');
    root.dataset.drawn = look + ':' + (open || '');
    root.className = `cp look-cards look-${look}${settled ? ' settled' : ''}`;
    renderCards(root, board, totals(board), look, open, board.now || Date.now() / 1000, analysis);
    return;
  }
  const t = totals(board);
  const now = board.now || Date.now() / 1000;
  const agents = board.agents || {};
  const k = (n) => (n >= 1000 ? `${(n / 1000).toFixed(0)}K` : String(n));
  root.className = `cp look-${look}`;
  root.innerHTML = `
    <header class="cp-top">
      <h1>THE CREW</h1>
      <button type="button" class="cp-results" data-results title="Everything the crew made - reports, analyses, Shorts">RESULTS <b>${KEYS.reduce((n, k) => n + (((board.agents || {})[k] || {}).results || []).length, 0)}</b> ›</button>
      <div class="cp-meta"><span><i class="cp-led${t.working ? ' lit' : ''}"></i><b>${t.working}</b> working</span>
        <span><i class="cp-led amb"></i><b>${t.runs}</b> jobs today</span>
        <span><i class="cp-led${t.errors ? ' bad' : ''}"></i><b>${t.errors}</b> errors</span></div>
      ${looks(look)}
      <div class="cp-knobs"><label><i class="cp-knob"></i>VOICE</label><label><i class="cp-knob v2"></i>ROUTINES</label></div>
    </header>
    <div class="cp-flow">
      <div class="cp-src"><span class="cp-node">YOU</span><span class="cp-node apollo">APOLLO</span></div>
      <svg class="cp-wires" aria-hidden="true"></svg>
      <div class="cp-lanes">${KEYS.map((key) => lane(key, agents[key] || {}, open === key, now)).join('')}</div>
    </div>
    <footer class="cp-foot">
      <div class="cp-g"><b>${t.runs}</b><span>RUNS TODAY</span></div>
      <div class="cp-g"><b>${t.success}</b><span>SUCCESS</span></div>
      <div class="cp-g"><b>${t.avg}</b><span>AVG JOB</span></div>
      <div class="cp-g"><b>${t.errors}</b><span>ERRORS</span></div>
      <div class="cp-g"><b>${t.cost}</b><span>COST TODAY</span></div>
    </footer>`;
  requestAnimationFrame(() => wires(root, agents));
}

/* A wire from Apollo to each lane; lit, with light running, while it works. */
function wires(root, agents) {
  const svg = root.querySelector('.cp-wires');
  const flow = root.querySelector('.cp-flow');
  if (!svg || !flow) return;
  const box = flow.getBoundingClientRect();
  const ap = root.querySelector('.cp-node.apollo').getBoundingClientRect();
  const w = svg.getBoundingClientRect().width || 60;
  svg.setAttribute('viewBox', `0 0 ${w} ${box.height}`);
  const y0 = ap.top + ap.height / 2 - box.top;
  svg.innerHTML = [...root.querySelectorAll('.cp-lane')].map((el) => {
    const who = el.querySelector('.cp-who').getBoundingClientRect();
    const y = who.top + who.height / 2 - box.top;
    const busy = Boolean((agents[el.dataset.key] || {}).working);
    const d = `M0,${y0} C${w / 2},${y0} ${w / 2},${y} ${w},${y}`;
    return `<path class="cp-wire${busy ? ' busy' : ''}" d="${d}"/>${busy
      ? `<circle r="2.6" class="cp-spark"><animateMotion dur="1.5s" repeatCount="indefinite" path="${d}"/></circle>` : ''}`;
  }).join('');
}

/* A job handed over: a bright pulse runs down the wire from Apollo to
 * `key`'s lane, and the lane lights as it arrives. */
export function sendTo(root, key) {
  if (root && root.classList.contains('look-cards')) {
    const el = root.querySelector(`.cc-card[data-key="${key}"]`);
    const wire = [...root.querySelectorAll('.cc-wire')][[...root.querySelectorAll('.cc-card')].indexOf(el)];
    if (!el || !wire) return;
    const ns = 'http://www.w3.org/2000/svg';
    const dot = document.createElementNS(ns, 'circle');
    dot.setAttribute('r', '5'); dot.setAttribute('class', 'cp-send');
    const move = document.createElementNS(ns, 'animateMotion');
    move.setAttribute('dur', '0.8s'); move.setAttribute('fill', 'freeze');
    move.setAttribute('path', wire.getAttribute('d')); move.setAttribute('begin', 'indefinite');
    dot.appendChild(move); wire.parentNode.appendChild(dot);
    root.querySelector('.cc-hub .cp-node')?.classList.add('sending');
    move.beginElement();
    setTimeout(() => { dot.remove(); el.classList.add('incoming'); root.querySelector('.cc-hub .cp-node')?.classList.remove('sending'); }, 800);
    setTimeout(() => el.classList.remove('incoming'), 2000);
    return;
  }
  const svg = root && root.querySelector('.cp-wires');
  const lanes = root ? [...root.querySelectorAll('.cp-lane')] : [];
  const i = lanes.findIndex((el) => el.dataset.key === key);
  if (!svg || i < 0) return;
  const path = svg.querySelectorAll('.cp-wire')[i];
  if (!path) return;
  const d = path.getAttribute('d');
  const ns = 'http://www.w3.org/2000/svg';
  const trail = document.createElementNS(ns, 'path');
  trail.setAttribute('d', d);
  trail.setAttribute('class', 'cp-send-trail');
  const dot = document.createElementNS(ns, 'circle');
  dot.setAttribute('r', '4.5');
  dot.setAttribute('class', 'cp-send');
  const move = document.createElementNS(ns, 'animateMotion');
  move.setAttribute('dur', '0.9s');
  move.setAttribute('fill', 'freeze');
  move.setAttribute('path', d);
  move.setAttribute('begin', 'indefinite');
  dot.appendChild(move);
  svg.append(trail, dot);
  root.querySelector('.cp-node.apollo')?.classList.add('sending');
  move.beginElement();
  setTimeout(() => {
    lanes[i].classList.add('incoming');
    dot.remove();
    root.querySelector('.cp-node.apollo')?.classList.remove('sending');
  }, 900);
  setTimeout(() => { trail.remove(); lanes[i].classList.remove('incoming'); }, 2200);
}
