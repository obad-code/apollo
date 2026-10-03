/* Agents mode: Apollo's crew.
 *
 *   The wheel     LYLA, THEIA, MONEYPENNY and Q as glowing orbs on a turning
 *                 drum (wheel.js), each in its own colour with its mark.
 *   Its focus     click one and it comes forward, big: who it is and what it
 *                 is doing right now, with its live pipeline under it - for a
 *                 few seconds, and then...
 *   The map       ...the whole crew as one workflow: you, Apollo in the
 *                 middle, each agent with what it turns out, the wires
 *                 running with light where work is moving.
 *   The board     behind them all, a dashboard of what the crew is doing -
 *                 today's jobs by hour, the latest jobs, spend, tools,
 *                 issues, alerts - widgets you rearrange by dragging them
 *                 (widgetgrid.js). Its numbers are Apollo's own (crew.board
 *                 in Python), never made up.
 *
 * Everything here is drawn from data; app.js feeds it and shows it. */

import { LOOKS, emblem } from './lylaagent.js';

export const KEYS = ['LYLA', 'THEIA', 'MONEYPENNY', 'Q'];
export const FOCUS_MS = 4600;         // how long one agent stays forward before the map

export const ROLES = {
  LYLA: ['Research & media', 'Finds things out, gathers sources, reads your connected accounts, downloads videos.'],
  THEIA: ['Professor · analyst', 'Takes any idea and thinks it through: analysis, a hard critique, and the best way to do it.'],
  MONEYPENNY: ['Markets desk', 'Reads a stock or your whole watchlist: a verdict, the reasons, the red flags, what to sell first.'],
  Q: ['Quartermaster', 'Turns "tell Claude to add..." into a ticket on GitHub, and Claude builds it.'],
};

const OUTPUTS = {
  LYLA: ['Sources', 'Downloads'],
  THEIA: ['Analysis', 'Verdict'],
  MONEYPENNY: ['Verdicts', 'Red flags'],
  Q: ['GitHub issue', '@claude'],
};

const esc = (value) => String(value ?? '').replace(/[&<>"']/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const short = (text, most = 64) => {
  const s = String(text || '').replace(/\s+/g, ' ').trim();
  return s.length > most ? `${s.slice(0, most - 1).trimEnd()}…` : s;
};
const look = (key) => LOOKS[key] || LOOKS.LYLA;

/* One agent: a small creature - a plain shape with fully white or fully
 * black eyes that blink and look about, bouncing while it works. LYLA keeps
 * her own look: the little amber robot from her room. */
const CREATURES = {
  THEIA: { eye: '#000', at: [[37, 50], [63, 50]], mouth: [50, 66],
    body: '<circle cx="50" cy="52" r="40" fill="#fff"/>' },
  MONEYPENNY: { eye: '#fff', at: [[37, 50], [63, 50]], mouth: [50, 66],
    body: '<rect x="12" y="13" width="76" height="76" rx="24" fill="#09090b" stroke="rgba(255,255,255,.22)" stroke-width="1.5"/>' },
  Q: { eye: '#000', at: [[40, 62], [60, 62]], mouth: [50, 75],
    body: '<path d="M50 12Q55 12 58 17L92 79Q96 88 86 88H14Q4 88 8 79L42 17Q45 12 50 12Z" fill="#fff"/>' },
  LYLA: { eye: '#120c02', at: [[39, 50], [61, 50]], mouth: [50, 66], square: true,
    body: '<rect x="47.5" y="3" width="5" height="13" rx="2" fill="#FFB000"/><circle cx="50" cy="5" r="5" fill="#ff7a00"/>'
      + '<rect x="12" y="16" width="76" height="72" rx="22" fill="#FFB000"/>'
      + '<circle cx="27" cy="64" r="5" fill="#ff7a00" opacity=".55"/><circle cx="73" cy="64" r="5" fill="#ff7a00" opacity=".55"/>' },
};

export function creature(key, size = 100) {
  const c = CREATURES[key] || CREATURES.THEIA;
  const eyes = c.at.map(([x, y]) => (c.square
    ? `<rect class="cr-eye" x="${x - 5}" y="${y - 7}" width="10" height="14" rx="3" fill="${c.eye}"/>`
    : `<ellipse class="cr-eye" cx="${x}" cy="${y}" rx="5.5" ry="7.5" fill="${c.eye}"/>`)).join('');
  const [mx, my] = c.mouth;
  return `<svg class="cr-svg" width="${size}" height="${size}" viewBox="0 0 100 100" aria-hidden="true">
    <g class="cr-body">${c.body}<g class="cr-look"><g class="cr-eyes">${eyes}</g>
    <path d="M${mx - 6} ${my}q6 5 12 0" stroke="${c.eye}" stroke-width="3" fill="none" stroke-linecap="round"/></g></g></svg>`;
}

export function orb(key) {
  const l = look(key);
  return `<span class="orb creature cr-${key.toLowerCase()}" style="--rgb:${l.rgb};--hex:${l.hex};--lit:${l.light}">
    <i class="orb-ring"></i>${creature(key)}
  </span><span class="orb-name"><b>${key}</b><small>${esc(ROLES[key][0])}</small></span>`;
}

/* Is it really working? From what the desk reports: a step in the last
 * three minutes is working; a job with no step for longer is stuck; a
 * failure newer than its last good job is failing; else it is idle. */
export function health(agent = {}, now = Date.now() / 1000) {
  const steps = agent.steps || [];
  const last = steps.length ? steps[steps.length - 1].t : 0;
  if (agent.working) {
    return now - last > 180 ? { state: 'stuck', text: `No move for ${ago(now - last)}` }
      : { state: 'working', text: `Moving · last step ${ago(now - last)} ago` };
  }
  const err = agent.error;
  if (err && err.when > (agent.last_done || 0)) return { state: 'failing', text: `Last job failed: ${short(err.why, 90)}` };
  return { state: 'idle', text: agent.last_done ? `Ready · last job ${ago(now - agent.last_done)} ago` : 'Ready · no jobs yet' };
}

function ago(seconds) {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.round(s / 60)}m`;
  if (s < 86400) return `${Math.round(s / 3600)}h`;
  return `${Math.round(s / 86400)}d`;
}

/* What an agent is doing, in a line. */
export function doing(agent) {
  if (!agent) return 'Ready';
  if (agent.working) return `Working: ${short(agent.working, 70)}`;
  if (agent.waiting) return `${agent.waiting} waiting`;
  return agent.done_today ? `Ready · ${agent.done_today} done today` : 'Ready';
}

/* An agent brought forward: the creature, and its work as it happens - a
 * calm line of steps drawing in, the one in hand pulsing, and a plain
 * verdict on whether it is really working. */
export function focusMarkup(key, agent = {}, last, now = Date.now() / 1000) {
  const l = look(key), h = health(agent, now);
  const steps = agent.working ? (agent.steps || []) : [];
  const done = agent.done_today || 0, failed = agent.failed_today || 0;
  const rate = done + failed ? Math.round((done / (done + failed)) * 100) : null;
  const line = steps.length ? `<ol class="work-steps">${steps.map((s, i) => `
      <li class="${i === steps.length - 1 ? 'now' : ''}" style="--i:${i}"><i></i>
        <span>${esc(short(s.text || s.stage, 80))}</span><em>${ago(now - s.t)}</em></li>`).join('')}</ol>`
    : `<p class="work-empty">${agent.working ? 'Starting…' : 'Nothing in hand right now.'}</p>`;
  return `<div class="focus-orb${agent.working ? ' busy' : ''}">${orb(key)}</div>
    <div class="focus-text work" style="--rgb:${l.rgb}">
      <h2>${key}</h2>
      <p class="focus-role">${esc(ROLES[key][0])}</p>
      <p class="work-health h-${h.state}"><i></i><b>${h.state.toUpperCase()}</b><span>${esc(h.text)}</span></p>
      ${agent.working ? `<p class="work-task">${esc(short(agent.working, 140))}</p>` : ''}
      ${line}
      <div class="work-stats">
        <div><b>${done}</b><span>done today</span></div>
        <div><b>${rate === null ? '—' : `${rate}%`}</b><span>success</span></div>
        <div><b>${agent.avg_ms ? `${(agent.avg_ms / 1000).toFixed(0)}s` : '—'}</b><span>avg job</span></div>
        <div><b>${agent.waiting || 0}</b><span>waiting</span></div>
      </div>
      ${last ? `<p class="focus-last"><small>LAST RESULT</small>${esc(short(last.summary || last.task, 160))}</p>` : ''}
    </div>`;
}

/* --- the map ---------------------------------------------------------------- */

const W = 1200, H = 640;
const HUB = { x: 600, y: 330 };
const SPOTS = { LYLA: { x: 330, y: 190 }, THEIA: { x: 870, y: 190 },
                MONEYPENNY: { x: 330, y: 490 }, Q: { x: 870, y: 490 } };
const SHORT_ROLE = { LYLA: 'Research & media', THEIA: 'Professor', MONEYPENNY: 'Markets desk', Q: 'Quartermaster' };

function curve(a, b) {
  const mx = (a.x + b.x) / 2;
  return `M${a.x},${a.y} C${mx},${a.y} ${mx},${b.y} ${b.x},${b.y}`;
}

/* The whole crew as one workflow. `agents` is the board's state per agent;
 * `focus` the one to light up. */
export function mapMarkup(agents = {}, focus = null) {
  const defs = KEYS.map((key) => {
    const l = look(key);
    return `<linearGradient id="wire-${key}" x1="0" x2="1">
        <stop offset="0" stop-color="#FFB000"/><stop offset="1" stop-color="${l.hex}"/></linearGradient>`;
  }).join('');
  const wires = [], nodes = [];
  const you = 'M600,78 L600,262';
  wires.push(`<g class="map-run"><path class="map-glow" d="${you}" stroke="#FFD48A"/>
    <path class="map-wire you" d="${you}" stroke="url(#wire-you)"/>
    ${[0, 0.5].map((d) => `<circle r="3" fill="#FFF0CE" filter="url(#bloom)"><animateMotion dur="1.8s" begin="${d * 1.8}s" repeatCount="indefinite" path="${you}"/></circle>`).join('')}</g>`);
  for (const key of KEYS) {
    const l = look(key), at = SPOTS[key], agent = agents[key] || {};
    const busy = Boolean(agent.working), lit = !focus || focus === key;
    const d = curve({ x: HUB.x + (at.x < HUB.x ? -78 : 78), y: HUB.y }, { x: at.x + (at.x < HUB.x ? 92 : -92), y: at.y });
    wires.push(`<g class="map-run${busy ? ' busy' : ''}${lit ? '' : ' dim'}">
      <path class="map-glow" d="${d}" stroke="${l.hex}"/>
      <path class="map-wire" d="${d}" stroke="url(#wire-${key})"/>
      ${[0, 0.33, 0.66].map((delay) => `<circle r="${busy ? 4 : 3}" fill="${l.hex}" filter="url(#bloom)">
        <animateMotion dur="${busy ? 1.4 : 3.2}s" begin="${delay * (busy ? 1.4 : 3.2)}s" repeatCount="indefinite" path="${d}"/></circle>`).join('')}
    </g>`);
    const side = at.x < HUB.x ? -1 : 1;
    OUTPUTS[key].forEach((name, i) => {
      const ox = at.x + side * 196, oy = at.y - 34 + i * 68;
      const od = curve({ x: at.x + side * 92, y: at.y }, { x: ox - side * 62, y: oy });
      wires.push(`<g class="map-run out${lit ? '' : ' dim'}"><path class="map-wire thin" d="${od}" stroke="${l.hex}"/>
        <circle r="2.4" fill="${l.hex}"><animateMotion dur="2.4s" begin="${i * 0.8}s" repeatCount="indefinite" path="${od}"/></circle></g>`);
      nodes.push(`<g class="map-out${lit ? '' : ' dim'}" transform="translate(${ox - 62},${oy - 17})">
        <rect width="124" height="34" rx="12" fill="rgba(${l.rgb},.10)" stroke="rgba(${l.rgb},.45)"/>
        <text x="62" y="22" text-anchor="middle">${esc(name)}</text></g>`);
    });
    nodes.push(`<g class="map-agent${busy ? ' busy' : ''}${focus === key ? ' focus' : ''}${lit ? '' : ' dim'}" transform="translate(${at.x - 92},${at.y - 46})" style="--rgb:${l.rgb}">
      <rect class="map-card" width="184" height="92" rx="24" fill="url(#card-${key})" stroke="${l.hex}"/>
      <g transform="translate(16,22) scale(.75)">${emblem(key, 64).replace(/^<svg[^>]*>|<\/svg>$/g, '')}</g>
      <text class="map-name" x="74" y="40"${key.length > 6 ? ' style="font-size:14px;letter-spacing:.1em"' : ''}>${key}</text>
      <text class="map-role" x="74" y="58">${esc(SHORT_ROLE[key])}</text>
      <text class="map-state" x="16" y="80">${esc(short(doing(agent), 24))}</text>
    </g>`);
  }
  const cards = KEYS.map((key) => {
    const l = look(key);
    return `<linearGradient id="card-${key}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="rgba(${l.rgb},.26)"/><stop offset="1" stop-color="${l.deep}"/></linearGradient>`;
  }).join('');
  return `<svg class="crew-map-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="The crew's workflow: you speak to Apollo, Apollo hands work to LYLA, THEIA, MONEYPENNY and Q, and tells you what they found.">
    <defs>
      <filter id="bloom" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3.5" result="b"/>
        <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      <filter id="halo" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="14"/></filter>
      <linearGradient id="wire-you" gradientUnits="userSpaceOnUse" x1="600" y1="78" x2="600" y2="262"><stop offset="0" stop-color="#FFF0CE"/><stop offset="1" stop-color="#FFB000"/></linearGradient>
      <radialGradient id="hub" cx=".5" cy=".42" r=".6"><stop offset="0" stop-color="#fff6dc"/><stop offset=".35" stop-color="#FFB000"/><stop offset="1" stop-color="#3a1d00"/></radialGradient>
      ${defs}${cards}
    </defs>
    ${wires.join('')}
    <g class="map-you" transform="translate(530,32)"><rect width="140" height="46" rx="16"/>
      <text x="70" y="29" text-anchor="middle">YOU · VOICE</text></g>
    <g class="map-hub">
      <circle cx="${HUB.x}" cy="${HUB.y}" r="96" fill="#FFB000" opacity=".18" filter="url(#halo)"/>
      <circle cx="${HUB.x}" cy="${HUB.y}" r="68" fill="url(#hub)" stroke="#FFD48A" stroke-width="1.5"/>
      <ellipse cx="${HUB.x}" cy="${HUB.y}" rx="68" ry="26" fill="none" stroke="rgba(255,240,206,.45)"/>
      <ellipse cx="${HUB.x}" cy="${HUB.y}" rx="26" ry="68" fill="none" stroke="rgba(255,240,206,.35)"/>
      <path d="M${HUB.x},${HUB.y - 22} L${HUB.x + 6},${HUB.y - 6} L${HUB.x + 22},${HUB.y} L${HUB.x + 6},${HUB.y + 6} L${HUB.x},${HUB.y + 22} L${HUB.x - 6},${HUB.y + 6} L${HUB.x - 22},${HUB.y} L${HUB.x - 6},${HUB.y - 6}Z" fill="#fff" filter="url(#bloom)"/>
      <text class="map-hub-name" x="${HUB.x}" y="${HUB.y + 104}" text-anchor="middle">APOLLO</text>
      <text class="map-hub-role" x="${HUB.x}" y="${HUB.y + 124}" text-anchor="middle">decides who does what · speaks for all of them</text>
    </g>
    ${nodes.join('')}
  </svg>`;
}

/* --- the board's widgets -------------------------------------------------------- */

export const WIDGETS = [
  { id: 'runs', size: 'wide', label: 'Runs' },
  { id: 'status', size: 'sm', label: 'System status' },
  { id: 'cost', size: 'sm', label: 'Cost' },
  { id: 'errors', size: 'sm', label: 'Errors' },
  { id: 'traces', size: 'wide', label: 'Traces' },
  { id: 'evals', size: 'sm', label: 'Evals' },
  { id: 'tools', size: 'sm', label: 'Tools' },
  { id: 'tokens', size: 'sm', label: 'Token usage' },
];

const shell = (title, meta, body) => `<section class="w-shell">
  <header><h3>${esc(title)}</h3>${meta ? `<span>${meta}</span>` : ''}</header>
  <div class="w-body">${body}</div></section>`;

const money = (n) => `$${(Number(n) || 0).toFixed(2)}`;
const tokens = (n) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)}K` : String(n || 0));

export function widget(id, board = {}) {
  const agents = board.agents || {};
  const now = board.now || Date.now() / 1000;
  if (id === 'runs') {
    const hours = board.hours || {};
    const peak = Math.max(1, ...KEYS.flatMap((k) => hours[k] || []));
    const hour = new Date(now * 1000).getHours();
    const total = KEYS.reduce((n, k) => n + (hours[k] || []).reduce((a, b) => a + b, 0), 0);
    return shell('Runs', `${total} today`, `<div class="w-heat">${KEYS.map((k) => {
      const l = look(k);
      return `<span class="w-heat-name">${k.slice(0, 5)}</span><span class="w-heat-row">${(hours[k] || new Array(24).fill(0)).map((v, h) =>
        `<i title="${k} ${h}:00 · ${v}" style="--a:${v ? 0.25 + 0.75 * (v / peak) : 0.06};--rgb:${l.rgb}"${h === hour ? ' class="now"' : ''}></i>`).join('')}</span>`;
    }).join('')}<span></span><span class="w-heat-hours"><b>00</b><b>06</b><b>12</b><b>18</b></span></div>`);
  }
  if (id === 'status') {
    const brains = board.brains || {};
    const states = KEYS.map((k) => [k, health(agents[k], now)]);
    const bad = states.filter(([, h]) => h.state === 'stuck' || h.state === 'failing').length;
    return shell('System status', bad ? `<b class="bad">${bad} need a look</b>` : '<b class="ok">operational</b>',
      `<ul class="w-status">${states.map(([k, h]) => `<li><i class="w-dot s-${h.state}"></i><b>${k}</b><em>${h.state}</em></li>`).join('')}
      ${Object.entries(brains).map(([name, on]) => `<li><i class="w-dot ${on ? 's-idle' : 's-off'}"></i><b>${name}</b><em>${on ? 'key set' : 'not set'}</em></li>`).join('')}</ul>`);
  }
  if (id === 'cost') {
    const s = board.spend || {};
    return shell('Cost', 'today, estimated', `<p class="w-big">${money(s.cost)}</p>
      <p class="w-sub">${s.turns || 0} turns · ${tokens(s.tokens || 0)} tokens</p>`);
  }
  if (id === 'errors') {
    const i = board.issues || {};
    const agentErrs = KEYS.filter((k) => health(agents[k], now).state === 'failing')
      .map((k) => `${k}: ${short((agents[k].error || {}).why, 22)}`);
    const lines = [...agentErrs, ...(i.top || [])];
    const n = agentErrs.length + (i.count || 0);
    return shell('Errors', n ? `<b class="bad">${n}</b>` : '<b class="ok">none</b>',
      `<p class="w-big">${n}</p>${lines.slice(0, 3).map((t) => `<p class="w-line"><i class="w-dot bad"></i>${esc(short(t, 30))}</p>`).join('')
      || '<p class="w-sub">Nothing is failing.</p>'}`);
  }
  if (id === 'traces') {
    const jobs = (board.jobs || []).slice(0, 5);
    const longest = Math.max(1, ...jobs.map((j) => j.took || 0));
    return shell('Traces', 'latest jobs', jobs.length ? `<ol class="w-traces">${jobs.map((j) => {
      const l = look(j.agent);
      return `<li style="--rgb:${l.rgb}"><b>${esc(j.agent)}</b><span>${esc(short(j.task, 40))}</span>
        <i style="--w:${Math.max(4, ((j.took || 0) / longest) * 100)}%"></i><em>${j.took ? `${(j.took / 1000).toFixed(1)}s` : ''}</em></li>`;
    }).join('')}</ol>` : '<p class="w-sub">No jobs yet. They start on their own every day, or ask Apollo.</p>');
  }
  if (id === 'evals') {
    const done = KEYS.reduce((n, k) => n + ((agents[k] || {}).done_today || 0), 0);
    const failed = KEYS.reduce((n, k) => n + ((agents[k] || {}).failed_today || 0), 0);
    const rate = done + failed ? done / (done + failed) : null;
    const deg = rate === null ? 0 : rate * 360;
    return shell('Evals', 'jobs finished well', `<div class="w-ring" style="--deg:${deg}deg"><b>${rate === null ? '—' : `${Math.round(rate * 100)}%`}</b></div>
      <p class="w-sub">${done} ok · ${failed} failed today</p>`);
  }
  if (id === 'tools') {
    const list = board.tools || [];
    const top = Math.max(1, ...list.map((t) => t[1]));
    return shell('Tools', 'today', list.length ? `<ul class="w-bars">${list.slice(0, 4).map(([name, n]) =>
      `<li><span>${esc(name)}</span><i style="--w:${(n / top) * 100}%"></i><em>${n}</em></li>`).join('')}</ul>`
      : '<p class="w-sub">None yet today.</p>');
  }
  if (id === 'tokens') {
    const s = board.spend || {};
    const g = (s.gemini || {}), c = (s.claude || {});
    const gt = (g.prompt || 0) + (g.response || 0), ct = (c.prompt || 0) + (c.response || 0);
    const total = gt + ct || 1;
    return shell('Token usage', tokens(gt + ct), `<ul class="w-bars">
      <li><span>Gemini</span><i style="--w:${(gt / total) * 100}%;--c:#FFB000"></i><em>${tokens(gt)}</em></li>
      <li><span>Claude</span><i style="--w:${(ct / total) * 100}%;--c:#a77be0"></i><em>${tokens(ct)}</em></li></ul>`);
  }
  return '';
}
