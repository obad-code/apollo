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

/* Headlines come from Google News and posts come from Truth Social. Neither is
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

const TOPICS = ['gaming', 'marvel', 'movies', 'markets'];

// dataservice.INTERVALS x 3. Past this a panel is showing something it could
// not refresh, and it has to say so - a price from an hour ago that looks
// current is worse than no price at all.
const STALE_AFTER = { market: 180, news: 1800, posts: 900, weather: 2700, system: 15 };

const SAMPLE = {
  market: {
    status: 'NYSE opens in 37h 37m',
    indices: [
      { symbol: '^GSPC', name: 'S&P 500', price: 7650.5, change_pct: 0.17, spark: [] },
      { symbol: '^IXIC', name: 'Nasdaq', price: 26522.54, change_pct: 0.39, spark: [] },
    ],
    watchlist: [
      { symbol: 'AAPL', price: 336.13, change_pct: -0.26, logo: 'logos/AAPL.png',
        target: 328.22, upside: -2.35, pe: 38.59,
        spark: [330, 332, 331, 335, 338, 336, 334, 337, 336, 334, 336] },
      { symbol: 'MSFT', price: 493.78, change_pct: -0.8, logo: 'logos/MSFT.png',
        target: 560.4, upside: 13.5, pe: 31.2,
        spark: [498, 496, 495, 492, 490, 494, 493, 491, 494, 492, 494] },
      { symbol: 'NVDA', price: 222.27, change_pct: 1.34, logo: 'logos/NVDA.png',
        target: 327.7, upside: 47.43, pe: 28.1,
        spark: [206, 210, 214, 212, 218, 224, 229, 232, 226, 220, 222] },
      { symbol: 'TSLA', price: 364.27, change_pct: -0.53, logo: 'logos/TSLA.png',
        target: 396.94, upside: 8.97, pe: 334.19,
        spark: [372, 368, 366, 370, 367, 364, 361, 365, 363, 366, 364] },
      { symbol: 'AMZN', price: 253.71, change_pct: 1.0, logo: 'logos/AMZN.png',
        target: 288.1, upside: 13.6, pe: 34.8,
        spark: [246, 249, 248, 251, 250, 252, 255, 253, 252, 254, 254] },
      { symbol: 'GOOGL', price: 201.35, change_pct: -0.3, logo: 'logos/GOOGL.png',
        target: 224.6, upside: 11.5, pe: 26.4,
        spark: [205, 203, 204, 202, 203, 201, 200, 202, 201, 202, 201] },
      { symbol: 'META', price: 665.75, change_pct: -2.43, logo: 'logos/META.png',
        target: 790.2, upside: 18.7, pe: 24.9,
        spark: [692, 686, 682, 679, 674, 670, 673, 668, 666, 669, 666] },
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
  stamps: { market: Date.now() / 1000, news: Date.now() / 1000, posts: Date.now() / 1000,
            weather: Date.now() / 1000, system: Date.now() / 1000 },
};

const state = {
  snapshot: null,
  prices: new Map(),
  phase: 'idle',
  entered: false,
  topic: 0,
  settleTimer: null,
  level: 0,
  levelSmooth: 0,
};

/* --- the shader, the ring and LYLA --------------------------------------- */

const shader = new Shader($('shader'));
shader.start();
window.addEventListener('resize', () => shader.resize());

const lyla = new Lyla($('lyla'), {
  label: $('lyla-label'), icon: $('lyla-icon'),
  bar: $('lyla-bar'), pct: $('lyla-pct'), ring: $('ring'),
});
lyla.start();

const ring = $('ring').getContext('2d');
const RINGS = [[1.0, 22, 0.026, '255,193,94'], [0.85, 18, -0.034, '255,176,0'],
               [0.7, 14, 0.045, '86,197,214']];
let ringClock = 0;
let lastFrame = performance.now();
let ringFrame = null;

function drawRing(now) {
  const dt = Math.min(0.05, (now - lastFrame) / 1000);
  lastFrame = now;
  ringClock += dt * (state.phase === 'thinking' ? 5 : 1);
  // Eased, not followed: the raw level jumps every packet, and a ring that
  // jumps with it reads as a fault rather than as breathing.
  state.levelSmooth += (state.level - state.levelSmooth)
                     * (1 - Math.exp(-dt / (state.level > state.levelSmooth ? 0.05 : 0.28)));
  const breath = 1 + 0.09 * state.levelSmooth;
  const size = $('ring').width;
  const centre = size / 2;
  ring.clearRect(0, 0, size, size);
  for (const [fraction, count, turns, colour] of RINGS) {
    const radius = centre * 0.82 * fraction * breath;
    const start = ringClock * turns * Math.PI * 2;
    ring.strokeStyle = `rgba(${colour},${(0.28 + 0.22 * state.levelSmooth).toFixed(3)})`;
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
               5 + 1.8 * state.levelSmooth, 0, Math.PI * 2);
      ring.fill();
    }
    ring.shadowBlur = 0;
  }
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
          stroke="${up ? 'var(--up)' : 'var(--down)'}" stroke-width="2"
          stroke-linejoin="round" stroke-linecap="round"/>
  </svg>`;
}

/* One stock, as a card: its mark, what it costs, what it did, and what the
 * analysts make of it. The same shape as the card the overlay draws - white
 * paper, the price large, the curve under it, the valuation along the foot -
 * so the two halves of Apollo say the same thing the same way. */
function stockCard(quote) {
  const mark = quote.logo
    ? `<img class="mark" src="${esc(quote.logo)}" alt="">`
    : `<span class="mark none">${esc((quote.symbol || '?')[0])}</span>`;
  const target = quote.target
    ? `<b>${money(quote.target)}</b> target${quote.upside != null
        ? ` <i class="${moveClass(quote.upside)}">${quote.upside >= 0 ? '+' : ''}${quote.upside.toFixed(1)}%</i>`
        : ''}`
    : '<b>—</b> target';
  const pe = quote.pe ? `<b>${quote.pe.toFixed(1)}</b> P/E` : '<b>—</b> P/E';
  return `
    <div class="card" data-symbol="${esc(quote.symbol)}">
      <div class="card-top">
        ${mark}
        <span class="ticker">${esc(quote.symbol)}</span>
        <span class="price">${money(quote.price)}</span>
        <span class="move ${moveClass(quote.change_pct)}">${moveText(quote.change_pct)}</span>
      </div>
      ${sparkline(quote.spark, quote.change_pct >= 0)}
      <div class="card-foot">${target}<i class="dot">·</i>${pe}</div>
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
  list.innerHTML = (market.watchlist || []).map((quote) => stockCard(quote)).join('');

  // A price that moved since the last snapshot flashes its row; one that did
  // not stays still, or the whole column would blink every minute. Rows are
  // found by position rather than by a selector built from a ticker, which
  // would be one more piece of feed data steering the page.
  (market.watchlist || []).forEach((quote, i) => {
    const previous = state.prices.get(quote.symbol);
    const row = list.children[i];
    if (previous !== undefined && previous !== quote.price && row) {
      row.classList.add(quote.price > previous ? 'flash-up' : 'flash-down');
      setTimeout(() => row.classList.remove('flash-up', 'flash-down'), 700);
    }
    state.prices.set(quote.symbol, quote.price);
  });
}

function renderHeadlines(news) {
  $('headlines-head').innerHTML = 'Headlines' + stale('news');
  $('topics').innerHTML = TOPICS.map((topic, i) =>
    `<span class="chip ${i === state.topic ? 'on' : ''}">${esc(topic)}</span>`).join('');
  const chosen = TOPICS[state.topic];
  const stories = (news && news[chosen]) || [];
  $('stories').innerHTML = stories.slice(0, 4).map((story) => `
    <div class="story">${esc(story.title)}<span>${esc(story.source)} · ${esc(story.age)}</span></div>`).join('')
    || '<div class="story">Nothing came back for this topic<span>the feed is quiet</span></div>';
}

function renderPosts(posts) {
  $('posts-head').innerHTML = 'Trump · Truth Social' + stale('posts');
  $('post-list').innerHTML = (posts || []).slice(0, 3).map((post) => `
    <div class="post">${esc(post.text.slice(0, 160))}${post.text.length > 160 ? '…' : ''}
      <span>${esc(post.age)}${post.market ? ' · <b class="moving">market-moving</b>' : ''}</span>
    </div>`).join('') || '<div class="post">No posts in the last day</div>';
}

function renderStrip(snapshot) {
  const usage = snapshot.usage || {};
  const system = snapshot.system || {};
  const clips = snapshot.clips || {};
  $('tokens').textContent = usage.tokens
    ? `${usage.tokens.toLocaleString()} · approx $${(usage.cost || 0).toFixed(2)}`
    : '—';
  $('system').innerHTML =
    `CPU ${system.cpu ?? '—'}% · GPU ${system.gpu ?? '—'}% · RAM ${system.ram ?? '—'}%${stale('system')}`;
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
  $('weather').innerHTML = weather && weather.temp !== undefined
    ? `Riyadh ${weather.temp}° · ${esc(weather.text)} · high ${weather.high}° low ${weather.low}°${stale('weather')}`
    : 'Riyadh · weather unavailable';
}

function render(snapshot) {
  state.snapshot = snapshot;
  renderMarkets(snapshot.market || {});
  renderHeadlines(snapshot.news || {});
  renderPosts(snapshot.posts);
  renderStrip(snapshot);
  renderWeather(snapshot.weather);
  enter();
}

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

  const answering = phase === 'thinking' || phase === 'speaking';
  const attending = phase !== 'idle';
  document.body.classList.toggle('listening', phase === 'listening');
  document.body.classList.toggle('thinking', phase === 'thinking');
  document.body.classList.toggle('answering', answering);
  $('answer').classList.toggle('show', answering);
  // The room steps back as far as the state warrants: a little while it is
  // listening to you, all the way once it is answering.
  shader.speed(phase === 'thinking' ? 4 : attending ? 2 : 1);

  const hint = $('hint');
  hint.textContent = SAYS[phase] || '';
  hint.classList.toggle('busy', attending);

  if (phase === 'listening') {
    $('you').textContent = '';
    $('reply').textContent = '';
    $('visual').innerHTML = '';
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
      <span><i class="${phase === 'Listening' ? 'ok' : ''}" style="color:var(--cyan)">●</i>MIC</span>`;
  },
  turn(who, text) {
    if (who === 'You') {
      $('you').textContent = text;
      return;
    }
    reveal($('reply'), text);
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
    if (name === 'full') { shader.start(); lyla.start(); ringStart(); enter(); }
    else { shader.stop(); lyla.stop(); ringStop(); }
  },
  level(value) { setLevel(value); },
  briefing(payload) { if (payload) render(payload); },
};

render(SAMPLE);
