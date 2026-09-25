/* Ultra mode's displays, as data: which ones there are, where each sits on
 * the grid, how big it is, whether it is shown, minimized or the one
 * expanded - and the one line each says about itself when it is minimized.
 *
 * No DOM here, so node can run it (tests/test_tiles.py). app.js lays the
 * page out from a layout, and apollo.py keeps it (displays.py), so it is
 * the same tomorrow. Every change returns a new layout; nothing is changed
 * in place, so a layout handed to the bridge is never altered after it. */

export const COLUMNS = 12;
export const ROWS = 6;             // the default fills exactly this many
export const MIN_W = 2;            // narrower than two columns is not a display

// The order they are laid out in by default, which is also the order the
// grid packs them in: the map in the middle, the markets and the feed
// either side of it, and the work along the bottom.
export const DISPLAYS = ['today', 'osiris', 'feed', 'markets', 'projects', 'ideas',
                         'core', 'system', 'talks'];

export const NAMES = {
  today: 'Today', osiris: 'OSIRIS', feed: 'Feed', markets: 'Markets',
  projects: 'Projects', ideas: 'Ideas', core: 'Apollo', system: 'System', talks: 'Talks',
};

// Sizes by name, smallest first: columns by rows.
export const SIZES = { S: [2, 2], M: [3, 2], L: [4, 3], XL: [6, 4] };

// OSIRIS's layers (osiris.LAYERS), each one a switch in its settings.
export const LAYERS = ['maritime', 'cctv', 'cctv_previews', 'live_news', 'earthquakes',
                       'global_incidents', 'day_night', 'cables', 'sdk_sea', 'sdk_air',
                       'sdk_naval'];

const SPANS = {
  today: [3, 2], osiris: [6, 4], feed: [3, 4], markets: [3, 4], projects: [2, 2],
  ideas: [2, 2], core: [2, 2], system: [3, 2], talks: [3, 2],
};

export function defaultLayout() {
  const items = {};
  for (const id of DISPLAYS) {
    const [w, h] = SPANS[id];
    // Talks is kept back: the record of what was said matters less to a
    // morning's work than the rest, and the screen is full without it.
    items[id] = { shown: id !== 'talks', w, h, min: false };
  }
  return { ultra: false, focus: null, order: [...DISPLAYS], items, layers: [...LAYERS] };
}

// A number of cells, or the fallback for anything that is not a number -
// "4" included: the page only ever writes numbers, so a string is damage.
const whole = (value, low, high, fallback) => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return fallback;
  return Math.max(low, Math.min(high, Math.round(value)));
};

const isObject = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);

/* A layout read back from disk or handed over the bridge, made safe to lay
 * out: displays nobody has heard of dropped, each one there once, spans on
 * the grid, and anything that is not what it should be put back to its
 * default rather than trusted. */
export function sanitize(raw) {
  const fresh = defaultLayout();
  if (!isObject(raw)) return fresh;
  const seen = new Set();
  const order = [];
  for (const id of Array.isArray(raw.order) ? raw.order : []) {
    if (DISPLAYS.includes(id) && !seen.has(id)) { seen.add(id); order.push(id); }
  }
  for (const id of DISPLAYS) if (!seen.has(id)) order.push(id);
  const items = {};
  const given = isObject(raw.items) ? raw.items : {};
  for (const id of DISPLAYS) {
    const was = fresh.items[id];
    const item = isObject(given[id]) ? given[id] : {};
    items[id] = {
      shown: typeof item.shown === 'boolean' ? item.shown : was.shown,
      w: whole(item.w, MIN_W, COLUMNS, was.w),
      h: whole(item.h, 1, ROWS, was.h),
      min: item.min === true,
    };
  }
  let layers = fresh.layers;
  if (Array.isArray(raw.layers)) {
    // Known ones only, once each, in the order given - the order the map's
    // address lists them in.
    layers = raw.layers.filter((layer, i) => LAYERS.includes(layer) && raw.layers.indexOf(layer) === i);
  }
  const focus = DISPLAYS.includes(raw.focus) && items[raw.focus].shown && !items[raw.focus].min
    ? raw.focus : null;
  return { ultra: raw.ultra === true, focus, order, items, layers };
}

const copy = (layout) => sanitize(JSON.parse(JSON.stringify(layout)));

/* One display dragged onto another: they trade places. */
export function swap(layout, a, b) {
  const next = copy(layout);
  const i = next.order.indexOf(a), j = next.order.indexOf(b);
  if (i < 0 || j < 0 || i === j) return next;
  [next.order[i], next.order[j]] = [next.order[j], next.order[i]];
  return next;
}

export function resize(layout, id, w, h) {
  const next = copy(layout);
  const item = next.items[id];
  if (!item) return next;
  item.w = whole(w, MIN_W, COLUMNS, item.w);
  item.h = whole(h, 1, ROWS, item.h);
  return next;
}

/* Shown or hidden. The expanded one hidden, and the grid comes back. */
export function setShown(layout, id, shown) {
  const next = copy(layout);
  if (!next.items[id]) return next;
  next.items[id].shown = Boolean(shown);
  if (!shown && next.focus === id) next.focus = null;
  return next;
}

export function setMin(layout, id, min) {
  const next = copy(layout);
  if (!next.items[id]) return next;
  next.items[id].min = Boolean(min);
  if (min && next.focus === id) next.focus = null;
  return next;
}

/* "Put it on my screen": ultra mode, that display shown, whole, and
 * expanded, with the rest minimized beside it. null puts the grid back. */
export function focus(layout, id) {
  const next = copy(layout);
  if (id === null || id === undefined || !next.items[id]) {
    next.focus = null;
    return next;
  }
  next.ultra = true;
  next.items[id].shown = true;
  next.items[id].min = false;
  next.focus = id;
  return next;
}

export function setUltra(layout, on) {
  const next = copy(layout);
  next.ultra = Boolean(on);
  if (!on) next.focus = null;
  return next;
}

export function setLayers(layout, layers) {
  return sanitize({ ...copy(layout), layers: Array.isArray(layers) ? layers : [] });
}

/* Which displays are on the screen, in the order they are packed. */
export function visible(layout) {
  return layout.order.filter((id) => layout.items[id] && layout.items[id].shown);
}

/* The corner of a display dragged by (dx, dy) pixels: how many columns and
 * rows it covers now, on a grid of colW by rowH cells with `gap` between. */
export function spansFor({ w, h, dx, dy, colW, rowH, gap }) {
  const across = w * colW + (w - 1) * gap + dx;
  const down = h * rowH + (h - 1) * gap + dy;
  return {
    w: whole((across + gap) / (colW + gap), MIN_W, COLUMNS, w),
    h: whole((down + gap) / (rowH + gap), 1, ROWS, h),
  };
}

/* --- the line a minimized display says -------------------------------------
 * Plain text: the page sets it as text, never as markup. */

const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
const thousands = (n) => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
const signed = (pct) => `${pct >= 0 ? '+' : '-'}${Math.abs(pct).toFixed(2)}%`;
const known = (value) => typeof value === 'number' && Number.isFinite(value);
const cut = (text, most) => (text.length > most ? `${text.slice(0, most - 1)}…` : text);

const PHASES = {
  idle: 'Ready · hold Ctrl+Alt to talk', listening: 'Listening',
  thinking: 'Thinking', speaking: 'Answering',
};

export function summary(id, snapshot, extra = {}) {
  const s = isObject(snapshot) ? snapshot : {};
  const list = (value) => (Array.isArray(value) ? value : []);
  switch (id) {
    case 'today': {
      const parts = [];
      if (extra.clock) parts.push(String(extra.clock));
      const weather = isObject(s.weather) ? s.weather : {};
      if (known(weather.temp)) parts.push(`${weather.temp}°${weather.text ? ` ${weather.text}` : ''}`);
      const prayer = isObject(s.prayer) ? s.prayer : {};
      const now = known(extra.now) ? extra.now : Date.now();
      if (prayer.name && known(prayer.at) && prayer.at * 1000 > now) {
        const at = new Date(prayer.at * 1000);
        parts.push(`${prayer.name} ${String(at.getHours()).padStart(2, '0')}:${String(at.getMinutes()).padStart(2, '0')}`);
      }
      return parts.join(' · ') || 'The day, the weather and the next prayer';
    }
    case 'system': {
      const system = isObject(s.system) ? s.system : {};
      const usage = isObject(s.usage) ? s.usage : {};
      const gauge = (name, key) => `${name} ${known(system[key]) ? `${Math.round(system[key])}%` : '—'}`;
      const parts = [gauge('CPU', 'cpu'), gauge('GPU', 'gpu'), gauge('RAM', 'ram')];
      parts.push(`${thousands(known(usage.tokens) ? usage.tokens : 0)} tokens`);
      if (known(usage.cost)) parts.push(`$${usage.cost.toFixed(2)}`);
      return parts.join(' · ');
    }
    case 'markets': {
      const market = isObject(s.market) ? s.market : {};
      const parts = list(market.indices).filter((q) => q && known(q.change_pct))
        .map((q) => `${q.name || q.symbol || ''} ${signed(q.change_pct)}`.trim());
      const movers = list(market.watchlist).filter((q) => q && known(q.change_pct))
        .sort((a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct));
      if (movers.length) parts.push(`${movers[0].symbol} ${signed(movers[0].change_pct)}`);
      return parts.join(' · ') || 'No market data yet';
    }
    case 'feed': {
      const feed = list(extra.feed);
      if (!feed.length) return 'Nothing has come in yet';
      return `${plural(feed.length, 'story', 'stories')} · ${cut(String(feed[0].title || ''), 70)}`;
    }
    case 'osiris':
      return known(extra.layers) ? `Live map · ${plural(extra.layers, 'layer')}`
                                 : 'Live intelligence map';
    case 'projects': {
      const p = isObject(s.projects) ? s.projects : {};
      return [plural(list(p.sessions).length, 'session'), plural(list(p.folders).length, 'folder'),
              plural(list(p.repos).length, 'repo')].join(' · ');
    }
    case 'ideas': {
      const i = isObject(s.ideas) ? s.ideas : {};
      return `${plural(list(i.ideas).length, 'idea')} · ${plural(list(i.reminders).length, 'reminder')}`;
    }
    case 'talks': {
      const talks = list(s.talks);
      if (!talks.length) return 'No talks yet today';
      const last = talks[0] && talks[0].time ? ` · last at ${talks[0].time}` : '';
      return `${plural(talks.length, 'talk')}${last}`;
    }
    case 'core':
      return PHASES[extra.phase] || PHASES.idle;
    default:
      return '';
  }
}
