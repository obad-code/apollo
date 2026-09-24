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
  cardLit: null,          // the stock card under the pointer
  stock: null,            // the stock opened out of its card, or the add picker
  pending: new Map(),     // stocks asked for whose cards have not come yet
  marketKey: '',          // what the cards were last drawn from
  liveTimer: null,        // takes LIVE off the panel when the trades stop
};

// Whether the display is the idle screen. Up here because the clock, which
// starts ticking before the rest of the page is built, asks it.
const asleep = { on: false, timer: null, last: '' };

/* --- the shader, the ring and LYLA --------------------------------------- */

const shader = new Shader($('shader'));
shader.start();

/* The name in lit cells, in its three places: under the ring, on the idle
 * screen, and in the intro as Apollo comes up. Upright, in Orbitron at its
 * heaviest drawn at four fifths of its width - a little taller than it
 * comes - and arriving scrambled. */
const NAME = { font: '"Orbitron", "Segoe UI", sans-serif', weight: 900, stretch: 0.8 };
const wordmark = new LedWord($('wordmark'), { ...NAME, rows: 12, glow: 0.8, fill: 0.62, bulge: 0.18 });
const sleepWord = new LedWord($('sleep-word'), { ...NAME, rows: 16, fill: 0.7 });
const introWord = new LedWord($('intro-word'), { ...NAME, rows: 22, glow: 1.15 });
wordmark.scramble(0.75);
// The scramble-text component's own trigger: point at the name and it goes again.
$('wordmark').addEventListener('pointerenter', () => wordmark.scramble(0.75));

window.addEventListener('resize', () => {
  shader.resize();
  for (const word of [wordmark, sleepWord, introWord]) word.resize();
});

const INTRO_OFF_AT = 2850;       // ms: the tube switches off...
const INTRO_GONE_AT = 3500;      // ...and is gone, just before apollo.py lets go

function playIntro() {
  const box = $('intro');
  clearTimeout(box._off);
  clearTimeout(box._gone);
  box.classList.remove('off');
  box.classList.add('on');
  introWord.resize();              // it had no size while it was not shown
  introWord.scramble(1.0, 0.35);
  box._off = setTimeout(() => box.classList.add('off'), INTRO_OFF_AT);
  box._gone = setTimeout(() => {
    box.classList.remove('on', 'off');
    introWord.stop();
  }, INTRO_GONE_AT);
}

const lyla = new Lyla($('lyla'), {
  label: $('lyla-label'), icon: $('lyla-icon'),
  bar: $('lyla-bar'), pct: $('lyla-pct'), ring: $('ring'),
});
lyla.start();

// Click the display and LYLA comes after the pointer for a while (lyla.js).
document.addEventListener('pointerdown', (event) => lyla.follow(event.clientX, event.clientY));
document.addEventListener('pointermove', (event) => lyla.pointer(event.clientX, event.clientY));

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
  tickSleep();
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
  // Earnings within the week earn a word on the card itself.
  const days = earningsIn(quote);
  const soon = days !== null && days >= 0 && days <= 7
    ? `<i class="dot">·</i><b class="soon">Earnings ${earningsWords(days)}</b>` : '';
  return `
    <div class="card" data-symbol="${esc(quote.symbol)}">
      <div class="card-top">
        ${mark}
        <span class="ticker">${esc(quote.symbol)}</span>
        <span class="price">${money(quote.price)}</span>
        <span class="move ${moveClass(quote.change_pct)}">${moveText(quote.change_pct)}</span>
      </div>
      ${sparkline(quote.spark, quote.change_pct >= 0)}
      <div class="card-foot">${target}<i class="dot">·</i>${pe}${soon}</div>
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
  // leave rather than vanish.
  const watched = market.watchlist || [];
  for (const [symbol, asked] of [...state.pending]) {
    if (watched.some((quote) => quote.symbol === symbol) || Date.now() - asked.since > PENDING_FOR) {
      state.pending.delete(symbol);
    }
  }
  const before = [...list.children].map((card) => card.dataset.symbol).filter(Boolean);
  const after = watched.map((quote) => quote.symbol).concat([...state.pending.keys()]);
  const leaving = before.filter((symbol) => !after.includes(symbol));

  if (state.entered && leaving.length) {
    // Let them go first, then draw the rest - otherwise the row under a
    // removed card jumps up while the card is still fading.
    for (const symbol of leaving) {
      const card = [...list.children].find((c) => c.dataset.symbol === symbol);
      if (card) animate(card, { opacity: [1, 0], transform: ['scale(1)', 'scale(.94)'] },
                        { duration: 0.26, ease: 'easeOut' });
    }
    clearTimeout(state.cardsTimer);
    state.cardsTimer = setTimeout(() => {
      for (const card of [...list.children]) {
        if (leaving.includes(card.dataset.symbol)) card.remove();
      }
      renderMarkets(market);
    }, 280);
    return;
  }

  // A snapshot comes every few seconds for the machine's numbers; the cards
  // are rebuilt only when something on them changed, or the frame under the
  // pointer would drop off its card every five seconds.
  const key = JSON.stringify([after, watched.map((quote) =>
    [quote.price, quote.change_pct, quote.target, quote.pe, quote.logo, quote.spark]), state.entered]);
  if (key === state.marketKey) return;
  state.marketKey = key;
  const lit = state.cardLit ? (state.cardLit.dataset.symbol || 'add') : null;
  unlightCard();
  list.innerHTML = watched.map((quote) => stockCard(quote)).join('')
    + [...state.pending].map(([symbol, asked]) => pendingCard(symbol, asked.name)).join('')
    + (watched.length + state.pending.size < WATCH_MAX ? ADD_SLOT : '');
  if (lit) lightCard(lit === 'add' ? list.querySelector('.add') : cardFor(lit));

  if (state.entered) {
    const arriving = after.filter((symbol) => !before.includes(symbol));
    for (const symbol of arriving) {
      const card = [...list.children].find((c) => c.dataset.symbol === symbol);
      if (card) animate(card, {
        opacity: [0, 1], transform: ['translateY(10px) scale(.96)', 'translateY(0) scale(1)'],
      }, { ...SPRING, delay: 0.04 });
    }
  }

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

function renderChips() {
  $('topics').innerHTML = TOPICS.map((topic, i) =>
    `<span class="chip ${i === state.topic ? 'on' : ''}" data-topic="${i}">${esc(topic)}</span>`).join('');
}

function renderFeed(snapshot) {
  $('headlines-head').innerHTML = 'Feed' + stale('news');
  renderChips();
  const items = feedItems(snapshot).slice(0, 11);
  // A snapshot arrives every few seconds for the machine's numbers. The feed
  // is rebuilt only when the feed changed, or the row under the pointer would
  // lose its bar every five seconds.
  const key = state.topic + '#' + items.map((item) => [item.title, item.age].join('|')).join('\n');
  if (key === state.feedKey) return;
  state.feedKey = key;
  state.feed = items;
  unlight();
  $('stories').innerHTML = items.map((item, i) => `
    <div class="story${item.moving ? ' moving' : ''}" data-i="${i}">
      <span class="num">${numbered(i)}</span>
      <span class="what">${esc(String(item.title).slice(0, 150))}</span>
      <span class="who"><b>${esc(item.source)}</b> · ${esc(item.age)}${
        item.moving ? ' · <i>market-moving</i>' : ''}${
        item.eye ? ' · <i class="eye">Private Eye</i>' : ''}</span>
      ${item.image ? '<span class="pic"></span>' : ''}
    </div>`).join('')
    || '<div class="story empty"><span class="num">—</span><span class="what">Nothing has come in yet</span>'
     + '<span class="who">the feeds are quiet</span></div>';
  $('peek').innerHTML = items.map((item) => `<div class="shot">${shot(item)}</div>`).join('');
}

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
const peekAt = { x: 0, y: 0, tx: 0, ty: 0, frame: null, placed: false };
let peekTop = 10;

const rowAt = (index) => $('stories').children[index] || null;

function light(index) {
  if (state.open || index === state.lit) return;
  const row = rowAt(index);
  if (!row || row.classList.contains('empty')) return;
  if (state.lit >= 0) {
    const before = rowAt(state.lit);
    if (before) before.classList.remove('lit');
    closeShot(state.lit);
  }
  state.lit = index;
  row.classList.add('lit');
  const bar = $('feed-bar');
  bar.style.transform = `translateY(${row.offsetTop}px) scaleY(${row.offsetHeight / 100})`;
  bar.style.opacity = '1';
  openShot(index);
}

function unlight() {
  if (state.lit >= 0) {
    const row = rowAt(state.lit);
    if (row) row.classList.remove('lit');
    closeShot(state.lit);
  }
  state.lit = -1;
  $('feed-bar').style.opacity = '0';
  $('peek').classList.remove('on');
}

function openShot(index) {
  const frame = $('peek').children[index];
  if (!frame) return;
  clearTimeout(frame._closing);
  frame.classList.remove('gone', 'open');
  peekTop += 1;
  frame.style.zIndex = String(peekTop);
  void frame.offsetWidth;                  // from closed, every time
  frame.classList.add('open');
  $('peek').classList.add('on');
  follow();
}

function closeShot(index) {
  const frame = $('peek').children[index];
  if (!frame || !frame.classList.contains('open')) return;
  frame.classList.remove('open');
  frame.classList.add('gone');
  frame._closing = setTimeout(() => frame.classList.remove('gone'), 640);
}

/* Beside the feed, on the side the screen has room: level with the pointer,
 * and drifting with it by up to PEEK_WANDER either way. */
function peekTarget() {
  const panel = $('headlines').getBoundingClientRect();
  const peek = $('peek');
  const width = peek.offsetWidth, height = peek.offsetHeight;
  const across = (peekAt.tx - panel.left) / Math.max(1, panel.width) - 0.5;
  const x = panel.left - width - 30 + across * PEEK_WANDER * 2;
  const y = Math.max(24, Math.min(window.innerHeight - height - 24, peekAt.ty - height / 2));
  return [x, y];
}

function follow() {
  if (peekAt.frame !== null) return;
  const step = () => {
    const [x, y] = peekTarget();
    if (!peekAt.placed) { peekAt.x = x; peekAt.y = y; peekAt.placed = true; }
    peekAt.x += (x - peekAt.x) * PEEK_LERP;
    peekAt.y += (y - peekAt.y) * PEEK_LERP;
    $('peek').style.transform = `translate3d(${peekAt.x.toFixed(1)}px, ${peekAt.y.toFixed(1)}px, 0)`;
    const settled = Math.abs(x - peekAt.x) < 0.3 && Math.abs(y - peekAt.y) < 0.3;
    // Frames only while there is somewhere to go.
    peekAt.frame = state.lit >= 0 || !settled ? requestAnimationFrame(step) : null;
  };
  peekAt.frame = requestAnimationFrame(step);
}

$('stories').addEventListener('pointerover', (event) => {
  const row = event.target.closest('.story');
  if (row && row.dataset.i !== undefined) light(Number(row.dataset.i));
});
$('feed').addEventListener('pointermove', (event) => {
  peekAt.tx = event.clientX;
  peekAt.ty = event.clientY;
});
$('feed').addEventListener('pointerleave', () => {
  unlight();
  peekAt.placed = false;
});
$('stories').addEventListener('click', (event) => {
  const row = event.target.closest('.story');
  if (row && row.dataset.i !== undefined) openStory(Number(row.dataset.i));
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
  noted('story', item.title, item.source);
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
  if (event.key === 'Escape') { closeStory(); closeStock(); }
});

/* --- the stocks, picked the way the feed is -----------------------------------
 *
 * A frame slides to the card under the pointer, and a click opens the stock
 * out of its card across the whole panel: its chart over a day, a week, a
 * month, six months or a year, with a line you can run along it; what it
 * did; what the analysts think it is worth; and a button that takes it off
 * the list. The slot after the last card puts one on. Voice does the same
 * through apollo.py: "open Nvidia", "add Palantir", "take off Tesla". */

const SPANS = [['1d', '1D'], ['5d', '5D'], ['1mo', '1M'], ['6mo', '6M'], ['1y', '1Y']];
const WATCH_MAX = 12;             // watchlist.MAX
const PENDING_FOR = 45000;        // a card asked for and never delivered goes
const BIG_W = 600, BIG_H = 200, BIG_PAD = 14;

const bridge = () => (window.pywebview && window.pywebview.api) || null;
const cardFor = (symbol) =>
  [...$('watchlist').children].find((card) => card.dataset.symbol === symbol) || null;

function pendingCard(symbol, name) {
  return `
    <div class="card pending" data-symbol="${esc(symbol)}">
      <div class="card-top"><span class="mark none">${esc(String(symbol)[0])}</span>
        <span class="ticker">${esc(symbol)}</span><span class="price">…</span></div>
      <div class="chart empty"></div>
      <div class="card-foot">Fetching ${esc(name)}</div>
    </div>`;
}

const ADD_SLOT = `
    <button class="card add" type="button">
      <span class="plus">+</span><b>Add a stock</b><small>or say “add Palantir”</small>
    </button>`;

function lightCard(card) {
  if (state.stock || !card || card === state.cardLit || card.classList.contains('pending')) return;
  if (state.cardLit) state.cardLit.classList.remove('lit');
  state.cardLit = card;
  card.classList.add('lit');
  const frame = $('watch-frame');
  // Sized to the card, moved by transform: the cards are one size, so the
  // size is set once and it is only the move that animates.
  frame.style.width = `${card.offsetWidth}px`;
  frame.style.height = `${card.offsetHeight}px`;
  frame.style.transform = `translate(${card.offsetLeft}px, ${card.offsetTop}px)`;
  frame.style.opacity = '1';
}

function unlightCard() {
  if (state.cardLit) state.cardLit.classList.remove('lit');
  state.cardLit = null;
  $('watch-frame').style.opacity = '0';
}

/* What Apollo is told about a stock it opened, so it can talk about it. */
const toldStock = (quote) => ({
  symbol: String(quote.symbol || ''), name: String(quote.name || ''),
  price: quote.price, change_pct: quote.change_pct, target: quote.target ?? null,
  upside: quote.upside ?? null, pe: quote.pe ?? null });

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
        `<span class="chip${span === '1d' ? ' on' : ''}" data-span="${span}">${label}</span>`).join('')}
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
  unlightCard();
  const view = $('stock');
  state.stock = { symbol, quote, span: '1d', points: quote.spark || [], times: [] };
  view.innerHTML = stockMarkup(quote);
  openOver(view, $('markets'), cardFor(symbol));
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
  state.stock = null;
  const view = $('stock');
  view.setAttribute('aria-hidden', 'true');
  view.style.clipPath = clipTo(open.picker ? $('watchlist').querySelector('.add') : cardFor(open.symbol),
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
  unlightCard();
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
  lightCard(event.target.closest('.card'));
});
$('watch-area').addEventListener('pointerleave', () => unlightCard());
$('watchlist').addEventListener('click', (event) => {
  const card = event.target.closest('.card');
  if (!card) return;
  if (card.classList.contains('add')) openPicker();
  else if (card.dataset.symbol && !card.classList.contains('pending')) openStock(card.dataset.symbol);
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

function tickCard(quote, before) {
  // The next full redraw compares against this, so it has nothing to flash.
  state.prices.set(quote.symbol, quote.price);
  const card = cardFor(quote.symbol);
  if (!card || card.classList.contains('pending')) return;
  const price = card.querySelector('.card-top .price');
  const move = card.querySelector('.card-top .move');
  if (price) price.textContent = money(quote.price);
  if (move) {
    move.className = `move ${moveClass(quote.change_pct)}`;
    move.textContent = moveText(quote.change_pct);
  }
  if (quote.price !== before) flicker(price, quote.price > before);
  const chart = card.querySelector('.chart');
  if (chart && quote.spark && quote.spark.length > 1) {
    chart.outerHTML = sparkline(quote.spark, quote.change_pct >= 0);
  }
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
    tickCard(quote, before);
    const open = state.stock;
    if (open && !open.picker && open.symbol === quote.symbol) tickStock(quote, tick, before);
  }
  if (traded) markLive();
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
  renderFeed(snapshot);
  renderStrip(snapshot);
  renderWeather(snapshot.weather);
  enter();
}

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
  document.body.classList.toggle('asleep', on);
  $('sleep').setAttribute('aria-hidden', on ? 'false' : 'true');
  shader.sleep(on);
  clearInterval(asleep.timer);
  if (on) {
    unlight();
    closeStory();
    // Under the idle screen only the dots are seen; nothing else earns frames.
    lyla.stop();
    ringStop();
    wordmark.stop();
    sleepWord.resize();
    sleepWord.scramble(0.9, 0.5);  // as the idle screen fades in
    tickSleep();
    nextFact();
    asleep.timer = setInterval(nextFact, FACT_EVERY);
  } else {
    sleepWord.stop();
  }
  if (!on && state.mode === 'full') {
    wordmark.scramble(0.75);
    ringStart();
    if ($('lyla-block').dataset.hidden !== 'true') lyla.start();
  }
}

/* Which panels are on the display. Apollo can take one off by voice, so they
 * leave rather than disappear: the grid would otherwise reflow in one frame
 * and everything else on the screen would jump. */
const PANEL_OF = {
  markets: 'markets', feed: 'headlines', clock: 'clock-block',
  status: 'status-block', strip: 'strip', lyla: 'lyla-block', core: 'core',
};

function setPanels(wanted) {
  for (const [panel, id] of Object.entries(PANEL_OF)) {
    const element = $(id);
    if (!element) continue;
    const show = wanted[panel] !== false;
    const already = element.dataset.hidden !== 'true';
    if (show === already) continue;
    element.dataset.hidden = show ? 'false' : 'true';
    if (show) {
      element.style.display = '';
      animate(element, { opacity: [0, 1], transform: ['scale(.97)', 'scale(1)'] },
              { ...SPRING });
    } else {
      const done = animate(element, { opacity: [1, 0], transform: ['scale(1)', 'scale(.97)'] },
                           { duration: 0.24, ease: 'easeOut' });
      const hide = () => { if (element.dataset.hidden === 'true') element.style.display = 'none'; };
      // The grid reflows only once the panel has finished leaving.
      if (done && done.finished && done.finished.then) done.finished.then(hide, hide);
      else setTimeout(hide, 260);
    }
  }
  // LYLA's room is a full-window canvas, not a grid cell, so it is hidden by
  // stopping her rather than by leaving an empty canvas on screen.
  if (wanted.lyla === false) lyla.stop();
  else if (state.phase === 'idle') lyla.start();
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
  // The matrix carries the word while it is working, so the hint stands down
  // rather than saying "Thinking" a second time just above it.
  hint.textContent = phase === 'thinking' ? '' : (SAYS[phase] || '');
  hint.classList.toggle('busy', attending && phase !== 'thinking');

  // The matrix replaces the word "Thinking" entirely while it is working.
  $('thinking').classList.toggle('on', phase === 'thinking');
  if (phase === 'thinking') dots.play(THINKING);
  else dots.stop();

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
    state.mode = name;
    // The overlay has the screen while Apollo is at rest; a shader drawing to
    // a window nobody can see is a GPU burning for nothing.
    if (name === 'full') {
      shader.start();
      if (!asleep.on) { lyla.start(); ringStart(); wordmark.scramble(0.75); }
      else sleepWord.start();
      enter();
    } else {
      shader.stop(); lyla.stop(); ringStop();
      wordmark.stop(); sleepWord.stop();
      unlight();
      unlightCard();
    }
  },
  level(value) { setLevel(value); },
  panels(state) { setPanels(state); },
  briefing(payload) { if (payload) render(payload); },
  sleep(on) { setSleep(on); },
  // As Apollo comes up: the name, once, and the tube switching off.
  intro() { playIntro(); },
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
