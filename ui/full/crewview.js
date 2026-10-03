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

/* One orb: a sphere of light in the agent's colour, its mark inside, a
 * gloss on top, and a ring that runs while it is working. */
export function orb(key) {
  const l = look(key);
  return `<span class="orb" style="--rgb:${l.rgb};--hex:${l.hex};--lit:${l.light}">
    <i class="orb-bloom"></i><i class="orb-ring"></i><i class="orb-gloss"></i>
    <span class="orb-mark">${emblem(key, 64)}</span>
  </span><span class="orb-name"><b>${key}</b><small>${esc(ROLES[key][0])}</small></span>`;
}

/* What an agent is doing, in a line. */
export function doing(agent) {
  if (!agent) return 'Ready';
  if (agent.working) return `Working: ${short(agent.working, 70)}`;
  if (agent.waiting) return `${agent.waiting} waiting`;
  return agent.done_today ? `Ready · ${agent.done_today} done today` : 'Ready';
}

/* The focus card around an agent's orb. */
export function focusMarkup(key, agent, last) {
  const l = look(key);
  return `<div class="focus-orb">${orb(key)}</div>
    <div class="focus-text" style="--rgb:${l.rgb}">
      <h2>${key}</h2>
      <p class="focus-role">${esc(ROLES[key][0])}</p>
      <p class="focus-what">${esc(ROLES[key][1])}</p>
      <p class="focus-now${agent && agent.working ? ' busy' : ''}"><i></i>${esc(doing(agent))}</p>
      ${last ? `<p class="focus-last"><small>LAST</small>${esc(short(last.summary || last.task, 120))}</p>` : ''}
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
  { id: 'crew', size: 'wide', label: 'The crew' },
  { id: 'spend', size: 'sm', label: 'Spend today' },
  { id: 'issues', size: 'sm', label: 'Issues' },
  { id: 'hours', size: 'wide', label: 'Jobs by hour' },
  { id: 'jobs', size: 'wide', label: 'Latest jobs' },
  { id: 'alerts', size: 'sm', label: 'Market alerts' },
  { id: 'tools', size: 'sm', label: 'Tools used today' },
];

const shell = (title, meta, body) => `<section class="w-shell">
  <header><h3>${esc(title)}</h3>${meta ? `<span>${meta}</span>` : ''}</header>
  <div class="w-body">${body}</div></section>`;

const money = (n) => `$${(Number(n) || 0).toFixed(2)}`;
const tokens = (n) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)}K` : String(n || 0));

export function widget(id, board = {}) {
  const agents = board.agents || {};
  if (id === 'crew') {
    return shell('The crew', `${KEYS.filter((k) => agents[k] && agents[k].working).length} working`,
      `<ul class="w-crew">${KEYS.map((k) => {
        const l = look(k), a = agents[k] || {};
        return `<li style="--rgb:${l.rgb}"><i class="w-dot${a.working ? ' busy' : ''}"></i>
          <b>${k}</b><span>${esc(short(doing(a), 34))}</span><em>${a.done_today || 0}</em></li>`;
      }).join('')}</ul>`);
  }
  if (id === 'spend') {
    const s = board.spend || {};
    const g = (s.gemini || {}), c = (s.claude || {});
    const gt = (g.prompt || 0) + (g.response || 0), ct = (c.prompt || 0) + (c.response || 0);
    const total = gt + ct || 1;
    return shell('Spend today', 'estimated', `<p class="w-big">${money(s.cost)}</p>
      <p class="w-sub">${tokens(s.tokens || 0)} tokens · ${s.turns || 0} turns</p>
      <div class="w-split"><i style="flex:${gt / total || 0.0001};background:#FFB000"></i><i style="flex:${ct / total || 0.0001};background:#a77be0"></i></div>
      <p class="w-legend"><span><i style="background:#FFB000"></i>Gemini</span><span><i style="background:#a77be0"></i>Claude</span></p>`);
  }
  if (id === 'issues') {
    const i = board.issues || {};
    return shell('Issues', i.failing ? `<b class="bad">${i.failing} failing</b>` : 'all clear',
      `<p class="w-big">${i.count || 0}</p>${(i.top || []).map((t) => `<p class="w-line"><i class="w-dot ${i.failing ? 'bad' : ''}"></i>${esc(short(t, 26))}</p>`).join('')
      || '<p class="w-sub">Nothing is wrong.</p>'}`);
  }
  if (id === 'hours') {
    const hours = board.hours || {};
    const peak = Math.max(1, ...KEYS.flatMap((k) => hours[k] || []));
    const now = new Date((board.now || Date.now() / 1000) * 1000).getHours();
    const total = KEYS.reduce((n, k) => n + (hours[k] || []).reduce((a, b) => a + b, 0), 0);
    return shell('Jobs by hour', `${total} today`, `<div class="w-heat">${KEYS.map((k) => {
      const l = look(k);
      return `<span class="w-heat-name">${k.slice(0, 5)}</span><span class="w-heat-row">${(hours[k] || new Array(24).fill(0)).map((v, h) =>
        `<i title="${k} ${h}:00 · ${v}" style="--a:${v ? 0.25 + 0.75 * (v / peak) : 0.06};--rgb:${l.rgb}"${h === now ? ' class="now"' : ''}></i>`).join('')}</span>`;
    }).join('')}<span></span><span class="w-heat-hours"><b>00</b><b>06</b><b>12</b><b>18</b></span></div>`);
  }
  if (id === 'jobs') {
    const jobs = board.jobs || [];
    return shell('Latest jobs', 'newest first', jobs.length ? `<ol class="w-jobs">${jobs.slice(0, 4).map((j) => {
      const l = look(j.agent);
      return `<li style="--rgb:${l.rgb}"><i class="w-dot"></i><b>${esc(j.agent)}</b>
        <span>${esc(short(j.task, 48))}</span><em>${j.took ? `${(j.took / 1000).toFixed(1)}s` : ''}</em></li>`;
    }).join('')}</ol>` : '<p class="w-sub">No jobs yet. Ask Apollo to have one of them look into something.</p>');
  }
  if (id === 'alerts') {
    const a = board.alerts || {};
    return shell('Market alerts', a.watching ? '<b class="ok">watching</b>' : 'off',
      `<p class="w-big">${a.sent_hour || 0}</p><p class="w-sub">sent this hour · big news by email and voice</p>`);
  }
  if (id === 'tools') {
    const list = board.tools || [];
    const top = Math.max(1, ...list.map((t) => t[1]));
    return shell('Tools used', 'today', list.length ? `<ul class="w-bars">${list.slice(0, 4).map(([name, n]) =>
      `<li><span>${esc(name)}</span><i style="--w:${(n / top) * 100}%"></i><em>${n}</em></li>`).join('')}</ul>`
      : '<p class="w-sub">None yet today.</p>');
  }
  return '';
}
