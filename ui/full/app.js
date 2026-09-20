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

const Motion = window.Motion || {};
const animate = Motion.animate || ((el, props, opts) => {
  // Motion is vendored; if it is missing the page must still render, just
  // without the choreography.
  Object.assign(el.style, props);
  return { finished: Promise.resolve() };
});

const $ = (id) => document.getElementById(id);
const RISE = { opacity: [0, 1], transform: ['translateY(16px)', 'translateY(0px)'] };
const SPRING = { type: 'spring', stiffness: 220, damping: 26 };

const TOPICS = ['gaming', 'marvel', 'movies', 'markets'];
const HIDE_AFTER = { market: 180, news: 1800, posts: 900, weather: 2700 };

const SAMPLE = {
  market: {
    status: 'NYSE opens in 37h 37m',
    indices: [
      { symbol: '^GSPC', name: 'S&P 500', price: 7650.5, change_pct: 0.17, spark: [] },
      { symbol: '^IXIC', name: 'Nasdaq', price: 26522.54, change_pct: 0.39, spark: [] },
    ],
    watchlist: [
      { symbol: 'AAPL', price: 336.13, change_pct: -0.26, spark: [330, 332, 331, 335, 336, 334, 336] },
      { symbol: 'MSFT', price: 493.78, change_pct: -0.8, spark: [498, 496, 495, 492, 494, 493, 494] },
      { symbol: 'NVDA', price: 222.27, change_pct: 1.34, spark: [216, 218, 217, 220, 219, 221, 222] },
      { symbol: 'TSLA', price: 364.27, change_pct: -0.53, spark: [368, 366, 367, 364, 365, 363, 364] },
      { symbol: 'AMZN', price: 253.71, change_pct: 1.0, spark: [250, 251, 250, 252, 253, 252, 254] },
      { symbol: 'GOOGL', price: 201.35, change_pct: -0.3, spark: [203, 202, 203, 201, 202, 201, 201] },
      { symbol: 'META', price: 665.75, change_pct: -2.43, spark: [682, 679, 674, 670, 668, 666, 666] },
    ],
  },
  news: {
    gaming: [{ title: "Marvel's Wolverine sold very well on PlayStation 5", source: 'levelup', age: '1h ago' },
             { title: 'Maono G3 mixer launches with dual-PC streaming', source: 'Notebookcheck', age: '1h ago' }],
    marvel: [{ title: "Marvel's Wolverine compared to Uncharted 4", source: 'GameGPU', age: '56m ago' }],
    movies: [{ title: "'Resident Evil' obliterates franchise box office records", source: "Murphy's Multiverse", age: '14m ago' }],
    markets: [{ title: "2026's top stock flashes buy signal", source: "Investor's Business Daily", age: '2h ago' }],
  },
  posts: [{ text: 'Over the years, there have been many Hoaxes...', age: '6h ago', market: true },
          { text: 'Many people think that the words "Artificial Intelligence" are inaccurate...', age: '8h ago', market: false }],
  weather: { temp: 32, high: 42, low: 30, text: 'clear' },
  system: { cpu: 16, ram: 83, gpu: 3, gpu_name: 'NVIDIA GeForce RTX 4060 Ti', vram: 2.1 },
  usage: { tokens: 839, cost: 0.02, estimated: true, turns: 1 },
  clips: { saved_today: 0, seconds: 60 },
  updated: Date.now() / 1000,
};

const state = {
  snapshot: null,
  prices: new Map(),
  phase: 'idle',
  entered: false,
  topic: 0,
};

/* --- the shader, the ring and LYLA --------------------------------------- */

const shader = new Shader($('shader'));
shader.start();
window.addEventListener('resize', () => shader.resize());

const ring = $('ring').getContext('2d');
const RINGS = [[1.0, 22, 0.026, '255,193,94'], [0.85, 18, -0.034, '255,176,0'],
               [0.7, 14, 0.045, '86,197,214']];
let ringClock = 0;
let lastFrame = performance.now();

function drawRing(now) {
  const dt = Math.min(0.05, (now - lastFrame) / 1000);
  lastFrame = now;
  ringClock += dt * (state.phase === 'thinking' ? 5 : 1);
  const size = $('ring').width;
  const centre = size / 2;
  ring.clearRect(0, 0, size, size);
  for (const [fraction, count, turns, colour] of RINGS) {
    const radius = centre * 0.82 * fraction;
    const start = ringClock * turns * Math.PI * 2;
    ring.strokeStyle = `rgba(${colour},.28)`;
    ring.lineWidth = 2;
    ring.beginPath();
    for (let i = 0; i <= count; i++) {
      const angle = start - Math.PI / 2 + (i * Math.PI * 2) / count;
      const x = centre + Math.cos(angle) * radius;
      const y = centre + Math.sin(angle) * radius;
      i ? ring.lineTo(x, y) : ring.moveTo(x, y);
    }
    ring.stroke();
    ring.shadowColor = `rgba(${colour},.9)`;
    ring.shadowBlur = 14;
    ring.fillStyle = `rgba(${colour},.95)`;
    for (let i = 0; i < count; i++) {
      const angle = start - Math.PI / 2 + (i * Math.PI * 2) / count;
      ring.beginPath();
      ring.arc(centre + Math.cos(angle) * radius, centre + Math.sin(angle) * radius,
               5, 0, Math.PI * 2);
      ring.fill();
    }
    ring.shadowBlur = 0;
  }
  requestAnimationFrame(drawRing);
}
requestAnimationFrame(drawRing);

/* --- the clock ------------------------------------------------------------ */

function tickClock() {
  const now = new Date();
  // Read from the clock rather than counting frames, so it can neither drift
  // nor stall while the display is open.
  $('hhmm').textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  $('seconds').textContent = ':' + String(now.getSeconds()).padStart(2, '0');
  $('date').textContent = now.toLocaleDateString('en-GB',
    { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
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

function sparkline(points) {
  if (!points || points.length < 2) return '';
  const low = Math.min(...points), high = Math.max(...points);
  const span = high - low || 1;
  const step = 96 / (points.length - 1);
  const path = points.map((value, i) =>
    `${i ? 'L' : 'M'}${(i * step).toFixed(1)},${(24 - ((value - low) / span) * 22).toFixed(1)}`).join('');
  const rising = points[points.length - 1] >= points[0];
  return `<svg viewBox="0 0 96 26" preserveAspectRatio="none"><path d="${path}" fill="none"
    stroke="${rising ? 'var(--up)' : 'var(--down)'}" stroke-width="1.6"
    stroke-linejoin="round" stroke-linecap="round"/></svg>`;
}

function renderMarkets(market) {
  $('market-clock').textContent = market.status || '';
  $('indices').innerHTML = (market.indices || []).map((quote) => `
    <div class="index">
      <div class="name">${quote.name || quote.symbol}</div>
      <div class="value">${money(quote.price)}<span class="move ${moveClass(quote.change_pct)}">${moveText(quote.change_pct)}</span></div>
    </div>`).join('');

  const list = $('watchlist');
  list.innerHTML = (market.watchlist || []).map((quote) => `
    <div class="stock" data-symbol="${quote.symbol}">
      <span class="ticker">${quote.symbol}</span>
      ${sparkline(quote.spark)}
      <span class="price">${money(quote.price)}</span>
      <span class="move ${moveClass(quote.change_pct)}">${moveText(quote.change_pct)}</span>
    </div>`).join('');

  // A price that moved since the last snapshot flashes its row; one that did
  // not stays still, or the whole column would blink every minute.
  for (const quote of market.watchlist || []) {
    const previous = state.prices.get(quote.symbol);
    if (previous !== undefined && previous !== quote.price) {
      const row = list.querySelector(`[data-symbol="${quote.symbol}"]`);
      if (row) {
        row.classList.add(quote.price > previous ? 'flash-up' : 'flash-down');
        setTimeout(() => row.classList.remove('flash-up', 'flash-down'), 700);
      }
    }
    state.prices.set(quote.symbol, quote.price);
  }
}

function renderHeadlines(news) {
  $('topics').innerHTML = TOPICS.map((topic, i) =>
    `<span class="chip ${i === state.topic ? 'on' : ''}">${topic}</span>`).join('');
  const chosen = TOPICS[state.topic];
  const stories = (news && news[chosen]) || [];
  $('stories').innerHTML = stories.slice(0, 4).map((story) => `
    <div class="story">${story.title}<span>${story.source} · ${story.age}</span></div>`).join('')
    || '<div class="story">Nothing came back for this topic<span>the feed is quiet</span></div>';
}

function renderPosts(posts) {
  $('post-list').innerHTML = (posts || []).slice(0, 3).map((post) => `
    <div class="post">${post.text.slice(0, 160)}${post.text.length > 160 ? '…' : ''}
      <span>${post.age}${post.market ? ' · <b class="moving">market-moving</b>' : ''}</span>
    </div>`).join('') || '<div class="post">No posts in the last day</div>';
}

function renderStrip(snapshot) {
  const usage = snapshot.usage || {};
  const system = snapshot.system || {};
  const clips = snapshot.clips || {};
  $('tokens').textContent = usage.tokens
    ? `${usage.tokens.toLocaleString()} · approx $${(usage.cost || 0).toFixed(2)}`
    : '—';
  $('system').textContent = `CPU ${system.cpu ?? '—'}% · GPU ${system.gpu ?? '—'}% · RAM ${system.ram ?? '—'}%`;
  $('clips').textContent = clips.saved_today !== undefined
    ? `${clips.saved_today} today · last ${clips.seconds || 60}s buffered` : '—';
  const age = snapshot.updated ? Math.max(0, Date.now() / 1000 - snapshot.updated) : null;
  $('updated').textContent = age === null ? '—'
    : age < 60 ? 'just now' : `${Math.floor(age / 60)}m ago`;
}

function renderWeather(weather) {
  const now = new Date();
  const start = new Date(now.getFullYear(), 0, 0);
  const day = Math.floor((now - start) / 86400000);
  const week = Math.ceil(((now - start) / 86400000 + start.getDay() + 1) / 7);
  const hijri = new Intl.DateTimeFormat('en-TN-u-ca-islamic-umalqura',
    { day: 'numeric', month: 'long', year: 'numeric' }).format(now);
  $('date-extra').textContent = `Day ${day} · Week ${week} · ${hijri}`;
  $('weather').textContent = weather && weather.temp !== undefined
    ? `Riyadh ${weather.temp}° · ${weather.text} · high ${weather.high}° low ${weather.low}°`
    : 'Riyadh · weather unavailable';
}

function render(snapshot) {
  state.snapshot = snapshot;
  renderMarkets(snapshot.market || {});
  renderHeadlines(snapshot.news || {});
  renderPosts(snapshot.posts);
  renderStrip(snapshot);
  renderWeather(snapshot.weather);
  if (!state.entered) enter();
}

/* --- the choreography ------------------------------------------------------ */

function enter() {
  state.entered = true;
  const panels = [...document.querySelectorAll('.rise')];
  panels.forEach((panel, i) => {
    animate(panel, RISE, { ...SPRING, delay: i * 0.04 });
  });
}

function setPhase(phase) {
  state.phase = phase;
  const answering = phase === 'thinking' || phase === 'speaking';
  document.body.classList.toggle('answering', answering);
  $('answer').classList.toggle('show', answering);
  shader.speed(answering ? 3 : 1);
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
      <span><i class="${phase === 'Listening' ? 'ok' : ''}" style="color:var(--cyan)">●</i>MIC</span>`;
  },
  turn(who, text) {
    if (who === 'You') {
      $('you').textContent = text;
    } else {
      const reply = $('reply');
      reply.textContent = text;
      reply.setAttribute('dir', /[֐-ࣿ]/.test(text) ? 'rtl' : 'ltr');
    }
  },
  visual(payload) { $('visual').innerHTML = chart(payload); },
  data(snapshot) { render(snapshot); },
  note(text) {
    const note = $('note');
    note.textContent = text || '';
    note.classList.toggle('show', Boolean(text));
    clearTimeout(note._timer);
    note._timer = setTimeout(() => note.classList.remove('show'), 6000);
  },
  fatal(text) { window.apollo.note(text); },
  mode(name) {
    // The overlay has the screen while Apollo is at rest; a shader drawing to
    // a window nobody can see is a GPU burning for nothing.
    if (name === 'full') shader.start();
    else shader.stop();
  },
  level() {},
  briefing(payload) { if (payload) render(payload); },
};

render(SAMPLE);
