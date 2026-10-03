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

const KEYS = ['LYLA', 'THEIA', 'MONEYPENNY', 'Q'];
const ROLE = { LYLA: 'Research & media', THEIA: 'Professor', MONEYPENNY: 'Markets desk', Q: 'Quartermaster' };
export const STAGES = ['Received', 'Reading', 'Thinking', 'Done'];

const esc = (v) => String(v ?? '').replace(/[&<>"']/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const short = (t, n = 70) => { const s = String(t || '').replace(/\s+/g, ' ').trim(); return s.length > n ? `${s.slice(0, n - 1)}…` : s; };

/* Where a job has got to, from the desk's own steps: 0..3, or -1 idle. */
export function stageOf(agent = {}) {
  if (!agent.working) return -1;
  const steps = agent.steps || [];
  const last = steps.length ? steps[steps.length - 1].stage : 'received';
  return { received: 0, step: 1, asking: 2, done: 3 }[last] ?? 1;
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
        ? `<b>${esc(short(last.summary || last.task, 60))}</b><button type="button" class="cp-open" data-file="${esc(last.file || '')}" data-link="${esc(last.link || '')}">${last.link ? 'Open on GitHub ›' : 'Open report ›'}</button>`
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
        : results.length ? `<ul>${results.map((r) => `<li><button type="button" class="cp-open" data-file="${esc(r.file || '')}" data-link="${esc(r.link || '')}">${esc(short(r.summary || r.task, 80))} ›</button></li>`).join('')}</ul>`
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

/* The five instruments under the lanes: a figure on a lit screen, and
 * beside it the shape of the day - jobs by hour, a ring, a needle, a lamp,
 * the split between the two brains. All from the board. */
function instruments(board, t) {
  const hours = board.hours || {};
  const byHour = new Array(24).fill(0).map((_, h) => KEYS.reduce((n, k) => n + ((hours[k] || [])[h] || 0), 0));
  const peak = Math.max(1, ...byHour);
  const nowH = new Date((board.now || Date.now() / 1000) * 1000).getHours();
  const bars = `<span class="cp-bars">${byHour.map((v, h) =>
    `<i style="--h:${v ? 0.2 + 0.8 * (v / peak) : 0.06}"${h === nowH ? ' class="now"' : ''}></i>`).join('')}</span>`;
  const rate = t.success === '—' ? 0 : parseInt(t.success, 10) / 100;
  const ring = `<span class="cp-ring" style="--r:${rate}"></span>`;
  const secs = parseInt(t.avg, 10) || 0;
  const needle = `<span class="cp-dial"><i style="--a:${Math.min(1, secs / 120) * 180 - 90}deg"></i></span>`;
  const lamp = `<span class="cp-bulb${t.errors ? ' on' : ''}"></span>`;
  const sp = board.spend || {};
  const gt = ((sp.gemini || {}).prompt || 0) + ((sp.gemini || {}).response || 0);
  const ct = ((sp.claude || {}).prompt || 0) + ((sp.claude || {}).response || 0);
  const split = `<span class="cp-split"><i style="flex:${gt || 1}"></i><i style="flex:${ct || 0.0001}"></i></span>`;
  const k = (n) => (n >= 1000 ? `${(n / 1000).toFixed(0)}K` : String(n));
  return [
    { label: 'RUNS', value: t.runs, sub: 'by hour', viz: bars, lit: t.runs > 0 },
    { label: 'SUCCESS', value: t.success, sub: 'finished well', viz: ring, lit: rate >= 0.8 },
    { label: 'AVG JOB', value: t.avg, sub: 'per job', viz: needle, lit: secs > 0 },
    { label: 'ERRORS', value: t.errors, sub: t.errors ? 'need a look' : 'all clear', viz: lamp, lit: !t.errors, alarm: Boolean(t.errors) },
    { label: 'COST', value: t.cost, sub: `${k(t.tokens)} tokens`, viz: split, lit: true },
  ];
}

export function render(root, board = {}, { look = 'minimal', open = null } = {}) {
  const t = totals(board);
  const now = board.now || Date.now() / 1000;
  const agents = board.agents || {};
  const k = (n) => (n >= 1000 ? `${(n / 1000).toFixed(0)}K` : String(n));
  root.className = `cp look-${look}`;
  root.innerHTML = `
    <header class="cp-top">
      <h1>THE CREW</h1>
      <div class="cp-meta"><span><b>${t.working}</b> working</span><span><b>${t.runs}</b> jobs today</span>
        <span><b>${t.success}</b> success</span><span><b>${t.cost}</b> today</span></div>
      <div class="cp-looks" role="group" aria-label="Look">
        <button type="button" data-look="minimal" class="${look === 'minimal' ? 'on' : ''}">MINIMAL</button>
        <button type="button" data-look="console" class="${look === 'console' ? 'on' : ''}">CONSOLE</button>
      </div>
    </header>
    <div class="cp-flow">
      <div class="cp-src"><span class="cp-node">YOU</span><span class="cp-node apollo">APOLLO</span></div>
      <svg class="cp-wires" aria-hidden="true"></svg>
      <div class="cp-lanes">${KEYS.map((key) => lane(key, agents[key] || {}, open === key, now)).join('')}</div>
    </div>
    <footer class="cp-foot">${instruments(board, t).map((m) => `
      <div class="cp-inst${m.alarm ? ' alarm' : ''}">
        <header><i class="cp-led${m.lit ? ' lit' : ''}"></i><span>${m.label}</span></header>
        <div class="cp-screen"><b>${m.value}</b><small>${m.sub}</small>${m.viz}</div>
      </div>`).join('')}
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
